"""
Password management module for IT helpdesk.

Handles password resets with role-based access control and account status checks.
"""

from enum import Enum
import secrets
import string


class AccountStatus(Enum):
    ACTIVE = "active"
    LOCKED = "locked"
    DISABLED = "disabled"


class PasswordResetResult(Enum):
    SUCCESS = "success"
    DENIED_UNAUTHORIZED = "denied_unauthorized"
    DENIED_DISABLED = "denied_disabled"


class PasswordManager:
    """
    Handles password reset flows.

    Business Rules:
    - Admins can reset any employee's password
    - Regular users can only reset their own password
    - Disabled accounts cannot have passwords reset
    - Locked accounts are unlocked first, then reset proceeds
    - MFA-enabled employees get MFA re-enrollment flag in result
    """

    def reset_password(
        self,
        target_employee: dict,
        requester_employee: dict,
    ) -> dict:
        """
        Process a password reset request.

        Args:
            target_employee: Employee record whose password is being reset
            requester_employee: Employee record of person requesting the reset

        Returns:
            Dict with status, temp_password, account_unlocked, mfa_reenrollment_required
        """
        requester_role = requester_employee.get("role", "user")
        requester_id = requester_employee["id"]
        target_id = target_employee["id"]

        # Role check: users can only reset their own password
        if requester_role != "admin" and requester_id != target_id:
            return {
                "status": PasswordResetResult.DENIED_UNAUTHORIZED.value,
                "message": "You can only reset your own password. Contact an admin for assistance.",
            }

        # Check account status
        account_status = AccountStatus(target_employee.get("account_status", "active"))

        if account_status == AccountStatus.DISABLED:
            return {
                "status": PasswordResetResult.DENIED_DISABLED.value,
                "message": "Account is disabled. Contact your administrator.",
            }

        account_unlocked = False
        if account_status == AccountStatus.LOCKED:
            account_unlocked = True

        # Generate temporary password
        temp_password = self._generate_temp_password()

        mfa_enabled = target_employee.get("mfa_enabled", False)
        if isinstance(mfa_enabled, str):
            mfa_enabled = mfa_enabled.lower() in ("true", "1", "yes")

        return {
            "status": PasswordResetResult.SUCCESS.value,
            "temp_password": temp_password,
            "account_unlocked": account_unlocked,
            "mfa_reenrollment_required": mfa_enabled,
            "employee_id": target_id,
            "employee_email": target_employee.get("email", ""),
            "message": self._build_success_message(account_unlocked, mfa_enabled),
        }

    def _generate_temp_password(self) -> str:
        chars = string.ascii_letters + string.digits + "!@#$%"
        return "".join(secrets.choice(chars) for _ in range(16))

    def _build_success_message(self, account_unlocked: bool, mfa_enabled: bool) -> str:
        parts = ["Password has been reset successfully."]
        if account_unlocked:
            parts.append("Account was locked and has been unlocked.")
        if mfa_enabled:
            parts.append("MFA re-enrollment is required on next login.")
        parts.append("A temporary password has been generated.")
        return " ".join(parts)
