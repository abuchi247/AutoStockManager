# Backup, Recovery, and Data Retention Policy

This document defines the backup schedule, recovery objectives, encryption requirements,
retention policies, restore verification procedures, and access controls for the
AutoStockManager production deployment.

**Owner:** Infrastructure / DevOps team lead
**Review cadence:** Quarterly or after any significant schema/data change
**Last reviewed:** Initial version (see git history)

---

## 1. Recovery Objectives

| Metric | Target | Rationale |
|--------|--------|-----------|
| **Recovery Point Objective (RPO)** | ≤ 1 hour | Point-in-time recovery (PITR) or frequent logical backups ensure at most 1 hour of data loss |
| **Recovery Time Objective (RTO)** | ≤ 4 hours | Includes detection, decision, restore, validation, and traffic switch |

These targets apply to the PostgreSQL database which is the authoritative source of truth
for financial records, inventory ledgers, sales, purchases, invoices, users, and audit trails.
Redis session data is not subject to RPO/RTO guarantees; sessions are re-established on login.

---

## 2. Backup Schedule

### PostgreSQL Backups

| Type | Frequency | Retention | Storage |
|------|-----------|-----------|---------|
| Continuous WAL archiving (PITR) | Continuous | 7 days | Off-host encrypted object storage (S3/GCS/equivalent) |
| Full logical backup (`pg_dump --format=custom`) | Daily at 02:00 UTC | 30 days | Off-host encrypted object storage |
| Pre-release backup | Before each schema-changing release | 90 days | Off-host encrypted object storage |

### Managed PostgreSQL (Preferred)

When using a managed database service (RDS, Cloud SQL, Supabase, etc.):
- Enable automated daily snapshots with the managed provider's retention policy (minimum 7 days)
- Enable point-in-time recovery with a minimum 7-day window
- Supplement with a daily logical backup to a separate storage account for disaster recovery

### Self-Managed PostgreSQL

```bash
# Daily logical backup (run from a backup host, NOT the application server)
pg_dump \
  --format=custom \
  --no-owner \
  --file="/backup/autostockmanager-$(date +%Y%m%d-%H%M%S).dump" \
  "$BACKUP_PGDATABASE_URL"

# Encrypt before uploading to off-host storage
gpg --symmetric --cipher-algo AES256 \
  --output "/backup/autostockmanager-$(date +%Y%m%d-%H%M%S).dump.gpg" \
  "/backup/autostockmanager-$(date +%Y%m%d-%H%M%S).dump"

# Upload to off-host storage
aws s3 cp "/backup/autostockmanager-$(date +%Y%m%d-%H%M%S).dump.gpg" \
  "s3://${BACKUP_BUCKET}/postgres/daily/"

# Remove local unencrypted copy
rm -f "/backup/autostockmanager-$(date +%Y%m%d-%H%M%S).dump"
```

### Redis

Redis contains ephemeral session and rate-limit state. It is **not** backed up as part
of the RPO/RTO commitment. Loss of Redis data results in session invalidation (users
must re-authenticate) and rate-limit counter reset—both acceptable under the recovery model.

---

## 3. Encryption Requirements

| Requirement | Implementation |
|-------------|----------------|
| Encryption at rest | All backup files encrypted with AES-256 (GPG symmetric or provider-managed KMS) |
| Encryption in transit | All database connections use TLS (`sslmode=require` or provider-enforced TLS) |
| Key management | Encryption keys stored in cloud KMS or equivalent; rotated annually |
| Key access | Limited to backup-operator and restore-operator IAM roles |

**Never** store backup encryption keys in the same storage account as the backups themselves.

---

## 4. Off-Host Storage and Failure Domain Separation

- Backups MUST be stored in a separate failure domain from the production database.
- For cloud deployments: use a different storage account or region from the primary database.
- For self-managed: store encrypted backups on a physically separate server or cloud object store.
- Cross-region replication is recommended for critical production deployments.

**Monitoring:**
- Alert if the most recent successful backup is older than 2× the scheduled interval.
- Alert if backup storage capacity drops below 20% of allocated quota.
- Alert if PITR/WAL archiving falls behind by more than 15 minutes.

---

## 5. Restore Access Controls

| Role | Permissions |
|------|-------------|
| `backup-operator` | Create backups, verify backup integrity, upload to storage; NO restore or production DB access |
| `restore-operator` | Download backups, decrypt, restore to isolated environment; production restore requires approval |
| `dba-admin` | Full PostgreSQL administrative access; required for production restore execution |
| `application` | DML only (`SELECT`, `INSERT`, `UPDATE`, `DELETE`) on application tables; NO DDL or backup access |
| `migration` | DDL and DML on application schema; used only during deployment migration step |

Access to restore operations in production requires:
1. Approval from the on-call lead or engineering manager
2. A documented incident or planned maintenance window
3. Audit trail entry (who restored, when, from which backup, for what reason)

---

## 6. Restore Verification

### Schedule
- **Automated:** Weekly (or after each release cycle, whichever is more frequent)
- **Manual drill:** Quarterly with full team participation

### Procedure

Restore verification uses the `backend/scripts/verify_restore.py` script:

```bash
# Restore into an isolated environment (never production)
pg_restore \
  --dbname="$RESTORE_TEST_DATABASE_URL" \
  --no-owner \
  --clean \
  --if-exists \
  "/path/to/decrypted-backup.dump"

# Run integrity checks
cd backend
python -m scripts.verify_restore --database-url "$RESTORE_TEST_DATABASE_URL"
```

### Integrity Checks (automated)

The restore verification script validates:

1. **Schema version:** Alembic revision matches expected head
2. **Inventory ledger integrity:** Movement ledger net quantities match stock cache
3. **Sales records:** All sales have valid items, customer references, and non-negative totals
4. **Purchase records:** All purchase orders have valid supplier references and items
5. **Invoice integrity:** All invoices reference valid sales with consistent amounts
6. **User accounts:** All users have valid roles, hashed passwords, and audit timestamps
7. **Audit trail:** Audit entries reference valid entities and have monotonic timestamps

### Recording Results

Each verification produces a report with:
- Restore duration
- Recovered Alembic revision
- Table row counts for critical entities
- Integrity check pass/fail per category
- Any anomalies or warnings

Reports are stored alongside backup metadata in the off-host storage.

---

## 7. Data Retention and Deletion Policies

### Retention Schedule

| Data Category | Retention Period | Deletion Method | Justification |
|---------------|-----------------|-----------------|---------------|
| **Transaction records** (sales, purchases, invoices, payments) | 7 years | Archived then purged | Tax/regulatory compliance |
| **Inventory movements** (ledger entries) | 7 years | Archived then purged | Audit trail for financial records |
| **Audit trails** | 5 years | Soft-delete, then hard-delete after retention | Operational accountability |
| **Login history** | 1 year | Hard-delete older entries | Security review; minimize PII exposure |
| **Password reset markers** (used-token JTIs in Redis) | Token TTL (matches JWT expiry) | Auto-expired by Redis TTL | No value after expiry |
| **Background job records** (ARQ job metadata) | 30 days | Purge completed/failed job logs | Operational troubleshooting |
| **Application logs** | 90 days (hot), 1 year (cold) | Lifecycle policy in log aggregator | Incident investigation |
| **Database backups** | Daily: 30 days; Pre-release: 90 days; PITR: 7 days | Lifecycle policy on storage bucket | Recovery capability |
| **Personal data** (customer names, emails, phone) | Active + 2 years after last transaction | Anonymize or delete on request | Data minimization |
| **User accounts** (staff) | Active employment + 1 year | Deactivate, then anonymize | HR/audit requirements |

### Deletion Procedures

1. **Automated lifecycle policies:** Configure object storage lifecycle rules to expire
   old backups and logs according to the retention schedule.

2. **Scheduled database maintenance:** A periodic job (cron or deployment-triggered)
   should purge login history older than the retention window:
   ```sql
   DELETE FROM login_history WHERE created_at < NOW() - INTERVAL '1 year';
   ```

3. **Personal data requests:** On receiving a deletion request:
   - Verify the requestor's identity
   - Anonymize customer records (replace PII with `[DELETED]` tokens)
   - Retain transaction records with anonymized references for financial compliance
   - Log the deletion request and completion in the audit trail

4. **Backup lifecycle:** Expired backups are automatically removed by storage lifecycle
   policies. Manual deletion of backups requires restore-operator approval and audit logging.

### Data Classification

| Classification | Examples | Handling |
|----------------|----------|----------|
| **Critical/Financial** | Sales, purchases, invoices, payments, ledger entries | 7-year retention, encrypted backups, audit access |
| **Sensitive/PII** | Customer data, user emails, phone numbers | Encrypted at rest, anonymizable, retention-limited |
| **Operational** | Logs, job records, health metrics | Short retention, auto-purged |
| **Ephemeral** | Sessions, rate-limit counters, reset markers | Redis TTL, no backup required |

---

## 8. Ownership and Escalation

| Responsibility | Owner | Escalation |
|----------------|-------|------------|
| Backup schedule configuration | Infrastructure team | Engineering manager |
| Restore drill execution | On-call engineer (rotating) | Infrastructure lead |
| Retention policy compliance | Engineering manager | CTO / Legal |
| Incident restore decision | On-call lead | Engineering manager within 30 min |
| Personal data deletion | Data protection contact | Legal / Compliance |

---

## References

- `OPERATIONS_RUNBOOK.md` — Section 4 (Backup and restore expectations)
- `backend/scripts/verify_restore.py` — Automated integrity check script
- `backend/app/services/db_roles.py` — Database role definitions and least-privilege configuration
