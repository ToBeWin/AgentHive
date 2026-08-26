# AgentHive Channel Security

AgentHive accepts inbound messages through channel webhooks:

```text
POST /api/v1/channels/webhook/{channel_type}/{channel_key}
```

## License Gate

Channel creation is license-gated by `allowed_features`. The admin UI disables
unlicensed channel types, and the backend rejects `channel.create` when the
tenant license does not include the matching feature key.

| Channel type | Required feature |
| --- | --- |
| `web_widget` | `channel.web_widget` |
| `rest_api` | `channel.rest_api` |
| `wecom` | `channel.wecom` |
| `dingtalk` | `channel.dingtalk` |
| `feishu` | `channel.feishu` |

Webhook delivery for already configured channels still requires normal channel
status, signature, routing, Agent, and permission checks. License scope controls
what can be sold, configured, and enabled for a deployment; it is not a
replacement for request authentication.

Admins can disable a channel without deleting its configuration. Disabled
channels keep their webhook endpoint and audit trail, but inbound messages are
not routed into Agents and webhook ACK responses indicate the channel is not
active. Re-enable the channel only after the integration secret, endpoint
exposure, and target Agent routing have been reviewed.

For private deployments, every production channel that is exposed outside the
trusted network should configure a channel secret and sign requests. Unsigned
channels are allowed for internal development and controlled LAN-only widgets,
but they should not be used for internet-facing integrations.

## AgentHive HMAC Signature

REST API, Web Widget, and integration bridge channels can use the built-in
AgentHive HMAC signature protocol.

Required headers:

| Header | Value |
| --- | --- |
| `X-AgentHive-Timestamp` | Unix timestamp in seconds or milliseconds. |
| `X-AgentHive-Nonce` | Unique random value per request. |
| `X-AgentHive-Signature` | `sha256=<hex hmac>` or raw hex hmac. |

Signing base string:

```text
{timestamp}.{nonce}.{canonical_json_payload}
```

`canonical_json_payload` must be JSON encoded with sorted keys and compact
separators. The HMAC algorithm is `HMAC-SHA256`, keyed by the channel secret.

Example pseudo-code:

```python
import hashlib
import hmac
import json
import time
import uuid

payload = {"text": "hello", "external_user_id": "buyer-1"}
timestamp = str(int(time.time()))
nonce = uuid.uuid4().hex
canonical = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
signature = hmac.new(secret.encode("utf-8"), f"{timestamp}.{nonce}.{canonical}".encode("utf-8"), hashlib.sha256).hexdigest()

headers = {
    "X-AgentHive-Timestamp": timestamp,
    "X-AgentHive-Nonce": nonce,
    "X-AgentHive-Signature": f"sha256={signature}",
}
```

## Replay Window

AgentHive rejects signed webhooks when the timestamp differs from server time by
more than 300 seconds. Channel bridges should keep clock sync enabled through
NTP or the customer's standard time service.

## Failure Behavior

If a channel has a secret configured and signature verification fails:

- AgentHive returns a structured webhook ACK with `accepted=false`.
- The message is not routed into any Agent.
- The audit log records the channel, signature method, signature validity, and
  safe header/payload key names.
- Signature values, secrets, tokens, and authorization headers are never written
  to audit details.

## Audit Trail

For a known channel, AgentHive writes two webhook audit events:

| Action | Status | Purpose |
| --- | --- | --- |
| `channel.webhook.received` | `success` | Records that the platform received and normalized a webhook for this channel. |
| `channel.webhook.processed` | `success` or `failure` | Records the final routing outcome, including signature rejection, disabled channel, unsupported message type, or successful Agent routing. |

The receive event is committed before Agent routing so processing failures do
not erase the evidence that a webhook arrived. Processing audit details include
channel type/key, channel status, message type, conversation key, signature
status, routed flag, Agent key, conversation id, model key, and a safe error
code. They intentionally do not include raw message text, response text,
signature values, channel secrets, token values, authorization headers, or
header values.

Webhook ACK `processing.error` values are stable, integration-safe codes such
as `invalid_signature`, `channel_disabled`,
`unsupported_or_empty_message`, or `processing_exception`. Raw exception text
from Agent runtime, model providers, adapters, storage clients, or internal
services must not be returned to external channel callers. Use `request_id` and
the audit trail to correlate incidents during implementation or support.

Vendor-native WeCom, DingTalk, and Feishu verification can be layered behind
the same adapter contract. Until a vendor-native adapter is configured, bridge
those vendors through the AgentHive HMAC protocol at the integration boundary.
