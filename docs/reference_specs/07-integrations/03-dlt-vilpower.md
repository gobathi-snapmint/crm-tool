# Integration 03: SMS & DLT (Vilpower) Integration Protocol

## Purpose
This document details the regulatory compliance architecture for SMS messaging under TRAI guidelines, evaluating telecom DLT platforms (Vilpower, Jio, Airtel, Smartping), outlining the lack of official open APIs, and specifying the automated packaging / manual attestation workflow.

## Section Headings
1. Regulatory Landscape: TRAI TCCCPR & Telecom DLT Mandates
2. Platform Investigation: Vilpower / Jio DLT / Airtel / Smartping
   - API Availability Assessment (Lack of Official Unauthenticated APIs)
   - The No-Bypass Rule: Prohibition of Automated CAPTCHA / OTP Solving
3. Hybrid DLT Operational Architecture: Automated Preparation + Manual Submission
4. DLT Registration Package Schema (Header ID, PE ID, Template Type, Variables)
5. DLT Template Synchronizer (Batch CSV / Portal Scraper with Authenticated Session)
6. Fake DLT Connector Specification for CI/CD Testing
7. Assumptions & VERIFY Checklist
