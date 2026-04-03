"""
Access and software management module for IT helpdesk.

Handles access permission requests and software install requests
with role-based authorization.
"""

from datetime import date


class AccessManager:
    """
    Manages access requests and software installs.

    Business Rules - Access:
    - If employee already has equal or higher permission: no-op
    - Expired permissions: flag for renewal
    - Admins auto-approved for any access level
    - Non-admins requesting admin-level: requires approval ticket
    - Non-admins requesting read/write: auto-approved

    Business Rules - Software:
    - If requires_approval is false: auto-approve
    - If employee role in approved_roles: auto-approve
    - Otherwise: requires approval ticket
    """

    PERMISSION_HIERARCHY = {"read": 0, "write": 1, "admin": 2}

    def request_access(
        self,
        employee: dict,
        system: dict,
        permission_level: str,
        existing_permissions: list[dict],
    ) -> dict:
        """
        Process an access request.

        Args:
            employee: Employee record
            system: System record
            permission_level: Requested level (read/write/admin)
            existing_permissions: Current permissions for this employee+system

        Returns:
            Dict with status, details, and flags
        """
        requested_rank = self.PERMISSION_HIERARCHY.get(permission_level, -1)

        # Check existing permissions
        for perm in existing_permissions:
            existing_rank = self.PERMISSION_HIERARCHY.get(
                perm.get("permission_level", ""), -1
            )

            # Check for expiry
            expires_at = perm.get("expires_at")
            if expires_at:
                try:
                    expiry_date = date.fromisoformat(expires_at)
                    if expiry_date < date.today():
                        return {
                            "status": "expired_permission",
                            "message": (
                                f"Existing {perm['permission_level']} permission on "
                                f"{system['name']} expired on {expires_at}. "
                                f"Would you like to renew it?"
                            ),
                            "expired_permission_id": perm["id"],
                            "requires_approval": False,
                        }
                except ValueError:
                    pass

            # Already has equal or higher
            if existing_rank >= requested_rank:
                return {
                    "status": "already_has_access",
                    "message": (
                        f"Employee already has {perm['permission_level']} access to "
                        f"{system['name']}, which is equal or higher than requested "
                        f"{permission_level} access."
                    ),
                    "requires_approval": False,
                }

        employee_role = employee.get("role", "user")

        # Admins auto-approved for anything
        if employee_role == "admin":
            return {
                "status": "approved",
                "message": (
                    f"Admin access request auto-approved. "
                    f"{permission_level.capitalize()} permission granted for "
                    f"{system['name']}."
                ),
                "requires_approval": False,
                "permission_level": permission_level,
            }

        # Non-admin requesting admin level needs approval
        if permission_level == "admin":
            return {
                "status": "pending_approval",
                "message": (
                    f"Admin-level access to {system['name']} requires manager approval. "
                    f"A ticket will be created for review."
                ),
                "requires_approval": True,
                "permission_level": permission_level,
            }

        # Non-admin requesting read/write: auto-approve
        return {
            "status": "approved",
            "message": (
                f"{permission_level.capitalize()} permission granted for "
                f"{system['name']}."
            ),
            "requires_approval": False,
            "permission_level": permission_level,
        }

    def request_software_install(
        self,
        employee: dict,
        software: dict,
    ) -> dict:
        """
        Process a software install request.

        Args:
            employee: Employee record
            software: Software catalog record

        Returns:
            Dict with status and details
        """
        requires_approval = software.get("requires_approval", False)
        if isinstance(requires_approval, str):
            requires_approval = requires_approval.lower() in ("true", "1", "yes")

        if not requires_approval:
            return {
                "status": "approved",
                "message": f"{software['name']} has been approved for installation.",
                "requires_approval": False,
            }

        # Check if employee role is in approved_roles
        approved_roles = software.get("approved_roles", "")
        if isinstance(approved_roles, str):
            role_list = [
                r.strip().lower() for r in approved_roles.split(",") if r.strip()
            ]
        else:
            role_list = [str(r).lower() for r in approved_roles]

        employee_role = employee.get("role", "user").lower()

        if employee_role in role_list:
            return {
                "status": "approved",
                "message": (
                    f"{software['name']} has been approved for installation "
                    f"(role '{employee_role}' is pre-approved)."
                ),
                "requires_approval": False,
            }

        return {
            "status": "pending_approval",
            "message": (
                f"{software['name']} requires manager approval for role "
                f"'{employee_role}'. A ticket will be created for review."
            ),
            "requires_approval": True,
        }
