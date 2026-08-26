# Xvond Project Checkpoint

Date: 2026-08-26 (Asia/Muscat)
Branch: `staging`

## Current verified platform state

- Xvond Core: Python / FastAPI / PostgreSQL / Redis modular business platform.
- Local database migration `c8f2a1d4e930` applied successfully.
- Last locally verified full test run before the final checkpoint fixes: **127 passed, 22 warnings, 0 failed**.
- Customer Portal is tenant-scoped and service/capability driven.
- Billing is working for the current staging customer; AI Agents usage shows real agent count and token ledger behavior.

## Gulf Catering Hub staging customer

- Company ID: `4`
- AI Employee: `Website Customer Service`
- Agent ID: `6`
- Current real provider in local testing: `groq`
- Model: `openai/gpt-oss-20b`
- Website channel exists and is active/configured for staging.
- Company is active.
- Production readiness backend status was `ACTIVE` in local testing.

### Customer Portal verified manually

- Inbox loads real conversations.
- AI Employee filter works.
- Channel filter works.
- Search works.
- Conversation thread view works.
- New Customer Portal test conversations are tagged `portal_test` / `Test Console`.
- Older conversations created before source metadata remain `Unclassified` by design.
- Quotation Requests page works and reads the canonical ActionRequest records.
- Leads page works.
- Support Requests and Human Handoffs pages work.
- Billing page works.

### Real staging operation

`catering_quote #2`

- customer: نوار
- event date: 2026-09-15
- event type: Corporate Catering
- guest count: 80
- location: Muscat
- phone: 91234567
- requirements: بوفيه واستراحة قهوة
- status: completed

Legacy staging operation `catering_quote #1` contains the old 2024 date from before the Business Clock fix and is test data only. It should be cancelled/removed during staging cleanup before production.

## Conversation source architecture

`AIConversation` now supports generic channel metadata:

- `channel_id`
- `channel_type`
- `external_contact_id`

Implemented source tagging:

- Website -> `website`
- Voice -> `voice`
- WhatsApp -> `whatsapp`
- Customer test console -> `portal_test`

The unified Customer Inbox is ready for future channel types such as Instagram, but an Instagram channel adapter has **not** been implemented yet.

## AI Employee configuration fix at this checkpoint

The current admin AI Employee creation path previously created `AIAgent` and `AIAgentProfile` but did not create `AgentConfig`.

Fixed on `staging`:

- Every new admin-created AI Employee now gets an `AgentConfig` automatically.
- Existing/legacy employees get the missing config backfilled when their AI Employee profile is loaded or updated.
- Missing customer-control keys are filled from defaults.
- Explicit existing `False` values remain respected.

Default customer controls:

- `can_enable_disable = true`
- `can_view_conversations = true`
- `can_view_usage = true`
- `can_edit_prompt = false`
- `can_change_provider = false`
- `can_change_model = false`

The Inbox/legacy conversation-access fallback remains for compatibility with older data.

## Production Readiness UI fix at this checkpoint

Backend canonical field: `company_profile_ready`.

The current admin workspace still reads the older name `profile_ready`. To keep the API backward compatible and immediately fix the display, readiness now returns both:

- `company_profile_ready`
- `profile_ready`

Both carry the same boolean value. This fixes the false `Company profile: Needs setup` display for a genuinely ready company.

## Multi-provider AI architecture

Core provider adapters currently exist for:

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

Provider routing already supports:

- company default provider/model
- optional company fallback provider/model
- automatic candidate ranking
- recent failure-rate signal
- provider priority
- latency signal
- configured token price
- first-request automatic failover across eligible providers

Important current limitation:

- After a provider has produced a tool call, subsequent continuation rounds stay on that same provider. Cross-provider continuation failover is not implemented because provider continuation formats differ.
- This is a production-hardening item, not a blocker for the current single-provider staging flow.

## Architecture decisions that remain fixed

1. Xvond Admin and Customer Portal show the same canonical business records; they do not duplicate operation data.
2. Xvond Admin -> Operations is the operator view for real AI-created business actions.
3. Customer Portal exposes capability-specific pages such as Quotation Requests, Leads, Bookings, Orders, and Support according to enabled company capabilities.
4. A client without its own external system can use Xvond Operations as the execution destination.
5. A client with its own CRM/POS/ERP/API can use an Integration destination; the external system may remain the source of truth.
6. AI must not confirm a booking/order/quotation/action unless the configured action or integration actually succeeded.
7. Production deployment remains intentionally paused until staging hardening is complete.

## Immediate next steps after pulling this checkpoint

1. Run `pytest -q` and confirm the new total has 0 failures.
2. Refresh Xvond Admin and verify `Production Readiness -> Company profile` now shows `Ready` for Gulf Catering Hub.
3. Verify Agent ID 6 now has an `AgentConfig` row with the default customer controls after the Company Workspace loads.
4. Add a second real AI provider API key and test actual provider failover without changing the customer-visible employee.
5. Test one real External Integration action end-to-end.
6. Clean the legacy `catering_quote #1` staging record before production.

## Deployment later

Do not switch the laptop to production mode merely to make acceptance green.
When deployment resumes, deploy the complete Xvond runtime and then run production acceptance with live AI, HTTPS/public base URL, migrations, Redis, backups, and external restore verification before merging to production.
