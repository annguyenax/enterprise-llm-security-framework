# Phase 12G — Release Policy

**Policy:** `phase12g-release-allowlist-v2` (schema 2, machine-consumable; see
`release/release-allowlist.json`).

This policy governs the deterministic release candidate produced by
`scripts/release/build_release_candidate.py`. It is **fail-closed**: any file
that is not clearly REQUIRED or explicitly OPTIONAL, or that matches a PROHIBITED
pattern, aborts the build.

## Mechanically authoritative

The builder **loads and schema-validates** `release/release-allowlist.json` from
the tracked repository and derives its prohibited/required classification
**from that file** — it does not hard-code the rules. The policy's SHA-256 and
schema version are recorded in `release-manifest.json`, and the verifier
independently re-parses the policy embedded in the ZIP and confirms its SHA-256
matches the manifest. Changing the policy therefore changes the release identity
deterministically. Command-line input cannot broaden the policy; an
operator-supplied generated-file allowlist is exact and remains subject to every
prohibited rule.

## Control-file coverage (explicit)

- `release-manifest.json.files` lists exactly the payload entries (`repo/*`).
- `FILE_SIZES.json.files` covers payload + manifest (excludes `FILE_SIZES.json`
  and `SHA256SUMS.txt`).
- `SHA256SUMS.txt` covers payload + manifest + `FILE_SIZES.json` (excludes
  `SHA256SUMS.txt` itself).

The verifier enforces these three sets exactly and returns PASS only when every
control and payload invariant holds; NOT_VERIFIABLE is never treated as PASS.

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
