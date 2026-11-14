# 🛡️ PostgreSQL Database Migration Safety Checker

> **Hackathon**: HACKNAUTS 2.0 (Chitkara University)  
> **Team Name**: Load Balancers  
> **Team Members**: Ishika Badiyala | Harshita | Gurnoor  
> **Location**: Chitkara University, Punjab, India (30.86°N, 75.86°E)

---

## 📌 1. Problem Statement

Database schema migrations introduce severe production risks:
- **Table Locking & Outages**: A single `ALTER TABLE` on a live table can acquire an `ACCESS EXCLUSIVE` lock, freezing queries and taking down web services.
- **Development vs. Production Discrepancy**: Staging databases typically have ~1,000 rows where migrations finish in milliseconds. Production has crores of rows, causing table rewrites that take hours.
- **Lock Queues (Convoy Effect)**: In PostgreSQL, a migration waiting behind a slow query blocks **all subsequent queries**, even lightweight `SELECT` reads!
- **Unsafe Index Creation**: Standard `CREATE INDEX` blocks all `INSERT`, `UPDATE`, and `DELETE` operations during the entire index construction.
- **Monolithic Bulk Updates**: Monolithic `UPDATE` queries lock vast ranges of rows, flood the Write-Ahead Log (WAL), and trigger replication lag.

Most teams rely on manual DBA runbooks or text-only SQL linters. Text linters only inspect regex patterns and do not know the actual table size or whether lock queues are building up.

### Our Solution
A **pre-deployment migration safety checker** that parses SQL files into an Abstract Syntax Tree (AST) using `pglast`, cross-references live table statistics (`pg_stat_user_tables`, `pg_total_relation_size()`) via `psycopg3`, assigns severity-graded risks (`HIGH`, `MEDIUM`, `LOW`), and generates **production-ready safe SQL alternatives**.

> ⚠️ **Zero-Execution Guarantee**: The application **NEVER executes** the uploaded migration SQL against any connected database. It strictly performs read-only metadata catalog queries.

---

## 🏗️ 2. System Architecture & Workflow

```text
       +-----------------------+
       |   Upload SQL File     |
       +-----------+-----------+
                   |
         +---------+---------+
         |                   |
         v                   v
+-----------------+  +----------------------+
|  pglast Parse   |  | psycopg3 DB Connect  |
|  (Generate AST) |  | (Read-only metadata) |
+--------+--------+  +----------+-----------+
         |                      |
         | Parsed AST           | Live Row Counts,
         | & Line Numbers       | Table Sizes & Locks
         |                      |
         +---------> + <--------+
                     |
                     v
       +----------------------------+
       |  Rule-Based Safety Engine  |
       |  (8 Modular Safety Rules)  |
       +-------------+--------------+
                     |
                     v
       +----------------------------+
       |   Safe SQL Generator       |
       |  (CONCURRENTLY, NOT VALID) |
       +-------------+--------------+
                     |
                     v
       +----------------------------+
       | Final Report & Benchmarks  |
       |  (Streamlit, Plotly, DOT)  |
       +----------------------------+
```

### Key Architectural Principle
**SQL AST Parsing (`pglast`)** and **Database Metadata Extraction (`psycopg3`)** run as independent, parallel branches. `pglast` operates purely in memory with zero database dependency. When a database is connected, live catalog data enriches the risk engine. If no database is connected, the engine gracefully falls back to manual metadata or static analysis.

---

## 🧰 3. Technology Stack

- **Frontend**: Streamlit, Plotly (interactive latency timeseries), Graphviz (workflow and decision trees).
- **Backend API**: Python, FastAPI, Uvicorn, Pydantic.
- **SQL Parser**: `pglast` (official libpg_query PostgreSQL parser binding).
- **Database Driver**: `psycopg` 3 (psycopg3 read-only catalog inspector).
- **Testbed Environment**: Docker & Docker Compose running PostgreSQL 16 with 500,000 synthetic rows.
- **Unit Testing**: Pytest.

---

## 📂 4. Project Structure

```text
Database migration checker/
│
├── backend/
│   ├── main.py                  # FastAPI server with /connect-db, /analyze, /metadata
│   ├── database.py              # psycopg3 connection manager (safe parameterization, credential masking)
│   ├── parser.py                # pglast AST parser (extracts commands, line numbers, targets)
│   ├── metadata.py              # Catalog queries (pg_stat_user_tables, pg_class, locks) & demo datasets
│   ├── risk_engine.py           # Core rule engine combining AST + metadata to grade risk
│   ├── safe_sql.py              # Generates drop-in safe SQL alternatives
│   ├── report.py                # Markdown/JSON report generators & Graphviz DOT builders
│   ├── requirements.txt         # Python backend dependencies
│   └── rules/
│       ├── index_rules.py       # Non-concurrent index detection & write lock scoring
│       ├── alter_rules.py       # ALTER COLUMN TYPE & ADD COLUMN volatile defaults
│       ├── constraint_rules.py  # SET NOT NULL & unvalidated ADD FOREIGN KEY
│       └── update_rules.py      # Unbounded UPDATE & destructive DROP statements
│
├── frontend/
│   └── app.py                   # Streamlit interactive dashboard with Plotly & Graphviz
│
├── benchmarks/
│   ├── docker-compose.yml       # PostgreSQL 16 isolated test container
│   ├── setup.sql                # Schema setup with 500,000 seeded orders & customers
│   ├── benchmark.py             # Live latency test harness (concurrent workers)
│   └── benchmark_results.json   # Measured benchmark dataset for dashboard graphs
│
├── tests/
│   ├── test_parser.py           # Unit tests for AST parsing & line extraction
│   ├── test_rules.py            # Unit tests for safety rules
│   └── test_risk_engine.py      # Unit tests for risk scoring & safe SQL generation
│
├── samples/
│   ├── 01_unsafe_ecommerce_migration.sql   # Unsafe production anti-patterns
│   ├── 02_safe_ecommerce_migration.sql     # Safe zero-downtime migration
│   ├── 03_payments_high_risk_migration.sql # Destructive changes & volatile defaults
│   └── 04_simple_index_migration.sql       # Basic single index migration
│
├── run.ps1                      # One-click startup script (PowerShell)
├── run.bat                      # One-click startup script (Batch)
├── .env.example                 # Environment configuration template
└── README.md                    # Project documentation
```

---

## ⚡ 5. Setup & Execution Instructions

### Prerequisites
- Python 3.10+ (Python 3.11, 3.12, 3.13, 3.14 supported)
- (Optional) Docker for running local performance benchmarks

### Step 1: Install Dependencies
```bash
pip install -r backend/requirements.txt
```

### Step 2: Run Unit Tests
Verify all 18 unit tests pass:
```bash
pytest tests/
```

### Step 3: Start the Application

#### Option A: One-Click Launch (Windows)
Double-click `run.bat` or run:
```powershell
.\run.ps1
```

#### Option B: Manual Command Line Launch
Terminal 1 (Backend API):
```bash
uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

Terminal 2 (Streamlit UI):
```bash
streamlit run frontend/app.py
```
Open your browser at `http://localhost:8501`.

---

## 🔍 6. Safety Rules Implemented

| Rule | Detected Pattern | Production Risk | Severity | Safe Alternative |
|---|---|---|---|---|
| **Rule 1: Non-Concurrent Index** | `CREATE INDEX ...` without `CONCURRENTLY` | Acquires `SHARE` lock, blocks all `INSERT`, `UPDATE`, `DELETE` operations | **HIGH** on large tables | `CREATE INDEX CONCURRENTLY` |
| **Rule 2: ALTER COLUMN TYPE** | `ALTER TABLE ... TYPE ...` | Full table rewrite under `ACCESS EXCLUSIVE` lock | **HIGH** | Expand-Contract dual write pattern |
| **Rule 3: Direct SET NOT NULL** | `ALTER COLUMN ... SET NOT NULL` | Scans entire table under `ACCESS EXCLUSIVE` lock | **HIGH** | `CHECK ... NOT VALID` -> `VALIDATE CONSTRAINT` |
| **Rule 4: Unvalidated FOREIGN KEY** | `ADD CONSTRAINT ... FOREIGN KEY ...` without `NOT VALID` | Scans table, locks referenced table (`SHARE ROW EXCLUSIVE`) | **HIGH** | `ADD CONSTRAINT ... NOT VALID` then validate |
| **Rule 5: Unbounded UPDATE** | `UPDATE ...` without `WHERE` | Long transactions, locks all rows, WAL explosion | **HIGH** | Keyset / chunked pagination (batch of 5,000) |
| **Rule 6: Volatile Column Defaults** | `ADD COLUMN ... DEFAULT clock_timestamp()` | Forces table rewrite even on PostgreSQL 11+ | **HIGH** | Add nullable column -> backfill in batches |
| **Rule 7: Missing lock_timeout** | Migration lacking `SET lock_timeout` | Queues behind slow queries, blocking all incoming traffic | **HIGH** | Prepend `SET lock_timeout = '3s';` |
| **Rule 8: Destructive DROP** | `DROP TABLE` or `DROP COLUMN` | Immediate data loss, locks dependent queries | **HIGH** | 3-phase application deprecation |

---

## 📊 7. Measured Benchmark Results

We executed a controlled test against PostgreSQL 16 on a table with 500,000 rows under concurrent traffic (6 workers, 70% SELECT / 30% INSERT):

- **Normal `CREATE INDEX`**:
  - Maximum write query latency spiked to **3,418 ms**.
  - **48 write queries** were blocked in the lock queue waiting for the `SHARE` lock to release.
- **`CREATE INDEX CONCURRENTLY`**:
  - Maximum write query latency stayed low at **54 ms** (p95 = 34 ms).
  - **0 write queries** were blocked.
  - Overall migration duration was longer (6.8s vs 3.4s) due to two-pass index construction, but left production traffic 100% available!

---

## 🔮 8. Known Limitations & Future Scope

1. **Transaction Blocks**: `CREATE INDEX CONCURRENTLY` cannot run inside a multi-statement `BEGIN ... COMMIT` block. The safe SQL generator notes this constraint in comments.
2. **PostgreSQL Specific**: Currently built specifically for PostgreSQL's catalog architecture and locking model.
3. **Future Improvements**:
   - GitHub Action / PR Bot to comment risk summaries directly on pull requests.
   - Support for parsing Django, Rails, and Alembic migration files.
   - Ephemeral clone dry-runs using copy-on-write volumes to measure exact lock durations.

---

## 👥 Team Details & Hackathon Alignment

- **Event**: HACKNAUTS 2.0 (Chitkara University)
- **Team**: Load Balancers
- **SDG Alignment**: **SDG 9: Industry, Innovation, and Infrastructure** (Building reliable, outage-resistant software infrastructure).
- **Core Contribution**: Giving development teams automated, size-aware safety checking so migrations never trigger accidental production downtime.
