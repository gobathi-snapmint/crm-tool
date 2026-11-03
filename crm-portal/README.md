# Snapmint CRM Calendar Portal

The monthly CRM campaign calendar (`nov_mkp_calendar_full_view_PLAN_v1.3.csv` format) as a web app, with WhatsApp template approval and the WebEngage step built in.

```bash
python3 crm-portal/server.py          # http://127.0.0.1:8000 (Python 3.9+, no installs)
```

On first start, the server imports `nov_mkp_calendar_full_view_PLAN_v1.3.csv` from the repo root.

## Calendar
- There is one row per date × segment × channel, with the sheet's 19 columns: Day, Date, Product, Segment Name, Naming Structure, Segments to Exclude, Start and End Age, Gender, Location, Campaign Type, Channel, EXP, Comms A and B, Time, Banner_Url, Comments and Size.
- You can filter by day strip, channel, experiments and search, and add, edit or delete campaigns while the calendar is unlocked.
- **Import / export** uses CSV in exactly the sheet's format. Exporting an untouched import is byte-identical. *Calendar + WhatsApp columns* adds the template columns at the end.

## WhatsApp templates
Every `WA …` row is linked to a template. Rows with the same creative (copy, CTA, LP, banner and category) **share one template**, so the November calendar's 332 WhatsApp rows become 19 templates to approve.

The template columns follow the fields of the template-create request (Meta's format, which WSPs relay):

| Column | API field |
|---|---|
| Vendor | which API is called (TrustSignal / Route Mobile / Meta Cloud API) |
| WABA ID | `waba_id` (WSP body) or `/{WABA_ID}/message_templates` (Meta) |
| Sender number (WABA number) | `phone_number` |
| Template name | `name` (lowercase, digits, `_`) |
| Language | `language` (`en`, `en_US`, `hi`) |
| Category | `category` (UTILITY / MARKETING) |
| Header type, image URL, text | `components[HEADER]`, with `format` and `example.header_handle` |
| Body, sample values | `components[BODY].text`, `example.body_text` |
| Footer | `components[FOOTER].text` |
| Button type, text, URL, sample URL | `components[BUTTONS]` (URL or QUICK_REPLY), `example` |
| — | `parameter_format: POSITIONAL` |
| WebEngage URL variable, body variables | what WebEngage fills into `{{1}}`… at send time |

The columns are pre-filled from *Comments*:
- **Body:** the `Copy:` text.
- **Button text:** the `CTA:` text.
- **Button URL:** the `LP:` link. A `{{event[…]}}` product link becomes the dynamic suffix `{{1}}`. The expression is kept as the WebEngage URL variable, and its fallback ID becomes the sample URL.
- **Header image:** Banner_Url.

Templates are checked against Meta's rules as you type, and the editor shows a phone preview.

## Workflow
1. **Fill the calendar.** Templates start as **Draft**.
2. **Lock & send for approval.** Campaign rows freeze. Every draft template is queued and sent to its vendor **one API call at a time**, earliest first send first, with a configurable gap between calls. Templates with format errors block the lock until they are fixed.
3. The vendor submits each template to Meta. The portal polls the status endpoint and also accepts signed webhooks at `POST /webhooks/<vendor>` (`X-Hub-Signature-256`).
4. **Approved in the same category → WebEngage step.** Approved in a different category (UTILITY → MARKETING) or rejected → **Needs edit**. Nothing goes to WebEngage.
5. **Edit & resubmit.** The marketer changes the copy and clicks *Save & resubmit*, and the template goes back to the front of the queue:
   - A re-categorised template gets a new version name (`_v2`), because Meta keeps the old one.
   - A rejected template on Meta direct is edited in place.
6. **WebEngage.** If a template endpoint is configured, the portal pushes the template automatically. Otherwise the template shows the exact values to add in WebEngage (WhatsApp → Templates → Add Template), and the marketer confirms with the WebEngage template name or ID.
7. **Campaign set-up and launch** stay in WebEngage, done by a person. This is the next phase.

Simulation mode (the default) runs the whole flow without calling anyone. UTILITY copy with promotional wording comes back as MARKETING, as Meta would classify it.

## Feasibility (public docs, Nov 2026)
| Step | Feasible by API? |
|---|---|
| Submit template to Meta, read status, webhooks | **Yes:** Meta Graph `POST /{WABA_ID}/message_templates`, `GET /{template_id}`, `message_template_status_update` |
| Submit via TrustSignal / Route Mobile | **Ask the vendor.** Neither publishes a WhatsApp template-create API (TrustSignal documents SMS; Route Mobile's public template API is RCS). The adapter takes their create and status URLs, auth style and response field names. |
| Add approved template to WebEngage | **No public API.** WebEngage's REST API covers users, events, transactional campaigns, business events, journeys and surveys. WhatsApp templates are added in the dashboard (*Add Template*; in-dashboard *Create Template* exists for Infobip). Ask your WebEngage CSM for a private endpoint and paste it in Settings; until then the guided manual step is used. |
| Create the WhatsApp campaign in WebEngage | **No public API.** Same limitation. Next phase: a guided set-up sheet built from the Naming Structure column. |

## What we need to go live
Fill these in under **Settings**. They are stored only in `crm-portal/data/settings.json` (chmod 600, git-ignored).

| System | Needed |
|---|---|
| **TrustSignal** or **Route Mobile** | WhatsApp template **create** URL and **status** URL, API key and how it is sent, WABA ID, sender number, response field names for id / status / category / reason, and optionally a webhook secret. Ask the vendor whether caller IPs are allow-listed. |
| **Meta Cloud API** (alternative) | WABA ID, sender number, a System User token with `whatsapp_business_management`, App ID (header image upload), App Secret (webhook signature). |
| **WebEngage** | License code, REST API key (India DC `api.in.webengage.com`), the WSP name exactly as integrated, and a template endpoint if WebEngage provides one. |
| **Webhooks** (optional) | A public HTTPS URL forwarding to `/webhooks/<vendor>`. Polling works without it. |

## Files
- `server.py`: API, CSV import/export, template library, validation, vendor and WebEngage adapters, the queue worker, the poller and webhooks
- `static/index.html`, `static/styles.css`, `static/app.js`: the UI
- `data/`: calendar, settings and audit log (git-ignored)
