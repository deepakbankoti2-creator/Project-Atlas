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
│   │   │   └── ingestion.py  # Report ingestion service orchestrator
│   │   └── api/
│   │       ├── __init__.py
│   │       └── v1/
│   │           ├── __init__.py
│   │           └── endpoints.py # REST endpoints (db-status, reports, clients, ingest, search)
│   └── scripts/
│       ├── __init__.py
│       ├── test_db.py        # Database connection & table inspection test script
│       ├── generate_sample_reports.py # Generates test PDF reports matching assignment spec
│       └── ingest_reports.py # CLI ingestion script with summary stats and deduplication
└── tests/
    └── test_ingestion.py     # Comprehensive unit tests for pipeline components
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

`.env` entries:
```env
# Database Credentials
DB_HOST=localhost
DB_PORT=3306
DB_NAME=project_atlas
DB_USER=root
DB_PASSWORD=your_actual_mysql_password

# Ollama LLM & Embeddings
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_CHAT_MODEL=llama3.2:3b
OLLAMA_EMBED_MODEL=nomic-embed-text

# ChromaDB & Ingestion
CHROMA_PERSIST_DIR=data/chroma_db
CHROMA_COLLECTION_NAME=atlas_reports
REPORTS_DIR=data/reports
CHUNK_SIZE=600
CHUNK_OVERLAP=100
```

---

## 4. Database Connection Verification (Step 1)

Run the verification script:
```bash
python backend/scripts/test_db.py
```

The script connects to the configured MySQL instance, inspects tables and row counts, and verifies schema readiness without exposing credentials or executing destructive commands.

---

## 5. Report Ingestion and Vector Storage Pipeline (Step 2)

### Where to Place PDF Reports
Place your PDF files in the directory configured by `REPORTS_DIR` (default: `data/reports/`).
The ingestion pipeline automatically matches files named after the report ID (e.g. `R-101.pdf`, `R-102.pdf`, `R-103.pdf`) or containing the report ID in the file name.

To generate synthetic test PDFs matching the assignment's Appendix A:
```bash
python backend/scripts/generate_sample_reports.py
```

### Running the CLI Ingestion Command
To ingest all available reports:
```bash
python backend/scripts/ingest_reports.py
```

Optional CLI flags:
* Ingest a specific report:
  ```bash
  python backend/scripts/ingest_reports.py --report-id R-101
  ```
* Ingest from a custom directory:
  ```bash
  python backend/scripts/ingest_reports.py --reports-dir path/to/my_reports
  ```
* Force purge and re-index:
  ```bash
  python backend/scripts/ingest_reports.py --force-reindex
  ```

### Deduplication Guarantee
Chunks are stored using deterministic IDs: `{report_id}_p{page_number}_c{chunk_index}` (e.g., `R-101_p8_c0`). Re-running ingestion performs an idempotent upsert, guaranteeing that no duplicate chunks are created in ChromaDB.

---

## 6. Running Unit Tests

Run the test suite with pytest:
```bash
pytest tests/test_ingestion.py -v
```

Verified test coverage:
1. `test_pdf_extraction`: Validates PyMuPDF extracts text page by page with exact page numbers.
2. `test_missing_pdf_handling`: Validates safe error handling when a PDF is not found.
3. `test_chunking_and_metadata_preservation`: Confirms report ID, sector, region, publication year, access, and page number are retained in all chunks.
4. `test_deduplication_in_vector_store`: Proves re-ingesting the same chunks results in identical chunk count without duplicates.
5. `test_ingestion_service_skips_missing_safely`: Proves the service logs warnings and skips unreadable/missing files without crashing.

---

## 7. Running the FastAPI Backend Server

Start the development server with Uvicorn:
```bash
uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

Available endpoints:
* **Interactive Swagger UI**: `http://127.0.0.1:8000/docs`
* **Health Check**: `GET /health`
* **Database Status**: `GET /api/v1/db-status`
* **Trigger Ingestion**: `POST /api/v1/ingest`
* **Vector Store Stats**: `GET /api/v1/vector-status`
* **Semantic Search & Entitlements**: `GET /api/v1/search?q=smart%20water%20meter&client_id=C-01`