# Architecture Specification: CRM Campaign Execution Platform

## Purpose
This document provides the definitive technical architecture for the Snapmint CRM Campaign Execution Platform. It details the six structural layers, service topology, AWS infrastructure, data sovereignty boundaries, and security architecture.

## Section Headings
1. Architectural Principles & Hard Governance Rules
2. System Topology & 6-Layer Architecture
   - Layer 1: Experience & Workflow UI (Portal)
   - Layer 2: Core Services & Source of Truth
   - Layer 3: Specialized Agent Engine
   - Layer 4: Deterministic Guardrails & Validators
   - Layer 5: Enterprise Connectors & Vendor Adapters
   - Layer 6: Security, IAM & Data Governance
3. Architecture & Data Flow Diagrams (Mermaid)
   - System Context (C4 Level 1)
   - End-to-End Request Lifecycle Sequence
   - State Transition Lifecycle
4. AWS Infrastructure Architecture (Mumbai `ap-south-1`)
   - Compute: ECS Fargate vs Lambda Workers
   - Storage & State: Aurora PostgreSQL Multi-AZ
   - Asset Storage: Amazon S3 (KMS CMK, Signed URLs)
   - Orchestration: AWS Step Functions + SQS DLQ
5. Data Sovereignty & Network Isolation Design
   - India-Only Inference Profile Topology (`ap-south-1` & `ap-south-2`)
   - VPC Endpoints & PrivateLink Architecture
   - Non-PII Data Minimization Boundary
6. Performance, Scalability & Resilience Targets
7. Assumptions & VERIFY Checklist
