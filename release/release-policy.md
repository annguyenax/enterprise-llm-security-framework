# Phase 12G — Release Policy

**Policy:** `phase12g-release-allowlist-v3` (schema 3, machine-consumable; see
`release/release-allowlist.json`).

This policy governs the deterministic release candidate produced by
`scripts/release/build_release_candidate.py`. It is a **true closed-world
allowlist**: every tracked path must match exactly one inclusion rule (REQUIRED
or ALLOWED) or the build **fails closed**. There is **no default-allow branch**.

## Closed-world classification (mechanically authoritative)

The builder **loads and schema-validates** `release/release-allowlist.json` from
the tracked repository and classifies **every** path returned by `git ls-files`:

1. A **PROHIBITED** match (extension, exact name, path component, `.env*`, or an
   archive extension) fails the build immediately.
2. A path listed in `inclusion.required_paths` is classified **REQUIRED** (and
   must be tracked and present).
3. A path listed in `inclusion.allowed_archives` (exact path) is classified
   **ALLOWED_ARCHIVE** — see the nested-archive rule below.
4. A basename in `inclusion.allowed_exact_names`, or a suffix in
   `inclusion.allowed_extensions`, is classified **ALLOWED**.
5. A path that matches **no** inclusion rule fails closed as
   `unclassified_tracked_path`. A policy that declares overlapping/incompatible
   rule classes fails as `ambiguous_policy_classification`.

There is no logic equivalent to "include everything that is not prohibited".
Unclassified tracked files block the release.

The policy's SHA-256 and schema version are recorded in `release-manifest.json`
(under `policy`), and the verifier independently re-parses the policy embedded in
the ZIP and confirms its `policy_id`, `schema_version` and SHA-256 all match the
manifest. Changing the policy therefore changes the release identity
deterministically. Command-line input cannot broaden the policy or add inclusion
rules; an operator-supplied generated-file allowlist is exact, classified
`GENERATED`, and remains subject to every prohibited rule and the closed-world
classifier.

### Single policy snapshot

The policy file is read **once**; the same bytes are parsed, hashed and packaged.
The `policy_sha256` recorded in the manifest is the SHA-256 of exactly the bytes
placed in the archive.

## Archives (prohibited by default; fail-closed nested rule)

Archive extensions (`.zip`, `.tar`, `.gz`, `.tgz`, `.bz2`, `.xz`, `.zst`, `.7z`,
`.rar`) are **prohibited by default**. An archive is included only when its exact
path appears in `inclusion.allowed_archives` **with a documented reason**. For
each allowed archive the builder enumerates the central-directory entry **NAMES
ONLY** (it never extracts and never reads nested file bytes) and fails closed if
any nested name matches a prohibited rule. This never inspects raw benchmark
`*.jsonl` or `result.json` content — only entry names.

The single tracked archive `bao-cao-dinh-ky-01-ptit.zip` (LaTeX periodic-report
source: `.tex`/`.bib`/`.sty`/figures) is classified this way by explicit operator
decision.

## Control-file coverage (explicit)

- `release-manifest.json.files` lists exactly the payload entries (`repo/*`).
- `FILE_SIZES.json.files` covers payload + manifest (excludes `FILE_SIZES.json`
  and `SHA256SUMS.txt`).
- `SHA256SUMS.txt` covers payload + manifest + `FILE_SIZES.json` (excludes
  `SHA256SUMS.txt` itself).

The verifier enforces these three sets **exactly**, validates the manifest
against an exact schema (every field and type, `type(x) is int` for sizes so a
boolean is never accepted as a size), checks deterministic ZIP metadata, and
returns PASS only when every invariant holds. A malformed candidate returns a
content-free structured **FAIL** (never a traceback). **NOT_VERIFIABLE is never
treated as PASS** and never uses the PASS exit code.

## Verify before publication

The builder builds and fully verifies the candidate in a same-volume **staging**
directory, requires verifier **PASS**, then publishes the **exact verified bytes**
to the final destination via an **atomic no-clobber hard link** (`os.link`;
never `os.replace`, no overwrite, no force). It rechecks the published ZIP's
SHA-256 and size against the verified bytes and verifies the published ZIP again.
A pre-publication failure leaves **no** final directory or ZIP; staging is always
removed. The release path is `<output-dir>\release-candidate.zip`; **no sibling
`<output-dir>.zip` is created**.

## PROHIBITED (never packaged; any match fails closed)

- **Every `*.jsonl` file** — benchmark, holdout, validation and development
  records. A tracked JSONL is a hard error.
- `result.json` and raw evaluation records.
- Credentials and tokens; `*.pem`, `*.key`, `*.p12`, `*.pfx`,
  `credentials.json`, `secrets.json`, `id_rsa`, `id_ed25519`.
- `.env` and any `.env.*` **except** `.env.example` / `.env.sample` /
  `.env.template`.
- Databases (`*.db`, `*.sqlite`, `*.sqlite3`).
- Caches (`__pycache__`, `.pytest_cache`, `.mypy_cache`, `.ruff_cache`).
- `.git` metadata; virtual environments (`.venv`, `venv`, `env`); IDE state
  (`.idea`, `.vscode`); temporary files.
- Any archive not on the exact `allowed_archives` list, and any allowed archive
  containing a prohibited nested name.
- Authorization files, start receipts, attempt roots, and external audit working
  directories (git-ignored or outside the repository).

## Integrity guarantees

The builder also rejects symlinks / reparse points, path traversal, absolute and
drive-qualified paths, files outside the repository, and duplicate or
case-colliding logical paths; preserves arbitrary bytes exactly (64 MiB per-file
ceiling); and produces a deterministic ZIP plus a standard `SHA256SUMS.txt`. It
never parses benchmark records or `result.json`, and never prints record or
secret content.

This policy does not itself constitute a Phase 12G PASS.
