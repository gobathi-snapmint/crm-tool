# Agent 03: SMS & DLT Compliance Agent

## Purpose
This document specifies the SMS and DLT Compliance Agent responsible for matching copy variants against pre-approved TRAI Distributed Ledger Technology (DLT) templates, enforcing exact text hashing, calculating GSM-7/UCS-2 character limits, and managing the manual attestation packaging flow.

## Section Headings
1. Agent Role & Boundary Definition
2. TRAI DLT Regulatory Framework & Governance Rules
   - Principal Entity (PE ID), Sender Header ID, Template ID Registration
   - The No-Bypass Rule: No Automated CAPTCHA/OTP Solving
3. Template Matching & Exact Hash Verification Engine
   - SHA-256 Normalized Text Hashing
   - Variable Extraction & Character Budget Rules
4. Character Encoding & Split-Message Calculator (GSM-7 vs UCS-2)
5. Structured Output JSON Schema & System Prompt Skeleton
6. Manual DLT Packaging Workflow (For Unregistered Templates)
7. Escalation, Failure Handling & Blocked State Conditions
8. Comprehensive End-to-End Execution Trace Example
9. Assumptions & VERIFY Checklist
