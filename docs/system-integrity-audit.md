# System integrity audit - 2026-09-14

Repository: Nawar-Alsafadi-0/Xvond-core only. Baseline: 011eea9.

## Confirmed defects and repairs

| Area | Finding | Repair |
| --- | --- | --- |
| Conversation identity | WhatsApp sessions ignored phone identity; source insert left channel_id empty | Session uniqueness includes company, employee, phone and contact; bind the exact channel on every message and echo; reject conflicting contacts/channels |
| Existing data | Previous migration supplied type/contact but never channel_id | New migration fills only exact company/employee/phone matches; preserves ambiguous/conflicting rows |
| Profile/services | Omitted fields defaulted to empty values on update | Only submitted fields replace saved facts; independent editors send only owned fields; validate structured lists; preserve structured objects |
| Missing services | Generated knowledge omitted the fact that services were not saved | Explicit grounding instruction; recover only an unambiguous saved canonical Services JSON array; never derive a catalog from billing or business type |
| Embeddings | Live backfill could embed all company documents before answering | Live maintenance rebuilds lexical indexes only; query timeout falls back; log only exception class; reject non-finite vectors |
| Coexistence | Phone-token validity was presented as complete Coexistence | Verify app webhook fields and WABA subscribed app; require an observed echo; expose setup-required/echo-pending state |
| Webhook/worker | A crash after committing a claim lost the event permanently | Claim and processed result share the transaction; retry/dead-letter transitions use a Redis transaction |
| Handoff | Portal claims could race; AI could finish after human intervention | Serialize portal ownership mutations; signed echo marks control at ingress; check session/control again before sending AI response |
| Portal reply | Wrong channel possible through employee-wide lookup; blank replies accepted | Resolve exact conversation channel, reject blank text; preserve success-before-message-save behavior |
| Inbox | Tests/unclassified included by default | Default selects live channel types; explicit test/unknown filters remain; channel_id filtering supported |
| Runtime | Test chat could write to a live conversation before binding failed | Validate/bind source before provider execution; admin test conversations are classified too |
| Channel prompts | Website/voice temporarily dirtied the employee record | Request-scoped prompt overrides; defer commit until channel binding completes |
| Frontend | Slow requests could repaint another selected conversation; polling erased drafts | Request sequence guards, selected-conversation check, preserve current draft |
| Routing/cache | Core routes existed but no deployable shared-domain location map | Supply nginx include; no-store on authenticated responses and portal HTML; fingerprint changed frontend assets |
| Secret handling | Raw Meta/network exception text reached APIs/logs | Safe Meta errors, class-only embedding/runtime/retry diagnostics |
| Company lifecycle | Runtime/commercial state could be conflated | Canonical onboarding/testing/live/paused/suspended/cancelled/archived lifecycle with readiness-gated transitions and separate emergency runtime control |
| Employee go-live | Customer-side controls could bypass delivery ownership | Xvond Delivery Readiness owns activation; customer managers may stop an employee but cannot self-activate production AI |
| Support access | Support previously lacked a distinct least-privilege operations plane | Added authenticated read-only operator role, read-only operations UI, metadata-only company view, and tests that keep production mutations admin-only |
| Production acceptance | Pre-live checker incorrectly required already-live runtime and omitted operational gates | Acceptance runner now supports pre-live and --require-live modes, checks worker/backups/unresolved operations/deliveries, and emits safe error labels |

## Production routing and release consistency

`/admin-ui` already exists in FastAPI. Core code cannot override a reverse proxy
that serves the landing page before the request reaches Core. Include
`ops/nginx/core-locations.conf` in the existing xvond.com HTTPS server, adjust the
loopback port if APP_PORT differs, run `nginx -t`, then reload nginx. This file
does not replace the root landing-site location or touch Store.

With a CDN, bypass cache for authenticated API paths and portal HTML. Purge old
portal HTML once on deployment; changed script URLs have new versions. Configure
real-client-IP restoration only for explicitly trusted CDN/proxy address ranges.
Do not blindly trust client-supplied X-Forwarded-For.

Release the API and WhatsApp worker from the **same reviewed commit and image**.
Take a database backup and stop the old worker before schema migration. Build the
image, run migrations through the app entrypoint, wait for app readiness, then
start/recreate the worker. The Compose worker bypasses the app entrypoint and
must not be left running the previous image. Verify actual image IDs for both
containers, Alembic head, health/ready, and one authenticated portal flow.

After routing changes, verify both redirect and destination:

```
GET https://xvond.com/admin-ui
GET https://xvond.com/static/admin/index.html
GET https://xvond.com/customer-ui
GET https://xvond.com/health/ready
```

The first response must resolve to the admin HTML, not the landing page. The
customer and admin portals must fetch Core APIs on the same intended origin.

## Meta setup and acceptance

WABA `POST /subscribed_apps` and application `GET /subscriptions` are distinct
contracts. A WABA subscription does not prove that the application listens for
`smb_message_echoes`. The implementation checks the active
`whatsapp_business_account` subscription fields and verifies the app identity in
the WABA subscription list. Never copy access tokens into screenshots, logs, or
PRs.

Use the existing Business App number and the intended Coexistence Embedded
Signup configuration. Check Meta permissions, approved configuration, callback
verification, and `messages` plus `smb_message_echoes` fields. Optional history
and contact synchronization are not imported as live customer messages by this
change. A configured marker is not evidence of a received event.

Accept with a customer message, a manual Business App reply, and another customer
message: exactly one conversation, unchanged employee/channel, one human echo,
no AI response after human takeover. Then claim in the customer portal, send a
human reply to the same number, and explicitly return to AI. Repeat the webhook
and confirm no duplicate messages. Perform the check on the deployed image;
local mocks cannot prove production Meta subscriptions or routing.

## Verified repository / CI gates

Exact-head CI run #884 for commit `e85fcbcab93f923fa22a74debbeeb4720eee47bf`
completed successfully. It verified:

- dependency consistency (`pip check`)
- Python compilation
- a fresh PostgreSQL 17 database upgraded through Alembic head
- all admin/customer JavaScript syntax
- all shell-script syntax
- all 3 Meta Embedded Signup Node tests
- production Compose validation
- **516 Python tests passed**
- production Docker image build completed successfully

The repository also includes dedicated regression coverage for conversation
identity, duplicate webhooks, delayed echoes, human takeover/return-to-AI,
outbound delivery retries and unknown outcomes, lifecycle/readiness, customer
role boundaries, Support read-only RBAC/UI, onboarding workflow, production
acceptance, backup health, operations health, Meta Coexistence status, and
customer dashboard/Inbox consistency.

## Production-only acceptance gates

The repository is now CI-clean; the remaining gates are environment facts that
cannot be proven by repository CI and must be checked on the deployed production
image:

1. Deploy one reviewed commit/image to API and WhatsApp worker and verify their
   image IDs match.
2. Run Alembic to head against the real production database after a backup.
3. Run `scripts/production_acceptance.py` for the target company/employee before
   Go Live; optionally include `--live-ai` for a real provider health check.
4. Apply/verify the nginx Core routes and confirm `/admin-ui`, `/customer-ui` and
   `/health/ready` resolve to the intended Core origin.
5. Verify real Meta Coexistence with an actual customer message, native Business
   App reply, observed `smb_message_echoes`, AI suppression during human control,
   portal human reply, explicit Return to AI and duplicate-webhook replay.
6. Confirm backup freshness, worker health, zero unexplained unresolved external
   operations and no unsafe `unknown` WhatsApp delivery resend.
7. After Go Live, rerun production acceptance with `--require-live` and monitor
   first-day queue/dead jobs, AI failures/latency, handoffs, actions and delivery
   states.

## Known limits / non-blocking follow-up

- No safe source means no fabricated services; unresolved legacy source conflicts
  remain visible for investigation rather than being overwritten.
- Cross-system exactly-once delivery cannot be mathematically guaranteed when a
  provider accepts a network request immediately before process failure. Durable
  delivery state and explicit reconciliation prevent blind retry, but `unknown`
  outcomes still require operator judgment.
- Multi-worker horizontal scaling needs lease/heartbeat validation before more
  than one active WhatsApp worker is intentionally deployed.
- Python 3.14 CI reports deprecation warnings for legacy naive UTC timestamps and
  upstream Starlette/httpx compatibility. They are not current test failures but
  should be removed in a focused compatibility cleanup rather than mixed into the
  production-integrity release.
- Passing CI is not evidence of the external nginx/CDN/Meta/provider state; those
  remain production acceptance checks above.
