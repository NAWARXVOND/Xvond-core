# Xvond Commercial & Delivery Playbook

## Commercial promise

Xvond sells managed business outcomes powered by AI employees, automation and integrations. We do not sell generic chatbots, prompt access or unsupported channel promises.

Every sale must answer four questions before proposal:

1. What business outcome is the customer paying for?
2. Which AI employee role owns that outcome?
3. Which channels, tools and integrations are required to deliver it?
4. How will Xvond and the customer know the outcome is working after Go Live?

## Ideal early customer

Prioritize businesses where one or more of the following is expensive, repetitive or time-sensitive:

- customer inquiries and qualification;
- appointment/reservation handling;
- lead capture and follow-up;
- order/request intake;
- support triage and human escalation;
- repetitive back-office workflow between existing systems.

Prefer customers with a clear owner, measurable demand, usable business information and a channel Xvond supports reliably. Avoid custom complexity that cannot be tested or supported profitably.

## Standard sales flow

`Qualified lead -> discovery -> solution map -> demo -> proposal -> scope confirmation -> agreement/payment -> Operations handoff -> onboarding`

### Qualification

Sales records:

- business name and decision maker;
- current problem and cost of the problem;
- customer volume and busiest periods;
- current channels;
- required languages;
- required actions such as booking/order/lead/handoff;
- integrations and systems of record;
- expected human escalation path;
- target launch date;
- data/privacy constraints.

A lead is not qualified because they are interested in AI. They are qualified when there is a concrete workflow Xvond can improve and a decision maker willing to fund it.

### Demo

Demo the customer's future workflow, not a generic AI conversation. A good demo proves:

- the employee understands the business role;
- it uses verified company information;
- it can complete or safely hand off the required operation;
- channel behavior is realistic;
- human takeover is visible;
- unsupported actions are not fabricated.

### Proposal

Every proposal separates:

- one-time implementation/setup;
- recurring managed platform/service fee;
- included usage/limits;
- optional add-ons;
- third-party provider costs when applicable;
- custom work outside the standard scope;
- customer dependencies and target timeline;
- support scope and escalation expectations.

Do not bury custom integration work inside an unlimited monthly promise.

## Commercial package structure

Prices are configured through canonical `ServicePlan` records and may change without a code release. The commercial structure should remain stable:

### Launch

For one clearly defined AI employee and a standard supported channel/workflow.

Typical scope:

- discovery and configuration;
- one AI employee;
- business profile and knowledge setup;
- one supported production channel;
- standard handoff;
- standard reporting/usage;
- managed onboarding and Go Live.

### Operations

For businesses that need multiple workflows/channels, more usage or ongoing optimization.

Typical scope adds:

- additional channels or employees according to plan limits;
- approved business actions;
- supported integrations;
- workflow automation;
- operational monitoring and periodic optimization.

### Custom / Enterprise

For non-standard integrations, custom applications, dedicated workflows, complex security/compliance, higher traffic or special operational requirements.

Always scope implementation separately. Do not promise a fixed standard package for unknown custom work.

## Setup fee principle

Implementation work is not free. The setup/implementation price covers discovery, configuration, knowledge preparation, integration/channel work, testing and production acceptance. Recurring fees cover platform entitlement, managed operation/support and the agreed included usage.

## Scope control

A signed scope must define:

- AI employee role(s);
- channels;
- capabilities/actions;
- integrations;
- knowledge sources;
- languages;
- handoff path;
- usage limits;
- reporting expectations;
- exclusions.

Anything outside that boundary is a change request or new service assignment, not an informal promise.

## Sales-to-Operations handoff

Operations does not start from a sales chat. Sales hands over a structured brief containing:

- agreed outcome;
- signed scope;
- customer owner/admin contacts;
- purchased service plan(s);
- required channel ownership/access;
- business information still needed;
- integrations still needed;
- target test and Go-Live dates;
- known risks or custom commitments.

Operations then creates the Xvond Company in `onboarding` and follows `docs/customer-onboarding-runbook.md`.

## Launch acceptance

The customer moves from `testing` to `live` only when Delivery Readiness and the operational acceptance checklist pass. A successful internal AI test alone is not Go Live.

Acceptance includes realistic end-to-end scenarios for every sold capability. For example, a booking solution is not accepted until a real test can prove the intended booking workflow, failure behavior and human fallback.

## Support tiers principle

Support commitments must be explicit in the commercial plan. At minimum define:

- support channel;
- business hours or 24/7 commitment;
- severity definitions;
- response target by severity;
- what qualifies as platform incident vs customer change request;
- escalation owner.

Never promise an SLA that Operations cannot monitor from the control plane.

## Renewal and expansion

Review before renewal:

- actual usage;
- conversations/operations completed;
- failure and handoff patterns;
- provider cost;
- customer outcomes;
- unused purchased capabilities;
- additional workflow opportunities.

Expansion should come from a new measurable workflow, additional employee/channel, higher usage or integration—not from adding arbitrary AI features.

## Commercial guardrails

- No unsupported capability is sold as live functionality.
- No production integration is promised before technical feasibility is confirmed.
- No customer-specific business fact is hard-coded in an Xvond template.
- No unlimited usage is implied unless the actual plan intentionally supports it.
- No third-party cost is silently absorbed if the proposal says it is pass-through or separately billed.
- No customer reaches Live without an owner, canonical service entitlement and completed readiness gates.
- Unknown external action or message delivery outcomes are reconciled, never retried blindly to satisfy a customer complaint.
