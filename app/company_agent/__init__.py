"""Nhà Mộc Việt company assistant (P4): a multi-tool agent behind the gateway.

Lab-scale PoC. Guarded mode enforces: per-role tool allowlist, strict tool-call
parsing and argument validation, guards on every tool output before it re-enters
the model context, human approval for every write action, recipient allowlist
for email, and output link/image stripping. Unguarded mode removes all of it
for the A/B comparison. No real email is ever sent; actions are simulated.
"""
