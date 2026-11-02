# Snapmint CRM Campaign Portal & Content Agent Handover
**Project:** AI-Assisted CRM Campaign Execution Platform  
**Target Organization:** Snapmint (Fintech / BNPL, Mumbai, India)  
**System Architecture:** **Single AI Agent (Content Agent)** + **Deterministic APIs & Scripts** + **Human Launch Gate**  
**Current Date:** November 2026

---

## 1. Executive Summary & Simplified Architecture

### The Core Principle
We do **NOT** need an over-engineered multi-agent swarm. We only need **ONE single AI agent**:
* **The Content Agent (LLM):** Generates high-converting marketing copy variants, variables (`{{1}}`, `{{2}}`), CTA text, and category classification from brief/segment inputs.

**Everything else is purely API-driven, script-driven, or human-driven:**
1. **Content Generation:** ➔ **AI Agent** (Claude Sonnet on AWS Bedrock Mumbai `ap-south-1`).
2. **WhatsApp Template Submission:** ➔ **Deterministic API Call** (TrustSignal / Route Mobile).
3. **Approval Status Tracking:** ➔ **Deterministic Webhook Listener** (Meta Cloud $\to$ TrustSignal $\to$ Portal).
4. **WebEngage Sync:** ➔ **Deterministic REST API Call** (WebEngage Templates API).
5. **SMS / DLT Whitelisting:** ➔ **Human-Entered DLT ID + Script Hash Matching** (TRAI compliant; no OTP bypass).
6. **Campaign Launch:** ➔ **Human-Only Gate** in WebEngage (Hard governance rule).

```
┌────────────────────────────────────────────────────────────────────────┐
│                        1. CALENDAR PORTAL UI                           │
│     (19-Column CRM Spreadsheet Layout + Real-Time WSP/WebEngage UI)     │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                  ┌─────────────────┴─────────────────┐
                  ▼                                   ▼
       [Human Marketer Inputs]             [1. THE ONLY AI AGENT]
      Product, Segment, Date, Time,         Bedrock Claude Sonnet (Mumbai)
        Offer Guidance / Hook              Generates Comms A, Comms B,
                  │                         CTA Text, Naming & Category
                  │                                   │
                  └─────────────────┬─────────────────┘
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                     2. DETERMINISTIC API & SCRIPT PIPELINE             │
│                                                                        │
│  [Script: DLT Validator]        [API: TrustSignal Approval]            │
│   Matches SMS body against       POST /v1/whatsapp/templates           │
│   human-whitelisted DLT IDs             │                              │
│                                         ▼                              │
│                                 [Meta Automated Review]                │
│                                         │                              │
│                                         ▼                              │
│                                 [Webhook Callback]                     │
│                                 Status = APPROVED                      │
│                                         │                              │
│                                         ▼                              │
│                                 [API: WebEngage Template Sync]         │
│                                 POST /v1/accounts/{id}/templates       │
│                                 (Links template to TrustSignal)        │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                        3. HUMAN LAUNCH GATE                            │
│           Marketer reviews verified draft in WebEngage & clicks        │
│                             "LAUNCH CAMPAIGN"                          │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Hard Governance & Regulatory Rules

1. **Human-Only Launch Authority:** Scripts and AI agents **never** get launch permission. They stage verified drafts in WebEngage. A human marketer always reviews and presses "Launch".
2. **TRAI Telecom DLT Regulation (Vilpower):**
   * TRAI mandates human POC two-factor OTP + CAPTCHA for all Vilpower portal logins.
   * **There is NO public API for automated DLT template whitelisting.**
   * **Solution:** Human POC logs in to Vilpower, gets the DLT Template ID, and inputs it into our portal. A local Python script validates that the SMS text matches the approved DLT template hash.
3. **Data Residency & Zero Customer PII:**
   * All inference runs in AWS Mumbai (`ap-south-1`).
   * No customer phone numbers, names, or financial data are sent to LLMs—only aggregate segment definitions (e.g. `Cart_Abandoners_24h`).

---

## 3. The 2-Step Chained Automation Flow (WSP ➔ WebEngage)

### Step 1: Trigger TrustSignal Template Approval API
When content, CTA, and target URL are ready, the portal or backend script fires an API call to TrustSignal:
* **Endpoint:** `POST https://api.trustsignal.io/v1/whatsapp/templates`
* **Headers:**
  ```http
  Authorization: Bearer <TRUSTSIGNAL_API_KEY>
  Content-Type: application/json
  ```
* **Payload:**
  ```json
  {
    "name": "cart_recovery_mobile_v1",
    "category": "MARKETING",
    "language": "en",
    "components": [
      {
        "type": "HEADER",
        "format": "IMAGE",
        "example": { "header_handle": ["https://cdn.snapmint.com/banners/diwali_mobile.png"] }
      },
      {
        "type": "BODY",
        "text": "Hello {{1}}! Your smartphone is waiting. Complete checkout with ₹0 downpayment and easy EMIs of {{2}}!",
        "example": { "body_text": [["Rahul", "₹3,166"]] }
      },
      {
        "type": "BUTTONS",
        "buttons": [
          {
            "type": "URL",
            "text": "Complete Order Now",
            "url": "https://snapmint.com/cart?utm_source=wa&utm_medium=crm"
          }
        ]
      }
    ]
  }
  ```
* **Response:** Returns `HTTP 200` with `status: "PENDING_APPROVAL"`.
* **Meta Webhook Relay:** When Meta finishes automated review (1–5 minutes), TrustSignal calls our webhook endpoint:
  ```json
  {
    "event": "message_template_status_update",
    "template_name": "cart_recovery_mobile_v1",
    "status": "APPROVED",
    "category": "MARKETING"
  }
  ```
  The portal updates the campaign row badge to **`APPROVED`**.

---

### Step 2: Trigger WebEngage API to Register Approved Template
As soon as the template is approved, the portal/script triggers WebEngage to register the template under Snapmint's TrustSignal integration:
* **Endpoint:** `POST https://api.webengage.com/v1/accounts/{license_code}/templates`
* **Headers:**
  ```http
  Authorization: Bearer <WEBENGAGE_REST_API_KEY>
  Content-Type: application/json
  ```
* **Payload:**
  ```json
  {
    "channel": "WHATSAPP",
    "name": "cart_recovery_mobile_v1",
    "wsp_connector": "TrustSignal",
    "category": "MARKETING",
    "language": "en",
    "components": {
      "header_image": true,
      "body": "Hello {{1}}! Your smartphone is waiting. Complete checkout with ₹0 downpayment and easy EMIs of {{2}}!",
      "buttons": [
        {
          "type": "URL",
          "text": "Complete Order Now",
          "url": "https://snapmint.com/cart?utm_source=wa&utm_medium=crm"
        }
      ]
    }
  }
  ```
* **Response:** Returns `HTTP 201 Created` with `webengage_template_id: "we_wa_tpl_98472918"`.
* **Result:** The template immediately appears inside **WebEngage Campaign Builder** under TrustSignal sender credentials, ready for the marketer to select and launch.

---

## 4. Current Repository State & Working Code

| File | Purpose | Status |
| :--- | :--- | :--- |
| [`portal/index.html`](file:///Users/gobathi.p/Snap_projects/CRM%20Agent/portal/index.html) | Interactive Campaign Calendar with exact 19-column spreadsheet schema, CSV import/export, WhatsApp phone mockup, and 2-step TrustSignal $\to$ WebEngage execution UI | **Working & Tested** |
| [`portal/server.py`](file:///Users/gobathi.p/Snap_projects/CRM%20Agent/portal/server.py) | Lightweight Python 3 local proxy server (`http://localhost:8000`) with CORS bypass, TrustSignal mock dispatch, and WebEngage sync mock | **Working & Tested** |
| [`docs/Snapmint_CRM_Platform_Document_1_Overall_Agent_Plan.docx`](file:///Users/gobathi.p/Snap_projects/CRM%20Agent/docs/Snapmint_CRM_Platform_Document_1_Overall_Agent_Plan.docx) | Word document master plan for management review | **Complete** |
| [`docs/Snapmint_CRM_Platform_Document_2_Phase_1_Detailed_Plan.docx`](file:///Users/gobathi.p/Snap_projects/CRM%20Agent/docs/Snapmint_CRM_Platform_Document_2_Phase_1_Detailed_Plan.docx) | Word document detailed Phase 1 execution plan | **Complete** |
| [`docs/01-OVERALL-AGENT-PLAN.md`](file:///Users/gobathi.p/Snap_projects/CRM%20Agent/docs/01-OVERALL-AGENT-PLAN.md) | Markdown master plan | **Complete** |
| [`docs/02-PHASE-1-DETAILED-PLAN.md`](file:///Users/gobathi.p/Snap_projects/CRM%20Agent/docs/02-PHASE-1-DETAILED-PLAN.md) | Markdown Phase 1 plan | **Complete** |

---

## 5. The Exact 19-Column Spreadsheet Schema

The portal table strictly matches the CRM team's real operational columns:
1. `Day` (e.g. Monday)
2. `Date` (YYYY-MM-DD)
3. `Product` (0% EMI BNPL Mobiles, Personal Loan Cash, Partner Flash Sale, Repayment Reminder)
4. `Segment Name` (e.g. `Cart_Abandoners_24h`)
5. `Naming Structure` (e.g. `20261102_BNPL_CART_WA_MKTG_V1`)
6. `Segments to Exclude` (e.g. `Defaulted_Users, DND`)
7. `Start Age` (e.g. 21)
8. `End Age` (e.g. 50)
9. `Gender` (All / Male / Female)
10. `Location` (Pan India / Tier 1)
11. `Campaign Type` (Triggered / Promotional / Seasonal)
12. `Channel` (WhatsApp / SMS / Push)
13. `EXP` (A/B Test Variant code)
14. `Comms A` (Headline / Short Variant)
15. `Comms B` (Template Body with `{{1}}`, `{{2}}`)
16. `Time` (e.g. 11:00 AM)
17. `Banner_Url` (CDN Asset Link)
18. `Comments` (Marketer Guidance & WebEngage Template ID sync notes)
19. `Size` (Target Audience Count, e.g. 250,000)

*Plus WhatsApp execution fields: `WSP Vendor`, `WABA Number`, `Template Category` (Utility/Marketing), `Template Name`, `CTA Text`, `Target URL`, and `Status`.*

---

## 6. What Claude Needs to Do Next

When you start the next conversation with Claude, paste this prompt:

```markdown
I am continuing the Snapmint CRM Campaign Platform project. 
All architecture, schemas, and local code are documented in `docs/SNAPMINT-CRM-HANDOVER.md`.

Key Context:
1. We DO NOT need multiple agents. We only have ONE agent: the Content Agent (Claude Sonnet 5 on Bedrock Mumbai).
2. Everything else is deterministic:
   - WSP template submission to TrustSignal/Route Mobile via REST API.
   - Meta approval status captured via webhook.
   - Pushing approved templates to WebEngage via WebEngage REST API.
   - SMS DLT compliance handled via human OTP login into Vilpower + script hash matching.
   - Human clicks "Launch" inside WebEngage (AI never launches).
3. The local portal is live at `portal/index.html` and `portal/server.py`.

Next Goal:
Help me implement the real API calls in `portal/server.py` replacing the mock simulations:
1. Real TrustSignal API endpoint & webhook handler.
2. Real WebEngage template sync API call.
3. Bedrock `boto3` integration in Mumbai (`ap-south-1`) for the Content Agent to auto-fill the calendar row.
```
