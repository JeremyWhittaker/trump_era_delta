# Phase 3: Alert Reliability - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-19
**Phase:** 03-alert-reliability
**Areas discussed:** Test-email verification, Alert state storage, Restart/retry semantics, Payload compatibility

---

## Test-email verification

| Option | Description | Selected |
|--------|-------------|----------|
| Lightweight SMTP smoke check only | Verify connectivity without sending the full operator-facing payload | |
| Real test email through the live path | Send an actual message using the same payload, charts, and SMTP contract as live alerts | ✓ |
| Separate test-only email implementation | Keep a dedicated verification path with different rendering or recipients | |

**User's choice:** Accepted the recommended approach while proceeding without additional discussion.
**Notes:** Receiving the actual email remains the success signal, so test-email should prove the real path rather than a reduced simulation.

---

## Alert state storage

| Option | Description | Selected |
|--------|-------------|----------|
| Keep in-memory only | Continue relying on process-local state and accept restart blind spots | |
| Persist lightweight project-local runtime state | Store last observed and last delivered alert state in local runtime storage | ✓ |
| Add a heavier database dependency now | Introduce a fuller datastore immediately for alert history and state | |

**User's choice:** Accepted the recommended approach while proceeding without additional discussion.
**Notes:** The milestone is still single-operator and local-service-first, so lightweight persisted state is the right default.

---

## Restart and retry semantics

| Option | Description | Selected |
|--------|-------------|----------|
| Reset baseline on every restart | Never retry pending failures, just establish a fresh in-memory baseline | |
| Resume pending undelivered transition, never duplicate delivered ones | Persist enough state to avoid duplicates while allowing failed sends to retry | ✓ |
| Hard-fail the process on any email send error | Stop the service immediately rather than track retryable failures | |

**User's choice:** Accepted the recommended approach while proceeding without additional discussion.
**Notes:** This balances trustworthiness and practicality: already delivered transitions must not replay, but failed sends should not disappear silently.

---

## Payload compatibility

| Option | Description | Selected |
|--------|-------------|----------|
| Keep test and live payloads separate | Allow the two paths to evolve independently | |
| Normalize onto one payload/inline-image contract | Reuse one builder for HTML, text, and chart attachments across both paths | ✓ |
| Redesign the email format during reliability work | Change delivery behavior and presentation at the same time | |

**User's choice:** Accepted the recommended approach while proceeding without additional discussion.
**Notes:** Phase 3 is about reliable delivery and restart-safe behavior, not a redesign of the email template or alert interpretation.

---

## the agent's Discretion

- Exact runtime state-file schema and atomic-write approach
- Exact retry bookkeeping fields and transition identifier shape
- Exact local storage format as long as it remains lightweight and restart-safe

## Deferred Ideas

- Service-manager packaging remains Phase 4.
- Smoke-test harnesses remain Phase 5.
- Forecast productionization remains deferred to v2.
