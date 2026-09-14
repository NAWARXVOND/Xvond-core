# Customer Onboarding Runbook

This runbook is the default path for taking a signed Xvond customer from handoff to production. Deviations require an explicit technical/operations note.

## 1. Sales handoff

Record the agreed business outcome, service family, package, expected channels, languages, expected volume, required integrations, human-handoff owner and launch target. Do not use a business type as a substitute for the customer's actual services or policies.

Exit condition: the solution scope is specific enough that Operations can identify the required employee, knowledge, tools and channels.

## 2. Create tenant and owner

Create the Company through Xvond Admin. The company starts in `onboarding`; production runtime is off. Create the customer owner account and confirm the owner can access the Customer Portal.

Exit condition: tenant isolation is established and the customer owner can sign in without enabling production AI traffic.

## 3. Assign commercial entitlements

Assign canonical `ServicePlan` / `ServiceSubscription` records for every sold service. Do not create or rely on legacy generic subscriptions.

Exit condition: readiness and usage limits see exactly the services included in the signed scope.

## 4. Capture business truth

Customer/Operations completes Company Profile and Business Information: legal/display name where relevant, business type, services/products, working hours, policies, locations, contact paths and any facts the AI employee is allowed to state.

Exit condition: required business facts are stored canonically. Missing services remain missing; Xvond never invents them.

## 5. Create AI employee

Prefer an approved Agent Template when the role matches a standard Xvond delivery pattern. Customize only the fields required by the customer's actual operation.

Configure role, behavior, supported languages/dialect, response style, capabilities, customer controls and real provider/model routing. The employee remains Draft/off until Delivery Readiness passes.

Exit condition: one canonical AI employee represents the role across all assigned channels.

## 6. Add knowledge

Attach approved text, URLs and/or documents to the employee. Confirm tenant and employee ownership. Validate retrieval against representative customer questions, including fallback behavior when embeddings are unavailable.

Exit condition: expected answers are grounded in saved business facts/knowledge and unsupported facts are not invented.

## 7. Configure tools and integrations

Assign only the tools required for the sold workflow. Validate integration secrets through Xvond Admin and perform a non-destructive test where possible. External workflows must honor Xvond request IDs as idempotency keys.

Exit condition: every enabled tool has a real execution path, safe error behavior and an owner for unresolved operations.

## 8. Connect channels

Connect the purchased channels to the employee. A channel never gets an independent AI persona.

For WhatsApp Coexistence, verify WABA/app subscription, required webhook fields, real connection state and observed SMB echo evidence before treating Coexistence as ready. For Website, validate widget origin/configuration. Voice/other channels must expose only capabilities actually supported.

Exit condition: every enabled channel is connected to the correct Company and AI employee and source identity is stable.

## 9. Human handoff test

Test the actual channel capability. For WhatsApp/Website, verify takeover, owner assignment, human reply, no AI reply while human control is active, and explicit Return to AI. For unsupported channels, confirm the UI does not present a fake reply/takeover capability.

Exit condition: human control cannot race with or be overwritten by AI output.

## 10. Business action test

For booking/order/lead/custom workflows, validate one happy-path action and the relevant failure/retry path. Verify duplicate inbound delivery cannot execute the business action twice. Unknown external outcomes go to reconciliation rather than blind retry.

Exit condition: a customer-facing retry cannot duplicate a business side effect.

## 11. Delivery test

For WhatsApp, confirm outbound delivery is durably recorded before network execution, provider message IDs are tracked, status webhooks progress the delivery state where available, failed/retryable deliveries can be handled safely, and `unknown` outcomes are never automatically resent.

Exit condition: Support can distinguish prepared, accepted, delivered/read, failed and unknown transport state without reading customer content.

## 12. Move to testing

Operations sets Company lifecycle to `testing`. Customer Portal remains accessible; production runtime remains off. Run representative scripts for FAQs, service questions, unsupported questions, escalation, tool execution, duplicate messages, provider timeout/failure and channel reconnect behavior.

Exit condition: no open P0/P1 defect applies to the customer's sold path.

## 13. Production acceptance

Run the version-controlled production acceptance checks. Confirm database, migration head, Redis, real AI route, service entitlements, company/employee readiness, worker health, unresolved delivery/action attention, backup freshness and production routing.

For a real launch, also verify the public `/admin-ui` and `/customer-ui` routes reach Core through the production reverse proxy.

Exit condition: acceptance report is green or every non-green item has an explicit approved exception that does not affect the sold path.

## 14. Go Live

Set lifecycle to `live`. This transition is readiness-gated and activates company runtime; it does not bypass employee Delivery Readiness. Enable only employees/channels that passed their own go-live gate.

Record launch timestamp, package, active employee IDs, channels, support owner and known non-blocking limitations.

## 15. First-day monitoring

Review inbound processing, AI failures/latency, business actions, handoffs, outbound delivery statuses, queue/dead jobs and usage. Check that customer-facing conversation counts match the Inbox and no test/unclassified traffic appears in live views.

## 16. Ongoing service

Operations owns lifecycle changes, subscription changes, incident triage and renewal coordination. Customer manages approved business facts/knowledge and its own team within allowed permissions. Technical owns defects, releases, migrations, platform reliability, backups and provider/integration escalation.

### Pause

Use `paused` when the relationship remains active but runtime should stop temporarily. Preserve employee configuration so service can resume after checks.

### Suspend

Use `suspended` for a commercial/security/operational block. Portal and runtime access are blocked until Xvond explicitly resolves the condition.

### Cancel / Archive

`cancelled` terminates service. `archived` is the controlled historical state after retention/export obligations are addressed. Neither is a temporary runtime switch.
