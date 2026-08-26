# Xvond Project Checkpoint

Date: 2026-08-26 (Asia/Muscat)
Branch: `staging`

## Current verified platform state

- Xvond Core: Python / FastAPI / PostgreSQL / Redis modular AI business platform.
- Local database migration `c8f2a1d4e930` applied successfully.
- Latest verified full local test run: **132 passed, 0 failed, 0 warnings**.
- Customer Portal is tenant-scoped and service/capability driven.
- Billing works for the current staging customer.
- Groq live AI acceptance previously returned `XVOND_OK`.

## Gulf Catering Hub staging customer

- Company ID: `4`
- AI Employee: `Website Customer Service`
- Agent ID: `6`
- Real provider: `groq`
- Model: `openai/gpt-oss-20b`
- Website channel active/configured for staging.
- Company active.
- Production readiness backend previously reported `ACTIVE`.

### Customer Portal verified manually

- Inbox loads real conversations.
- AI Employee filter works.
- Channel filter works.
- Search works.
- Conversation thread view works.
- New Customer Portal test conversations are tagged `portal_test` / `Test Console`.
- Older conversations created before source metadata may remain `Unclassified`.
- Quotation Requests works from canonical ActionRequest records.
- Leads works.
- Support Requests / Human Handoffs works.
- Billing works.

### Real staging operation

Valid `catering_quote #2` completed for event date `2026-09-15`.

Legacy `catering_quote #1` contains the old 2024 date from before the Business Clock fix and is staging test data only. Clean it before production.

## Conversation source architecture

`AIConversation` supports generic channel metadata:

- `channel_id`
- `channel_type`
- `external_contact_id`

Implemented source tagging includes Website, Voice, WhatsApp and Customer Portal Test Console. The unified Customer Inbox is ready for future channel types, but an Instagram adapter is not implemented yet.

## AI Employee configuration

The current admin AI Employee creation path now creates `AgentConfig` automatically.

- New AI Employees receive default customer controls.
- Existing employees missing AgentConfig are backfilled on profile access/update.
- Missing customer-control keys receive defaults.
- Explicit existing `False` values remain respected.

Default customer controls:

- `can_enable_disable = true`
- `can_view_conversations = true`
- `can_view_usage = true`
- `can_edit_prompt = false`
- `can_change_provider = false`
- `can_change_model = false`

## Production Readiness UI

Backend canonical field: `company_profile_ready`.

The Admin compatibility layer maps the old `profile_ready` expectation to the canonical value, fixing the false `Company profile: Needs setup` display for a genuinely ready company.

## Admin / customer privacy boundary

Current product decision: Xvond Admin configures and operates the platform infrastructure, but customer conversation content and customer-created request payloads belong to the tenant Customer Portal or the tenant's connected external system.

Therefore:

- Xvond Admin no longer exposes customer-content Operations/Conversations tabs.
- Admin AI Employee Actions is configuration only and does not show real customer request payloads.
- Admin conversation/message APIs are not part of the active Admin surface.
- Admin request-list/status-management APIs are not part of the active Agent Actions surface.
- External integration reconciliation remains available to Xvond operators using safe technical metadata only.
- Admin still sees configuration, readiness, usage/cost, integrations, billing, audit/runtime health and worker status.

Customer Portal is the client-facing location for Inbox, quotation requests, leads, support requests and other capability-specific operational records.

## Multi-provider AI architecture

Adapters exist for:

- OpenAI
- Anthropic / Claude
- Google / Gemini
- xAI / Grok
- Groq
- Mock (development only)

Environment keys supported:

- `OPENAI_API_KEY`
- `ANTHROPIC_API_KEY`
- `GOOGLE_API_KEY`
- `XAI_API_KEY`
- `GROQ_API_KEY`

Provider routing supports company default, optional fallback, automatic ranking, recent failure-rate signal, provider priority, latency, configured token price and first-request failover.

Current limitation: after a provider has produced a tool call, continuation rounds stay on that same provider. Cross-provider continuation failover is a later production-hardening item.

## Warning cleanup completed

Python 3.14 deprecation/resource warnings found in provider-policy tests were removed:

- provider/model `created_at` defaults no longer call deprecated `datetime.utcnow()`;
- explicit UTC time is used while preserving existing naive DateTime storage;
- temporary SQLite engines are disposed after tests.

Verified result: **132 passed, 0 warnings**.

## Current architecture decisions

1. Xvond Admin is the configuration/technical control plane, not the tenant's customer-service inbox.
2. Customer operational data is shown to the tenant through Customer Portal or its connected external system.
3. Customer Portal exposes capability-specific pages such as Quotation Requests, Leads, Bookings, Orders and Support according to enabled capabilities.
4. A client without an external system can use Xvond internal operation storage.
5. A client with CRM/POS/ERP/API can use an Integration destination; the external system may remain source of truth.
6. AI must not confirm a booking/order/quotation/action unless the configured operation or external integration actually succeeds.
7. Production deployment remains paused until staging hardening and live acceptance are complete.

## Immediate next steps

1. Refresh Xvond Admin and visually verify the privacy/readiness UI after the latest changes.
2. Add a second real AI provider API key and test actual automatic failover while keeping the same customer-visible AI Employee.
3. Validate normal response, tool calling, failover and usage/cost logging with multiple real providers.
4. Test one real External Integration action end-to-end.
5. Clean legacy staging test records such as `catering_quote #1` before production acceptance.

## Deployment later

Do not switch the laptop to production mode merely to make acceptance green.
When deployment resumes, deploy the complete Xvond runtime and then run production acceptance with live AI, HTTPS/public base URL, migrations, Redis, backups and restore verification before merging to production.
