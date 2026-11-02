# Technical Prompt for Claude: CRM Campaign Calendar Portal & WSP-to-WebEngage Feasibility

```markdown
# ROLE & CONTEXT
You are a Principal Solutions Architect and Senior Full-Stack Engineer working with Snapmint (an Indian BNPL / Fintech company based in Mumbai). 
We are building a central **CRM Campaign Calendar Portal** to manage our multi-channel communication (WhatsApp, SMS, Push). 

Currently, our marketing team manually fills a 19-column campaign spreadsheet, manually creates WhatsApp templates in WSP portals (Route Mobile / TrustSignal), waits for Meta approval, and then manually re-creates the template inside WebEngage. 

We want to automate this workflow with a **Single AI Content Agent** and a **Deterministic 2-Step Chained API Pipeline**.

---

## SECTION 1: CORE FEASIBILITY QUESTIONS TO EVALUATE

Please evaluate and answer the technical feasibility of the following three core questions:

### Question 1: WSP WhatsApp Template Approval Feasibility
* Can we programmatically submit WhatsApp templates (Body with `{{1}}`, `{{2}}`, Header Image, CTA Button Text, Dynamic Target URL, Category: `MARKETING` or `UTILITY`) for Meta approval via WSPs like **TrustSignal** (`api.trustsignal.io`) or **Route Mobile** (`apis.rmlconnect.net`)?
* How does authentication work (Bearer tokens, API keys)? Does TrustSignal accept calls from any server URL, or does it enforce IP whitelisting?
* How do we capture the approval status in real-time? Is it via webhooks (`message_template_status_update`) or polling? How do we authenticate incoming webhooks (HMAC SHA-256 signatures)?

### Question 2: WebEngage Automated Template Sync Feasibility
* Once the template receives `APPROVED` status from Meta/WSP, can we automatically trigger an API call to **WebEngage** (`POST /v1/accounts/{license_code}/templates`) to register and map this approved template under our TrustSignal/Route Mobile connector?
* How does WebEngage handle the mapping between the WSP-approved template name and the WebEngage template registry?
* Once synced via API, will the template be immediately selectable inside WebEngage Campaign Builder for marketers to launch campaigns to targeted segments?

### Question 3: Telecom DLT SMS Regulation Feasibility (Vilpower / TRAI)
* Can we automate SMS template whitelisting via an open API on telecom DLT platforms like Vilpower?
* *Context:* As per TRAI TCCCPR regulations, Vilpower requires mandatory human POC two-factor OTP + CAPTCHA for all logins. 
* Evaluate whether an automated API exists, and if not, how the portal should handle SMS compliance (e.g., human logs in via OTP, inputs the approved DLT ID, and a local script verifies the SHA-256 hash of the message text).

---

## SECTION 2: SYSTEM ARCHITECTURE & GOVERNANCE RULES

### Hard Governance Rules (Non-Negotiable)
1. **Single AI Agent (Content Agent Only):** We DO NOT want a complex multi-agent swarm. We only want ONE agent: the **Content Agent** (powered by Claude Sonnet on AWS Bedrock in Mumbai `ap-south-1`). Everything else must be deterministic REST APIs, Python/JS scripts, or human actions.
2. **Human-Only Launch Gate:** AI agents and automated scripts **NEVER** get campaign-launch permissions in WebEngage or WSP dashboards. The platform prepares, validates, and stages drafts; human marketers review and click launch.
3. **Data Residency & Zero Customer PII:** All LLM inference must reside in AWS Mumbai (`ap-south-1`). No customer PII (phone numbers, names, Aadhaar) may be sent to LLMs—only aggregate segment characteristics (e.g., `Cart_Abandoners_24h`).

### The 2-Step Chained Workflow
```
[Marketer or AI Agent inputs copy, variables, CTA, and URL]
                           │
                           ▼
[Step 1: TrustSignal API Call] ──► POST https://api.trustsignal.io/v1/whatsapp/templates
                           │       (Submits template spec to Meta for review)
                           ▼
                  [Meta Automated Review]
                           │
                           ▼
                  [Webhook Callback] ──► Status becomes "APPROVED"
                           │
                           ▼
[Step 2: WebEngage API Call] ────► POST https://api.webengage.com/v1/accounts/{license_code}/templates
                                   (Maps approved template to TrustSignal connector in WebEngage)
                           │
                           ▼
        [Marketer inspects draft in WebEngage & clicks "Launch"]
```

---

## SECTION 3: CALENDAR PORTAL REQUIREMENTS

Please design and implement the CRM Campaign Calendar Portal adhering to the following specifications:

### 1. The Exact 19-Column Calendar Schema
The portal must display, search, filter, and export/import the CRM team's exact 19 columns:
1. `Day` (e.g., Monday)
2. `Date` (YYYY-MM-DD)
3. `Product` (0% EMI BNPL Mobiles, Personal Loan Cash, Partner Flash Sale, EMI Repayment Reminder)
4. `Segment Name` (e.g., `Cart_Abandoners_24h`)
5. `Naming Structure` (e.g., `20261102_BNPL_CART_WA_MKTG_V1`)
6. `Segments to Exclude` (e.g., `Defaulted_Users, DND`)
7. `Start Age` (e.g., 21)
8. `End Age` (e.g., 50)
9. `Gender` (All / Male / Female)
10. `Location` (Pan India / Tier 1)
11. `Campaign Type` (Triggered / Promotional / Seasonal)
12. `Channel` (WhatsApp / SMS / Push)
13. `EXP` (A/B Test Variant Code)
14. `Comms A` (Headline / Short Variant)
15. `Comms B` (Template Body with `{{1}}`, `{{2}}`)
16. `Time` (e.g., 11:00 AM)
17. `Banner_Url` (CDN Asset Image Link)
18. `Size` (Audience Count, e.g., 250,000)
19. `Comments` (Marketer Guidance & Sync Notes)

*Plus WhatsApp execution fields: `WSP Vendor`, `WABA Number`, `Template Category` (UTILITY / MARKETING), `Template Name`, `CTA Text`, `Target URL`, and `Approval Status`.*

### 2. Local Architecture (Zero Heavy Dependencies)
* **Frontend:** Clean, responsive, single-page application (`index.html`) using Vanilla CSS and JavaScript. Must include search, multi-filter, CSV Export/Import, and local state persistence via browser `localStorage`.
* **Phone Mockup:** Real-time visual WhatsApp preview showing header images, dynamic variable replacement (`{{1}}` $\to$ "Rahul"), and CTA buttons.
* **Backend:** Zero-dependency Python 3 proxy server (`server.py`) running on `http://localhost:8000` to prevent browser CORS issues when communicating with TrustSignal and WebEngage APIs.

### 3. Interactive 2-Step Chained Pipeline UI
Inside the row editor modal, provide a dedicated tab for **WSP API Approval & WebEngage Push**:
* **Visual Progress Badges:** `1. Draft` $\to$ `2. TrustSignal Meta` $\to$ `3. Approved` $\to$ `4. WebEngage Sync`.
* **Step 1 Button:** "Send Template to TrustSignal for Approval" $\to$ displays request payload and returns simulated/live `HTTP 200 PENDING_APPROVAL`, followed by webhook update to `APPROVED`.
* **Step 2 Button:** Automatically reveals "Push Approved Template to WebEngage" $\to$ sends template spec to WebEngage REST API, receives WebEngage Template ID, and updates the calendar row.

---

## SECTION 4: DELIVERABLES EXPECTED

Please provide:
1. **Feasibility Verdict & Technical Analysis:** Clear answers to the three core questions (TrustSignal WSP API, WebEngage Sync API, and Vilpower DLT regulation).
2. **API Request & Response Contracts:** Exact cURL commands, endpoints, headers, and JSON payloads for:
   * TrustSignal template creation (`POST /v1/whatsapp/templates`).
   * Meta approval webhook payload (`message_template_status_update`).
   * WebEngage template registration (`POST /v1/accounts/{license_code}/templates`).
3. **Working Code & Architecture:**
   * Review or refine the implementation in `portal/index.html` and `portal/server.py`.
   * Outline how the Python backend connects to AWS Bedrock Mumbai (`boto3`) to power the Content Agent auto-fill button.
```
