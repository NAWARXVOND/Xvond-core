# Xvond Current Engineering Checkpoint

Date: 2026-08-26 (Asia/Muscat)
Branch: `staging`

## Validation state

Last locally verified state before the latest admin privacy hardening:

- `127 passed`
- `0 failed`
- `22 warnings`
- Alembic upgraded through `c8f2a1d4e930`
- PostgreSQL and Redis running locally
- Groq live AI acceptance previously returned `XVOND_OK`

The commits after that 127-test run must be validated locally with `pytest -q` before this checkpoint is considered fully green.

## Current product architecture

Xvond is a modular AI business platform. The current core includes:

- Companies / tenant isolation
- Company Profile / Business Information
- Capabilities/modules
- AI Employees
- Knowledge
- Actions / business operations
- Channels (Website, WhatsApp; voice runtime support exists; Instagram adapter is not implemented yet)
- Integrations
- Customer Portal
- Usage/cost tracking
- Service billing and limits
- Audit/runtime events
- Production readiness checks

Canonical company flow:

`Company -> Capabilities -> AI Employee -> Knowledge + Actions -> Channels -> Customers`

## Customer Portal

The modular Customer Portal has been verified locally for Gulf Catering Hub:

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

Conversation source metadata now supports:

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

The runtime now injects the company's authoritative timezone/date context. Incomplete future-facing dates must resolve to the next matching future/current date unless the conversation explicitly specifies another year or a past date.

## AI provider architecture

Provider adapters currently exist for:

- OpenAI
- Groq
- Anthropic / Claude
- Google / Gemini
- xAI / Grok
- Mock (development only)

The runtime provider policy can automatically rank enabled models using recent reliability, provider priority, latency and configured token cost. It creates a failover chain and tries the next provider when the initial provider fails.

Known routing hardening item: after a provider has started a multi-round tool continuation, the continuation currently stays on that provider. Cross-provider recovery during an in-progress tool continuation is not yet implemented.

## Admin / customer privacy boundary

Product decision: Xvond Admin is the operator/configuration control plane. Customer conversation content and customer-created business request payloads belong to the tenant Customer Portal or the tenant's connected external system.

Latest hardening:

- Removed Admin human-chat router from the active application surface
- Removed Admin request-list / request-status management routes from the registered Agent Actions router
- Removed Admin conversation content endpoints from Admin Operations
- Admin External Integration reconciliation returns operator-safe metadata only, without customer request payloads
- Admin UI no longer loads customer requests, conversations or handoff sessions
- Admin workspace hides Operations and Conversations customer-content surfaces
- AI Employee Actions configuration no longer displays Real Customer Operations
- Usage/cost, configuration, readiness, integrations, billing and audit/runtime health remain available to Xvond Admin

Customer Portal tenant-scoped routes remain the place for the client to view and manage its own customer operations and conversations.

## AI Employee configuration

Admin-created AI Employees now receive `AgentConfig` automatically with Customer Portal controls. Older employees without an AgentConfig are backfilled on profile access. Explicit customer-control values are preserved.

Default controls include:

- can enable/disable: true
- can view conversations: true
- can view usage: true
- can edit prompt: false
- can change provider: false
- can change model: false

## Production Readiness UI

Backend canonical readiness field is `company_profile_ready`.

A legacy Admin renderer expected `profile_ready`, causing a false `Needs setup` display even when backend readiness was ACTIVE. The Admin privacy/compatibility layer now maps the canonical field so Company Profile readiness displays correctly.

## Billing

Gulf Catering Hub has an AI Agents Starter service subscription. Verified Customer Portal billing showed:

- Agents: `1 / 1`
- Tokens: `0 / Unlimited` for the current billing period at the time of verification
- Online payment method: Not configured

Future subscription card payment belongs inside Billing; it is not a separate customer-facing Xvond service.

## Deployment state

Deployment is intentionally paused. Do not set the local laptop to production just to force readiness green.

When deployment resumes, deploy the full Xvond Core/runtime with PostgreSQL/Redis, HTTPS/reverse proxy, production secrets, migrations, live acceptance and off-server backups. Production data-residency preference remains Oman.

## Next engineering priorities

1. Pull latest `staging` and run the complete local test suite. Also verify Admin JS syntax through the existing CI-compatible Node check if needed.
2. Visually verify the Admin privacy boundary: no Operations/Conversations customer-content tabs, no customer request list inside Actions, and Company Profile readiness displays Ready.
3. Add and live-test at least one second real AI provider, then validate normal response, tool calling, first-request failover and usage/cost logging across providers.
4. Run one real External Integration end-to-end: Customer -> AI -> Action -> external API -> verified success -> AI confirmation.
5. Review and eliminate the remaining pytest deprecation warnings after capturing their exact sources from the next local test run.
6. Clean old staging-only request/conversation data before production acceptance.
7. Re-run `scripts.production_acceptance --live-ai` after deployment; only then merge the production PR.
