# Xvond Project Checkpoint

Last refreshed: 2026-08-27 (Asia/Muscat)

## Canonical architecture

Xvond is a modular AI business platform built on Python, FastAPI, PostgreSQL and Redis.

Canonical product flow:

`Company -> AI Employee -> Shared Knowledge + Shared Tools -> Channel-specific behavior -> Customers`

The same AI Employee can operate across Website, WhatsApp and Voice without duplicating the employee core. Channel behavior is layered on top of shared company knowledge and tools.

## Core platform

Current platform includes:

- tenant-scoped Companies and Users
- JWT/session revocation and role-based access
- Company Profile / Business Information
- modular capabilities
- AI Employees and provider routing
- Knowledge
- Tools / Action Requests
- Website, WhatsApp and Voice channels
- Integrations
- Customer Portal / unified Inbox
- Usage and provider-cost tracking
- service billing and limits
- automation
- analytics
- audit/runtime observability
- production readiness checks
- PostgreSQL/Redis production Compose
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

Business facts are grounded in current company knowledge or successful tool results. The runtime must never claim a booking, order, quotation, cancellation, payment or other action succeeded unless the corresponding tool reports success.

PII protection is enabled by default in production before content is sent to external AI providers. Protected values are restored locally when required for tool execution and customer-visible output.

Known non-blocking future hardening: after a provider has already initiated a provider-specific multi-round tool continuation, that continuation remains on the same provider. Cross-provider continuation-state translation is not implemented.

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
- coexistence/human handoff
- outbound delivery handling
- channel-specific language, dialect, tone, response style, response length, emoji style and instructions
- Meta Embedded Signup path on the current architecture
- Meta setup readiness requires app ID, app secret, config ID and verify token
- WABA/phone ownership verification and app subscription are part of provisioning
- secrets are encrypted at rest

### Voice

- generic authenticated Voice turn contract for non-Vapi providers
- Vapi uses its dedicated authenticated OpenAI-compatible callback rather than the generic Voice token route
- shared AgentRuntime, Knowledge and Tools
- voice-specific language, dialect, tone, greeting, voice settings, interruption behavior and instructions
- conversation/call correlation through existing channel source metadata
- provisioning checkpoints, recovery and readiness validation

Live Vapi calling is intentionally not marked verified until a real Vapi key and phone number are supplied.

## Security and privacy

- passwords use the current password policy and secure hashing
- access tokens support issuer, audience, expiry, token-version revocation and server-side logout
- bundled Admin and Customer Portal browser sessions use an HttpOnly SameSite session cookie instead of persisting bearer credentials in localStorage
- bearer tokens remain supported for non-browser API clients
- production cookies use Secure
- public CORS remains credential-free; cross-origin browser credentials are not enabled
- channel/integration/analytics secrets use encrypted configuration storage
- external HTTP tool execution includes SSRF protections
- Admin is the infrastructure/configuration control plane and does not expose tenant customer-content payloads as an operator inbox
- Customer Portal is tenant scoped

## Admin UI

There is one active Company Workspace implementation. Obsolete Admin workspace files and the retired legacy billing/business Admin APIs were removed so they cannot silently reappear as an alternate product surface.

Current Company Workspace covers company information, capabilities, AI Employees, Knowledge, Channels, Integrations, Usage, Users, Billing and technical logs/readiness according to the active UI modules.

## Data and migrations

The migration chain builds successfully from a fresh PostgreSQL database through the current head in CI. Conversation source metadata is generic:

- `channel_id`
- `channel_type`
- `external_contact_id`

This supports the unified Inbox and future channel adapters without adding channel-specific conversation tables.

## CI / release gate

GitHub CI is configured for pull requests targeting `main` or `staging`, and pushes to `main` or `staging`.

Every release candidate must pass:

1. dependency installation
2. fresh PostgreSQL `alembic upgrade head`
3. Admin and Customer JavaScript syntax checks
4. shell-script syntax checks
5. production Compose validation
6. full pytest suite
7. production Docker image build

A release is not considered code-ready if any one of these steps fails.

## External validation boundary

The codebase can be validated without production secrets, but the following cannot truthfully be called live-verified until credentials/infrastructure are supplied:

- real Vapi phone call
- real Meta customer Embedded Signup/onboarding
- live multi-provider AI acceptance using the intended production providers
- real external CRM/POS/ERP/API action
- deployed HTTPS/reverse-proxy acceptance
- off-site backup restore against the chosen production storage

No live provider, Meta or Vapi credential belongs in Git or this checkpoint.

## Branch model

- `main` = canonical production/release branch
- `staging` = canonical integration branch
- `feat/*` / `fix/*` = temporary branches created from current `staging`

`main` and `staging` must not be allowed to remain hundreds of commits apart. A release hardening cycle ends by merging the validated integration candidate and aligning the release branch deliberately.
