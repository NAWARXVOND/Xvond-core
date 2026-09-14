# Xvond Support Incident Runbook

This runbook is for the internal `support` role. Support is an operational read-only role. It may inspect Xvond control-plane health and incident metadata but must not change company lifecycle/runtime, billing, providers, channels, integrations, AI Employee production state, retry external effects, or reconcile uncertain outcomes.

## Operating boundary

Start from Xvond Admin Dashboard and the Support read-only company view. Diagnose from metadata before requesting deeper access. Do not use customer message bodies, contact payloads, credentials, tokens, prompts or tenant documents for routine triage.

Support may inspect:

- company lifecycle and runtime state;
- AI Employee and channel operational state;
- service/subscription state;
- aggregate usage and AI failure counts;
- WhatsApp worker/queue/dead-job health;
- backup freshness;
- unresolved external-operation metadata;
- unresolved WhatsApp delivery metadata.

Support must escalate any action that changes production state to Xvond Admin/Operations or Technical.

## Severity

- **P0:** multi-customer outage, data/security incident, database/Redis unavailable, production routing unavailable, or widespread message/action duplication risk.
- **P1:** one live customer cannot use a sold production channel or critical action; unresolved delivery/action state risks customer impact.
- **P2:** degraded/non-critical feature, intermittent AI/provider failure, onboarding/testing blocker without live outage.
- **P3:** configuration question, cosmetic issue, report/request with no active customer impact.

## First checks

1. Confirm the affected Company and current lifecycle/runtime state.
2. Check Dashboard Needs Attention and AI failures in the last 24 hours.
3. Check WhatsApp Worker, queue, retrying and dead-job counts when messaging is involved.
4. Check backup health for platform incidents; a stale/missing backup is an independent escalation even when customer traffic works.
5. Open the Support company view and inspect employee/channel state, service entitlement and aggregate usage.
6. Check unresolved external operations and unresolved WhatsApp deliveries.
7. Record timestamps, Company ID, AI Employee ID, Channel ID, Conversation ID or Delivery/Operation ID as applicable. Do not copy customer message content into the incident record.

## WhatsApp: customer says the AI did not reply

Check in this order:

1. Company lifecycle/runtime: a paused/suspended/cancelled tenant or stopped runtime explains intentional inactivity.
2. AI Employee production state and assigned WhatsApp channel state.
3. Worker health and queue depth.
4. Unresolved delivery records for the company.
5. AI failure count/usage for the same period.
6. Coexistence/connection state through the operational channel metadata available to Admin/Technical if Support cannot establish the cause from the read-only view.

Escalate to Operations/Admin if activation, channel change or lifecycle change is required. Escalate to Technical if worker/runtime/provider behavior is abnormal.

Never retry an `unknown` delivery. An unknown provider outcome can duplicate a customer-facing message if resent blindly.

## WhatsApp: failed delivery

If the delivery is `failed`, record Delivery ID, Company ID, Channel ID, attempts and safe provider error/status codes. Support does not press retry. Admin/Operations decides whether the delivery is safely retryable through the protected retry endpoint.

If the delivery is `unknown`, escalate for reconciliation. Do not interpret it as failed and do not request a blind resend.

## Worker offline / queue growing

Treat an offline worker with a growing queue as P1, or P0 if multiple live customers are affected.

Record worker lease/heartbeat state and queue counts. Do not requeue dead jobs from Support. Technical/Admin owns worker restart, dead-job retry and deployment checks.

## Human handoff complaint

Support may identify the Company, AI Employee, channel and conversation identifiers but should not read customer message bodies by default. Escalate when the complaint requires ownership mutation, Return to AI, manual reply investigation or Meta Coexistence evidence.

A Business App/manual human reply must not be treated as proof of handoff unless the corresponding platform echo/control evidence exists.

## AI failure / incorrect provider behavior

Use aggregate usage/failure metadata to establish timing, provider/model route and frequency. Do not request raw prompts or customer messages as the first diagnostic step.

Escalate to Technical for repeated provider/network errors, routing failures, latency spikes or runtime exceptions. Escalate to Operations if the issue is caused by service entitlement, lifecycle, readiness or intentional configuration.

## External business operation unresolved

Statuses such as `executing`, `external_failed` or `cancelling` require reconciliation against the external CRM/POS/API before Xvond changes the operation state. Support only records the operation metadata and escalates. Support must not choose `executed`, `not_executed` or `cancelled` on behalf of Operations.

## Backup warning

- `healthy`: no action.
- `stale`: escalate to Technical the same working period; P1 when recovery protection is materially outside policy.
- `missing`: escalate immediately. Treat as P1 until backup behavior is understood.
- offsite `not_configured`: record only if offsite backup is not expected; if policy says it should exist, escalate.

Support never receives repository credentials or backup secrets through the dashboard.

## Routing / portal incident

If `/admin-ui` or `/customer-ui` resolves to the wrong application, returns stale HTML, or cannot reach Core APIs, escalate to Technical. Verify the public route, Core health/readiness and reverse-proxy/CDN behavior. Do not change nginx/CDN configuration from Support.

## Escalation record

Every escalation should contain only the minimum useful metadata:

- severity and customer impact;
- Company ID/name;
- lifecycle/runtime state;
- affected AI Employee/Channel ID;
- Delivery/Operation/Conversation ID when relevant;
- UTC timestamp/window;
- worker/backup/AI failure state;
- safe status/error codes;
- checks already performed.

Do not attach customer messages, phone numbers, access tokens, credentials, prompts or documents unless an explicitly authorized privacy-aware support workflow requires them.

## Resolution ownership

- **Support:** observe, classify, collect safe metadata, communicate status, escalate.
- **Operations/Xvond Admin:** customer lifecycle, subscriptions, Go Live, safe retries/reconciliation, supported configuration changes.
- **Technical:** deployments, migrations, worker/runtime failures, provider/integration defects, database/Redis, backups, reverse proxy/CDN, security incidents.

Support closes an incident only after the owning team confirms resolution and the read-only control-plane indicators return to the expected state.