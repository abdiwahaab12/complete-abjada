from __future__ import annotations

from typing import Optional

SUPER_ADMIN_ROLES = frozenset({"super_admin", "admin"})
EMPLOYEE_ROLES = frozenset({"employee", "tailor", "cashier"})
STAFF_ROLES = SUPER_ADMIN_ROLES | EMPLOYEE_ROLES


def is_super_admin_role(role: Optional[str]) -> bool:
    return (role or "") in SUPER_ADMIN_ROLES


def is_employee_role(role: Optional[str]) -> bool:
    return (role or "") in EMPLOYEE_ROLES


def normalize_staff_role(role: Optional[str]) -> str:
    """Map legacy roles to canonical names for UI."""
    r = (role or "").lower()
    if r in SUPER_ADMIN_ROLES:
        return "super_admin" if r == "super_admin" else "admin"
    if r in EMPLOYEE_ROLES:
        return "employee"
    return r or "employee"


# API path prefixes employees cannot access at all (any method)
EMPLOYEE_FORBIDDEN_API_PREFIXES = (
    "/api/transactions",
    "/api/transaction-categories",
    "/api/banks",
    "/api/swaps",
    "/api/reports",
    "/api/categories",
    "/api/finance",
)

# Under /api/auth — only super admin
EMPLOYEE_FORBIDDEN_AUTH_PATHS = (
    "/api/auth/staff",
)


def employee_may_access_api_path(path: str, method: str) -> bool:
    """Return False if employee role must not call this API."""
    p = path.split("?")[0]
    # Global payment log (financial module) — Super Admin only
    if p == "/api/payments/transactions" or p.startswith("/api/payments/transactions/"):
        return False
    for prefix in EMPLOYEE_FORBIDDEN_API_PREFIXES:
        if p == prefix or p.startswith(prefix + "/"):
            return False
    for ap in EMPLOYEE_FORBIDDEN_AUTH_PATHS:
        if p == ap or p.startswith(ap + "/"):
            return False
    # Inventory: read-only for employees
    if p == "/api/inventory" or p.startswith("/api/inventory/"):
        if method in ("POST", "PUT", "PATCH", "DELETE"):
            return False
    # User directory (staff listing) — super admin use
    if p == "/api/auth/users":
        return False
    return True
