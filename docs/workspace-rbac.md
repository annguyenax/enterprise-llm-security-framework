# Workspace RBAC and delegated task workflow

This is a lab-scale proof of concept using synthetic accounts and SQLite. It is not production-ready.

## Authorization boundaries

| Role | People visibility | Task scope | Conversations | Documents |
|---|---|---|---|---|
| `superadmin` | All departments and users | Creates department tasks, sees all tasks, may override progress | May inspect all; cannot send as another user | All scopes |
| `leader` | Leader and employees in their own department | Receives department tasks and delegates child tasks to members in that department | Own only | Own plus authorized department documents |
| `member` | No roster endpoint | Sees and updates only tasks assigned to self | Own only | Own plus authorized department documents |

The API enforces these boundaries before retrieval or model invocation. A leader cannot target an employee from another department. A member cannot read another member's private conversation or personal documents.

## Task flow

```text
SuperAdmin
  -> department task (automatically assigned to that department's leader)
     -> child task assigned by leader to one member in the same department
        -> member updates 0–100% progress
           -> parent progress is recalculated from all child tasks
```

Relevant endpoints are `GET /v1/team`, `GET /v1/tasks`, `POST /v1/tasks/department`, `POST /v1/tasks/{id}/delegate`, and `PATCH /v1/tasks/{id}/progress`.

## Synthetic accounts

Fresh databases are seeded only when the `users` table is empty:

- `superadmin` / `SuperAdmin#2026`
- `it.leader` / `ITLeader#2026`; `it.user1` / `ITUser1#2026`; `it.user2` / `ITUser2#2026`
- `hr.leader` / `HRLeader#2026`; `hr.user1` / `HRUser1#2026`; `hr.user2` / `HRUser2#2026`

Passwords are stored as PBKDF2-HMAC-SHA256 hashes with per-account random salts. Session tokens are stored only as SHA-256 hashes and expire after seven days.
