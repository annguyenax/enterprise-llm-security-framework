"""Department/role ACL for the furniture database (contract table)."""
from __future__ import annotations

from app.sql_agent.models import SqlActor

# Tables any guarded query may NEVER read, whatever the actor.
FORBIDDEN_TABLES = frozenset({
    "internal_secrets", "sqlite_master", "sqlite_schema", "sqlite_temp_master",
    "sqlite_temp_schema", "sqlite_sequence", "sqlite_stat1",
})

# (department, role) -> (allowed tables, denied "table.column")
_ACL: dict[tuple[str, str], tuple[frozenset[str], frozenset[str]]] = {
    ("kinhdoanh", "member"): (
        frozenset({"products", "inventory", "orders", "order_items", "branches", "product_reviews",
                   "promotions", "shipments"}),
        frozenset({"products.dealer_price", "shipments.address"}),
    ),
    ("kinhdoanh", "leader"): (
        frozenset({"products", "inventory", "orders", "order_items", "branches", "product_reviews",
                   "promotions", "shipments", "customers"}),
        frozenset({"customers.phone", "customers.email", "shipments.address"}),
    ),
    ("khovan", "member"): (
        frozenset({"products", "inventory", "warehouses", "branches", "shipments", "order_items"}),
        frozenset({"products.dealer_price"}),
    ),
    ("khovan", "leader"): (
        frozenset({"products", "inventory", "warehouses", "branches", "shipments", "order_items", "suppliers"}),
        frozenset({"products.dealer_price"}),
    ),
    ("cskh", "member"): (
        frozenset({"products", "orders", "order_items", "product_reviews", "customers", "shipments",
                   "warranty_claims", "support_tickets", "promotions", "branches"}),
        frozenset({"products.dealer_price"}),
    ),
    ("ketoan", "member"): (
        frozenset({"orders", "order_items", "receivables", "products", "customers", "suppliers",
                   "promotions", "employees", "branches"}),
        frozenset({"customers.phone", "customers.email"}),
    ),
    ("nhansu", "member"): (
        frozenset({"employees", "branches"}),
        frozenset({"employees.monthly_salary"}),
    ),
    ("nhansu", "leader"): (
        frozenset({"employees", "branches"}),
        frozenset(),
    ),
    ("it", "member"): (
        frozenset({"branches", "warehouses", "products"}),
        frozenset({"products.dealer_price"}),
    ),
}
# Roles not listed for a department inherit the closest lower role.
_ROLE_FALLBACK = {"leader": "member"}


def _key(actor: SqlActor) -> tuple[str, str] | None:
    if not isinstance(actor, SqlActor):
        return None
    if not isinstance(actor.department, str) or not isinstance(actor.role, str):
        return None
    dept = actor.department.strip().casefold().replace(" ", "").replace("_", "")
    role = actor.role.strip().casefold()
    if (dept, role) in _ACL:
        return dept, role
    fallback = _ROLE_FALLBACK.get(role)
    if fallback and (dept, fallback) in _ACL:
        return dept, fallback
    return None


def permissions(actor: SqlActor) -> tuple[frozenset[str], frozenset[str]]:
    """Return (allowed tables, denied columns). Unknown actors get nothing."""
    key = _key(actor)
    if key is None:
        return frozenset(), frozenset()
    return _ACL[key]
