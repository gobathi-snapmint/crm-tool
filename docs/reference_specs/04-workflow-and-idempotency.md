# Workflow Engine & Idempotency Specification

## Purpose
This document defines the formal campaign execution state machine, AWS Step Functions workflow definitions, asynchronous task coordination via SQS, idempotency key generation, failure recovery algorithms, and the operational protocol for handling "Needs Verification" states.

## Section Headings
1. Workflow Philosophy & The Zero-Ambiguity Rule
2. Campaign State Machine Specification
   - Complete State List & Lifecycle Map
   - State Transition Matrix (Allowed Events, Guards, Transitions)
3. Idempotency Architecture
   - Idempotency Key Composition: `Hash(campaign_id + version + operation_type)`
   - Windowing, De-duplication, and Distributed Lock Management
4. The "Needs Verification" Resolution Protocol
   - Timeout Handling & Ambiguous Network Response Triaging
   - Manual & Automated Reconciliation Workflows
5. AWS Step Functions State Machine Definition (ASL JSON)
   - Step Functions Workflow Graph
   - Task Definitions, Catch Blocks, and SQS Dead Letter Queues
6. Retry Policy & Failure Matrix Across All External Calls
7. Assumptions & VERIFY Checklist
