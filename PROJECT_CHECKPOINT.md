# Xvond Project Checkpoint

Last refreshed: 2026-09-15 (Asia/Muscat)

## Canonical architecture

Xvond is a modular managed AI operations platform built on Python, FastAPI, PostgreSQL and Redis.

Canonical customer runtime:

`Customer Channel -> Xvond Core -> AI Employee + Knowledge + Rules -> authorized Action -> Workflow Engine -> execution target -> Xvond result -> Customer`

Responsibilities are deliberately separated:

- Xvond Core is the product/control plane and AI decision layer.
- Channels such as Website, WhatsApp and Voice are communication surfaces.
- One AI Employee may serve multiple channels; channels do not own independent persona or business truth.
- Xvond validates scope, required fields, customer confirmation, permissions and execution state.
- The Workflow Engine (self-hosted n8n) is the authoritative side-effect execution plane for operational actions.
- AI providers never call the Workflow Engine directly.
- The Workflow Engine does not access the Xvond application database directly.
- Workflow execution uses stable request identity, idempotency and fail-closed results.

## Readiness model

Xvond distinguishes three different facts:

1. **Code ready**: repository CI passes.
2. **Production ready**: the deployed API, worker, database, Redis, Workflow Engine where required, migrations, backups and routing pass production acceptance.
3. **Service ready**: the exact sold customer path has passed real end-to-end acceptance with its external providers and channels.

Passing CI never proves Meta, Vapi, a customer CRM/POS/calendar, DNS/reverse proxy or off-site storage is live.

## Customer delivery lifecycle

Canonical delivery sequence:

1. Create Company.
2. Complete Company Profile and AI service subscription.
3. Create AI Employee in Draft.
4. Configure employee identity/behavior and attach Knowledge.
5. Configure Actions only when the employee needs operational side effects.
6. Configure at least one customer Channel.
7. Move through onboarding/testing and complete non-customer-facing validation.
8. Activate the Company once setup readiness passes.
9. Go Live the AI Employee through Delivery Readiness.
10. Activate the intended customer Channel.
11. Run the controlled real-channel acceptance window before announcing the service to the customer.
12. Verify `ready_for_customer`, complete external acceptance and begin first-day monitoring.

Setup readiness and live readiness are intentionally different. A configured channel is sufficient for company setup; a live channel is required before customer-ready status becomes true. Company deactivation is an emergency stop and disables all AI Employees. Re-enabling an employee requires its normal Go Live gate again.

Because Meta/Vapi and similar providers can only prove real delivery while the production route is enabled, their final external smoke test is a controlled post-activation acceptance step. The service is not commercially handed over merely because the lifecycle flag is `live`.

## Core platform

Current platform includes:

- tenant-scoped Companies and Users
- JWT/session revocation and role-based access
- Company Profile / Business Information
- modular capabilities
- AI Employees and provider routing
- Knowledge
- generic Actions / Action Requests
- Website, WhatsApp and Voice channels
- Connected Apps / Integrations metadata
- Customer Portal / unified Inbox
- Usage and provider-cost tracking
- service billing entitlements and limits
- automation and analytics foundations
- audit/runtime observability
- delivery and production readiness checks
- PostgreSQL/Redis production Compose
- Workflow Engine/n8n with a separate PostgreSQL database
- local and encrypted off-site backup/restore tooling
- repeatable production release tooling

## AI runtime

Implemented provider adapters:

- OpenAI
- Anthropic / Claude
- Google / Gemini
- xAI / Grok
- Mock for development only

Do not advertise an AI provider as supported until a runtime adapter exists, is configured and has passed the intended production acceptance path.

Routing supports company default/fallback selection, eligible-provider ranking, reliability signal, priority, latency/cost signals and first-request failover.

Business facts are grounded in current company Knowledge or successful action results. The runtime must never claim a booking, order, quotation, cancellation, payment or other action succeeded unless the corresponding action reports success.

PII protection is enabled by default in production before content is sent to external AI providers. Protected values are restored locally when required for tool execution and customer-visible output.

Known non-blocking future hardening: after a provider has initiated a provider-specific multi-round tool continuation, that continuation remains on the same provider. Cross-provider continuation-state translation is not implemented.

## Workflow Engine and business actions

The registered customer business-action tool is `WorkflowActionRequestTool`.

Xvond sends routing metadata and customer/action data to the Workflow Engine but strips credential-like fields from action configuration. External execution credentials belong to the workflow plane.

Supported destination model:

- `xvond_internal`: Workflow Engine calls the private Xvond internal execution endpoint.
- `integration`: Workflow Engine resolves a company/integration route from its execution registry and invokes the external system.
- unconfigured/unsupported routes fail closed.

The internal Workflow callback is protected with the shared Xvond/Workflow secret and supports availability, execute and cancel with idempotency receipts.

Configured integration types such as CRM, POS, ERP, calendar, webhook and custom API are routing/configuration contracts. A named integration is not service-ready until its actual provider binding, credentials and end-to-end action path are tested.

Production release requires the Workflow Engine container to pass HTTP health when enabled. An AI Employee with enabled business actions also requires the canonical Workflow Engine `health_check` to succeed before Go Live and during production acceptance.

## Channel architecture

### Website

- origin/domain validation
- widget key authentication
- signed visitor tokens for conversation continuity
- source tagging into the unified conversation model
- human-handoff awareness

A real public-domain smoke test remains required before a sold Website channel is declared service-ready.

### WhatsApp

- Meta Cloud API webhook verification/signature validation
- phone-number routing across tenants
- idempotency and Redis worker path
- human-handoff/coexistence awareness
- outbound delivery handling and provider status tracking
- Meta Embedded Signup provisioning
- WhatsApp Business App Coexistence onboarding for eligible client numbers
- WABA/phone ownership verification and app subscription
- secrets encrypted at rest

WhatsApp exposes two separate truths:

- `connected`: the Meta transport is usable. Embedded Signup data is valid, the phone/token probe succeeds, the Xvond app is subscribed to the WABA and required webhook fields (`messages`, `smb_message_echoes`) are subscribed.
- `coexistence_ready`: a real WhatsApp Business App echo has been observed, proving the automatic human-takeover path in practice.

A fresh correctly subscribed Coexistence connection may serve AI traffic before the first human echo. The first real Business App reply supplies the echo evidence and activates human control. Missing app/WABA/webhook subscription setup still fails closed.

A live Meta customer acceptance remains mandatory before calling WhatsApp service-ready: customer inbound, AI outbound, native Business App human reply, AI suppression during human control, portal handoff/reply, explicit Return to AI and duplicate webhook replay.

### Voice

- generic authenticated Voice turn contract for non-Vapi providers
- Vapi dedicated authenticated callback path
- shared AgentRuntime, Knowledge and Actions
- voice-specific behavior/provisioning checkpoints

Live Voice is not service-ready until a real provider key, phone number and call path are tested end to end.

## Security and privacy

- current password policy and secure hashing
- issuer/audience/expiry/token-version session revocation
- bundled Admin and Customer Portal use HttpOnly SameSite session cookies
- bearer tokens remain supported for non-browser API clients
- production cookies use Secure
- public CORS is credential-free
- channel/integration/config secrets use encrypted storage
- external HTTP security includes SSRF controls
- Xvond Admin is the infrastructure/configuration control plane and does not expose tenant customer-content payloads as an operator inbox
- Customer Portal remains tenant scoped

Enterprise-specific governance claims such as formal data-residency commitments, DPA coverage, subprocessor policy or customer-specific retention guarantees must not be sold unless separately implemented and contractually established.

## Admin UI

The Company Workspace is the active operator control plane for:

- company identity and lifecycle
- capabilities
- AI Employees
- Knowledge
- Channels
- Operations metadata/reconciliation
- Connected Apps
- Usage
- Users
- Billing entitlements
- logs/readiness

Obsolete duplicate Admin API surfaces should not be reintroduced.

## Billing truth

`ServicePlan` / `ServiceSubscription` are the canonical commercial entitlement and limit system. They do not constitute a payment gateway, invoicing ledger or accounting system.

Until an automated payment stack is intentionally implemented, payment collection/invoicing may remain an Operations process while Core remains authoritative for service entitlement, periods, limits and usage.

## Data and migrations

The migration chain must build from a fresh PostgreSQL database in CI.

Conversation source metadata is generic:

- `channel_id`
- `channel_type`
- `external_contact_id`

This supports the unified Inbox and future channel adapters without adding channel-specific conversation tables.

## CI and release gate

GitHub CI runs for pull requests and pushes to `main` or `staging` and checks:

1. dependency installation and `pip check`
2. Python compilation
3. fresh PostgreSQL `alembic upgrade head`
4. Admin and Customer JavaScript syntax
5. shell-script syntax
6. Meta Embedded Signup tests
7. production Compose validation
8. full pytest suite
9. production Docker image build

A change is not code-ready until this gate passes.

Production deployment should use `scripts/deploy_production.sh`. The release flow validates a clean Git state and Compose configuration, brings database/Redis up, takes a fresh database backup before application replacement, stops the previous WhatsApp worker, builds one reviewed application image, recreates API and worker from that same image, waits for service health, starts and verifies Workflow Engine health when enabled, confirms the API/worker image IDs match and can run customer-specific production acceptance.

## External validation boundary

The following cannot truthfully be called live-verified by repository CI alone:

- deployed server environment/secrets and the exact released image
- real Meta customer Embedded Signup/Coexistence onboarding
- real WhatsApp inbound/outbound/human-handoff acceptance on a client number
- real Voice/Vapi phone call
- live AI acceptance with the intended production providers
- real external CRM/POS/ERP/calendar/API action
- deployed HTTPS/reverse-proxy/CDN acceptance
- off-site backup restore against the chosen production storage

No live provider, Meta, Workflow Engine, Vapi or customer integration secret belongs in Git.

## Branch model

- `main` = canonical release branch
- `staging` = integration mirror and must be kept aligned with a validated released `main`
- `feat/*` and `fix/*` = temporary change branches

After a validated release merge and exact-head CI success, `staging` should be fast-forwarded/aligned to the resulting `main` commit so the branches do not drift.
