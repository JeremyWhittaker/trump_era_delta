# Quick Task: Monthly Trump Trade Setup Update

Date: 2026-05-08

## Request

Send a monthly email update showing where the monitored symbol is in the Trump trade setup. Send it only on the first day of each month and adjust the email subject accordingly.

## Plan

1. Extend persisted alert state with monthly update fields so repeated monitor cycles on the first day do not resend after a successful delivery.
2. Add a monthly delivery mode to the shared alert payload subject.
3. Wire monthly update evaluation into the monitor cycle after data freshness passes, reusing the existing report/chart email payload.
4. Document the monthly update behavior and add focused tests for monthly state, subject, and monitor-cycle scheduling.

## Validation

- Run the unit test suite.
- Run service preflight where practical.

