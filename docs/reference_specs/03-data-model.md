# Data Model Specification: CRM Campaign Execution Platform

## Purpose
This document specifies the complete PostgreSQL database schema, data dictionaries, relational integrity rules, indexing strategies, append-only audit structures, and retention policies for the Snapmint CRM Campaign Execution Platform.

## Section Headings
1. Data Design Principles & Source-of-Truth Mandate
2. Entity Relationship Diagram (Mermaid)
3. Full PostgreSQL DDL Specification
   - `campaign` & `campaign_version` (Immutability & Version Trees)
   - `content_item` & `asset` (Multi-channel Copies & Rendered Assets)
   - `template` (WhatsApp & SMS/DLT Template Ledger)
   - `draft` (WebEngage Execution Specs & Draft Statuses)
   - `workflow_run` & `external_call` (Idempotency & Vendor Interaction Log)
   - `approval` (4-Tier Permission Sign-offs)
   - `issue` (Blocking Defects & Resolution History)
   - `library_item` (Approved Examples & Embeddings Reference)
   - `metric_snapshot` (SQL-Derived Performance Attributions)
   - `audit_event` (Append-Only Cryptographic Audit Trail)
4. Template Hashing & Deterministic Matching Mechanics
   - Normalization Pipeline (Whitespace, Punctuation, Unicode)
   - SHA-256 Text Hashing for DLT & WhatsApp Verification
5. Indexing, Partitioning & Performance Strategy
6. Data Retention, Archival & Purge Policies
7. Assumptions & VERIFY Checklist
