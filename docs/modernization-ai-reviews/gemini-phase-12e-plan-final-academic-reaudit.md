# Gemini Phase 12E Revised Academic Plan Re-Audit

## Repository Snapshot Inspected

* Bundle directly inspected: Yes


* Branch from manifest: `phase-12e-ablation-evaluation`

* Commit from manifest: `d82bac7828e2e54520e0aa29271e820a52ec6f47`

* Exact commit independently verified: No


* Verification limitations: Gemini GitHub import does not expose full immutable Git metadata



## Previous Academic Finding Resolution

* Status: PASS
* Evidence: The plan explicitly resolves the previous execution-path and missing/errored-case handling findings.
* Blocking: No

## Internal Validity

* Status: PASS
* Case-error policy: The revised plan strictly defines the policy for case errors: "Mọi exception nào ở một case ⇒ ghi đúng một record cho case với `case_status=error|timeout`, fixed safe `error_category`, `correct=false`". These cases "vẫn nằm trong diagnostic error-adjusted denominator" (remain in the diagnostic error-adjusted denominator) and do not disappear.


* Execution-path limitation: Section 8 specifies a single execution contract (`run_rag_query_uncommitted`) for the ablation matrix to maintain parity across C0-C7. A C0 HTTP-parity smoke test is separated as non-metric evidence to evaluate the perimeter defense without confounding the matrix data. The HTTP perimeter limitation is now explicitly recorded.


* Blocking: No

## Construct and Statistical Validity

* Status: PASS
* C4/C5 interpretation: The plan mandates that C4/C5 "live-mock delta chỉ là completeness observation và không được dùng cho necessity/redundancy claim" (live-mock delta is a completeness observation only and must not be used for necessity/redundancy claims). Leakage is evaluated through an approved scripted offline provider, separated from the primary matrix.


* Reporting policy: ABR (now correctly termed AOMR: Allowed Outcome Match Rate) and FPR must be reported jointly for each configuration. Higher-order interactions and trusted-internal ablation profiles are deferred to future evaluations because the sample size is inadequate.


* Blocking: No

## Critical Academic Issues

None.

## Major Academic Issues

None.

## Minor Issues

None.

## Required Corrections Before Implementation

None.

## Final Verdict

PASS