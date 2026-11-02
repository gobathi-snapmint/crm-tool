# Agent 05: Campaign Debugging & Anomaly Diagnostic Agent

## Purpose
This document specifies the Debugging and Anomaly Diagnostic Agent responsible for triaging failed workflow runs, analyzing external vendor API error responses, identifying configuration regressions, and proposing specific root-cause fixes.

## Section Headings
1. Agent Role & Boundary Definition
2. Failure Ingestion Pipeline & Event Triaging
3. Diagnosis Categories:
   - Vendor API Errors & Quota Exhaustions
   - Template Rejection Diagnoses (Meta & DLT)
   - Configuration & UTM Validation Failures
   - Read-Back Mismatches
4. Tool Definitions & Log Retrieval Boundaries (Zero Customer Data)
5. Structured Output JSON Schema (Root Cause, Impact, Suggested Remediation)
6. System Prompt Skeleton & Diagnostic Prompts
7. Automated Self-Healing Limits vs Human Escalation
8. Comprehensive Diagnostic Trace Example
9. Assumptions & VERIFY Checklist
