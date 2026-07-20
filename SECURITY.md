# Security policy

Please do not open a public issue for a vulnerability or include credentials,
private event payloads, customer data, or exploit details in public logs.

For the hackathon release, contact the repository owner privately through the
security contact configured on the hosting account. Include the affected
version, impact, a minimal reproduction, and any suggested mitigation.

Supported release: `v1.x`. We aim to acknowledge a valid report within 72 hours.

## Built-in controls

- Allowlisted tools and deterministic risk classification.
- Mandatory approval for external, financial, and destructive actions.
- Action-hash binding and database-backed idempotency.
- Event ingestion key support and explicit untrusted-text classification.
- Redacted public system status and environment-only secrets.
- Demo reset disabled outside demo mode.

