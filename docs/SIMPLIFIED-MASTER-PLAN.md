# Snapmint AI CRM Platform: Simplified Master Plan (Phase-by-Phase)

**Target Audience:** Leadership, VP of Product, Head of CRM, Tech Leads  
**Purpose:** A clear, non-technical, phase-wise roadmap explaining what we are building, why, and how it delivers value.

---

## 1. Executive Summary: What Are We Building?

Today, Snapmint’s CRM and Retention team spends **24 to 48 hours** launching a single campaign because marketers have to jump between 4 different systems:
1. **Telecom DLT Portal (Vilpower):** Checking SMS template IDs and character limits.
2. **WhatsApp Provider Dashboard (Route Mobile / Gupshup):** Creating message templates and waiting for Meta approval.
3. **WebEngage:** Building the campaign, pasting text, adding UTM links, and attaching banner images.
4. **Internal Spreadsheets & Databricks:** Verifying product EMI rules and tracking conversions.

**Our Goal:** Replace this friction with **ONE Unified CRM Campaign Calendar Portal**.
A marketer fills a single brief (Product line, Audience segment, Trigger event, CTA, and optional Custom Comments). The system automatically writes the copy, renders brand graphics, checks DLT & WhatsApp policies, prepares the WebEngage draft, and presents a pre-flight QA report. 

**The Golden Rule:** AI agents **NEVER** launch campaigns autonomously. A human campaign manager must review the final draft and click the launch button.

---

## 2. High-Level Project Mindmap

```
SNAPMINT CRM PLATFORM
│
├── INPUT LAYER (The Portal)
│   ├── Campaign Calendar (Month / Week / Day view)
│   ├── Brief Form (Product Line, Segment, Event, CTA)
│   └── Custom Instructions Box (Marketer's specific notes/offers)
│
├── INTELLIGENCE LAYER (AWS Bedrock Mumbai)
│   ├── Phase 1: Content & Copy Agent (English, Hindi, Hinglish)
│   ├── Phase 2: Creative Renderer (Brand tokens to PNG in <400ms)
│   ├── Phase 3: WhatsApp Approval Agent (Dual-Model Policy Check)
│   ├── Phase 4: SMS / DLT Matcher (SHA-256 Hash & GSM-7 Calculator)
│   └── Phase 5: WebEngage Package Builder (Guided Checklist & Diff)
│
├── GUARDRAIL LAYER (Deterministic Code & Databricks)
│   ├── Character Limit & UTM Parameter Validators
│   ├── Zero Customer PII in Prompts (Aggregates & Rules Only)
│   └── Real Conversion Metrics from Databricks SQL (No AI math)
│
└── GOVERNANCE LAYER (Human in the Loop)
    ├── Unified Pre-Flight QA Report
    └── Strict Human-Only Launch Gate
```

---

## 3. Phase-by-Phase Execution Roadmap

Here is the entire plan broken down into clear, manageable phases:

```
+---------------------------------------------------------------------------------------------------------+
| PHASE-BY-PHASE ROADMAP OVERVIEW                                                                         |
+---------+------------------------+-------------+--------------------------------------------------------+
| Phase   | Focus Area             | Timeline    | Core Deliverable / Outcome                             |
+---------+------------------------+-------------+--------------------------------------------------------+
| Phase 0 | Foundations & Spikes   | Weeks 0 - 4 | Golden eval dataset (50 past campaigns), Bedrock setup |
| Phase 1 | The Portal & Content   | Weeks 4 - 10| Working Portal + Bedrock Content Agent + Creative Spec |
| Phase 2 | WhatsApp & SMS Auto    | Weeks 10- 24| Automated Route Mobile API submit & DLT Hash Match     |
| Phase 3 | Multi-Language & Debug | Weeks 20- 34| Full Hinglish/Hindi support & Automated API Debugging  |
| Phase 4 | Databricks Feedback    | Weeks 30- 40| Lakehouse SQL join; Top 10% campaigns feed AI library  |
| Phase 5 | Autonomous Planning    | Weeks 38- 52| AI proposes monthly calendar based on user fatigue     |
+---------+------------------------+-------------+--------------------------------------------------------+
```

### Phase 0: Foundations & Technical Spikes (Weeks 0 – 4)
* **Goal:** Set up AWS Bedrock infrastructure and test vendor integration capabilities before building.
* **Key Tasks:**
  1. Set up AWS Bedrock India Geographic inference profile (`in.anthropic.claude-sonnet-5`) in Mumbai (`ap-south-1`).
  2. Assemble a **Golden Benchmark Dataset** of 50 to 100 historical Snapmint campaigns with human ratings.
  3. Conduct technical spikes with WebEngage API, Route Mobile WhatsApp API, and Vilpower DLT.
  4. Seed the Content Library with the top 200 best-performing past campaign messages.
* **Gate at Week 4:** Security sign-off on India-only data residency and confirmed API boundaries.

### Phase 1: The Campaign Portal & Content Agent (Weeks 4 – 10)
* **Goal:** Build the central portal UI and connect it to Bedrock to produce verified multi-channel copy variants and creative specs from a calendar brief.
* **Key Tasks:**
  1. Build the React + FastAPI Campaign Portal (Calendar view + Campaign Brief submission form).
  2. Add inputs for Product Line, Audience Type, Trigger Event, CTA URL, and **Custom Comments / Marketer Notes**.
  3. Connect FastAPI backend to AWS Bedrock in Mumbai to generate 3 copy options (English, Hindi, Hinglish).
  4. Build the Headless Chromium rendering engine in our Mumbai VPC to generate brand PNG banners in &lt;400ms.
  5. Deliver a unified human review queue where marketers can inspect copy, edit text, and see character limits.
* **Gate at Week 10:** 10 real Snapmint campaigns created and reviewed entirely inside the portal with zero policy errors.

### Phase 2: Automated WhatsApp & SMS/DLT Connectors (Weeks 10 – 24)
* **Goal:** Automate external template submissions and compliance checks.
* **Key Tasks:**
  1. Connect Route Mobile / Infobip API to submit WhatsApp templates programmatically.
  2. Implement **Dual-Model Consensus** (Claude Sonnet 5 + GPT-5.6 Terra) to ensure marketing copy is never mistakenly submitted as Utility.
  3. Implement **SHA-256 DLT text matching** for SMS to ensure 100% compliance with TRAI regulations.
  4. Build the WebEngage Guided Execution Package and automated read-back diff checker.
* **Gate at Week 24:** WhatsApp first-pass approval rate &gt;= 90%; DLT text mismatches drop to 0%.

### Phase 3: Regional Breadth & Automated Debugging (Weeks 20 – 34)
* **Goal:** Expand multi-language reach and handle vendor API errors gracefully.
* **Key Tasks:**
  1. Deepen colloquial Hinglish and pure Devanagari Hindi copywriting models.
  2. Add support for Push notifications and In-App message specifications.
  3. Deploy the **Debugging Agent** to analyze vendor error codes (e.g., quota limits, invalid phone numbers) and recommend fixes.
* **Gate at Week 34:** Automated triage resolves &gt;= 60% of common API errors without engineering intervention.

### Phase 4: Databricks Lakehouse Feedback Loop (Weeks 30 – 40)
* **Goal:** Close the learning loop using real business outcomes from Databricks.
* **Key Tasks:**
  1. Connect Databricks SQL Warehouse via PrivateLink to pull delivery rates, CTR, and 30-day BNPL conversion metrics.
  2. Deploy the **Analytics Agent** to draft weekly and monthly performance reports for leadership.
  3. Automatically tag high-performing copy (top 10% conversion) and ingest it into the Bedrock Knowledge Base so future agents learn from winning campaigns.
* **Gate at Week 40:** 100% of campaign performance reports generated deterministically from SQL.

### Phase 5: Capacity-Aware Calendar Planning (Weeks 38 – 52)
* **Goal:** Assist the CRM team in planning future campaigns based on audience fatigue and business targets.
* **Key Tasks:**
  1. Deploy Claude Opus 5 combined with an operations research constraint solver.
  2. Enforce frequency caps (e.g., maximum 2 WhatsApps and 3 SMS messages per customer per week).
  3. Generate proposed weekly and monthly CRM schedules allocating high-converting slots to top merchant promotions.
* **Gate at Week 52:** Marketing team adopts &gt;= 50% of system-proposed calendar schedules.

---

## 4. Summary of What is Automated vs. What is Manual

| Stage | Automated by Platform | Strictly Manual (Human Operator) |
|---|---|---|
| **Brief Creation** | Pulls past campaign benchmarks; auto-fills standard tags | Inputs business target, selects product line & segment, adds custom notes |
| **Copy & Creatives** | Generates 3 copy variants (EN/HI/Hinglish); renders PNG banners | Selects preferred variant; edits copy if needed; approves final image |
| **WhatsApp Compliance**| Dual-model policy check; submits to Route Mobile API | Approves any template categorized as Utility; manages WABA profile |
| **SMS / DLT** | SHA-256 hash match; GSM-7/UCS-2 credit calculation | Submits unregistered templates on Vilpower with OTP/CAPTCHA |
| **WebEngage Drafting** | Generates complete execution spec; verifies read-back diff | Pastes spec into WebEngage dashboard (or uses companion tool) |
| **Campaign Launch** | **BLOCKED: Zero autonomous launch authority** | **Authorized human campaign manager clicks final Launch button** |
| **Post-Launch Analysis**| Pulls SQL metrics from Databricks; writes summary report | Reviews weekly ROI; decides budget allocations for next cycle |

---

## 5. Next Steps

For complete details on how to build the portal, connect it to Bedrock, handle segments and events, and the exact training feasibility, see the companion document:  
👉 **[`docs/PHASE-1-EXECUTION-BLUEPRINT.md`](file:///Users/gobathi.p/Snap_projects/CRM%20Agent/docs/PHASE-1-EXECUTION-BLUEPRINT.md)**
