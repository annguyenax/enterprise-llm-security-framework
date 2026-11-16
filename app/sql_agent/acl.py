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
        frozenset({"products", "inventory", "orders", "order_items", "branches", "product_reviews"}),
        frozenset({"products.dealer_price"}),
    ),
    ("kinhdoanh", "leader"): (
        frozenset({"products", "inventory", "orders", "order_items", "branches", "product_reviews", "customers"}),
        frozenset({"customers.phone", "customers.email"}),
    ),
    ("khovan", "member"): (
        frozenset({"products", "inventory", "warehouses", "branches"}),
        frozenset({"products.dealer_price"}),
    ),
    ("khovan", "leader"): (
        frozenset({"products", "inventory", "warehouses", "branches", "suppliers"}),
        frozenset({"products.dealer_price"}),
    ),
    ("cskh", "member"): (
        frozenset({"products", "orders", "order_items", "product_reviews", "customers"}),
        frozenset({"products.dealer_price"}),
    ),
    ("ketoan", "member"): (
        frozenset({"orders", "order_items", "receivables", "products", "customers", "suppliers"}),
        frozenset({"customers.phone", "customers.email"}),
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
