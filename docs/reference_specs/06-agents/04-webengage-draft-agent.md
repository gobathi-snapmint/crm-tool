# Agent 04: WebEngage Draft & Execution Spec Agent

## Purpose
This document specifies the WebEngage Draft Agent responsible for generating precise campaign execution specifications, validating payload completeness, orchestrating draft creation (via API spike discovery or guided portal execution), and performing deterministic read-back diff verification.

## Section Headings
1. Agent Role & Boundary Definition
2. WebEngage Integration Reality & Decision Tree
   - Public API Constraints: Lack of Draft Creation Endpoints
   - The Guided Execution Package vs Programmatic Draft Path
3. Execution Specification Payload Structure (Targeting, Channel, Payload, UTM, Caps)
4. Deterministic Read-Back Diff & Verification Algorithm
5. Structured Output JSON Schema & System Prompt Skeleton
6. Fallback Browser Automation Architecture (Design, Security, Sandbox Isolation)
7. Escalation, Failure Handling & Blocked State Conditions
8. Comprehensive End-to-End Execution Trace Example
9. Assumptions & VERIFY Checklist
