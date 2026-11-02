# Integration 04: Databricks Analytics SQL Views & Pipeline

## Purpose
This document specifies the read-only integration between the CRM Campaign Execution Platform and Snapmint's Databricks Lakehouse. It defines the SQL views, non-PII aggregation schemas, query patterns, and performance metric feeds.

## Section Headings
1. Architectural Boundary: Lakehouse Truth vs Agent Narratives
2. Databricks SQL Warehouse Connection Configuration
   - Personal Access Token (PAT) / Service Principal in AWS Secrets Manager
   - VPC Peering / PrivateLink between AWS Mumbai VPC and Databricks
3. Standard Analytics SQL View Specifications
   - `vw_crm_campaign_delivery_daily`
   - `vw_crm_attribution_conversion_30d`
   - `vw_crm_bnpl_portfolio_risk_aggregates`
4. Strict No-PII Query Mandate & Verification Guardrails
5. Fake Databricks Connector Specification for Local & CI Development
6. Assumptions & VERIFY Checklist
