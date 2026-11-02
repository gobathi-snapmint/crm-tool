# Evaluation Harness & Benchmark Protocol

## Purpose
This document details the evaluation framework, golden benchmark dataset, quantitative scoring rubrics, LLM-as-a-judge calibration protocol, and CI/CD quality gating required prior to deploying or modifying any foundation model, system prompt, or retrieval configuration.

## Section Headings
1. The Eval-First Doctrine: Why Evaluation Precedes Agent Deployment
2. Golden Benchmark Dataset Specification
   - Composition: 50-100 Curated Historical Campaigns (80% Train/Tune, 20% Held-Out)
   - Benchmark Item JSON Schema
3. Multi-Dimensional Scoring Rubrics
   - Category Match & Policy Compliance (WhatsApp Utility vs Marketing)
   - Exact Character Counting & DLT Hash Match (SMS)
   - Brand Tone, Value Proposition & CTA Clarity
   - Hallucination & PII Leakage Detection (Zero Tolerance)
4. Model Bake-off Protocol (Claude Sonnet 5 vs GPT-5.6 Terra vs Claude Haiku 4.5)
5. LLM-as-a-Judge Calibration & Inter-Annotator Agreement (Cohen's Kappa)
6. CI/CD Automated Regression Gating Architecture
7. Target Evaluation Pass Bars
8. Assumptions & VERIFY Checklist
