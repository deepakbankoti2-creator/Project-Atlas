# Project Atlas — AI Software Developer / Report Copilot

Project Atlas is an AI-powered software developer and report copilot that analyzes intelligence research reports, market metrics, and client report entitlements.

---

## 1. Project Overview & Architecture

```
Project-Atlas/
├── .env.example              # Template environment variables for MySQL
├── .gitignore                # Protects credentials (.env) and virtual environments
├── README.md                 # Complete documentation and run guide
├── requirements.txt          # Python dependencies
└── backend/
    ├── __init__.py
    ├── main.py               # FastAPI application entrypoint with health & API routes
    ├── app/
    │   ├── __init__.py
    │   ├── core/
    │   │   ├── __init__.py
    │   │   ├── config.py     # Environment variable loading & safe DB URL generation
    │   │   └── database.py   # SQLAlchemy engine, sessionmaker & get_db dependency
    │   ├── models/
    │   │   ├── __init__.py
    │   │   └── schema.py     # SQLAlchemy ORM models matching existing MySQL tables
    │   └── api/
    │       ├── __init__.py
    │       └── v1/
    │           ├── __init__.py
    │           └── endpoints.py # REST endpoints to query reports, metrics, & clients
    └── scripts/
        ├── __init__.py
        └── test_db.py        # Database connection & table inspection test script
```

---

## 2. Existing Database Schema (`project_atlas`)

The database `project_atlas` contains 3 core tables created in MySQL Workbench:

### Table 1: `reports`
* **Purpose:** Stores research, market outlook, and intelligence publications.
* **Columns:**
  * `id` (`VARCHAR(10)`, Primary Key) — Unique report identifier (e.g., `R-101`, `R-102`).
  * `title` (`VARCHAR(255)`, Not Null) — Report publication title.
  * `publisher` (`VARCHAR(100)`, Not Null) — Authoring entity or research publisher (e.g., `CMR`, `Aquila Insights`).
  * `published` (`DATE`, Not Null) — Release date of the report.
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
* Python 3.11+ (Python 3.13 installed)
* MySQL Server 8.0 running locally on port 3306

### Step 1: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 2: Configure Environment Variables
Copy `.env.example` to `.env` and fill in your actual MySQL credentials:
```bash
cp .env.example .env
```

Edit `.env`:
```env
DB_HOST=localhost
DB_PORT=3306
DB_NAME=project_atlas
DB_USER=root
DB_PASSWORD=your_actual_mysql_password
```

---

## 4. Running the Database Connection Test

Run the verification script:
```bash
python backend/scripts/test_db.py
```

The script will:
1. Connect to the configured MySQL instance using SQLAlchemy.
2. Verify the connected database is `project_atlas`.
3. Inspect and list all existing tables without running any destructive commands.
4. Count and inspect existing rows and columns.
5. Report whether connection succeeded without exposing passwords or secrets.

---

## 5. Running the FastAPI Backend Server

Start the development server with Uvicorn:
```bash
uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

* Interactive Swagger Docs: `http://127.0.0.1:8000/docs`
* Health Check: `http://127.0.0.1:8000/health`
* Database Status: `http://127.0.0.1:8000/api/v1/db-status`
* Reports API: `http://127.0.0.1:8000/api/v1/reports`
* Clients API: `http://127.0.0.1:8000/api/v1/clients`