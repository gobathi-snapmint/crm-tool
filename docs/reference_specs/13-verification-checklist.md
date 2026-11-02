# Week 1 Verification Checklist & Discovery Runbook

## Purpose
This document provides actionable command-line scripts, AWS CLI validation routines, security questionnaires, and vendor interview templates for Week 1 of Phase 0 to verify all underlying assumptions across AWS Bedrock, Security, WebEngage, WhatsApp BSPs, and DLT.

## Section Headings
1. Purpose & Week 1 Execution Protocol
2. AWS Bedrock Infrastructure & Inference Profile Verification (ap-south-1)
   - Exact CLI Commands: `aws bedrock list-inference-profiles`, `aws bedrock list-foundation-models`
   - Quota Verification: TPM and RPM limits in Mumbai
   - CloudTrail Inference Region Audit Setup
3. Snapmint Security & Compliance Questionnaire
   - "India-Only" (`ap-south-1` + `ap-south-2`) vs "Mumbai-Only" Policy Clarification
   - Non-PII Data Minimization Boundary Approval
4. WebEngage Technical Investigation Checklist
   - Vendor Inquiries: Undocumented Draft APIs, Private MCP Servers, API Roadmap
   - Browser Automation Approval & Isolation Boundary
5. WhatsApp Business Solution Provider (BSP) Technical Checklist
   - Route Mobile, Gupshup, Onexctel, TrustSignal Template APIs
   - Webhook Delivery Guarantees & Category Rejection Payloads
6. DLT / Vilpower Technical Checklist
   - Entity ID, Header ID, Template API Status, Batch Sync File Formats
7. Decision Gate Synthesis & Go/No-Go Criteria for Week 4
