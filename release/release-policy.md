# Phase 12G — Release Policy

**Base:** `409e5f3e0770d1bf908d217481994dac3e786c76` · **Policy:**
`phase12g-release-allowlist-v1` (see `release/release-allowlist.json`).

This policy governs the deterministic release candidate produced by
`scripts/release/build_release_candidate.py`. It is **fail-closed**: any file
that is not clearly REQUIRED or explicitly OPTIONAL, or that matches a PROHIBITED
pattern, aborts the build.

## Source of truth

The release is built from **tracked Git files** (`git ls-files`) plus an
**explicit operator-supplied generated-file allowlist**. Ignored files are never
packaged by discovery. Because the benchmark `*.jsonl`, holdout evidence,
authorization files, receipts, attempt roots and external audit directories are
all either git-ignored or live outside the repository, they are **structurally
excluded** — the build never enumerates the working tree for untracked content.

## REQUIRED (packaged)

- Tracked source code and tests.
- Tracked manifests and configuration needed for review (`requirements.txt`,
  `redteam/prompts-manifest.json`, `datasets/v2/manifests/*.json`, …).
- Phase 12F documentation (`docs/phase12f/**`) and other tracked `docs/**`.
- Tracked Markdown/text corpus and design docs (`datasets/**/*.md`).
- License and repository metadata safe for distribution (`LICENSE*`, `README*`,
  `.gitignore`, `.gitattributes`, `.env.example`).

## OPTIONAL (only when explicitly supplied)

Included only via the generated-file allowlist, each pinned by SHA-256 and byte
size and re-checked at build time:

- a safe generated dependency inventory (e.g. `pip freeze`),
- operator-supplied content-free test summaries.

An OPTIONAL file that fails its pinned hash/size, or matches a prohibited
pattern, fails the build.

## PROHIBITED (never packaged; any match fails closed)

- **Every `*.jsonl` file** — benchmark, holdout, validation and development
  records. A tracked JSONL is a hard error.
- `result.json` and raw evaluation records.
- Raw holdout / validation / development evidence.
- Credentials and tokens; `*.pem`, `*.key`, `*.p12`, `*.pfx`,
  `credentials.json`, `secrets.json`, `id_rsa`, `id_ed25519`.
- `.env` and any `.env.*` **except** `.env.example` / `.env.sample` /
  `.env.template`.
- Databases (`*.db`, `*.sqlite`, `*.sqlite3`).
- Caches (`__pycache__`, `.pytest_cache`, `.mypy_cache`, `.ruff_cache`).
- `.git` metadata; virtual environments (`.venv`, `venv`, `env`); IDE state
  (`.idea`, `.vscode`); temporary files.
- Authorization files, start receipts, attempt roots, and external audit working
  directories.

## Integrity guarantees

The builder also rejects symlinks / reparse points, path traversal, absolute
paths, files outside the repository, and duplicate logical paths; preserves
UTF-8 bytes exactly; produces a deterministic ZIP and a standard
`SHA256SUMS.txt`; and reopens and verifies the ZIP before publishing. It never
parses benchmark records or `result.json`, and never prints record or secret
content.

This policy does not itself constitute a Phase 12G PASS.
