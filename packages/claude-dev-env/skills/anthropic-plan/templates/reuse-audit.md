# Reuse Audit

| Item | Kind | Verdict | Searched | Found | Decision | Evidence |
|---|---|---|---|---|---|---|
| _send_failure_alert | helper | reused | shared_utils/alerts | existing public helper covers the alert send | call the existing helper | shared_utils/alerts/notify.py:48 |

Summary: reused 1, extract-to-shared 0, new-justified 0, config-local 0, unjustified-reproduction 0.
