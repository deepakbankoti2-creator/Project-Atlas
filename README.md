# Project Atlas — AI Software Developer / Report Copilot

Project Atlas is an AI-powered software developer and report copilot that analyzes syndicated market research reports, granular market metrics, and client report purchase entitlements.

---

## 1. Project Overview & Architecture

```
Project-Atlas/
├── .env                      # Local environment credentials (ignored by git)
├── .env.example              # Template environment variables for MySQL, Ollama, & ChromaDB
├── .gitignore                # Protects credentials (.env), Chroma DB files, & Python caches
├── README.md                 # Complete documentation and execution guide
├── requirements.txt          # Python dependencies (FastAPI, SQLAlchemy, PyMuPDF, ChromaDB, etc.)
├── data/
│   ├── reports/              # PDF reports directory (e.g., R-101.pdf, R-102.pdf, R-103.pdf)
│   └── chroma_db/            # Persistent ChromaDB vector storage (git-ignored)
├── backend/
│   ├── __init__.py
│   ├── main.py               # FastAPI application entrypoint with health & API routes
│   ├── app/
│   │   ├── __init__.py
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   ├── config.py     # Environment variable loading & safe DB URL generation
│   │   │   ├── database.py   # SQLAlchemy engine, sessionmaker & get_db dependency
│   │   │   └── vector_store.py # Persistent ChromaDB vector storage & entitlement filtering
│   │   ├── ingestion/
│   │   │   ├── __init__.py
│   │   │   ├── extractor.py  # Page-by-page PDF text extraction via PyMuPDF
│   │   │   └── chunker.py    # Overlapping text chunker with stable chunk IDs & metadata
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   └── schema.py     # SQLAlchemy ORM models matching existing MySQL tables
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── embedding.py  # Local Ollama nomic-embed-text integration & fallback
│   │   │   ├── metadata_mapper.py # MySQL-to-report metadata mapper
│   │   │   ├── ingestion.py  # Report ingestion service orchestrator
│   │   │   ├── entitlement.py # Pre-retrieval client entitlement enforcement
│   │   │   ├── security.py   # Prompt injection detection & untrusted context framing
│   │   │   ├── retrieval.py  # Secure RAG hybrid search & supporting passage builder
│   │   │   └── rag_generator.py # Cited RAG answer generator with Ollama/fallback
│   │   └── api/
│   │       ├── __init__.py
│   │       └── v1/
│   │           ├── __init__.py
│   │           └── endpoints.py # REST endpoints (db-status, reports, clients, ingest, retrieve, chat)
│   └── scripts/
│       ├── __init__.py
│       ├── test_db.py        # Database connection & table inspection test script
│       ├── generate_sample_reports.py # Generates test PDF reports matching assignment spec
│       ├── ingest_reports.py # CLI ingestion script with summary stats and deduplication
│       └── test_rag_pipeline.py # Interactive verification of entitlement & injection defense
└── tests/
    ├── test_ingestion.py     # Unit tests for extraction, chunking, and Chroma persistence
    └── test_rag.py           # Unit tests for entitlement boundaries, injection, & citations
```

---

## 2. Existing Database Schema (`project_atlas`)

The database `project_atlas` contains 3 core tables created in MySQL Workbench:

### Table 1: `reports`
* **Purpose:** Stores research, market outlook, and intelligence publications.
* **Columns:**
  * `id` (`VARCHAR(10)`, Primary Key) — Unique report identifier (e.g., `R-101`, `R-102`).
  * `title` (`VARCHAR(255)`, Not Null) — Report publication title.
  * `publisher` (`VARCHAR(100)`, Not Null) — Authoring research publisher (e.g., `CMR`, `Aquila Insights`).
  * `published` (`DATE`, Not Null) — Publication date.
  * `sector` (`VARCHAR(50)`, Not Null) — Target industry vertical (e.g., `Utilities`, `Consumer Durables`).
  * `access` (`ENUM('paid', 'public')`, Not Null) — Access entitlement classification.

### Table 2: `market_metrics`
* **Purpose:** Stores quantitative market findings, CAGR projections, regional shares, and scoping notes extracted from reports.
* **Columns:**
  * `id` (`INT`, Auto Increment, Primary Key) — Unique metric entry ID.
  * `report_id` (`VARCHAR(10)`, Foreign Key references `reports.id`) — Links metric to parent report.
  * `metric` (`VARCHAR(100)`) — Name of measurement (e.g., `Market size`, `CAGR`, `Regional share`).
  * `region` (`VARCHAR(100)`) — Geographic scope (e.g., `Global`, `APAC`).
  * `period` (`VARCHAR(50)`) — Target timeframe or forecast window (e.g., `2024`, `2025-2030`).
  * `value` (`VARCHAR(50)`) — Metric value (e.g., `USD 4.21 B`, `11.2%`).
  * `scope_note` (`TEXT`) — Methodological notes, inclusions, or segment scope.

### Table 3: `clients`
* **Purpose:** Stores enterprise client profiles and their purchased report access permissions.
* **Columns:**
  * `id` (`VARCHAR(10)`, Primary Key) — Unique client account ID (e.g., `C-01`, `C-02`).
  * `company` (`VARCHAR(100)`, Not Null) — Organization name.
  * `contact_email` (`VARCHAR(100)`, Not Null) — Client point-of-contact email address.
  * `purchased_reports` (`TEXT`, Not Null) — Comma-separated list of purchased report IDs (e.g., `R-101, R-103`).

---

## 3. Setup and Installation

### Prerequisites
* Python 3.11+ (tested on Python 3.13)
* MySQL Server 8.0 running locally on port 3306
* Ollama running locally (`ollama run nomic-embed-text`)

### Step 1: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 2: Configure Environment Variables
Copy `.env.example` to `.env` and fill in your actual credentials:
```bash
cp .env.example .env
```

---

## 4. Database Connection Verification (Step 1)

Run the verification script:
```bash
python backend/scripts/test_db.py
```

---

## 5. Report Ingestion and Vector Storage Pipeline (Step 2)

### Generate Seed PDF Documents
```bash
python backend/scripts/generate_sample_reports.py
```

### Ingest Reports via CLI
```bash
python backend/scripts/ingest_reports.py
```

Chunks are stored with stable IDs: `{report_id}_p{page_number}_c{chunk_index}`, guaranteeing **zero duplicate chunks** on repeated runs.

---

## 6. Secure Retrieval-Augmented Generation (Step 3)

### How Entitlement is Enforced (Pre-Retrieval)
1. **Pre-LLM Authorization Check**: The `EntitlementService` validates the client ID and queries MySQL for purchased reports.
   * `C-01`: Purchased `R-101`, `R-103` + Public `R-102`.
   * `C-02`: Purchased `R-103` + Public `R-102`. Restricted: `R-101`.
2. **Hard Vector Query Filter**: ChromaDB is queried with `where={"report_id": {"$in": accessible_reports}}`. **Protected chunks are never retrieved into memory and never sent to the LLM.**
3. **Restricted Report Upgrade Offer**: If an unauthorized client targets a paid report they have not bought, an upgrade notice is generated, and zero protected figures are disclosed.
4. **Prompt Injection Defense**: Retrieved text is tagged inside `<untrusted_source_document>` tags. Injections (such as R-102 page 14's command to print client emails) are neutralized and logged.
5. **Hybrid Search**: Combines semantic vector similarity with exact keyword and page/report metadata boosting.

### Running Interactive RAG Pipeline Verification
```bash
python backend/scripts/test_rag_pipeline.py
```

---

## 7. Running Unit Tests

Run the complete test suite (12 tests):
```bash
pytest tests/ -v
```

Verified test coverage:
* `test_pdf_extraction`: Validates PyMuPDF extracts text page by page.
* `test_missing_pdf_handling`: Validates safe error handling on missing files.
* `test_chunking_and_metadata_preservation`: Confirms metadata retention across chunks.
* `test_deduplication_in_vector_store`: Validates idempotent ChromaDB upserts.
* `test_ingestion_service_skips_missing_safely`: Proves graceful file skipping.
* `test_client_entitlements_resolution`: Validates client authorization boundaries.
* `test_unknown_client_rejected`: Rejects unauthorized client IDs.
* `test_c01_can_retrieve_r101_market_size`: C-01 retrieves USD 4.21 B from R-101.
* `test_c02_cannot_retrieve_r101_figures`: C-02 receives 0 chunks from R-101 and an upgrade notice.
* `test_injection_trap_treated_as_data`: R-102 p.14 trap is neutralized; no client emails leaked.
* `test_empty_or_unmatched_query_handling`: Unknown query returns safe limitations without fabrication.
* `test_supporting_passages_have_complete_citations`: Every passage contains report ID, title, and page number.

---

## 8. Running the FastAPI Backend Server

Start the development server with Uvicorn:
```bash
uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

Available endpoints:
* **Swagger UI**: `http://127.0.0.1:8000/docs`
* **Health Check**: `GET /health`
* **Database Status**: `GET /api/v1/db-status`
* **Trigger Ingestion**: `POST /api/v1/ingest`
* **Vector Store Stats**: `GET /api/v1/vector-status`
* **Secure Retrieval**: `POST /api/v1/retrieve`
  ```json
  {
    "client_id": "C-01",
    "question": "What is the global smart water meter market size in 2024?",
    "top_k": 5
  }
  ```
* **RAG Chat**: `POST /api/v1/chat`
  ```json
  {
    "client_id": "C-02",
    "question": "What is the 2024 global market size in R-101?",
    "top_k": 5
  }
  ```