# What I would do with one more week
**Cognitive Market Research and Consulting (CMR) — Project Atlas Copilot**  
*Author: AI Software Developer (Generative & Agentic AI Candidate) | October 2026*

---

### Context & Current Foundation
Project Atlas currently delivers a robust, secure, and production-tested Report Copilot. Its foundation includes:
- **7-node LangGraph agent workflow** (Router, Entitlement Resolver, Deterministic Calculator, Critic Reconciler, SQL Aggregate Tool, Human Escalator, and Synthesis Writer).
- **Zero-leak pre-retrieval filtering** against client licenses in persistent ChromaDB.
- **Strict deterministic arithmetic** ($Base \times (1 + CAGR)^n$) with base-year compound ambiguity disclosure.
- **Sandboxed prompt-injection mitigation** and parameterized, read-only SQL execution.
- **PHP CodeIgniter 3 portal integration** with CSRF protection, HTML entity escaping, client context switching, and feedback capture.
- **100% test pass rate** (40 unit tests, 6 CI3 integration suites, and 27 evaluation benchmark scenarios).

If granted an additional week (7 calendar days) of dedicated engineering time, I would execute the following structured day-by-day roadmap to scale this foundation from a single-node prototype into a high-concurrency, multimodal enterprise research platform.

---

### 7-Day Engineering Roadmap

#### Day 1: Multimodal Document Parsing & Complex Table Extraction
- **Gap in Current System**: PyMuPDF extracts plain text and standard text blocks; complex multi-segment market share matrices and graphic bar charts (e.g., in slide decks or image-dense PDFs) are parsed as linearized text, losing 2D spatial relationships.
- **Action**: Integrate a hybrid vision/OCR parser using **Nougat** or **LayoutLMv3** (with fallback to `pdfplumber` / PyMuPDF table finder). Extract revenue matrices directly into structured Markdown tables and JSON key-value records.
- **Measurable Target**: 100% extraction fidelity for tabular data across reports R-101 to R-106, with table cells individually addressable during semantic retrieval.

#### Day 2: Cross-Encoder Re-Ranking & Semantic Caching
- **Gap in Current System**: ChromaDB cosine distance retrieval coupled with BM25 lexical keyword boosting returns top-$k$ candidates, but lacks deep cross-attention re-scoring between user queries and retrieved snippets.
- **Action**:
  1. Integrate a lightweight local cross-encoder model (`cross-encoder/ms-marco-MiniLM-L-6-v2` or `bge-reranker-base`) as a LangGraph intermediate node to re-rank top 30 chunks down to the 5 most salient passages.
  2. Implement an in-memory / Redis semantic cache using vector embeddings with a cosine similarity threshold $\ge 0.96$.
- **Measurable Target**: Reduce repeat query latency from ~150ms down to $<15\text{ms}$ (0 LLM inference cost), while boosting NDCG@5 retrieval precision on complex queries by $\ge 18\%$.

#### Day 3: Asynchronous Token Streaming & Server-Sent Events (SSE)
- **Gap in Current System**: The FastAPI `/chat` endpoint returns a single atomic JSON response after full LangGraph execution (~1.5s–3.2s when invoking local Ollama). The CodeIgniter 3 frontend displays a loading spinner until completion.
- **Action**: Refactor LangGraph execution to yield streaming events via FastAPI `StreamingResponse` (Server-Sent Events). Update `Atlas_client.php` and the CI3 frontend JavaScript (`EventSource` / fetch streaming) to render the router classification, citations, and generated tokens incrementally.
- **Measurable Target**: Time-to-First-Token (TTFT) $<450\text{ms}$ in the browser, dramatically enhancing perceived user responsiveness.

#### Day 4: Deep Observability with OpenTelemetry & Langfuse
- **Gap in Current System**: Observability is handled via structured Python logging, request latency headers (`X-Process-Time`), and MySQL conversation/feedback tables. Token usage, node-by-node latency bottlenecks, and hallucination scores are not aggregated in a visual dashboard.
- **Action**: Instrument LangGraph nodes and Ollama calls with **OpenTelemetry** and native **Langfuse** / **LangSmith** SDK tracing. Capture exact input/output tokens, per-node latency breakdowns, and correlate user thumbs-up/down feedback directly to prompt versions and retrieval chunks.
- **Measurable Target**: 100% trace capture on all requests with sub-millisecond trace overhead; live dashboard displaying operational cost, latency percentiles (p50, p95, p99), and critic failure rates.

#### Day 5: Enhanced Conversation Memory & Multi-Turn Context Resolution
- **Gap in Current System**: The API accepts a `session_id` and persists conversation turns in MySQL, but the LangGraph retriever processes each question in isolation without re-writing pronouns or contextual follow-ups (e.g., *"What is its CAGR?"* following *"What was R-101's 2024 market size?"*).
- **Action**: Add a Context Query Rewriter node to LangGraph. If a `session_id` has prior messages, a fast local model pass rewrites the input query into a self-contained canonical search query before entitlement resolution and vector search.
- **Measurable Target**: $\ge 90\%$ accuracy on multi-turn pronoun and anaphora resolution across a 15-question conversational evaluation dataset.

#### Day 6: Self-Service License Upgrades & Stripe Billing Integration
- **Gap in Current System**: When client `C-02` attempts to access restricted report `R-101`, the system correctly refuses access and offers a static upgrade message directing them to `sales@cmr-insights.com`.
- **Action**: Embed an actionable upgrade flow into the CodeIgniter 3 UI. Create a `/portal/upgrade` checkout route integrated with Stripe Checkout Webhooks that automatically updates `clients.purchased_reports` in MySQL upon successful purchase and triggers ChromaDB entitlement cache invalidation.
- **Measurable Target**: End-to-end upgrade flow completed in $<60$ seconds, immediately granting instant access to restricted reports without requiring manual database administration.

#### Day 7: Load Testing, Security Hardening & Zero-Downtime Deployment
- **Gap in Current System**: Docker Compose starts all containers locally, but has not been stress-tested under concurrent client load or configured for automated CI/CD pipeline deployments.
- **Action**:
  1. Author a Locust load-testing script simulating 50 concurrent corporate clients submitting mixed factual, calculation, and SQL aggregate queries.
  2. Implement rate limiting (FastAPI `slowapi`, e.g., 60 req/min per client ID).
  3. Author GitHub Actions CI/CD workflows for automated linting (`ruff`, `phpstan`), automated test execution (`pytest`, PHPUnit), and container vulnerability scanning (`trivy`).
- **Measurable Target**: Maintain p95 latency $<2.5\text{s}$ at 50 concurrent virtual users with 0% error rate; 100% pass rate on automated security and lint checks.

---

### Summary of Future Work vs. Current Implementation

| Capability | Current Status in Repo | After 1 Additional Week |
| :--- | :--- | :--- |
| **PDF Extraction** | PyMuPDF text & metadata parsing | Hybrid vision/OCR with structured table parsing |
| **Retrieval Engine** | Dense ChromaDB + BM25 keyword boost | Cross-encoder re-ranking + Redis semantic caching |
| **UI Streaming** | Atomic HTTP POST with client-side spinner | Real-time token streaming via Server-Sent Events (SSE) |
| **Observability** | Structured console logs + MySQL conversation history | Full OpenTelemetry & Langfuse trace dashboard |
| **Multi-Turn Context** | Turn persistence in MySQL; single-turn retrieval | Automated query re-writing for multi-turn follow-ups |
| **Client Entitlement** | Strict pre-retrieval vector filtering & refusal | Self-service one-click Stripe purchase & instant unlock |
| **Load Resilience** | Tested sequentially & unit-tested (40 pytest) | Locust-verified 50-client concurrency with rate limiting |
