# Xvond Project Checkpoint

Last refreshed: 2026-08-31 (Asia/Muscat)

## Canonical architecture

Xvond is a modular AI business platform built on Python, FastAPI, PostgreSQL and Redis.

Canonical customer runtime:

`Customer Channel -> Xvond Core -> AI Employee + Knowledge + Rules -> authorized Action -> Workflow Engine -> execution target -> Xvond result -> Customer`

Responsibilities are deliberately separated:

- Xvond Core is the product/control plane and AI decision layer.
- Channels such as Website, WhatsApp and Voice are communication surfaces.
- Xvond validates scope, required fields, customer confirmation, permissions and execution state.
- The Workflow Engine (self-hosted n8n) is the authoritative side-effect execution plane for operational actions.
- AI providers never call the Workflow Engine directly.
- The Workflow Engine does not access the Xvond application database directly.
- Workflow execution uses stable request identity, idempotency and fail-closed results.

The same AI Employee can operate across Website, WhatsApp and Voice without duplicating the employee core.

## Customer delivery lifecycle

Canonical delivery sequence:

1. Create Company.
2. Complete Company Profile and AI service subscription.
3. Create AI Employee in Draft.
4. Configure employee identity/behavior and attach Knowledge.
5. Configure Actions only when the employee needs operational side effects.
6. Configure at least one customer Channel.
7. Activate Company after setup readiness passes.
8. Go Live the AI Employee through Delivery Readiness.
9. Activate the customer Channel.
10. Verify `ready_for_customer` and run a customer-facing smoke test.

Setup readiness and live readiness are intentionally different. A configured channel is sufficient for company setup; a live channel is required before customer-ready status becomes true. Company deactivation is an emergency stop and disables all AI Employees. Re-enabling an employee requires its normal Go Live gate again.

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
- service billing and limits
- automation and analytics
- audit/runtime observability
- delivery and production readiness checks
- PostgreSQL/Redis production Compose
- Workflow Engine/n8n with a separate PostgreSQL database
- local and encrypted off-site backup/restore tooling

## AI runtime

Supported provider adapters:

- OpenAI
- Anthropic / Claude
- Google / Gemini
- xAI / Grok
- Groq
- Mock for development only

Routing supports company default/fallback selection, eligible-provider ranking, reliability signal, priority, latency/cost signals and first-request failover.

Business facts are grounded in current company Knowledge or successful action results. The runtime must never claim a booking, order, quotation, cancellation, payment or other action succeeded unless the corresponding action reports success.

PII protection is enabled by default in production before content is sent to external AI providers. Protected values are restored locally when required for tool execution and customer-visible output.

Known non-blocking future hardening: after a provider has initiated a provider-specific multi-round tool continuation, that continuation remains on the same provider. Cross-provider continuation-state translation is not implemented.

## Workflow Engine

The registered customer business-action tool is `WorkflowActionRequestTool`.

Xvond sends routing metadata and customer/action data to the Workflow Engine but strips credential-like fields from action configuration. External execution credentials belong to the workflow plane.

Supported destination model:

- `xvond_internal`: Workflow Engine calls the private Xvond internal execution endpoint.
- `integration`: Workflow Engine resolves a company/integration route from its execution registry and invokes the external system.
- unconfigured/unsupported routes fail closed.

The internal Workflow callback is protected with the shared Xvond/Workflow secret and supports availability, execute and cancel with idempotency receipts.

## Channel architecture

### Website

- origin/domain validation
- widget key authentication
- signed visitor tokens for conversation continuity
- source tagging into the unified conversation model
- human-handoff awareness

### WhatsApp

- Meta Cloud API webhook verification/signature validation
- phone-number routing across tenants
- idempotency and Redis worker path
- human-handoff/coexistence awareness
- outbound delivery handling
- Meta Embedded Signup provisioning
- WhatsApp Business App coexistence onboarding for eligible client numbers
- WABA/phone ownership verification and app subscription
- secrets encrypted at rest

A live Meta customer Embedded Signup/Coexistence onboarding remains an external acceptance boundary until Meta permissions are approved and a real client number is tested end to end.

### Voice

- generic authenticated Voice turn contract for non-Vapi providers
- Vapi dedicated authenticated callback path
- shared AgentRuntime, Knowledge and Actions
- voice-specific behavior/provisioning checkpoints

Live Vapi calling is intentionally not marked verified until a real Vapi key and phone number are supplied.

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

## Admin UI

The Company Workspace is the active operator control plane for:

- company identity
- capabilities
- AI Employees
- Knowledge
- Channels
- Operations metadata/reconciliation
- Connected Apps
- Usage
- Users
- Billing
- logs/readiness

Obsolete duplicate Admin API surfaces should not be reintroduced.

## Data and migrations

The migration chain must build from a fresh PostgreSQL database in CI.

Conversation source metadata is generic:

- `channel_id`
- `channel_type`
- `external_contact_id`

This supports the unified Inbox and future channel adapters without adding channel-specific conversation tables.

## CI / release gate

GitHub CI runs for pull requests and pushes to `main` or `staging` and checks:

1. dependency installation and `pip check`
2. Python compilation
3. fresh PostgreSQL `alembic upgrade head`
4. Admin and Customer JavaScript syntax
5. shell-script syntax
6. production Compose validation
7. full pytest suite
8. production Docker image build

A change is not code-ready until this gate passes.

## External validation boundary

The following cannot truthfully be called live-verified without real credentials/infrastructure:

- real Meta customer Embedded Signup/Coexistence onboarding
- real WhatsApp inbound/outbound/human-handoff acceptance on a client number
- real Vapi phone call
- live multi-provider AI acceptance with intended production providers
- real external CRM/POS/ERP/API action
- deployed HTTPS/reverse-proxy acceptance
- off-site backup restore against chosen production storage

No live provider, Meta, Workflow Engine or Vapi secret belongs in Git.

## Branch model

- `main` = canonical release branch
- `staging` = integration mirror and must be kept aligned with released `main`
- `feat/*` and `fix/*` = temporary change branches

After a validated release merge, `staging` should be fast-forwarded/aligned to the resulting `main` commit so the branches do not drift.
