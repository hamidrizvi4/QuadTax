#!/usr/bin/env python3
"""
Data retention and cleanup script for QuadTax engine.

Issue #12: Implement data retention policy to prevent data exposure.
This script cleans up old output files and audit logs.
"""

import os
from datetime import datetime, timedelta
from pathlib import Path
import argparse
import logging


def setup_logging() -> None:
    """Configure logging for the retention script."""
    if not os.path.exists("logs"):
        os.makedirs("logs")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler("logs/retention.log"),
            logging.StreamHandler(),
        ],
    )


def cleanup_old_outputs(retention_days: int = 30) -> list:
    """Remove output files older than retention_days.

    Returns:
        list: List of deleted file paths
    """
    outputs_dir = Path("outputs")
    cutoff_date = datetime.now() - timedelta(days=retention_days)
    deleted_files: list = []

    if not outputs_dir.exists():
        logging.info("Outputs directory does not exist, skipping cleanup.")
        return deleted_files

    for file_path in outputs_dir.rglob("*"):
        if file_path.is_file():
            try:
                mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                if mtime < cutoff_date:
                    file_path.unlink()
                    deleted_files.append(str(file_path))
                    logging.info("Deleted: %s", file_path)
            except Exception as e:  # noqa: BLE001
                logging.warning("Error deleting %s: %s", file_path, e)

    return deleted_files


def cleanup_old_audit_logs(retention_days: int = 30) -> list:
    """Remove audit log files older than retention_days."""
    audit_dir = Path("outputs/audit_logs")
    cutoff_date = datetime.now() - timedelta(days=retention_days)
    deleted_files: list = []

    if not audit_dir.exists():
        logging.info("Audit logs directory does not exist, skipping cleanup.")
        return deleted_files

    for log_file in audit_dir.glob("*"):
        try:
            if log_file.is_file():
                mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
                if mtime < cutoff_date:
                    log_file.unlink()
                    deleted_files.append(str(log_file))
                    logging.info("Deleted audit log: %s", log_file)
        except Exception as e:  # noqa: BLE001
            logging.warning("Error processing audit log %s: %s", log_file, e)

    return deleted_files


def main() -> int:
    """Main retention script entrypoint."""
    parser = argparse.ArgumentParser(description="QuadTax Data Retention Cleanup Tool")
    parser.add_argument(
        "-d",
        "--days",
        type=int,
        default=30,
        help="Number of days to retain files (default: 30)",
    )
    args = parser.parse_args()
    retention_days = args.days

    setup_logging()
    logging.info("Starting retention cleanup with %d days threshold...", retention_days)

    deleted_inputs = cleanup_old_outputs(retention_days)
    logging.info("Deleted %d output files older than %d days.", len(deleted_inputs), retention_days)

    deleted_logs = cleanup_old_audit_logs(retention_days)
    logging.info("Deleted %d audit logs older than %d days.", len(deleted_logs), retention_days)

    total = len(deleted_inputs) + len(deleted_logs)
    logging.info("Retention cleanup completed. Total deleted: %d", total)
    return total


if __name__ == "__main__":
    deleted_count = main()
    exit(0 if deleted_count >= 0 else 1)