# Agent 06: Campaign Analytics & Performance Narrative Agent

## Purpose
This document specifies the Analytics Agent responsible for reading deterministic Databricks SQL campaign metrics, generating executive performance summaries (WoW/MoM/MTD), synthesizing actionable insights, and tagging high-performing creative assets into the Content Library.

## Section Headings
1. Agent Role & Boundary Definition
2. The Deterministic Metrics Rule: SQL Truth vs Model Narrative
   - Why LLMs Never Calculate Numbers or Run Aggregations Directly
   - Databricks SQL View Query Protocol
3. Performance Aggregation Metrics (Delivery Rate, CTR, Conversion Rate, GMV BNPL, Default Rate)
4. Tool Definitions & Databricks Query Boundaries
5. Structured Output JSON Schema (Executive Narrative, Breakdown, Library Tags)
6. System Prompt Skeleton & Analytical Prompts
7. Automated Library Feedback: Seeding Winning Copy & Creative Tags
8. End-to-End Analytics Generation Example
9. Assumptions & VERIFY Checklist
