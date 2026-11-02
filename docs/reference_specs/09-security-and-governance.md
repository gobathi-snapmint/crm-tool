# Security, IAM & Data Governance Specification

## Purpose
This document establishes the comprehensive security architecture, IAM role segregation, Indian data residency controls, cryptographic audit logging, Bedrock Guardrail configurations, and compliance boundaries (DPDP Act, RBI Digital Lending Guidelines) for the Snapmint CRM Campaign Execution Platform.

## Section Headings
1. Core Security Principles & The Non-Negotiable Hard Rules
2. Identity & Access Management (IAM) 4-Role Matrix
   - Role 1: `ContentGenerator` (Model invocation, RAG query, asset generation)
   - Role 2: `TemplateSubmitter` (WhatsApp & SMS external template writes)
   - Role 3: `DraftCreator` (WebEngage campaign creation & read-back)
   - Role 4: `CampaignLauncher` (Exclusive Human-Only Launch Authority)
3. Data Minimization & Zero-Customer-PII Policy
4. Data Sovereignty & Inference-Region Audit Logging
   - India-Only Inference Profiles (`ap-south-1` & `ap-south-2`)
   - AWS CloudTrail Real-Time Region Verification & Alarms
5. Amazon Bedrock Guardrails Specification
   - PII Redaction Filters & Blocked Entity Categories
   - Sensitive Financial Product & Regulatory Policy Filters
6. Cryptographic Audit Trail Architecture (`audit_event` Table & S3 Vault)
7. Human Approval Checkpoints & Operational Attestations
8. Assumptions & VERIFY Checklist
