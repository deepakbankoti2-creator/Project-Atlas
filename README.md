# Project Atlas — AI Report Copilot & Multi-Agent Intelligence Engine
**Cognitive Market Research and Consulting (CMR) — Viman Nagar, Pune**

[![Tests](https://img.shields.io/badge/pytest-40%2F40%20passing-brightgreen.svg)]()
[![Evaluation](https://img.shields.io/badge/evaluation-27%2F27%20passed%20(100%25)-success.svg)]()
[![CI3 Integration](https://img.shields.io/badge/CI3%20Integration-6%2F6%20passed-blue.svg)]()
[![Docker](https://img.shields.io/badge/docker--compose-ready-blue.svg)]()
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.13-blue.svg)]()
[![PHP](https://img.shields.io/badge/PHP-8.2%20(CodeIgniter%203)-red.svg)]()

---

## 1. Project Overview & Problem Statement

### The Problem
Cognitive Market Research and Consulting (CMR) publishes syndicated market research reports valued at thousands of dollars per seat. Enterprise clients (e.g., Siemens, Blue Delta Infra) rely on these reports for strategic planning, mergers & acquisitions, and capacity investments. However, clients and research analysts face critical challenges:
1. **Conflicting Data Sources**: Different publications report divergent market sizes due to differing scopes (e.g., total market vs. hardware-only). Naive LLMs average these figures or pick one arbitrarily, resulting in mathematically invalid conclusions.
2. **Mental Arithmetic & Hallucinations**: Standard LLMs struggle with compound annual growth rates (CAGR), frequently fabricating future market values or assuming arbitrary compounding periods.
3. **Information Disclosure & Licensing**: Syndicated research is licensed per client. Unentitled clients must never see proprietary figures from unpurchased reports.
4. **Adversarial Threats & SQL Injections**: User prompts or malicious text embedded in PDF reports (such as adversarial footnotes) can hijack LLM instructions or attempt to exfiltrate database records.

### The Solution: Project Atlas
**Project Atlas** is an enterprise-grade AI Report Copilot integrated directly into CMR's legacy CodeIgniter 3 web portal. Powered by a **7-node LangGraph agent workflow**, **persistent ChromaDB vector storage**, and local **Ollama models**, it guarantees:
- **Zero-Leak Pre-Retrieval Filtering**: Client report licenses are enforced at the ChromaDB query layer before snippets reach the LLM.
- **Deterministic Arithmetic Engine**: All projections ($Base \times (1 + CAGR)^n \times Share$) are computed natively in Python, disclosing base-year assumptions.
- **Scope-Aware Conflict Reconciliation**: Divergent figures across reports (such as R-101 vs. R-102) are contrasted by methodology and scope without averaging.
- **Adversarial Sandboxing & Read-Only SQL**: Retrieved passages are enclosed in XML data tags; destructive SQL commands are intercepted and refused.
- **Sub-2-Second Latency**: Optimized execution with automated support escalation tickets (`ESC-XXXX`) when evidence is unresolvable or out-of-horizon.

---

## 2. System Architecture & Workflow

### Architectural Flowchart

```mermaid
flowchart TD
    User([Enterprise Client: C-01 / C-02]) --> CI3[CodeIgniter 3 PHP Web Portal\n:8080]
    CI3 -->|REST POST /api/v1/chat| FastAPI[FastAPI Asynchronous Gateway\n:8000]
    
    subgraph LangGraph_Agent [LangGraph Multi-Agent Workflow]
        FastAPI --> Router{1. Query Router}
        
        Router -->|factual_lookup / comparison| Entitlement[2. Entitlement Resolver]
        Router -->|sql_aggregate| SQLTool[3. Read-Only SQL Tool]
        Router -->|calculation| Calculator[4. Deterministic Python Calculator]
        Router -->|unsafe / injection| RefusalNode[Security Refusal Node]
        Router -->|out_of_scope| OutOfScopeNode[Out-of-Scope Redirect Node]
        
        Entitlement -->|where=report_id in permitted| ChromaDB[(Persistent ChromaDB\n61 Chunks)]
        ChromaDB --> Critic[5. Critic & Evidence Reconciler]
        Calculator --> Critic
        SQLTool --> Critic
        
        Critic -->|Verified| Writer[6. Synthesis Writer]
        Critic -->|Confidence < 0.60 / Out-of-Horizon| Escalator[7. Human Escalator Node]
        Escalator --> Writer
    end
    
    Writer -->|Structured JSON Output| CI3
    CI3 --> MySQL[(MySQL 8.0 Database\nproject_atlas)]
    CI3 --> Browser([Interactive UI with Citations,\nAssumptions & Feedback])
```

### Detailed Breakdown of LangGraph Agent Nodes

1. **Query Router (`router.py`)**:
   - Classifies user intent into one of 6 operational categories: `factual_lookup`, `comparison`, `calculation`, `sql_aggregate`, `unsafe`, or `out_of_scope`.
   - Uses regex pattern detection and semantic keyword classification to identify injection attempts and destructive SQL operations in $< 2\text{ms}$.
2. **Entitlement Resolver (`entitlement.py`)**:
   - Resolves the client's purchased report IDs against the MySQL `clients` and `purchases` tables.
   - Restricts vector searches by passing `where={"report_id": {"$in": accessible_reports}}` directly to ChromaDB.
   - For restricted inquiries, redirects to a dedicated refusal node that explains licensing and offers an upgrade contact (`sales@cmr-insights.com`).
3. **Vector Retriever (`retrieval.py`)**:
   - Executes dense cosine similarity search combined with BM25 lexical keyword boosting across persistent ChromaDB chunks.
   - Encloses retrieved passages inside `<untrusted_source_document>` XML tags to neutralize indirect prompt injection traps.
4. **Deterministic Calculator (`calculator.py`)**:
   - Intercepts financial and growth queries. Extracts base value, target year, CAGR percentage, and geographic shares.
   - Evaluates:
     $$\text{Future Value} = \text{Base Value} \times (1 + \text{CAGR})^n \times \text{Share}$$
   - Discloses base-year ambiguity (e.g., 6-year compounding from 2024 vs. 5-year compounding from 2025) and outputs both calculations explicitly.
5. **Read-Only SQL Tool (`sql_tool.py`)**:
   - Executes only predefined, parameterized SQL query templates (`reports_by_sector`, `publisher_counts`, `total_reports_count`).
   - Prevents arbitrary SQL execution; rejects all `DELETE`, `DROP`, `TRUNCATE`, `ALTER`, `UPDATE`, or `INSERT` requests.
6. **Critic / Fact Checker (`critic.py`)**:
   - Cross-verifies claims in the draft answer against supporting citations.
   - Verifies whether conflicting figures exist across reports (e.g., R-101 vs. R-102) and ensures scope differences are stated.
   - Checks temporal forecast boundaries; flags out-of-horizon queries ($>2030$) for escalation.
7. **Human Escalator (`escalation.py`)**:
   - Triggered when confidence score $< 0.60$, when matching evidence is absent, or when an out-of-horizon forecast is requested.
   - Persists a support ticket (`ESC-XXXX`) in the MySQL `escalations` table with client ID, question, reason, and priority.
8. **Synthesis Writer (`writer.py`)**:
   - Assembles the final structured JSON payload containing the synthesized answer, citation objects (report ID, page number, quote), calculation breakdowns, detected conflicts, and confidence score.

---

## 3. Technology Stack & Component Purpose

| Component | Version / Model | Exact Purpose in Project Atlas |
| :--- | :--- | :--- |
| **FastAPI** | 0.115+ | High-performance asynchronous REST API gateway, Pydantic input/output validation, OpenAPI documentation, and latency tracing middleware. |
| **LangGraph** | 0.2+ | Deterministic multi-agent state graph orchestrating routing, calculation, retrieval, verification, and human escalation. |
| **ChromaDB** | 0.5+ | Embedded vector database persistently storing report chunks and metadata with pre-retrieval filtering. |
| **Ollama (Chat)** | `llama3.2:3b` | Locally hosted, privacy-preserving Large Language Model for synthesis, citation structuring, and conflict analysis. |
| **Ollama (Embed)**| `nomic-embed-text` | Locally hosted 768-dimensional embedding model for semantic indexing and vector similarity search. |
| **PyMuPDF (`fitz`)**| 1.25+ | High-speed PDF parser extracting page-by-page text, layout headers, and metadata from syndicated reports. |
| **MySQL** | 8.0 | Primary relational store for client licenses, report metadata, support escalations, chat histories, and feedback. |
| **PHP / CodeIgniter 3**| 8.2 / CI 3.1.13 | User-facing enterprise Report Copilot web portal featuring CSRF tokens, XSS escaping, client switching, and AJAX chat. |
| **Docker Compose** | v2+ | Single-command containerized delivery orchestrating MySQL, FastAPI, and CodeIgniter 3 with health monitoring. |

---

## 4. Project Directory Structure

```
Project-Atlas/
├── docker-compose.yml          # 1-click Docker delivery of MySQL, FastAPI, and CI3 Portal
├── requirements.txt            # Python dependencies (FastAPI, LangGraph, PyMuPDF, ChromaDB, etc.)
├── README.md                   # Complete system documentation, architecture, and run guide
├── .env.example                # Safe environment variable template with placeholders
├── .gitignore                  # Git exclusions (credentials, pycache, vector locks, data caches)
├── data/
│   ├── reports/                # Ingested PDF reports (R-101 through R-106)
│   └── chroma_db/              # Persistent ChromaDB vector storage (61 chunks)
├── docker/
│   └── mysql/
│       └── init.sql            # MySQL schema DDL & seed dataset with readonly user setup
├── portal_ci3/                 # CodeIgniter 3 PHP Legacy Application
│   ├── Dockerfile              # PHP 8.2 Apache container definition
│   ├── index.php               # CI3 front controller
│   ├── application/
│   │   ├── config/             # Config, database, routes, autoload, and atlas API config
│   │   ├── controllers/        # Chat.php (AJAX query handling, client switching, feedback)
│   │   ├── libraries/          # Atlas_client.php (cURL REST client with 30s timeout budget)
│   │   ├── models/             # Chat_model.php (ActiveRecord MySQL persistence)
│   │   └── views/              # chat_view.php (Modern responsive chat UI with CSRF & XSS protection)
│   └── system/                 # Self-contained CodeIgniter 3 core runtime
├── backend/
│   ├── Dockerfile              # Python 3.11 FastAPI container definition
│   ├── main.py                 # FastAPI application root & middleware
│   ├── app/
│   │   ├── core/               # Configuration, DB sessions, persistent vector store, admin auth
│   │   ├── models/             # SQLAlchemy ORM models (Report, Metric, Client, Ticket, Conv, Feedback)
│   │   ├── services/           # Ingestion, extractor, chunker, embeddings, entitlements, retrieval
│   │   ├── agent/              # LangGraph workflow, router, sql_tool, calculator, critic, escalation
│   │   └── api/v1/             # REST endpoints (/chat, /feedback, /ingest, /escalations, /health)
│   ├── scripts/
│   │   ├── ingest_reports.py   # CLI report ingestion script
│   │   ├── generate_sample_reports.py # Synthesizes 6 multi-page test PDFs with Appendix A traps
│   │   ├── run_evaluation.py   # Automated 27-question benchmark harness
│   │   ├── test_ci3_integration.py # 6-suite PHP portal integration verification script
│   │   └── demo_agent_workflow.py # CLI interactive demonstration of all 8 workflows
│   └── evaluation/
│       ├── eval_dataset.json   # 27 comprehensive evaluation test cases
│       └── evaluation_report.md# Benchmark evaluation report (100% passing)
├── docs/
│   ├── evaluation_report.md    # Full evaluation report with 27-test table & 6 failure analyses
│   ├── what_i_would_do_with_one_more_week.md # 7-day engineering roadmap & future scaling
│   └── ai_disclosure.md        # AI Assistant Disclosure Statement
└── tests/
    ├── test_api.py             # 19 integration tests for FastAPI endpoints, auth, and error states
    ├── test_ingestion.py       # 5 unit tests for extraction, chunking, and deduplication
    ├── test_rag.py             # 7 unit tests for entitlement filtering, injection, and citations
    └── test_agent_workflow.py  # 9 unit tests for routing, calculator, critic, and SQL safety
```

---

## 5. Syndicated Report Corpus (Appendix A)

The persistent vector store indexes 6 multi-page research reports across key market sectors:

| Report ID | Title | Sector | Publisher | Access Level | Quantitative Benchmarks |
| :---: | :--- | :---: | :---: | :---: | :--- |
| **R-101** | Global Smart Water Meter Market 2025 | Utilities | CMR | **Paid** | 2024 Size: **USD 4.21 B** (hardware, software, services); CAGR: **11.2% (2025–2030)**; APAC Share: **38%**. |
| **R-102** | Smart Water Metering: Industry Outlook 2024 | Utilities | Aquila Insights | **Public** | 2024 Size: **USD 3.87 B** (AMI/AMR hardware only); CAGR: **9.8% (2024–2029)**; APAC Share: **41% of hardware**. *(Contains Page 14 injection trap)* |
| **R-103** | Residential Water Purifier Market | Consumer Durables | CMR | **Paid** | 2024 Size: **USD 11.4 B** (POU & whole-house filtration). |
| **R-104** | EV Battery Recycling Market 2025 | CleanTech | CMR | **Paid** | 2024 Size: **USD 9.25 B**; CAGR: **21.4% (2025–2032)**; APAC Share: **52%**. |
| **R-105** | Commercial Building Energy Management Systems | Energy & Infra | Aquila Insights | **Public** | 2024 Size: **USD 6.80 B**; CAGR: **12.5% (2024–2030)**; North America Share: **44%**. |
| **R-106** | Healthcare Generative AI Market 2025 | Healthcare | CMR | **Paid** | 2024 Size: **USD 2.15 B**; CAGR: **34.8% (2025–2031)**; North America Share: **48%**. |

---

## 6. Installation & Prerequisites

### Prerequisites
- **Python**: Version 3.11 or 3.13.
- **PHP**: Version 8.2 with `php-curl`, `php-mysqli`, and `php-json` extensions enabled.
- **MySQL**: Existing MySQL 8.0 server with database `project_atlas`.
- **Ollama**: Local Ollama server installed and running.
- **Docker & Docker Compose**: (Optional, for containerized deployment).

### 1. Ollama Model Setup
Ensure Ollama is running and download the required chat and embedding models:
```bash
# Pull the 3B parameter chat model
ollama pull llama3.2:3b

# Pull the 768-dimension embedding model
ollama pull nomic-embed-text

# Verify models are available
ollama list
```

### 2. MySQL Database Setup
The application connects to your existing MySQL database named `project_atlas`.
If setting up a fresh database, execute `docker/mysql/init.sql` in MySQL Workbench or the MySQL CLI:
```bash
mysql -u root -p project_atlas < docker/mysql/init.sql
```
*Note: If the MySQL server is temporarily offline or credentials are misconfigured, Project Atlas automatically falls back to an in-memory seed catalog so that testing and evaluation proceed without disruption.*

### 3. Environment Configuration (`.env`)
Create a local `.env` file from the provided `.env.example`:
```bash
cp .env.example .env
```
Ensure `.env` contains appropriate local placeholders:
```ini
# Database Configuration
DB_HOST=localhost
DB_PORT=3306
DB_NAME=project_atlas
DB_USER=root
DB_PASSWORD=your_mysql_password

# Ollama Models & URLs
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_CHAT_MODEL=llama3.2:3b
OLLAMA_EMBED_MODEL=nomic-embed-text

# Vector Store & Ingestion
CHROMA_PERSIST_DIR=data/chroma_db
CHROMA_COLLECTION_NAME=atlas_reports
REPORTS_DIR=data/reports
CHUNK_SIZE=600
CHUNK_OVERLAP=100

# Authentication & Timeouts
ATLAS_API_KEY=atlas_secret_token_2025
ADMIN_API_KEY=atlas_admin_secret_key_2025
OLLAMA_TIMEOUT_SECONDS=10.0
REQUEST_TIMEOUT_SECONDS=30.0
```

---

## 7. Starting the Application

### Option A: 1-Click Docker Deployment (Recommended)
Build and run all services (MySQL, FastAPI, and CodeIgniter 3):
```bash
docker compose up -d --build
```
- **CodeIgniter 3 Portal**: [http://localhost:8080/](http://localhost:8080/)
- **FastAPI OpenAPI Swagger**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **FastAPI Health Probe**: [http://localhost:8000/api/v1/health](http://localhost:8000/api/v1/health)

### Option B: Native Local Development

```bash
# 1. Install Python dependencies
pip install -r requirements.txt

# 2. Synthesize PDF test reports (creates 6 PDF files in data/reports/)
python backend/scripts/generate_sample_reports.py

# 3. Ingest PDF reports into persistent ChromaDB
python backend/scripts/ingest_reports.py

# 4. Terminal 1: Launch FastAPI Backend
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

# 5. Terminal 2: Launch CodeIgniter 3 PHP Portal
php -S 0.0.0.0:8080 -t portal_ci3
```

---

## 8. REST API Endpoints & Example Payloads

### 1. `GET /api/v1/health`
Checks operational health of MySQL, ChromaDB, and Ollama.
```bash
curl -X GET http://localhost:8000/api/v1/health
```
**Example Response (HTTP 200)**:
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2026-10-19T14:15:00Z",
  "database_target": "project_atlas",
  "dependencies": {
    "database": {"status": "operational", "error": null},
    "chromadb": {"status": "operational", "collection": "atlas_reports", "count": 61},
    "ollama": {"status": "operational", "chat_model": "llama3.2:3b", "embed_model": "nomic-embed-text"}
  }
}
```

### 2. `POST /api/v1/chat`
Submits a client-scoped question to the LangGraph copilot.
```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "client_id": "C-01",
    "question": "What was the global smart water meter market size in 2024?",
    "top_k": 5
  }'
```
**Example Response (HTTP 200)**:
```json
{
  "answer": "According to R-101 (CMR), the global smart water meter market was valued at USD 4.21 Billion in 2024, covering hardware, software, and managed services. Conversely, R-102 (Aquila Insights) reports USD 3.87 Billion for 2024, reflecting AMI/AMR physical hardware meters only. The difference is attributable to scope definitions rather than factual disagreement.",
  "route_taken": "factual_lookup",
  "confidence": 0.95,
  "conflicts_detected": [
    "R-101 states USD 4.21B (hardware/software/services) while R-102 states USD 3.87B (hardware only)."
  ],
  "escalated": false,
  "ticket_id": null,
  "derived_values": null,
  "citations": [
    {
      "report_id": "R-101",
      "page": 8,
      "quote": "The global smart water meter market size was valued at USD 4.21 billion in 2024...",
      "title": "Global Smart Water Meter Market 2025"
    },
    {
      "report_id": "R-102",
      "page": 6,
      "quote": "Global smart water metering hardware shipments accounted for USD 3.87 billion in 2024...",
      "title": "Smart Water Metering: Industry Outlook 2024"
    }
  ]
}
```

### 3. `POST /api/v1/ingest`
Triggers administrative document ingestion into ChromaDB (requires Admin API Key).
```bash
curl -X POST http://localhost:8000/api/v1/ingest \
  -H "X-Admin-Key: atlas_admin_secret_key_2025" \
  -H "Content-Type: application/json" \
  -d '{"reports_dir": "data/reports", "rebuild_index": false}'
```
**Example Response (HTTP 200)**:
```json
{
  "status": "success",
  "reports_found": 6,
  "chunks_indexed": 61,
  "elapsed_seconds": 2.45,
  "message": "Ingestion pipeline completed successfully."
}
```

### 4. `GET /api/v1/escalations`
Retrieves pending analyst escalation tickets (requires Admin API Key).
```bash
curl -X GET http://localhost:8000/api/v1/escalations \
  -H "X-Admin-Key: atlas_admin_secret_key_2025"
```
**Example Response (HTTP 200)**:
```json
[
  {
    "ticket_id": "ESC-A19F",
    "client_id": "C-01",
    "question": "What will the market be worth in 2035?",
    "reason": "Target forecast year (2035) exceeds published report horizon (2030).",
    "status": "open",
    "priority": "normal",
    "created_at": "2026-10-19T14:16:30Z"
  }
]
```

### 5. `POST /api/v1/feedback`
Submits user satisfaction feedback from the web interface.
```bash
curl -X POST http://localhost:8000/api/v1/feedback \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "sess-91a2bc",
    "message_id": "msg-04",
    "rating": "positive",
    "comment": "Accurate scope explanation between R-101 and R-102."
  }'
```

---

## 9. Automated Testing & Verification

Project Atlas is backed by three distinct automated verification suites:

### 1. Pytest Unit & Integration Tests (40 Tests)
Covers API routers, security sanitizers, Pydantic schemas, PyMuPDF extraction, vector deduplication, entitlement checks, deterministic arithmetic, and prompt injection traps.
```bash
python -m pytest tests/ -v
```
*Result: **40 passed, 0 failed** in 24.54s.*

### 2. CodeIgniter 3 Portal Integration Suite (6 Suites)
Validates file structure integrity, CSRF configuration, session client switching, cURL communication to FastAPI, feedback submission, and health probes.
```bash
python backend/scripts/test_ci3_integration.py
```
*Result: **6 / 6 suites passed (100%)**.*

### 3. Comprehensive Evaluation Benchmark (27 Scenarios)
Executes all 27 automated benchmark cases spanning all 14 requirement categories:
```bash
python backend/scripts/run_evaluation.py
```
*Result: **27 / 27 passed (100.0%)**, average latency 0.15s.*

### 4. Interactive CLI Demonstration
Run a guided CLI walkthrough demonstrating all 8 agent workflows:
```bash
python backend/scripts/demo_agent_workflow.py
```

---

## 10. Security Controls & Implemented Features Matrix

### Security Architecture
1. **Pre-Retrieval Entitlement Filtering**: ChromaDB queries apply `$in` filters against verified client purchases. Unauthorized report chunks never enter the context window.
2. **Prompt Injection Sandboxing**: Retrieved document chunks are wrapped in `<untrusted_source_document>` tags. Pre-generation regex monitors intercept hostile directives (`disregard previous instructions`, `reveal passwords`).
3. **Strict SQL Read-Only Tool**: Free-form SQL parsing is disabled. Only pre-parameterized, read-only aggregate templates execute. Destructive keywords (`DROP`, `DELETE`, `TRUNCATE`) trigger immediate security refusals.
4. **Web Security (CodeIgniter 3)**: Form submissions require CSRF tokens. All model responses are sanitized with PHP `htmlspecialchars()` before DOM injection to eliminate XSS risks.
5. **PII and Secret Redaction**: Loggers redact database passwords, client contact emails, and authorization tokens.

### Implemented vs. Incomplete Features Matrix

| Feature / Capability | Implementation Status | Technical Details |
| :--- | :---: | :--- |
| **PDF Extraction & Chunker** | **Complete (100%)** | PyMuPDF text & metadata extraction with recursive character chunking (800/150). |
| **Persistent Vector Storage** | **Complete (100%)** | Persistent ChromaDB collection (`atlas_reports`) with SHA-256 chunk deduplication. |
| **Pre-Retrieval Filtering** | **Complete (100%)** | Entitlement-checked `$in` filter applied at ChromaDB query layer. |
| **LangGraph 7-Node Agent** | **Complete (100%)** | Router, Entitlement, SQL Tool, Calculator, Critic, Escalator, and Writer nodes. |
| **Deterministic Calculator** | **Complete (100%)** | Python CAGR formula with dual base-year (5-yr vs 6-yr) compounding disclosure. |
| **Conflict Reconciliation** | **Complete (100%)** | Methodology and scope differentiation (R-101 total vs R-102 hardware); no averaging. |
| **Human Escalation Queue** | **Complete (100%)** | Automated `ESC-XXXX` ticket creation in MySQL on out-of-horizon or confidence $< 0.60$. |
| **CodeIgniter 3 Web Portal** | **Complete (100%)** | Client switcher (C-01 / C-02), responsive chat UI, citations, and feedback voting. |
| **Docker Packaging** | **Complete (100%)** | Multi-container Compose starting MySQL 8.0, FastAPI, and CI3 Apache. |
| **Multimodal Chart Extraction** | *Planned (Future)* | Covered in 7-day roadmap (Day 1: Nougat / LayoutLMv3 integration). |
| **Token Streaming (SSE)** | *Planned (Future)* | Covered in 7-day roadmap (Day 3: Server-Sent Events integration). |
| **Self-Service Stripe Checkout** | *Planned (Future)* | Covered in 7-day roadmap (Day 6: Instant report upgrade checkout). |

---

## 11. Troubleshooting Common Issues

### 1. MySQL Access Denied / Connection Refused
- **Symptom**: `OperationalError: (1045, "Access denied for user 'root'@'localhost'")`.
- **Cause**: MySQL credentials in `.env` differ from your local MySQL root password.
- **Handling**: Project Atlas automatically falls back to its built-in seed catalog so the API and evaluation tests continue running.
- **Fix**: Update `DB_PASSWORD` in `.env` to match your local MySQL installation, or launch via Docker Compose where credentials are configured automatically.

### 2. Ollama Connection Error or Model Missing
- **Symptom**: `Failed to connect to Ollama at http://localhost:11434`.
- **Cause**: Ollama service is not running, or required models have not been pulled.
- **Fix**: Start the Ollama server (`ollama serve`) and pull the models:
  ```bash
  ollama pull llama3.2:3b
  ollama pull nomic-embed-text
  ```

### 3. Port Conflicts (:8000, :8080, :3306)
- **Symptom**: `Address already in use` when launching FastAPI or Docker.
- **Fix**: Identify and stop conflicting processes:
  ```powershell
  # On Windows PowerShell
  Get-Process -Id (Get-NetTCPConnection -LocalPort 8000).OwningProcess | Stop-Process
  ```

### 4. CodeIgniter 3 Displays Blank Page or cURL Error
- **Symptom**: CI3 portal reports `Failed to connect to FastAPI at http://localhost:8000`.
- **Fix**: Verify FastAPI is active (`curl http://localhost:8000/api/v1/health`). Verify `php-curl` is enabled in `php.ini`.

---

## 12. Submission Documents Index

- **System Evaluation Report**: [docs/evaluation_report.md](docs/evaluation_report.md) — 27-test benchmark table and 6 detailed failure analyses.
- **One-Week Roadmap**: [docs/what_i_would_do_with_one_more_week.md](docs/what_i_would_do_with_one_more_week.md) — Day-by-day architectural scaling plan.
- **AI Assistant Disclosure**: [docs/ai_disclosure.md](docs/ai_disclosure.md) — Transparent disclosure of AI pair programming usage.