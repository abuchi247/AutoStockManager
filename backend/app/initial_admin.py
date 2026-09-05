"""Auto-provision an initial admin account on first startup.

When the users table is empty (fresh deployment), this module creates a single
Admin user with a cryptographically random password and logs it to stdout
exactly once. The account has must_change_password=True so the operator is
forced to set a real password on first login.

This eliminates the need for hardcoded default credentials in documentation or
scripts, and ensures every deployment starts with a unique temporary password.
"""

import logging
import secrets
import string
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory
from app.models.user import User
from app.services.auth_service import hash_password

logger = logging.getLogger(__name__)

# Password character set: letters + digits + safe punctuation
_PASSWORD_ALPHABET = string.ascii_letters + string.digits + "!@#$%&*"
_PASSWORD_LENGTH = 16


def _generate_temporary_password() -> str:
    """Generate a random password that satisfies complexity requirements.

    Guarantees at least one uppercase, one lowercase, and one digit.
    """
    while True:
        password = "".join(secrets.choice(_PASSWORD_ALPHABET) for _ in range(_PASSWORD_LENGTH))
        has_upper = any(c.isupper() for c in password)
        has_lower = any(c.islower() for c in password)
        has_digit = any(c.isdigit() for c in password)
        if has_upper and has_lower and has_digit:
            return password


async def ensure_initial_admin() -> None:
    """Create an initial admin if no users exist in the database.

    This is safe to call on every startup — it only creates the admin when
    the users table is completely empty (fresh deployment). The temporary
    password is logged at WARNING level so it appears in container logs
    even with default log levels.
    """
    async with async_session_factory() as session:
        # Check if any users exist (including soft-deleted ones, to avoid
        # re-provisioning if an admin was deleted)
        result = await session.execute(
            select(func.count()).select_from(User)
        )
        user_count = result.scalar_one()

        if user_count > 0:
            logger.debug("initial_admin_skipped", extra={"reason": "users_exist", "count": user_count})
            return

        # Generate credentials
        temp_password = _generate_temporary_password()
        password_hash = hash_password(temp_password)

        # Create the admin user
        admin = User(
            id=uuid.uuid4(),
            username="admin",
            email="admin@localhost",
            password_hash=password_hash,
            role="Admin",
            is_active=True,
            failed_login_attempts=0,
            must_change_password=True,
        )

        session.add(admin)
        try:
            await session.commit()
        except IntegrityError:
            # Concurrency guard: the backend runs multiple uvicorn workers
            # (WEB_CONCURRENCY), and each runs this startup hook. On a fresh
            # database several workers can all read user_count == 0 and race to
            # insert the "admin" row; exactly one wins and the rest hit the
            # unique constraint on username. That is a benign outcome — the
            # admin now exists — so roll back and exit quietly instead of
            # crashing the worker's startup with an alarming traceback.
            await session.rollback()
            logger.info(
                "initial_admin_already_created_by_another_worker",
                extra={"username": "admin"},
            )
            return

        # Log the temporary password prominently. This is the ONLY time it
        # appears — it is not stored anywhere in plaintext.
        logger.warning(
            "initial_admin_created",
            extra={
                "username": "admin",
                "temporary_password": temp_password,
                "action_required": "Change this password on first login",
            },
        )
        # Also print to stdout for operators who may not have structured logging
        print("\n" + "=" * 70)
        print("  INITIAL ADMIN ACCOUNT CREATED")
        print("=" * 70)
        print(f"  Username:           admin")
        print(f"  Temporary Password: {temp_password}")
        print(f"  Email:              admin@localhost")
        print("")
        print("  You MUST change this password on first login.")
        print("  This password will not be shown again.")
        print("=" * 70 + "\n")
