# System integrity audit - 2026-09-15

Repository: `Nawar-Alsafadi-0/Xvond-core`.

This audit separates repository correctness from deployed-service acceptance. A green CI run proves the reviewed code and build gates; it does not prove external Meta/Vapi/provider/customer infrastructure.

## Confirmed defects and repairs

| Area | Finding | Repair |
| --- | --- | --- |
| Conversation identity | WhatsApp sessions previously ignored phone identity and source binding could omit the exact channel | Session identity includes company, employee, phone and contact; conversations bind the exact channel/contact and reject conflicting source identity |
| Existing conversation data | Legacy source migration could not safely infer a channel in every case | Backfill only exact company/employee/phone matches; preserve ambiguous/conflicting rows for investigation |
| Profile/services truth | Partial profile updates could replace omitted values with empty defaults | Update only submitted fields and preserve independent structured business facts |
| Missing services | Knowledge/runtime could be tempted to infer services from business type or package | Ground answers only in canonical saved business facts/Knowledge or confirmed action results |
| Embeddings | Live maintenance could perform expensive company-wide work in a customer turn | Keep live maintenance bounded; lexical fallback remains available and diagnostics avoid sensitive payloads |
| WhatsApp Coexistence | Transport connectivity and human-takeover proof were conflated, creating a first-reply deadlock | `connected` now proves usable Meta transport/subscriptions; `coexistence_ready` separately records an observed Business App echo. A fresh correctly subscribed channel can answer by AI before the first native human reply |
| Webhook/worker durability | A crash at the wrong point could strand a claimed inbound event | Claim/processing semantics are resumable; duplicate handling, retry/dead-letter transitions and outbound delivery state are durable/idempotent |
| Handoff | Human intervention could race a generated AI response | Signed Business App echo marks human control; contact/session ownership is serialized and the runtime rechecks control before AI delivery |
| Portal reply | Employee-wide routing could select the wrong channel and blank replies were possible | Resolve the exact conversation channel and validate outbound human content |
| Inbox | Test/unclassified traffic could pollute customer live views | Live channel types are the default customer view while explicit test/unknown filters remain available |
| Runtime | Test chat/source binding could fail after provider work began | Validate and bind conversation source before provider execution and classify admin test conversations |
| Channel prompts | Channel behavior could temporarily mutate the canonical employee record | Use request-scoped channel prompt overrides |
| Frontend | Slow requests/polling could repaint another conversation or erase a draft | Request sequencing and selected-conversation guards preserve active UI state |
| Reverse proxy/cache | Core routes existed without a deployable shared-domain routing contract | Version-controlled nginx Core locations plus no-store behavior for authenticated/portal surfaces |
| Secret/error handling | Raw Meta/network exception details could escape into operator surfaces | Return safe structural diagnostics; keep credentials and raw provider error bodies out of APIs/logs |
| Company lifecycle | Commercial lifecycle and runtime emergency state could be conflated | Canonical lifecycle plus separate runtime/emergency-stop behavior |
| Employee Go Live | Configuration alone could enable an operational employee while the Workflow Engine/master workflow was unavailable | Delivery Readiness now performs the canonical Workflow Engine `health_check` immediately before enabling any employee with business actions |
| Workflow deployment | n8n could be considered ready merely because its process was running | Production Compose has a real n8n `/healthz` healthcheck; release waits for that health state |
| Provider catalog | Groq had been intentionally removed from `AIEngine`, but a stale production seed still re-enabled Groq and its models | Groq is retired from the seed catalog; existing historical Groq provider/model rows are disabled, not deleted |
| Support access | Production support needed a least-privilege operational view | Read-only Support role/operations plane exposes technical metadata without becoming a tenant-content inbox |
| Production release | Manual command sequences could leave API/worker on different images or skip release safety | `scripts/deploy_production.sh` enforces clean Git/Compose, backup-before-replace, one reviewed app image, health waits, workflow startup when required, API/worker image equality and optional customer acceptance |
| Production acceptance | A pre-live checker could conflate setup and live state or ignore real business-action execution infrastructure | Separate pre-live/post-live modes, worker/backups/incidents/provider checks and real Workflow Engine health for action-enabled employees |

## Runtime truth model

Xvond uses three distinct readiness levels:

1. **Code ready**: exact reviewed commit passes repository CI.
2. **Production ready**: the deployed image, database migrations, Redis/worker, Workflow Engine where required, backups and reverse-proxy routes pass production checks.
3. **Service ready**: the exact sold customer path passes real external acceptance with its actual channel/provider/integration.

No UI flag, saved token or green CI run substitutes for the next level.

## Production release consistency

The canonical release entrypoint is:

```sh
./scripts/deploy_production.sh
```

The release flow validates the Git working tree and production Compose, starts database/Redis, takes a fresh database backup before replacing the application, stops the previous WhatsApp worker, builds one reviewed application image, recreates API and worker from that image, waits for API health, starts Workflow Engine services when enabled, waits for workflow database and n8n HTTP health, verifies API/worker image identity and can execute customer-specific production acceptance.

The API entrypoint applies Alembic migrations and safe startup tasks. The WhatsApp worker intentionally starts from the already-prepared application image and does not run an independent migration entrypoint.

After routing changes, verify the real HTTPS paths:

```text
GET https://xvond.com/admin-ui
GET https://xvond.com/static/admin/index.html
GET https://xvond.com/customer-ui
GET https://xvond.com/health/ready
```

Core cannot prove that an external reverse proxy/CDN sends these paths to the intended application. That remains deployed-environment acceptance.

## WhatsApp Meta truth and acceptance

WABA app subscription and application webhook-field subscription are distinct facts. Xvond verifies phone/token validity, the intended app in the WABA subscription list, and required `messages` plus `smb_message_echoes` webhook fields before reporting Meta transport as connected.

A real `smb_message_echoes` event is deliberately a separate `coexistence_ready` proof. Requiring that echo before the AI could send its first reply created an impossible loop; the fixed runtime allows a correctly subscribed channel to serve AI traffic and treats the first native WhatsApp Business App reply as the evidence that automatic human takeover works.

Final WhatsApp acceptance on the deployed image must prove:

- real customer inbound reaches the intended company/employee;
- exactly one AI reply is delivered to the same conversation;
- source/conversation identity remains stable;
- a native Business App reply produces `smb_message_echoes` and is mirrored to the Inbox;
- human takeover suppresses AI output;
- Customer Portal claim/reply stays on the exact channel/contact;
- explicit Return to AI resumes automation;
- replaying the same webhook does not duplicate messages, actions or outbound delivery.

## Business-action truth

The live customer business-action path is:

`AI Employee -> WorkflowActionRequestTool -> durable ActionRequest -> Workflow Engine -> intended execution target -> confirmed result -> AI/customer`

Booking/order/CRM/POS/ERP/calendar/webhook/custom-API names in catalogs are not themselves proof of a live integration. Provider-specific credentials/routes belong to the Workflow Engine and the exact customer action must be accepted against its intended target.

An operational employee cannot Go Live merely because `N8N_ENABLED`, URL and shared secret are populated. Delivery Readiness calls the canonical `health_check` before enabling the employee; production acceptance performs the corresponding workflow gate as well.

## Provider catalog truth

The provider catalog must match adapters actually registered by `AIEngine`. Implemented production provider families are OpenAI, Anthropic, Google and xAI; Mock remains development-only.

Groq was intentionally removed from the runtime. Production seeding no longer advertises it, and any historical Groq provider/model rows are retained only for history while being forced disabled. Existing customer routing that still references a retired provider should fail readiness and be explicitly reconfigured rather than silently switched to another provider.

## Customer activation and external acceptance

The `testing` lifecycle keeps production runtime off. This is intentional. Real Meta/Vapi inbound/outbound cannot be proven while the route is disabled, so final external acceptance uses a controlled production activation window:

1. complete all pre-live validation and `scripts/production_acceptance.py`;
2. activate only the intended Company/AI Employee/channel;
3. immediately run the designated real external-channel acceptance;
4. if it fails, deactivate/stop the affected runtime and return to a non-live lifecycle before customer handover;
5. only after external acceptance succeeds, record commercial customer handover;
6. run production acceptance with `--require-live` and monitor first-day operations.

This preserves fail-closed lifecycle semantics without pretending an external channel was tested while disabled.

## Repository CI gate

Every final release commit must pass the exact-head GitHub CI gate, including:

- dependency consistency (`pip check`);
- Python compilation;
- fresh PostgreSQL 17 migration to Alembic head;
- Admin/Customer JavaScript syntax;
- shell-script syntax;
- Meta Embedded Signup tests;
- production Compose validation;
- complete Python test suite;
- production Docker image build.

Do not hard-code an old test count as a lasting readiness claim; the exact-head CI result is the authority for the current release.

## Production-only acceptance gates

Repository CI cannot prove these environment facts:

1. the server is running the reviewed final commit/image;
2. API and WhatsApp worker image IDs match on the deployed host;
3. real production secrets/configuration are present and correct;
4. production database is at Alembic head after a fresh backup;
5. nginx/CDN routes `/admin-ui`, `/customer-ui`, APIs and `/health/ready` to Core correctly;
6. real Meta Coexistence passes the full WhatsApp acceptance above;
7. real Voice/Vapi calling passes for any sold Voice service;
8. intended live AI provider route succeeds with production credentials;
9. every sold external business action succeeds or fails safely against its actual CRM/POS/calendar/API target;
10. local/off-site backups are fresh and a chosen off-site backup can actually be restored;
11. there are no unexplained unresolved external actions or unsafe `unknown` delivery retries;
12. post-live first-day monitoring is clean enough for customer handover/continued service.

No live Meta/provider/customer integration secret belongs in Git.

## Known limits / focused follow-up

- Cross-system exactly-once delivery cannot be mathematically guaranteed when a third party accepts a request immediately before a network/process failure. Durable state and reconciliation prevent blind retry; `unknown` outcomes still require operator judgment.
- Horizontal WhatsApp worker scaling must preserve per-contact ordering/idempotency and should not be enabled by simply adding workers.
- Python 3.14/upstream compatibility warnings should be removed in a focused maintenance change, not mixed into customer-path acceptance.
- Formal enterprise governance claims such as customer-specific data residency, DPA/subprocessor commitments and retention guarantees require their own implemented/contractual program.
- Passing CI is evidence of repository integrity, not evidence of the external production environment.
