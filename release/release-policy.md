# Phase 12G — Release Policy

**Policy:** `phase12g-release-allowlist-v4` (schema 4, machine-consumable; see
`release/release-allowlist.json`).

This policy governs the deterministic release candidate produced by
`scripts/release/build_release_candidate.py`. It is a **true, mechanically
disjoint closed-world allowlist**: every tracked path is classified by **counting**
the inclusion rules whose effective match set contains it, and the build fails
closed unless exactly one permitted rule matches.

## Disjoint classification (no precedence)

For each tracked path, after every rule's semantics and explicit exclusions are
applied:

| Outcome | Reason code |
|---|---|
| 0 permitted matches | `unclassified_tracked_path` |
| more than 1 permitted match | `ambiguous_policy_classification` |
| a permitted **and** a prohibited match | `prohibited_policy_overlap` |
| exactly 1 prohibited (0 permitted) | `tracked_path_prohibited` |
| exactly 1 permitted match | include — record class + **unique rule ID** + matched rule form |

Overlap is **never** resolved by precedence, first-match, most-specific, or
"REQUIRED over ALLOWED" selection — those approaches hide an ambiguous policy.
Instead the loader **proves structural disjointness**: it checks that no two
rules can match the same possible path (exact/archive-path rules carry explicit
`exclude_exact_paths` so a REQUIRED exact path is *not* also matched by a broad
extension rule). The builder additionally proves **effective disjointness** over
the current tracked Git set (0 unclassified, 0 ambiguous, 0 overlap, 0 prohibited).

Each inclusion rule has a **unique stable `rule_id`**; the matched rule ID and
form are recorded per file in `release-manifest.json`, and the verifier
independently recomputes and re-checks them.

### Rule forms

- `exact_path` (REQUIRED or ALLOWED) — one specific tracked path.
- `extension` (ALLOWED) — a suffix, minus any `exclude_exact_paths`.
- `exact_name` (ALLOWED) — a bare filename (e.g. `.gitignore`, `.env.example`).
- `archive_path` (ALLOWED_ARCHIVE) — one specific archive, see below.

## Snapshot-bound archive inspection

Archives are prohibited by default. An allowed archive's safety is decided from
the **exact bound snapshot bytes** that are hashed and packaged — the builder
reads the tracked file **once** and inspects central-directory names from
`io.BytesIO(snapshot)`, never a second filesystem read. The result is bound to
the payload path, payload SHA-256, payload size, policy rule ID and the
archive-inspection version, and recorded as content-free metadata in the
manifest.

One **shared inspector** (`inspect_archive_bytes`) is used by both the builder and
the verifier with identical limits and reason codes. The verifier re-inspects the
exact packaged archive bytes and never trusts the manifest metadata merely
because it is present. Limits: archive ≤ 64 MiB, ≤ 10000 entries, entry name ≤
1024 bytes, total names ≤ 2 MiB, depth ≤ 32, comment ≤ 4096 bytes, supported
formats/compression only (STORED/DEFLATE). It rejects duplicate or case-colliding
nested names, absolute/traversal/drive/UNC/backslash/control-character names,
encrypted entries, unsupported compression, nested archives, prohibited nested
names, and malformed archives — **names/metadata only, never nested content**.

The single tracked archive `bao-cao-dinh-ky-01-ptit.zip` (LaTeX periodic-report
source) is classified this way by explicit operator decision.

## Mandatory external trust anchor (verification)

A candidate can never establish its own trust root. The verifier returns **PASS
only** when an **external trusted policy file** is supplied independently of the
candidate (`--expected-policy-file`): the verifier reads those trusted bytes,
schema-validates them, uses them for payload classification, and requires the
candidate-embedded policy bytes and the manifest policy identity to equal them
exactly. A trusted SHA alone (`--expected-policy-sha256`), or no anchor at all,
yields **NOT_VERIFIABLE — never PASS** (a candidate-self-consistency audit only,
with a non-PASS exit code). There is no `candidate_anchored` PASS mode. The
builder verifies both the staged and the published ZIP against the exact tracked
policy file it loaded.

When **generated files are present**, PASS additionally requires an external
trusted generated-allowlist anchor (`--expected-generated-sha256`, the SHA-256 of
the operator-supplied generated allowlist); without it the result is
NOT_VERIFIABLE. The manifest encodes a canonical `generated` object
(`{"count": N, "allowlist_sha256": …}`); the zero-generated state is exactly
`{"count": 0, "allowlist_sha256": null}`. A generated row must carry
`source="generated"`, `classification="GENERATED"`, the reserved generated
rule ID and `rule_form="generated"` together; tracked rows may carry none of
those markers.

## Content-free failure contract

Candidate-controlled values (entry/nested names, paths, manifest/policy/rule/
branch strings, malformed JSON/Unicode, OS/zip exception text) are **never**
emitted in findings, summaries, stderr or exceptions. Every parser/ZIP/filesystem
failure is converted at a single boundary into a structured result carrying only
a stable reason code, `content_free: true`, and safe identifiers (ordinal index,
count, or the SHA-256 of the offending value). Uncontrolled tracebacks and raw
exception messages are suppressed.

## Control-file coverage (explicit)

- `release-manifest.json.files` lists exactly the payload entries (`repo/*`).
- `FILE_SIZES.json.files` covers payload + manifest.
- `SHA256SUMS.txt` covers payload + manifest + `FILE_SIZES.json`.

The verifier enforces these sets exactly, validates the manifest against an
**exact schema at every level** (every field, exact type — `type(x) is int` so a
boolean or a float is never accepted where an integer is required — and canonical
values for `control_coverage`/`zip_policy`), reconciles all counts, confirms the
policy's REQUIRED paths are present, anchors the embedded policy to a trusted
expected identity when one is supplied, checks deterministic ZIP metadata, and
applies outer-ZIP resource bounds. A malformed candidate returns a content-free
structured **FAIL** (never a traceback); **NOT_VERIFIABLE is never PASS** and
never uses the PASS exit code.

## Verify before publication

The builder builds and fully verifies the candidate in a same-volume **staging**
directory, requires verifier **PASS** (anchored to the tracked policy identity),
then publishes the **exact verified bytes** with an **atomic no-clobber hard link**
(`os.link`; never `os.replace`, no overwrite, no force). It rechecks the published
ZIP's SHA-256/size against the verified bytes and verifies the published ZIP
again. A pre-publication failure leaves **no** final directory or ZIP; staging is
always removed; a pre-existing destination is never deleted. The release path is
`<output-dir>\release-candidate.zip`; **no sibling `<output-dir>.zip`** is created.

## PROHIBITED (never packaged; any match fails closed)

- **Every `*.jsonl`** (benchmark/holdout/validation/development records), and
  `result.json` and raw evaluation records.
- Credentials/tokens: `*.pem`, `*.key`, `*.p12`, `*.pfx`, `credentials.json`,
  `secrets.json`, `id_rsa`, `id_ed25519`.
- `.env` / `.env.*` except `.env.example` / `.env.sample` / `.env.template`.
- Databases (`*.db`, `*.sqlite`, `*.sqlite3`); caches; `.git`; virtual
  environments; IDE state; temporary files.
- Any archive not on the exact allow-list, any nested archive, and any allowed
  archive with a prohibited/unsafe nested name.
- Authorization files, receipts, attempt roots, external audit directories
  (git-ignored or outside the repository).

## Integrity guarantees

The builder rejects symlinks/reparse points, path traversal, absolute and
drive-qualified paths, files outside the repository, and duplicate or
case-colliding logical paths; preserves arbitrary bytes exactly (64 MiB per-file
ceiling); and produces a deterministic ZIP plus a standard `SHA256SUMS.txt`. It
never parses benchmark records or `result.json`, and never prints record or
secret content.

This policy does not itself constitute a Phase 12G PASS.
