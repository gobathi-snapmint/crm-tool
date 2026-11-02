# Agent Framework & Operational Standard

## Purpose
This document establishes the universal agent loop, tool execution protocol, auto-repair cycles, and governance boundaries shared by all seven specialized agents in the Snapmint CRM Campaign Execution Platform.

## Section Headings
1. Universal Agent Architecture & Execution Loop
   - Standard 6-Step Loop: Context Load -> Model Prompt -> Deterministic Validation -> Auto-repair (Max 2x) -> Blocked/Escalation -> Audit Commit
2. The Agent Security Boundary: No Customer PII
3. Foundation Model Assignment & Routing Matrix (Bedrock Mumbai)
4. Standard JSON Schema Structure & Tool Contract
5. Error Handling, Escalation, and Blocked State Protocol
6. Agent Inventory Summary (01 through 07)
7. Assumptions & VERIFY Checklist
