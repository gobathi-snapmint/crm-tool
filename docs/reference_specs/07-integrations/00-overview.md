# Integrations & Connectors Architecture

## Purpose
This document establishes the universal Connector Interface, standardized execution statuses, timeout protocols, and test double (fake connector) standards for all third-party and internal integrations in the Snapmint CRM Campaign Execution Platform.

## Section Headings
1. Enterprise Connector Philosophy & The Failure Isolation Boundary
2. The Standard Connector Interface Definition (Python / FastAPI)
   - Status Codes: `ok`, `failed`, `uncertain`, `unsupported`, `manual_required`
3. Network Resilience, Timeout Budgets & Idempotency Key Injection
4. Fake Connectors & Mock Test-Harness Standard
5. Connector Inventory Overview (01 through 04)
6. Assumptions & VERIFY Checklist
