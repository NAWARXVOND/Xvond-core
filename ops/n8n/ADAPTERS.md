# Workflow Adapter Wiring

Xvond Core never stores or executes third-party business integrations directly. The workflow engine owns provider credentials and side effects.

## Booking adapter

Supported actions:

- `create_booking.check_availability`
- `create_booking.execute`
- `create_booking.cancel`

The adapter may use Google Calendar, Microsoft 365, a booking SaaS, CRM, POS, ERP, or a custom API. Provider choice is deployment configuration, not a Core code change.

Execution requirements:

1. Read the canonical request produced by Xvond.
2. Use `data.idempotency_key` for every mutating provider call.
3. Never return `success=true` until the provider confirms the operation.
4. Return provider identifiers in `data`, for example `booking_id`.
5. On timeout or ambiguous provider state, return `success=false` and a stable error code so Xvond does not falsely confirm the action.

## Email adapter

Supported action:

- `send_email.execute`

The adapter may use SMTP, Microsoft 365, Google Workspace, SendGrid, Brevo, or another mail provider.

Execution requirements:

1. Validate recipient and content inside the workflow before sending.
2. Use `data.idempotency_key` to prevent duplicate sends where the provider supports it; otherwise persist an execution key inside the workflow engine before side effects.
3. Return `success=true` only after the provider accepts the message.
4. Return a provider `message_id` when available.

## Standard failure codes

Use one of these codes in `data.code` where applicable:

- `unauthorized`
- `invalid_contract`
- `unsupported_action`
- `missing_idempotency_key`
- `provider_not_configured`
- `provider_rejected`
- `provider_timeout`
- `provider_ambiguous`
- `validation_failed`

## Security rules

- Third-party credentials belong only in workflow-engine credentials/secrets.
- Do not commit credentials to GitHub or workflow JSON exports.
- Workflows must not connect directly to the Xvond application database.
- Xvond and the workflow engine communicate through the authenticated webhook contract only.
