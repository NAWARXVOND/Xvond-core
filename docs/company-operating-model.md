# Xvond Company Operating Model

## Positioning

Xvond is a managed AI operations company for businesses. The product is not a collection of unrelated bots. A customer buys business outcomes delivered through AI employees, automation, integrations and operating support.

The canonical model is:

`Company -> AI Employee -> Role / Behavior / Knowledge / Capabilities / Tools -> Channels -> Conversations -> Business Actions -> Human Handoff -> Usage / Operations`

One AI employee may serve multiple channels. A channel is a communication surface, not a separate AI brain.

## What Xvond sells

Xvond has six commercial solution families:

1. AI strategy and implementation consulting.
2. AI Employees for customer service, sales, booking, orders and other defined business roles.
3. Business automation and workflow orchestration.
4. Websites, portals and custom applications where they are part of the delivered solution.
5. Growth/marketing systems where Xvond is explicitly contracted to deliver them.
6. Custom AI/integration solutions.

The platform service catalog, AI employee capabilities and communication channels are separate concepts. A plan grants commercial entitlement to a service. An AI employee receives capabilities. Channels are assigned to that employee.

## Delivery model

Xvond operates as a Hybrid Managed Service.

Customer self-service is appropriate for business facts, approved knowledge, customer team management, inbox operations and safe settings. Xvond Operations owns sensitive provider configuration, production readiness, integrations, deployment, incident handling and unsupported/complex changes.

Do not expose a setting to the customer unless Xvond can reliably execute it.

## Customer lifecycle

Canonical commercial lifecycle:

- `onboarding`: tenant and owner exist; customer can access the portal; AI runtime is off.
- `testing`: setup is being validated; customer can access the portal; production AI runtime is off.
- `live`: readiness has passed and the company runtime may serve real traffic.
- `paused`: commercial relationship remains valid, customer can access the portal, runtime is off, configuration is preserved.
- `suspended`: portal and runtime are blocked pending an operational/commercial decision.
- `cancelled`: service is terminated; portal and runtime are blocked.
- `archived`: historical tenant retained for controlled retention/audit only.

`Company.active` is a runtime/emergency switch, not the commercial lifecycle. Emergency Stop may disable AI employees immediately without pretending that the commercial relationship changed.

## Standard customer journey

`Lead -> Discovery -> Solution Definition -> Proposal -> Agreement -> Company Creation -> Owner Access -> Service Subscription -> Business Information -> AI Employee Setup -> Knowledge -> Tools/Integrations -> Channels -> Test -> Delivery Readiness -> Go Live -> Monitor -> Support -> Review/Renew/Upgrade`

A customer is not Live merely because a channel token exists or an AI provider returns a response. Delivery Readiness is the authority for Go Live.

## Responsibilities

### Sales

Sales qualifies the business problem, expected outcome, channels, required integrations, volume expectations and commercial package. Sales must not promise unsupported channel capabilities or custom integrations before technical confirmation.

### Operations

Operations creates the company, confirms subscriptions, coordinates onboarding, verifies required business information, configures supported channels/integrations, reviews readiness, handles unresolved deliveries/actions and coordinates incidents.

### Technical

Technical owns provider configuration, platform releases, migrations, security, integrations, reliability, backups, observability and escalation of defects.

### Customer owner/admin

The customer owns the truth of business information, approved services/products/policies, customer-side account access and human conversation operations. Customer changes must remain tenant-scoped.

## Go-Live rule

No real customer is activated unless all required readiness checks pass. At minimum:

- tenant and owner exist;
- canonical service subscription exists;
- business profile contains the facts needed by the employee;
- employee role/profile/config are complete;
- approved knowledge exists where required;
- at least one supported channel is correctly connected;
- provider/model routing is real and eligible;
- required tools/integrations are configured and tested;
- handoff behavior matches the channel capability;
- production database/Redis/runtime are healthy;
- latest database migration is applied;
- unresolved critical delivery/action incidents are reviewed;
- backup status is acceptable;
- production routing exposes the correct Xvond application paths.

## Support operating principle

Support should diagnose incidents from Xvond control-plane metadata before SSH or SQL. Admin visibility must expose technical identifiers, lifecycle state, channel state, worker health, delivery state, action state and timestamps without exposing customer message bodies by default.

For WhatsApp, support should be able to trace:

`Inbound event -> WhatsApp session/conversation -> AI request/business action -> outbound delivery -> Meta status -> human handoff state`

Unknown external side effects or unknown message delivery outcomes must be reconciled, never retried blindly.

## Commercial/billing principle

`ServicePlan` and `ServiceSubscription` are the canonical entitlement system. Legacy plan/subscription tables are historical compatibility only and must not receive new onboarding writes.

Plans define service entitlement, included limits and commercial price. Usage is measured from actual platform events. Reaching a hard limit must not silently create billable overage unless the commercial policy explicitly supports it.

## Scaling rule

Do not scale concurrency by weakening idempotency or ordering. Multi-worker growth is allowed only when inbound processing, business actions and outbound delivery remain durable and idempotent with per-contact ordering guarantees.

## Product truth rules

- Never present a channel as connected solely because a token exists.
- Never present a feature as available if no real adapter executes it.
- Never infer a company's services from its business type or billing package.
- Never let a channel own independent employee persona/knowledge.
- Never retry an unknown external side effect blindly.
- Never expose tenant customer message payloads in the Xvond operator plane unless an explicitly authorized support workflow requires it.
