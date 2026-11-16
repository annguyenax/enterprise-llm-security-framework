"""P4 SQL agent lab: text-to-SQL with a gateway-side SQL guard (P2SQL defense).

Lab-scale proof-of-concept. The security controls live here, in the gateway,
not in the model: the guarded path enforces read-only, single-statement,
ACL-scoped SQL regardless of which LLM produced it.
"""
