# Content Library & Retrieval-Augmented Generation (RAG) Specification

## Purpose
This document details the architecture, data taxonomy, indexing strategy, and retrieval mechanics of the Snapmint Campaign Content Library. It specifies how Bedrock Knowledge Bases and vector search enable general foundation models to act as Snapmint BNPL brand specialists without fine-tuning.

## Section Headings
1. The Six-Layer Model Specialization Architecture
2. Content Library Schema & Metadata Taxonomy
   - Campaign Attributes, Financial Product Lines, Audience Archetypes
   - Performance Metadata (Conversion Rate, CTR, DLT/Meta Approval Status)
3. Knowledge Base Infrastructure & Vector Search Topology
   - Amazon Bedrock Knowledge Bases in Mumbai (`ap-south-1`)
   - Embedding Models: Titan Text Embeddings V2 vs Cohere Multilingual v3
   - Vector Store Evaluation in `ap-south-1` (OpenSearch Serverless vs Aurora pgvector)
4. Library Seeding & Golden Example Ingestion Plan
5. Hybrid Retrieval Pipeline & Context Ranking Filters
   - Channel, Product Line, Language, and Approval Filters
   - Semantic Similarity vs Metadata Hard Filters
6. Hindi, Hinglish & Regional Language Evaluation Plan
7. Reviewer-Edit Feedback Loop (Draft -> Final -> Reason Harvesting)
8. Assumptions & VERIFY Checklist
