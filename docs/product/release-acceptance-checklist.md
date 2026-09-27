# Release Acceptance Checklist

Use this checklist with a non-production deployment and synthetic accounts and
files. Record date, build/commit, browser/device, student tester, and qualified
content reviewer. Do not use real student documents. `PASS` requires observed
completion and comprehension; an automated test alone is evidence for software
behavior, not human acceptance.

## Student workflow

| Check | Acceptance evidence | Status |
| --- | --- | --- |
| Register, sign in, refresh, sign out, and sign in again | User completes the flow and understands session end | NOT RUN — human student test required |
| Browse Rights Explorer and search/filter published knowledge | User finds a relevant result and can identify its jurisdiction, source, and review metadata | NOT RUN — human student test required |
| Ask the Assistant an in-scope question | Response cites approved sources, states uncertainty and limitations, and offers a useful next step | NOT RUN — human student and content reviewer required |
| Ask an urgent/high-risk question | Urgent route appears before generation, gives actionable verified support, and avoids unnecessary questions | NOT RUN — qualified reviewer required |
| Upload a supported synthetic PDF and inspect analysis | User sees processing/extraction uncertainty, page evidence, limitations, and next steps | NOT RUN — human student test required |
| Download and delete own synthetic document/report | Own download succeeds; after deletion the report and object are unavailable | NOT RUN — human student test required |
| Open complaint guidance and find a help resource | User can identify a relevant route/contact and its verification context | NOT RUN — human student test required |

## Security and governance

| Check | Automated or observed evidence | Status |
| --- | --- | --- |
| Cross-account document, report, download, retry, and delete access | `tests/integration/test_documents.py` owner-isolation cases | Automated PASS |
| Anonymous private-object access denied and malware scan blocks infected input | `tests/integration/test_documents.py` MinIO and ClamAV cases | Automated PASS |
| Assistant high-risk routing, refusal, retrieval/provider failure, and injection handling | `tests/integration/test_assistant.py`, `tests/test_assistant_unit.py` | Automated PASS |
| Generic server errors do not expose internals and include correlation IDs | `tests/test_f10_hardening.py` | Automated PASS |
| Knowledge draft/review/publish and public visibility boundary | `tests/integration/test_knowledge.py` | Automated PASS |
| Help verification and student visibility | `tests/integration/test_guidance.py` | Automated PASS |
| Provenance anchor authorization, idempotency, immutable transitions, and outage behavior | F9 test record in `progress.md`; rerun chaincode suite for the candidate | NOT RUN — candidate-specific F9 suite not rerun |
| Assistant response rating and issue report are owner-scoped, idempotent, and metadata-only | `tests/integration/test_assistant.py::test_high_risk_skips_provider_and_missing_auth_is_401` | Automated PASS |
| Admin triage of feedback, stale content, failed analyses, and provider errors | Admin operational dashboard and triage workflow | NOT RUN — admin triage UI/API not present |
| Qualified reviewer signs off on content freshness, emergency routes, AI limits, and document interpretation | Signed reviewer/date and identified source set | NOT RUN — human qualified reviewer required |

## Accessibility and comprehension

| Check | Evidence | Status |
| --- | --- | --- |
| Keyboard-only core journey, focus order, and dialog behavior | Record browser and observed exceptions | NOT RUN — human accessibility review required |
| Screen reader status/error/source announcements | Record screen reader, browser, and issues | NOT RUN — human accessibility review required |
| Forced colors, zoom/reflow, mobile touch, and reduced motion | Record viewport/settings and issues | NOT RUN — human accessibility review required |
| Student comprehension, confidence calibration, and error recovery | Record task completion and user feedback without retaining unnecessary personal details | NOT RUN — human student acceptance required |

## Automated browser run

Record the command, result, browser, and service versions here for each release
candidate. Current repository Playwright coverage exercises registration/login,
dashboard and help calls, Rights Explorer search/filter/detail, responsive and
theme behavior, error handling, and logout. It does not currently exercise the
full Assistant or document lifecycle in a browser; use the backend integration
tests for their automated API/security evidence and complete the human workflow
checks above separately.

| Candidate | Command | Result | Notes |
| --- | --- | --- | --- |
| Current workspace | `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=<installed Chrome> npm run test:e2e` | PASS — 1 browser test | Registration/login/onboarding, dashboard/help and Rights Explorer search/filter/detail, responsive/theme/error handling, logout; Chrome. Does not cover Assistant/document lifecycle. |

Human student and qualified-reviewer acceptance are required by the industrial
specification's user acceptance testing and release-candidate acceptance
criteria. Marking these checks `NOT RUN` means the product is not accepted for
release; automated tests must not be presented as a substitute.
