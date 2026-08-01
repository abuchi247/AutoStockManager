"""Tests for the restore verification script.

Validates: Requirements 18.3, 18.4
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

from scripts.verify_restore import (
    CheckResult,
    CheckStatus,
    RestoreVerificationReport,
    RestoreVerifier,
)


class TestCheckResult:
    """Verify CheckResult dataclass behavior."""

    def test_creates_passed_result(self):
        result = CheckResult(
            name="test_check",
            status=CheckStatus.PASSED,
            message="All good",
        )
        assert result.name == "test_check"
        assert result.status == CheckStatus.PASSED
        assert result.details == {}

    def test_creates_failed_result_with_details(self):
        result = CheckResult(
            name="failed_check",
            status=CheckStatus.FAILED,
            message="Bad data",
            details={"count": 5},
        )
        assert result.status == CheckStatus.FAILED
        assert result.details["count"] == 5


class TestRestoreVerificationReport:
    """Verify report behavior."""

    def test_empty_report_passes(self):
        report = RestoreVerificationReport(
            database_url_host="localhost:5432/testdb",
            started_at=datetime.now(timezone.utc),
        )
        assert report.passed is True

    def test_report_with_all_passed_passes(self):
        report = RestoreVerificationReport(
            database_url_host="localhost:5432/testdb",
            started_at=datetime.now(timezone.utc),
            checks=[
                CheckResult("check1", CheckStatus.PASSED, "ok"),
                CheckResult("check2", CheckStatus.PASSED, "ok"),
                CheckResult("check3", CheckStatus.WARNING, "minor issue"),
            ],
        )
        assert report.passed is True

    def test_report_with_failure_fails(self):
        report = RestoreVerificationReport(
            database_url_host="localhost:5432/testdb",
            started_at=datetime.now(timezone.utc),
            checks=[
                CheckResult("check1", CheckStatus.PASSED, "ok"),
                CheckResult("check2", CheckStatus.FAILED, "data corruption"),
            ],
        )
        assert report.passed is False

    def test_report_with_skipped_only_passes(self):
        report = RestoreVerificationReport(
            database_url_host="localhost:5432/testdb",
            started_at=datetime.now(timezone.utc),
            checks=[
                CheckResult("check1", CheckStatus.SKIPPED, "table missing"),
            ],
        )
        assert report.passed is True

    def test_summary_includes_key_info(self):
        report = RestoreVerificationReport(
            database_url_host="db.example.com:5432/prod",
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            duration_seconds=12.5,
            alembic_revision="abc123",
            table_counts={"users": 10, "sales": 100},
            checks=[
                CheckResult("check1", CheckStatus.PASSED, "all good"),
                CheckResult("check2", CheckStatus.FAILED, "bad data"),
            ],
        )
        summary = report.summary()
        assert "db.example.com" in summary
        assert "abc123" in summary
        assert "users: 10" in summary
        assert "sales: 100" in summary
        assert "1 passed" in summary
        assert "1 failed" in summary
        assert "FAILED" in summary

    def test_summary_shows_passed_overall(self):
        report = RestoreVerificationReport(
            database_url_host="localhost:5432/testdb",
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            duration_seconds=3.0,
            checks=[
                CheckResult("check1", CheckStatus.PASSED, "all good"),
            ],
        )
        summary = report.summary()
        assert "OVERALL: PASSED" in summary


class TestRestoreVerifierInit:
    """Verify RestoreVerifier initialization."""

    def test_converts_asyncpg_url_to_sync(self):
        with patch("scripts.verify_restore.create_engine") as mock_engine:
            mock_engine.return_value = MagicMock()
            verifier = RestoreVerifier(
                "postgresql+asyncpg://user:pass@myhost:5432/mydb"
            )
            # Should have called create_engine with the sync URL
            call_args = mock_engine.call_args[0][0]
            assert "postgresql://" in call_args
            assert "asyncpg" not in call_args

    def test_extracts_host_info_without_credentials(self):
        with patch("scripts.verify_restore.create_engine") as mock_engine:
            mock_engine.return_value = MagicMock()
            verifier = RestoreVerifier(
                "postgresql+asyncpg://user:secret@db.example.com:5432/proddb"
            )
            assert "db.example.com" in verifier.host_info
            assert "proddb" in verifier.host_info
            # Must NOT contain credentials
            assert "secret" not in verifier.host_info
            assert "user:" not in verifier.host_info


class TestRestoreVerifierChecks:
    """Test individual integrity check methods with mocked DB connections."""

    def _make_verifier(self):
        """Create a verifier with a mocked engine."""
        with patch("scripts.verify_restore.create_engine") as mock_engine:
            mock_engine.return_value = MagicMock()
            return RestoreVerifier("postgresql://test:test@localhost/testdb")

    def test_alembic_revision_passed_single_head(self):
        verifier = self._make_verifier()
        report = RestoreVerificationReport(
            database_url_host="localhost",
            started_at=datetime.now(timezone.utc),
        )
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [("abc123def",)]
        mock_conn.execute.return_value = mock_result

        revision = verifier._check_alembic_revision(mock_conn, report)
        assert revision == "abc123def"
        assert report.checks[0].status == CheckStatus.PASSED

    def test_alembic_revision_failed_empty(self):
        verifier = self._make_verifier()
        report = RestoreVerificationReport(
            database_url_host="localhost",
            started_at=datetime.now(timezone.utc),
        )
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_conn.execute.return_value = mock_result

        revision = verifier._check_alembic_revision(mock_conn, report)
        assert revision is None
        assert report.checks[0].status == CheckStatus.FAILED

    def test_alembic_revision_warning_multiple_heads(self):
        verifier = self._make_verifier()
        report = RestoreVerificationReport(
            database_url_host="localhost",
            started_at=datetime.now(timezone.utc),
        )
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [("head1",), ("head2",)]
        mock_conn.execute.return_value = mock_result

        revision = verifier._check_alembic_revision(mock_conn, report)
        assert revision == "head1"
        assert report.checks[0].status == CheckStatus.WARNING

    def test_alembic_revision_handles_exception(self):
        verifier = self._make_verifier()
        report = RestoreVerificationReport(
            database_url_host="localhost",
            started_at=datetime.now(timezone.utc),
        )
        mock_conn = MagicMock()
        mock_conn.execute.side_effect = Exception("connection error")

        revision = verifier._check_alembic_revision(mock_conn, report)
        assert revision is None
        assert report.checks[0].status == CheckStatus.FAILED

    def test_sales_integrity_passed(self):
        verifier = self._make_verifier()
        report = RestoreVerificationReport(
            database_url_host="localhost",
            started_at=datetime.now(timezone.utc),
        )
        mock_conn = MagicMock()
        # First call: negative totals count, second: orphan items count
        mock_result_zero = MagicMock()
        mock_result_zero.scalar.return_value = 0
        mock_conn.execute.return_value = mock_result_zero

        verifier._check_sales_integrity(mock_conn, report)
        assert all(c.status == CheckStatus.PASSED for c in report.checks)

    def test_sales_integrity_detects_negative_totals(self):
        verifier = self._make_verifier()
        report = RestoreVerificationReport(
            database_url_host="localhost",
            started_at=datetime.now(timezone.utc),
        )
        mock_conn = MagicMock()
        # First call returns 3 (negative totals), second returns 0
        results = [MagicMock(), MagicMock()]
        results[0].scalar.return_value = 3
        results[1].scalar.return_value = 0
        mock_conn.execute.side_effect = results

        verifier._check_sales_integrity(mock_conn, report)
        assert report.checks[0].status == CheckStatus.FAILED
        assert "3" in report.checks[0].message

    def test_user_integrity_detects_missing_passwords(self):
        verifier = self._make_verifier()
        report = RestoreVerificationReport(
            database_url_host="localhost",
            started_at=datetime.now(timezone.utc),
        )
        mock_conn = MagicMock()
        # password check returns 2, role check returns 0, timestamp returns 0
        results = [MagicMock(), MagicMock(), MagicMock()]
        results[0].scalar.return_value = 2
        results[1].scalar.return_value = 0
        results[2].scalar.return_value = 0
        mock_conn.execute.side_effect = results

        verifier._check_user_integrity(mock_conn, report)
        assert report.checks[0].status == CheckStatus.FAILED
        assert "2" in report.checks[0].message

    def test_check_handles_missing_table_gracefully(self):
        """If a table doesn't exist, the check should be SKIPPED not crash."""
        verifier = self._make_verifier()
        report = RestoreVerificationReport(
            database_url_host="localhost",
            started_at=datetime.now(timezone.utc),
        )
        mock_conn = MagicMock()
        mock_conn.execute.side_effect = Exception("relation does not exist")

        verifier._check_audit_trail_integrity(mock_conn, report)
        assert report.checks[0].status == CheckStatus.SKIPPED
