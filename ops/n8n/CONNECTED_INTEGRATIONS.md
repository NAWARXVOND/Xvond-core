# Connected Integration Routing

The Xvond Core sends only company and integration identifiers plus safe action metadata to the Workflow Engine. Third-party execution credentials belong to the Workflow Engine.

## Webhook registry

The Workflow Engine reads `XVOND_WORKFLOW_INTEGRATIONS_JSON`, a JSON object keyed by `company_id:integration_id`.

Example shape (never commit real values):

```json
{
  "12:7": {
    "type": "webhook",
    "url": "https://customer.example.com/xvond",
    "secret": "workflow-owned-secret"
  }
}
```

Rules:

- Core never sends the webhook URL or secret in the action payload.
- The route must match both company ID and integration ID.
- Only HTTPS targets are allowed in production provisioning.
- Mutating requests keep the same Xvond idempotency key.
- No fallback to another route after an ambiguous side effect.
- A missing registry entry fails closed with `provider_not_configured`.
