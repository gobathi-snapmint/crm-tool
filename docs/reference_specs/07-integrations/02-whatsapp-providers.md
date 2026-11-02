# Integration 02: WhatsApp Provider Connector Matrix

## Purpose
This document specifies the provider-agnostic WhatsApp integration interface, provider-specific adapter mappings (Route Mobile, Gupshup, Onexctel, TrustSignal, Infobip), template submission APIs, webhook status polling, and verification spikes.

## Section Headings
1. WhatsApp Business Solution Provider (BSP) Landscape in India
2. Provider-Agnostic WhatsApp Interface (Template Submit, Status Query, Webhook Ingest)
3. Provider Adapter Specifications & Known APIs
   - Route Mobile WhatsApp Business API
   - Gupshup Enterprise Template API
   - Onexctel / TrustSignal / Infobip Adapters
4. Meta Template Lifecycle, Quality Rating & Rejection Webhooks
5. Provider Spike Plan & Verification Checklist (Weeks 1-4)
6. Fake WhatsApp Connector Specification for Test Harness
7. Assumptions & VERIFY Checklist
