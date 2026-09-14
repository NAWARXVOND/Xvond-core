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

## Production routing and release consistency

`/admin-ui` already existed in FastAPI. Core code cannot override a reverse proxy
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
PRs. Meta SDK references: [application subscriptions](https://github.com/facebook/facebook-python-business-sdk/blob/main/facebook_business/adobjects/application.py),
[WABA subscriptions](https://github.com/facebook/facebook-python-business-sdk/blob/main/facebook_business/adobjects/whatsappbusinessaccount.py).

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

## Limits that require explicit verification

- Production database, nginx/CDN and Meta state have not been changed or inferred.
- No safe source means no fabricated services; unresolved legacy source conflicts
  remain for investigation instead of overwriting customer history.
- Meta accepting a send followed by a process crash before database commit is an
  external-delivery ambiguity. This patch does not claim exactly-once delivery
  across the database and Meta API. A durable outbound reconciliation design is
  still needed for that guarantee.
- Queue recovery currently assumes a single active worker. Multi-worker leases
  and worker heartbeat readiness require further validation before scaling.
- The audit is broad but is not a claim that every unknown defect is eliminated.
  Final test/CI results and outstanding review items must accompany the PR.

## Review checkpoint (draft, not deployment-ready)

Local verification: 452 Python tests, two Meta SDK Node tests, all admin/customer
JavaScript syntax checks, Python compilation, pip dependency consistency,
single Alembic head, and git diff whitespace checks passed. The local Docker
daemon is unavailable, so PostgreSQL migration execution, Compose validation,
and image build must be verified in CI. No dedicated lint or typecheck task is
configured in this repository.

Outstanding before considering this audit complete:

1. Run the new migration on both a fresh PostgreSQL database and representative
   legacy fixtures; test its safe downgrade guard and conflicting-source cases.
2. Add real Redis/PostgreSQL concurrency tests for ingress markers, portal
   claim/return races, retry atomicity and a takeover during AI generation.
3. Review pending echo versus Return-to-AI ordering, duplicate old echo delivery,
   Redis outage behavior after DB commit, and requeue-dead crash recovery.
4. Validate successful Coexistence subscription payloads and echo activation;
   minimize remote probe latency and show all readiness states in both portals.
5. Reconcile customer dashboard counts/handoff endpoints with Inbox visibility
   and per-employee access controls; the Inbox fix alone does not fix dashboards.
6. Review queue worker leases/heartbeat health, webhook status/non-text events,
   malformed nested message content, log exception redaction across the system,
   and external-send acknowledgement/reconciliation gaps.
7. Check website/voice concurrency, runtime failure commits, new source arguments
   on every caller, and physical channel reconfiguration with existing history.
8. Add browser regression coverage for stale request guards and drafts, including
   logout and switching conversations during a pending human send.
9. Complete the remaining security, RBAC, privacy, integrations, observability,
   deployment-readiness and error-path review. Preserve Company -> Employee ->
   Channel -> Conversation; human handoff changes control only.
10. Check exact-head CI, update the PR/report with remaining findings, and do not
    merge this draft merely because the existing checks are green.
