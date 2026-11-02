# Snapmint CRM Campaign Execution Platform: Documentation Suite

Welcome to the technical and operational documentation repository for the **Snapmint CRM Campaign Execution Platform**. This system is an enterprise-grade campaign preparation and orchestration platform designed specifically for Snapmint’s CRM and Retention engineering teams.

---

## 1. The Two Primary Deliverables for Management

Per executive requirements, the documentation is divided into **two dedicated documents**:

| Deliverable | Formats | Purpose & Scope |
|---|---|---|
| **Document 1: Overall Agent Plan** | • **[Word Document (.docx)](file:///Users/gobathi.p/Snap_projects/CRM%20Agent/docs/Snapmint_CRM_Platform_Document_1_Overall_Agent_Plan.docx)**<br>• [Markdown Specification](file:///Users/gobathi.p/Snap_projects/CRM%20Agent/docs/01-OVERALL-AGENT-PLAN.md)<br>• [Printable HTML / PDF](file:///Users/gobathi.p/Snap_projects/CRM%20Agent/docs/document-1-overall-plan.html) | **The Master Plan from Content to Calendar Planning (Phases 0 to 5):**<br>• Executive vision & master system mindmap<br>• The 8 non-negotiable hard governance rules (human-only launch)<br>• All 8 agents (Content, Creative, WhatsApp, SMS/DLT, WebEngage, Debugging, Analytics, Planning)<br>• 12-month wave roadmap & autonomy ladder |
| **Document 2: Phase 1 Detailed Blueprint** | • **[Word Document (.docx)](file:///Users/gobathi.p/Snap_projects/CRM%20Agent/docs/Snapmint_CRM_Platform_Document_2_Phase_1_Detailed_Plan.docx)**<br>• [Markdown Specification](file:///Users/gobathi.p/Snap_projects/CRM%20Agent/docs/02-PHASE-1-DETAILED-PLAN.md)<br>• [Printable HTML / PDF](file:///Users/gobathi.p/Snap_projects/CRM%20Agent/docs/document-2-phase-1-detailed-plan.html) | **The Working Backbone, Content Engine & Whitelisting:**<br>• Building the Calendar Portal (Product, Segment, Event, CTA, and Custom Comments)<br>• Connecting to AWS Bedrock Mumbai (`in.anthropic.claude-sonnet-5`)<br>• **WhatsApp Service Provider (WSP) API Feasibility:** Route Mobile JWT API + Infobip + real-time status & category tracking via webhooks (`message_template_status_update`)<br>• **Vilpower DLT Reality:** Can we approve SMS templates via API? (TRAI regulatory ban on direct public API + aggregator whitelisting + SHA-256 local hash ledger)<br>• **Data Collection & Training Feasibility in Mumbai:** Claude vs Amazon Nova in Mumbai; why In-Context RAG wins; step-by-step training blueprint<br>• Phase 1 requirements & step-by-step procedure (Weeks 4 to 10) |

---

## 2. Interactive Portal & Simulator
* **[Interactive Brief Portal & Simulator](file:///Users/gobathi.p/Snap_projects/CRM%20Agent/docs/executive-brief-portal.html)**: Interactive web dashboard featuring Mermaid mindmaps, tab navigation, feasibility scorecards, and a **Live Campaign Simulator**.

---

## 3. Reference Engineering Specifications
All granular architectural specifications, database DDL schemas, state machines, and connector spike runbooks are archived in the reference folder:
* **[reference_specs/](file:///Users/gobathi.p/Snap_projects/CRM%20Agent/docs/reference_specs)**:
  - `01-management-brief.md`: Detailed 10-page architecture brief
  - `02-architecture.md`: 6-layer architecture and C4 diagrams
  - `03-data-model.md`: PostgreSQL schema, indexing, and DLT hashing
  - `04-workflow-and-idempotency.md`: Step Functions state machine and ASL JSON
  - `05-content-library-and-retrieval.md`: Bedrock Knowledge Base RAG setup
  - `06-agents/`: Detailed agent specs (Content, WhatsApp, SMS/DLT, WebEngage, Debugging, Analytics, Planning)
  - `07-integrations/`: Connector specs (WebEngage spike, WhatsApp providers, Vilpower DLT, Databricks)
  - `08-evaluation.md`: Golden benchmark dataset and CI regression gates
  - `09-security-and-governance.md`: 4-role IAM separation and DPDP Act compliance
  - `10-execution-plan.md`: 12-month engineering delivery plan
  - `11-rollout-and-operations.md`: Phased rollout (Shadow to Trusted) and runbooks
  - `12-risk-register.md`: Program risk matrix and mitigations
  - `13-verification-checklist.md`: Week 1 AWS CLI commands and vendor interview guides
