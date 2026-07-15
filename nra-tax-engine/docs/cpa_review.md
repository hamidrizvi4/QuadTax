# QuadTax CPA Review System

## 1. Review Panel Design

![Residency Decision Matrix]

## 2. Audit Trail State

![Audit Trail Example]

*(Implementation Note: Audit entries are stored in `ReturnStateObject.audit_trail` as JSON-filled dicts)*

## 3. Compliance Navigation

1. **Automated Filters**
- \* Mistrusted OCR words (highlighted in UI)
- \* Treaty article mismatch flags
- \* NY-specific heuristic buttons

2. **Manual Actions**
- [ ] Override dual-status dates
- [ ] Attach Form W-7
- [ ] Correct withholding discrepancies

## 4. Security Compliance

![](Data Flow Diagram)
*(All PII flows through encrypted channels; files only appear in memory during processing)*