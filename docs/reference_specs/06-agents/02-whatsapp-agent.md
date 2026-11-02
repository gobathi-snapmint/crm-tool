# Agent 02: WhatsApp Template & Policy Agent

## Purpose
This document specifies the WhatsApp Template & Policy Agent responsible for formatting WhatsApp message templates, classifying them under Meta policy (Utility vs Marketing), enforcing anti-disguise guardrails, running dual-model consensus reviews, and managing provider submission and status tracking.

## Section Headings
1. Agent Role & Boundary Definition
2. Meta Policy Enforcement: Strict Utility vs Marketing Governance
   - Anti-Disguise Guardrails: Why Promotional Content Cannot be Utility
   - Meta Business Policy 2026 Guidelines & Rejection Penalties
3. Dual-Model Consensus Review Architecture
   - Primary Classifier (Claude Sonnet 5) vs Secondary Arbiter (GPT-5.6 Terra)
   - Disagreement Routing to Human Reviewer
4. Structured Output JSON Schema (Template Body, Buttons, Variable Mapping)
5. System Prompt Skeleton & Few-Shot Classification Prompts
6. Deterministic Validation Suite (Variable Formats, Header Constraints, CTA URLs)
7. Provider API Submission & Webhook Status Tracking
8. Escalation, Failure Handling & Blocked State Conditions
9. Comprehensive End-to-End Execution Trace Example
10. Assumptions & VERIFY Checklist
