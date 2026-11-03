# CRM Campaign Calendar Portal: Feasibility, API Contracts, Architecture

Status: November 2026. Code: superseded by [`crm-portal/`](../crm-portal/README.md); this document keeps the vendor research.

## 1. Verdict at a glance

| Question | Verdict | Why |
|---|---|---|
| Q1: submit WhatsApp templates for Meta approval by API | **Feasible.** The most reliable route is the Meta Graph API. The TrustSignal route needs a contract from their team. | Meta's `POST /{WABA_ID}/message_templates` is public and documented. TrustSignal publishes only an SMS API (`POST api.trustsignal.io/v1/sms?api_key=…`). Its WhatsApp template endpoint, auth and webhook relay are not public. |
| Q2: auto-register the approved template in WebEngage by API | **Not feasible as specified today.** Use a human-in-the-loop handover, or a private API if WebEngage provides one. | WebEngage documents no template REST API. `POST /v1/accounts/{license_code}/templates` does not exist in its public docs. Templates are added in the dashboard: *Integrations → WhatsApp → Add Template* (name, text, namespace, language). In-app create-and-submit exists only for some WSPs (Infobip; the docs also mention AiSensy, Karix and Route Mobile). TrustSignal is not a listed WSP, so it would have to be onboarded as a *Private WSP*. |
| Q3: automate DLT SMS template registration (Vilpower) | **Not feasible, and must not be attempted.** Registration stays human; the portal verifies after the fact. | No public template API was found for Vilpower. Login requires OTP and CAPTCHA under TRAI TCCCPR. Scripting around CAPTCHA breaks the portal's terms and the intent of the regulation. |

The rest of the 2-step chain is fully deterministic and runs today in simulation:

> **Step 1:** validate → submit → signed webhook → APPROVED. **Step 2:** stage in WebEngage → human confirms. A human launches the campaign in WebEngage.

## 2. Question 1: WSP / Meta template approval

### 2.1 What can be automated
- **Body with `{{1}}`, `{{2}}`**: yes. Meta requires one sample value per variable (`example.body_text`).
- **Header image**: yes. The Meta Graph API needs a *resumable-upload handle*, not a URL. `server.py` uploads the banner first (`meta_upload_header_image`). WSPs usually accept a public HTTPS URL and do the upload themselves.
- **CTA URL button and dynamic URL**: yes. A dynamic URL may have only one variable, `{{1}}`, and it must be at the very end. It also needs an example.
- **Category MARKETING / UTILITY**: yes. Meta can re-categorise a template (a UTILITY template with promotional words becomes MARKETING). It reports this through a separate `template_category_update` webhook, which the server handles.

### 2.2 Authentication and network
| | Meta Graph API (direct) | TrustSignal (WSP) |
|---|---|---|
| Auth | `Authorization: Bearer <System User token>` with `whatsapp_business_management` permission | Public SMS docs show `?api_key=` as a query parameter. The WhatsApp template API auth is **unconfirmed**. `server.py` supports `WSP_AUTH_STYLE=bearer\|header\|query`. |
| IP allow-listing | Not required by Meta | **Not documented.** Plan for it anyway: send outbound calls from a fixed egress IP (NAT gateway or Elastic IP in ap-south-1) so it can be allow-listed if TrustSignal asks. |
| Precondition | Snapmint's WABA sits in Snapmint's own Meta Business Manager, and a System User has access to it | TrustSignal account manager supplies the template endpoint, payload and webhook spec |

**Ask TrustSignal for:** (1) the template create, status and delete endpoints with a payload sample; (2) the auth scheme and any IP allow-list; (3) whether they relay Meta's `message_template_status_update`, and how they sign it; (4) whether Snapmint can hold its own System User token on the WABA, which would let the portal call Meta directly.

### 2.3 Real-time status: webhooks, not polling
- Meta sends `message_template_status_update` (APPROVED / REJECTED / PAUSED / DISABLED …) to the subscribed webhook.
- **Signature:** `X-Hub-Signature-256: sha256=<hex HMAC-SHA256 of the raw body, keyed with the Meta App Secret>`. Compute it over the raw bytes, before JSON parsing, and compare in constant time. See `verify_signature()` in `server.py`.
- **Subscription handshake:** `GET /webhooks/whatsapp?hub.mode=subscribe&hub.verify_token=…&hub.challenge=…`. The server echoes `hub.challenge` back.
- **WSP relay:** if TrustSignal forwards the event with its own secret, set `WSP_WEBHOOK_SECRET` and the same verifier accepts either secret.
- **Fallback:** `GET /{template_id}?fields=status` on the Graph API (or the WSP equivalent) as a reconciliation job, for example every 15 minutes for templates still PENDING.
- The webhook URL must be public HTTPS. In production, put `/webhooks/whatsapp` behind API Gateway or an ALB. The loopback-only local server cannot receive it.

## 3. Question 2: WebEngage sync

- **No public template API.** The WebEngage REST APIs cover users, events, transactional campaigns and opt-ins. Templates are added in the dashboard, and the name and text must match the approved template character for character.
- **Mapping:** WebEngage looks up a template by **name + language + namespace (`<namespace>:<template_name>`)** under one WSP integration. At send time WebEngage posts `templateData.templateName` and the variables to the WSP, which resolves them against Meta. So the only "mapping" is an exact name and text match, and this is what the registration packet guarantees.
- **TrustSignal inside WebEngage:** TrustSignal is not a built-in WSP. It has to be added as a *Private WSP*: TrustSignal exposes one static HTTPS endpoint that WebEngage POSTs to (Bearer or Basic auth), and TrustSignal posts delivery reports back. The alternative is to pick a WSP that WebEngage already supports (Route Mobile is listed with in-app template creation and auto-approval).
- **Selectable in the Campaign Builder?** Yes, as soon as the template is added under the WSP integration. WebEngage lists only templates mapped to the WSP chosen in the message step.

**How the portal handles this:** *Step 2* calls `/api/webengage/stage`. It builds the exact registration packet (WSP, name, text, namespace, language, header, button). The marketer pastes it into WebEngage (about 30 seconds) and confirms with the WebEngage reference and their name. The confirmation is written to the audit log.
If WebEngage provides a private template endpoint, set `WEBENGAGE_TEMPLATE_API_URL` and `WEBENGAGE_API_KEY` with `PIPELINE_MODE=live`, and Step 2 calls it automatically. No UI change is needed.

**Ask WebEngage for:** (1) a partner or private template-registration API; (2) Private WSP onboarding for TrustSignal; (3) whether Route Mobile's in-app template creation would meet the need instead.

## 4. Question 3: DLT / Vilpower

- Every telecom DLT portal (Vilpower, Jio, Airtel, BSNL, and others) requires a human PE user to log in with OTP and CAPTCHA. No public template-registration API was found. Do **not** automate the login.
- **How the portal handles it:**
  1. A person registers the template on Vilpower (header, content template, variables as `{#var#}`, and any URLs or callback numbers whitelisted per TRAI's URL-whitelisting mandate).
  2. In the portal's **SMS DLT** tab they enter the 19-digit DLT Template ID, the sender header, the PE ID and the exact approved text. The server stores a **SHA-256 of the normalised approved text** (`{{n}}` → `{#var#}`, whitespace collapsed).
  3. Before handover, **Verify** re-hashes the current Comms B. Any edit, even one word, is flagged as a mismatch, because operator scrubbing would block it. URLs in the SMS trigger a whitelist warning.
- The DLT Template ID and header are then entered on the SMS send (WebEngage SMS SP / TrustSignal `template_id`) by a person.

## 5. API contracts

### 5.1 Template creation: Meta Graph API (documented; used in `WSP_PROVIDER=meta_cloud`)
```bash
curl -X POST "https://graph.facebook.com/v23.0/$WABA_ID/message_templates" \
  -H "Authorization: Bearer $META_SYSTEM_USER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "cart_recovery_mobile_v1",
    "language": "en",
    "category": "MARKETING",
    "components": [
      { "type": "HEADER", "format": "IMAGE",
        "example": { "header_handle": ["4::aW1hZ2UvcG5n..."] } },
      { "type": "BODY",
        "text": "Namaste {{1}}! Your smartphone is waiting. Complete checkout with ₹0 downpayment and easy EMIs of {{2}} per month.",
        "example": { "body_text": [["Rahul", "₹3,166"]] } },
      { "type": "FOOTER", "text": "Snapmint" },
      { "type": "BUTTONS", "buttons": [
        { "type": "URL", "text": "Complete Order Now",
          "url": "https://snapmint.com/cart?utm_source=wa&utm_medium=crm" } ] }
    ]
  }'
# 200 → {"id":"1234567890","status":"PENDING","category":"MARKETING"}
```
Header handle (resumable upload): `POST /{APP_ID}/uploads?file_length=&file_type=image/png` → `{"id":"upload:…"}`, then `POST /{upload_id}` with header `Authorization: OAuth $TOKEN`, header `file_offset: 0`, and the image bytes → `{"h":"4::…"}`.

### 5.2 Template creation: TrustSignal (`POST /v1/whatsapp/templates`, **contract unconfirmed**)
The path in the brief is not in TrustSignal's public docs. This is the shape `server.py` sends when `WSP_PROVIDER=trustsignal` and `WSP_TEMPLATE_URL` is set: the Meta payload plus `waba_id`, which is what most Indian BSPs accept. Confirm it with TrustSignal before going live.
```bash
curl -X POST "$WSP_TEMPLATE_URL" \
  -H "Authorization: Bearer $WSP_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{ "waba_id": "'$WABA_ID'", "name": "cart_recovery_mobile_v1", "language": "en",
        "category": "MARKETING", "components": [ ...same as 5.1, header may be a public URL... ] }'
```
The server reads the template ID from `id`, `template_id` or `data.template_id`, whichever is present.

### 5.3 Approval webhook: `message_template_status_update`
```http
POST /webhooks/whatsapp
X-Hub-Signature-256: sha256=9f2c…   (HMAC-SHA256(raw_body, META_APP_SECRET))
Content-Type: application/json

{
  "object": "whatsapp_business_account",
  "entry": [{
    "id": "<WABA_ID>",
    "time": 1793611200,
    "changes": [{
      "field": "message_template_status_update",
      "value": {
        "event": "APPROVED",
        "message_template_id": 1234567890,
        "message_template_name": "cart_recovery_mobile_v1",
        "message_template_language": "en",
        "reason": "NONE"
      }
    }]
  }]
}
```
Re-categorisation arrives as `"field": "template_category_update"` with `previous_category` / `new_category`. Rejections carry a `reason` such as `INVALID_FORMAT` or `TAG_CONTENT_MISMATCH`.

### 5.4 WebEngage registration (`POST /v1/accounts/{license_code}/templates`, **does not exist publicly**)
Today the equivalent is the dashboard form. The portal produces this packet (`/api/webengage/stage`):
```json
{
  "wsp": "TrustSignal (Private WSP)",
  "template_name": "cart_recovery_mobile_v1",
  "template_text": "Namaste {{1}}! Your smartphone is waiting. …",
  "template_language": "en",
  "template_namespace": "snapmint:cart_recovery_mobile_v1",
  "category": "MARKETING",
  "header": { "type": "IMAGE", "url": "https://cdn.snapmint.com/banners/diwali_mobile.png" },
  "button": { "type": "URL", "text": "Complete Order Now", "url": "https://snapmint.com/cart?…" },
  "variable_count": 2
}
```
If WebEngage provides a private endpoint, the same JSON is POSTed to `WEBENGAGE_TEMPLATE_API_URL` (`{license_code}` is substituted) with `Authorization: Bearer $WEBENGAGE_API_KEY`.

### 5.5 Portal's own endpoints
| Method & path | Purpose |
|---|---|
| `GET /api/config` | Mode, provider, and which integrations are configured (never secrets) |
| `POST /api/templates/validate` | Deterministic Meta and Snapmint checks (naming, 1024-character limit, sequential vars, no var at start/end, samples, CTA ≤ 25, https, dynamic-URL rule, PII, UTILITY-promo warning) |
| `POST /api/templates/preview-payload` | Shows the exact upstream payload |
| `POST /api/templates/submit` | Step 1. Idempotent: a 409 if the name is already PENDING or APPROVED |
| `GET /api/templates/status?name=` | Polled by the UI; state is driven by the webhook |
| `GET/POST /webhooks/whatsapp` | Meta handshake + signed status events |
| `POST /api/webengage/stage`, `/api/webengage/confirm` | Step 2 + human confirmation |
| `POST /api/sms/dlt-register`, `/api/sms/dlt-verify` | DLT lock + SHA-256 drift check |
| `POST /api/agent/generate-campaign` | Content Agent (PII-scrubbed) |
| `GET /api/audit` | Last 100 pipeline events |

There is deliberately **no launch endpoint**.

## 6. Architecture and governance

```
 Marketer ──► index.html (calendar, 19 cols, filters, CSV, previews)
                 │  fetch (same origin, no keys in browser)
                 ▼
          server.py (stdlib only, 127.0.0.1)
   ┌────────────┼──────────────┬───────────────────┬──────────────────┐
   ▼            ▼              ▼                   ▼                  ▼
 Validator   WSP / Meta     Webhook receiver   WebEngage staging   Content Agent
 (rules)     Graph API      (HMAC verify)      (packet + human     (Bedrock
                                               confirm / private    ap-south-1,
                                               API if granted)      the ONLY AI)
                              DLT verifier (SHA-256) ◄── human enters Vilpower result
                                        │
                            data/pipeline_state.json + audit log
                                        │
                 Human launches the campaign inside WebEngage (outside this system)
```

| Rule | Where it is enforced |
|---|---|
| Single AI agent | Only `/api/agent/generate-campaign` calls a model. Validation, submission, webhook handling, staging and DLT checks are plain code. The agent's draft goes through the same `validate_whatsapp()` as manual copy, and it is saved as a **Draft** row. |
| Human-only launch | No launch endpoint exists. WebEngage and WSP credentials are template-scoped. Use WebEngage roles so the portal's API key cannot launch campaigns. |
| Mumbai residency | `BEDROCK_REGION` must be `ap-south-*`. Model IDs starting `global.`, `apac.`, `us.` or `eu.` (cross-region inference profiles) are rejected. |
| Zero PII to the LLM | The brief carries aggregate segment names only. The server regex-scrubs phone numbers, emails, Aadhaar and PAN before the call and reports what it removed. Template text with PII-looking values fails validation. |
| Credentials | Environment variables only. The browser never sees a key. State files under `portal/data/` are git-ignored and never served. |

## 7. Content Agent on Bedrock (Mumbai)

`run_content_agent()` in `server.py` uses the Anthropic Python SDK's Bedrock client. It signs requests with the normal AWS credential chain (env vars, `~/.aws`, or the instance role), so no Anthropic API key is involved:

```python
from anthropic import AnthropicBedrockMantle

client = AnthropicBedrockMantle(aws_region="ap-south-1")
resp = client.messages.create(
    model="anthropic.claude-sonnet-5-5",      # BEDROCK_MODEL_ID; in-region ID, not a global./apac. profile
    max_tokens=4000,
    system=AGENT_SYSTEM,                       # copy rules, JSON-only output
    output_config={"effort": "medium"},
    messages=[{"role": "user", "content": scrubbed_brief}],
)
if resp.stop_reason == "refusal": ...          # surfaced to the marketer, nothing saved
```

Setup:
```bash
pip install anthropic
export AWS_PROFILE=snapmint-crm   # IAM: bedrock:InvokeModel on the Sonnet model in ap-south-1 only
export CONTENT_AGENT_ENABLED=1 BEDROCK_REGION=ap-south-1 BEDROCK_MODEL_ID=anthropic.claude-sonnet-5-5
python3 portal/server.py
```

Before going live, check the **Bedrock console for ap-south-1** to confirm the Sonnet model is offered *in-region*, not only through a cross-region inference profile. If it is available only through a profile, the residency rule is not met. Escalate rather than switch to a `global.` or `apac.` ID. Add an IAM condition on `aws:RequestedRegion = ap-south-1` and keep a CloudTrail trail for every `InvokeModel` call.

## 8. Running it

```bash
python3 portal/server.py                 # simulation: Meta approves ~6 s after submit
open http://127.0.0.1:8000
```

| Env var | Purpose |
|---|---|
| `PIPELINE_MODE` | `simulate` (default) or `live` |
| `WSP_PROVIDER` | `trustsignal`, `route_mobile`, or `meta_cloud` |
| `META_WABA_ID`, `META_APP_ID`, `META_SYSTEM_USER_TOKEN`, `META_APP_SECRET`, `META_WEBHOOK_VERIFY_TOKEN`, `META_GRAPH_VERSION` | Meta Graph API + webhook |
| `WSP_TEMPLATE_URL`, `WSP_API_KEY`, `WSP_AUTH_STYLE`, `WSP_WEBHOOK_SECRET` | WSP template API (once TrustSignal confirms the contract) |
| `WEBENGAGE_LICENSE_CODE`, `WEBENGAGE_TEMPLATE_API_URL`, `WEBENGAGE_API_KEY`, `WEBENGAGE_WSP_NAME` | WebEngage (API only if WebEngage provides one) |
| `CONTENT_AGENT_ENABLED`, `BEDROCK_REGION`, `BEDROCK_MODEL_ID` | Content Agent |
| `SIM_APPROVAL_SECONDS`, `HOST`, `PORT` | Local tuning |

In simulation mode the fake Meta webhook is HMAC-signed and goes through the same verification code as a real one. A template that fails validation comes back REJECTED. The browser keeps the calendar in `localStorage` (one browser only). The server keeps pipeline state in `portal/data/pipeline_state.json`. For a shared team calendar, the next step is a small database (Postgres or DynamoDB in ap-south-1) behind the same endpoints.

## 9. Open items before going live
1. TrustSignal: the WhatsApp template API contract, auth, IP allow-list, and webhook relay signing.
2. WebEngage: a private template API, or Private WSP onboarding for TrustSignal. Otherwise, decide whether Route Mobile should be the WebEngage-facing WSP.
3. Meta: confirm Snapmint owns the WABA in its own Business Manager and can create a System User token.
4. AWS: confirm Sonnet is offered in-region in ap-south-1. Set up the IAM role, CloudTrail, and a fixed egress IP.
5. Hosting: a public HTTPS webhook endpoint, SSO in front of the portal, and a shared database in place of `localStorage`.

## Sources
- WebEngage, WhatsApp integration: https://docs.webengage.com/docs/whatsapp
- WebEngage, Private/self-service WSP: https://docs.webengage.com/docs/self-service-wsp
- TrustSignal API integration (SMS only, `api_key` query param): https://trustsignal.io/api-integration/
- Third-party guides on Meta webhook signatures (confirm against Meta's own docs): https://hookdeck.com/webhooks/platforms/guide-to-whatsapp-webhooks-features-and-best-practices, https://webhookrelay.com/blog/whatsapp-cloud-api-webhooks/
- DLT registration overviews: https://developer.exotel.com/docs/sms-support/dlt-guide, https://www.enablex.io/insights/a-step-by-step-guide-to-dlt-registration/
