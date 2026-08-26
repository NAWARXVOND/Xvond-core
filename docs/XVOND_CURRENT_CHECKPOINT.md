# Xvond Current Engineering Checkpoint

Date: 2026-08-26 (Asia/Muscat)
Branch: `staging`

## Verified validation state

Latest locally verified full test run:

- `132 passed`
- `0 failed`
- `0 warnings`
- Alembic upgraded through `c8f2a1d4e930`
- PostgreSQL and Redis running locally
- Groq live AI acceptance previously returned `XVOND_OK`

The previous Python 3.14 `datetime.utcnow()` deprecation warnings and SQLite resource warnings in `tests/test_provider_policy.py` were eliminated. Provider/model timestamps now use an explicit UTC clock while preserving the existing naive database representation, and temporary SQLite engines are disposed after tests.

## Current product architecture

Xvond is a modular AI business platform. The current core includes:

- Companies / tenant isolation
- Company Profile / Business Information
- Capabilities/modules
- AI Employees
- Knowledge
- Actions / business operations
- Channels
- Integrations
- Customer Portal
- Usage/cost tracking
- Service billing and limits
- Audit/runtime events
- Production readiness checks

Canonical company flow:

`Company -> Capabilities -> AI Employee -> Knowledge + Actions -> Channels -> Customers`

## Customer Portal

The modular Customer Portal has been manually verified locally for Gulf Catering Hub:

- AI Employees
- Test AI Employee
- Unified Inbox
- Inbox filter by AI Employee
- Inbox filter by Channel
- Inbox search
- Conversation thread view
- Quotation Requests
- Leads
- Support Requests / Human Handoffs
- Usage
- Billing

Conversation source metadata supports:

- `channel_id`
- `channel_type`
- `external_contact_id`

New test-chat conversations are tagged `portal_test` / Test Console. Older conversations created before source tracking may remain `Unclassified`.

## Gulf Catering Hub staging tenant

- Company ID: `4`
- AI Employee ID: `6`
- AI Employee: `Website Customer Service`
- Active website channel configured
- Real provider: Groq
- Model: `openai/gpt-oss-20b`
- Quotation capability active
- `catering_quote` action configured and runtime-ready
- Valid quotation request `#2` completed for 2026-09-15
- Old test request `#1` contains the pre-business-clock 2024 date and should be cleaned up before production

## Business clock

The runtime injects the company's authoritative timezone/date context. Incomplete future-facing dates resolve to the next matching current/future date unless the conversation explicitly specifies another year or a past date.

## AI provider architecture

Provider adapters currently exist for:

- OpenAI
- Groq
- Anthropic / Claude
- Google / Gemini
- xAI / Grok
- Mock (development only)

Environment keys supported:

- `OPENAI_API_KEY`
- `ANTHROPIC_API_KEY`
- `GOOGLE_API_KEY`
- `XAI_API_KEY`
- `GROQ_API_KEY`

The runtime provider policy supports:

- company default provider/model
- optional company fallback provider/model
- automatic ranking across enabled models
- recent reliability/failure signal
- provider priority
- latency signal
- configured token cost
- first-request automatic failover across eligible providers

Known hardening item: after a provider starts a multi-round tool continuation, continuation stays on that provider. Cross-provider recovery during an in-progress tool continuation is not yet implemented.

## Admin / customer privacy boundary

Product decision: Xvond Admin is the operator/configuration control plane. Customer conversation content and customer-created business request payloads belong to the tenant Customer Portal or the tenant's connected external system.

Implemented boundary:

- Admin human-chat router removed from the active application surface
- Admin request-list / request-status management routes removed from the registered Agent Actions router
- Admin conversation content endpoints removed from Admin Operations
- Admin External Integration reconciliation returns operator-safe metadata only, without customer request payloads
- Admin UI no longer loads customer requests, conversations or handoff sessions
- Admin workspace no longer exposes customer-content Operations or Conversations tabs
- AI Employee Actions configuration no longer displays Real Customer Operations
- Usage/cost, configuration, readiness, integrations, billing and audit/runtime health remain available to Xvond Admin

Customer Portal tenant-scoped routes remain the place for the client to view and manage its own customer operations and conversations.

## AI Employee configuration

Admin-created AI Employees receive `AgentConfig` automatically with Customer Portal controls. Older employees without an AgentConfig are backfilled on profile access. Explicit customer-control values are preserved.

Default controls:

- can enable/disable: true
- can view conversations: true
- can view usage: true
- can edit prompt: false
- can change provider: false
- can change model: false

## Production Readiness UI

Backend canonical readiness field is `company_profile_ready`.

A legacy Admin renderer expected `profile_ready`, causing a false `Needs setup` display even when backend readiness was ACTIVE. Compatibility mapping now keeps the display aligned with the canonical readiness result.

## Billing

Gulf Catering Hub has an AI Agents Starter service subscription. Verified Customer Portal billing showed:

- Agents: `1 / 1`
- Tokens: `0 / Unlimited` at the time of verification
- Online payment method: Not configured

Future subscription card payment belongs inside Billing; it is not a separate customer-facing Xvond service.

## Deployment state

Deployment is intentionally paused. Do not set the local laptop to production merely to force readiness green.

When deployment resumes, deploy the complete Xvond runtime with PostgreSQL/Redis, HTTPS/reverse proxy, production secrets, migrations, live acceptance and off-server backups. Production data-residency preference remains Oman.

## Next engineering priorities

1. Visually verify the latest Admin privacy/readiness changes after refresh: no customer Operations/Conversations surfaces, no customer request list inside Actions, and Company Profile readiness displays Ready.
2. Add and live-test at least one second real AI provider, then validate normal response, tool calling, first-request failover and usage/cost logging across providers.
3. Run one real External Integration end-to-end: Customer -> AI -> Action -> external API -> verified success -> AI confirmation.
4. Clean old staging-only request/conversation data, especially `catering_quote #1`, before production acceptance.
5. Run production acceptance only after deployment prerequisites are ready; merge to production only after live acceptance succeeds.

## Stable test checkpoint

Clean local test checkpoint: **132 passed, 0 warnings**.
Do not re-open previously closed Inbox/filter/privacy/readiness issues unless new code changes or a regression test proves a failure.
