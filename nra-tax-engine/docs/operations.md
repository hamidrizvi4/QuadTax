# Production Operations Guide

## 1. Docker Production Image Build

### Base Image
```dockerfile
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Copy requirements and install
COPY nra-tax-engine/pyproject.toml .
RUN pip install --no-cache-dir -e .

# Copy source code
COPY nra-tax-engine/ .

# Create non-root user
RUN useradd --create-home --shell /bin/bash app
USER app

# Expose port
EXPOSE 8000

# Healthcheck
HEALTHCHECK --interval=30s --timeout=3s \
  CMD curl -f http://localhost:8000/api/v1/healthz || exit 1

# Start command
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Build Command
```bash
docker build -t quadtax:latest .
```

## 2. Secrets Management

### HashiCorp Vault Integration
```bash
# Retrieve secrets from Vault
export QUADTAX_API_KEY=$(vault kv get -field=api_key secret/quadtax/prod)
export OPENAI_API_KEY=$(vault kv get -field=api_key secret/openai/prod)

# Start with injected secrets
./startup_helper.sh
```

### AWS Secrets Manager Alternative
```bash
# Retrieve from AWS Secrets Manager
aws secretsmanager get-secret-value --secret-id quadtax/prod \
 --query SecretString --output text | jq -r '.QUADTAX_API_KEY'
```

### Kubernetes Secret Reference
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: quadtax-secrets
type: Opaque
data:
  QUADTAX_API_KEY: base64-encoded-key
  OPENAI_API_KEY: base64-encoded-key
```

## 3. Zero-Downtime Deployment Script

### Blue-Green Deployment (AWS ECS)
```bash
#!/bin/bash
set -euo pipefail

CLUSTER="quadtax-prod"
SERVICE="tax-engine"
NEW_TASK_DEF="$(aws ecs register-task-definition \
 --family tax-engine \
 --container-definitions file://new-task-def.json \
 --query taskDefinition.taskDefinitionArn \
 --output text)"

# Deploy new task definition
aws ecs update-service \
 --cluster $CLUSTER \
 --service $SERVICE \
 --task-definition $NEW_TASK_DEF \
 --deployment-configuration maximumPercent=200,minimumHealthyPercent=100

# Wait for stability
aws ecs wait services-stable --cluster $CLUSTER --services $SERVICE

# Optional: Rollback on health check failures
if ! ./health-check-script.sh; then
  echo "Health check failed - initiating rollback"
  aws ecs update-service \
   --cluster $CLUSTER \
   --service $SERVICE \
   --task-definition "$(aws ecs describe-services --cluster $CLUSTER --services $SERVICE \
    --query services[0].deployments[0].taskDefinition --output text)"
  exit 1
fi
```

### Canary Deployment (Kubernetes)
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: quadtax-canary
spec:
  replicas: 2  # 20% of total capacity
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 25%
      maxUnavailable: 0
  selector:
    matchLabels:
      app: quadtax
      version: canary
  template:
    metadata:
      labels:
        app: quadtax
        version: canary
    spec:
      containers:
      - name: tax-engine
        image: quadtax:canary
        envFrom:
        - secretRef:
            name: quadtax-secrets
        readinessProbe:
          httpGet:
            path: /api/v1/healthz
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
```

## 4. Auto-Scale Configuration

### AWS Application Auto Scaling
```bash
# Register scalable target
aws application-autoscaling register-scalable-target \
 --service-namespace ecs \
 --resource-id service/$CLUSTER/$SERVICE \
 --scalable-dimension ecs:service:DesiredCount \
 --min-capacity 3 \
 --max-capacity 20

# Create scaling policy
aws application-autoscaling put-scaling-policy \
 --policy-name quadtax-cpu-utilization \
 --service-namespace ecs \
 --resource-id service/$CLUSTER/$SERVICE \
 --scalable-dimension ecs:service:DesiredCount \
 --policy-type TargetTrackingScaling \
 --target-tracking-scaling-policy-configuration file://cpu-target-tracking.json
```

### CPU Target Tracking Policy (cpu-target-tracking.json)
```json
{
  "TargetValue": 70.0,
  "PredefinedMetricSpecification": {
    "PredefinedMetricType": "ECSServiceAverageCPUUtilization"
  },
  "ScaleOutCooldown": 60,
  "ScaleInCooldown": 300
}
```

## 5. Monitoring & Alerting

### Key Metrics to Monitor
- **Health endpoint status**: Alert if `/api/v1/healthz` returns degraded
- **LLM call latency**: P95 < 2s for extraction calls
- **Error rate**: < 1% for 5xx responses
- **Cache hit rate**: > 80% for extraction cache
- **Request rate**: Alert if > 80% of rate limit sustained

### Sample Prometheus Alert Rules
```yaml
groups:
- name: quadtax-alerts
  rules:
  - alert: QuadTaxHealthDegraded
    expr: quadtax_health_status{status="degraded"} == 1
    for: 2m
    labels:
      severity: critical
    annotations:
      summary: "QuadTax health degraded"
      description: "Health check returning degraded status for {{ $value }} minutes"

  - alert: QuadTaxHighErrorRate
    expr: rate(quadtax_http_errors_total[5m]) > 0.01
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "High error rate on QuadTax"
      description: "Error rate is {{ $value }}% over 5m"

  - alert: QuadTaxLowCacheHitRate
    expr: quadtax_cache_hits_total / (quadtax_cache_hits_total + quadtax_cache_misses_total) < 0.8
    for: 15m
    labels:
      severity: warning
    annotations:
      summary: "Low cache hit rate"
      description: "Cache hit rate is {{ $value }}%, target >80%"
```

## 6. Log Rotation & Retention

### Systemd Journal Configuration (/etc/systemd/journald.conf)
```ini
Storage=persistent
SystemMaxUse=2G
SystemMaxFileSize=50M
MaxRetentionMonth=3
```

### Application Log Rotation (logrotate.conf)
```
/var/log/quadtax/*.log {
    daily
    rotate 14
    compress
    delaycompress
    missingok
    notifempty
    create 0640 app adm
    sharedscripts
    postrotate
        systemctl reload quadtax >/dev/null 2>&1 || true
    endscript
}
```

## 7. Backup & Disaster Recovery

### Audit Log Backup (Daily)
```bash
#!/bin/bash
BACKUP_DIR="/backups/quadtax/$(date +%Y-%m-%d)"
mkdir -p "$BACKUP_DIR"

# Backup audit logs
cp -r /var/log/quadtax/audit* "$BACKUP_DIR/"

# Backup configuration
cp /app/nra-tax-engine/.env.example "$BACKUP_DIR/config.backup"

# Upload to S3
aws s3 sync "$BACKUP_DIR" s3://quadtax-backups/prod/$(date +%Y-%m-%d)/
```

## 8. Security Hardening Checklist

### Container Security
- [ ] Run as non-root user (UID 1000+)
- [ ] Drop all Linux capabilities, add only NET_BIND_SERVICE
- [ ] Read-only root filesystem
- [ ] No new privileges: true
- [ ] Seccomp profile: docker-default

### Network Security
- [ ] Service mesh mTLS between client and API
- [ ] API Gateway rate limiting (secondary defense)
- [ ] CORS restricted to known domains
- [ ] Security headers enforced (X-Frame-Options, etc.)

### Data Protection
- [ ] PII never written to disk (only in-memory processing)
- [ ] TLS 1.3 enforced for all external connections
- [ ] Secrets injected at runtime, never in image layers