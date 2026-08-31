# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CV Matching is a sales automation system for parsing CVs from Google Docs, performing semantic AI-powered search using embeddings, and tracking submission history. The application has two main components:

- **Backend**: FastAPI REST API (main.py) with background task scheduling
- **Frontend**: Streamlit web UI (ui.py) with multi-page support

## Tech Stack

- **Backend Framework**: FastAPI with Uvicorn
- **Frontend**: Streamlit
- **Database**: PostgreSQL 15 with SQLAlchemy ORM
- **ML/AI**: Sentence Transformers (paraphrase-multilingual-MiniLM-L12-v2) for embeddings
- **Google Integration**: Google Drive API (Docs, Sheets, export)
- **Task Scheduling**: APScheduler (nightly maintenance jobs)

## Prerequisites & Setup

### Initial Setup
1. **Python 3.11+** and **Docker Desktop** required
2. Create `.env` file in project root (copy from `.env.example`):
   - Set DATABASE_URL, POSTGRES_PASSWORD, GOOGLE_CREDS_PATH, SPREADSHEET_URL
3. Place Google service account JSON file as `google_creds.json` in root
4. Start PostgreSQL: `docker-compose up -d` (creates database and pg_trgm extension)

### Environment Configuration
- `DATABASE_URL`: PostgreSQL connection (format: postgresql://user:password@host:port/database)
- `GOOGLE_CREDS_PATH`: Path to Google service account JSON
- `SPREADSHEET_URL`: Google Sheets export URL (Excel format)
- `API_BASE_URL`: Backend base URL (default: http://localhost:8000)

## Running the Application

### Backend
```
pip install -r requirements.txt
python -m uvicorn main:app --reload --port 8000
```
Backend runs on http://localhost:8000

### Frontend
```
python -m streamlit run ui.py
```
Frontend runs on http://localhost:8501

### Full Stack (Production-like)
```
docker-compose up --build
```

## High-Level Architecture

### Data Model (SQLAlchemy ORM in models.py)
- **Candidate**: Resume data (name, CV URL, extracted stack/seniority/direction, embeddings)
- **Submission**: Candidate submissions to clients via brokers (tracks status, request result)
- **Vacancy**: Job requisitions from the spreadsheet

### Core Processing Pipeline

#### 1. Data Synchronization (google_sheets.py)
- Downloads Excel from Google Sheets via Drive API
- Creates/updates Candidate records with CV URLs, submitted_at dates
- Creates/updates Submission records (client, broker, status, request_result)
- Upserts Vacancy records from request titles

##### Google Spreadsheet Columns
| Column | Description |
|--------|-------------|
| Date | Submission date |
| Request | Vacancy title |
| Broker | Intermediary/broker name |
| Client | End client name |
| Sales | Sales person |
| Thread | Unique vacancy identifier (used as vacancy id for deduplication) |
| Request description | Vacancy requirements text |
| Link | Candidate CV URL |
| Additional info | Extra notes |
| Candidate | Candidate full name |
| Status | Submission status |
| Request result | Outcome of the request |
| Save failed | Flag for failed saves |
| Registration | Registration info |
| Department | Candidate department/direction |
| CV Builder | CV builder tool used |
| TS Request Created | Timestamp: request created |
| TS CV Start | Timestamp: CV work started |
| TS CV Finished | Timestamp: CV work finished |
| TS Request Processed | Timestamp: request processed |

#### 2. CV Text Extraction (google_docs.py, used in main.py)
- Fetches CV text from Google Docs/PDF/DOCX files
- Tries Drive export first (more reliable), falls back to Docs API
- Stores raw text in Candidate.cv_text field

#### 3. CV Parsing (cv_parser.py)
- Extracts technical stack from CV text using regex matching against TECH_KEYWORDS dict
- Detects seniority level (Junior/Middle/Senior/Lead) from keywords or years of experience
- Identifies job direction (Backend, Frontend, Data Engineer, etc.) from DIRECTION_KEYWORDS
- Returns dict: {stack, seniority, direction}

#### 4. Embeddings Generation (embeddings.py)
- Uses SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
- Converts CV text to 384-dim vectors, stored as binary in Candidate.embedding
- Provides cosine_similarity() for vector comparison

#### 5. Search Methods

**Semantic Search** (main.py /semantic-match endpoint):
- Embeds query, compares against all candidate embeddings via cosine similarity
- Scores >= 30.0 are returned, sorted by score descending

**Fuzzy Search** (fuzzy_search.py):
- Uses PostgreSQL word_similarity() (pg_trgm extension)
- Matches keywords against stack and cv_text fields
- Supports configurable threshold (default 0.1 for 10% match)

**Classic Search** (matcher.py):
- Simple keyword extraction and substring matching
- Returns percentage of matched keywords

### Submission History & Badge Logic (fuzzy_search.py get_candidate_badge())
- 4-tier matching hierarchy for candidate badges:
  1. Exact (Client + Broker) match - red/yellow/green depending on request_result
  2. Client match - checks if submitted to same client via different broker
  3. Broker match - checks if worked with same broker on different project
  4. No history - "clean candidate" (green badge)
- Badges: green (available), yellow (in progress), red (employed/failed)

### Nightly Maintenance Job (main.py nightly_maintenance_job())
- Runs at 01:00 via APScheduler
- Full Excel sync + 2-day delta processing (texts, parsing, embeddings)
- Can be triggered manually via /sync-excel endpoint with background tasks

## File Structure

```
cv_matching/
├── main.py                 # FastAPI app, REST endpoints, background tasks
├── ui.py                   # Main Streamlit page (search interface)
├── pages/search.py         # Streamlit page (detailed candidate analysis)
├── models.py               # SQLAlchemy ORM models (Candidate, Submission, Vacancy)
├── db.py                   # Database connection & session setup
├── cv_parser.py            # CV text parsing (stack, seniority, direction extraction)
├── embeddings.py           # Sentence Transformer integration
├── fuzzy_search.py         # PostgreSQL fuzzy matching & badge logic
├── matcher.py              # Basic keyword matching
├── google_docs.py          # Google Docs/PDF/DOCX text extraction
├── google_sheets.py        # Google Sheets/Excel sync
├── docker-compose.yml      # PostgreSQL container
├── Dockerfile              # Application container (not used in current setup)
├── init.sql                # Database initialization (creates pg_trgm extension)
├── requirements.txt        # Python dependencies
├── .env.example            # Environment variables template
└── README.md               # Russian setup instructions
```

## API Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | / | Health check |
| POST | /sync-excel | Trigger full Excel sync + background processing |
| POST | /update-cv-texts | Download CV texts from Google Docs (with optional days_limit) |
| POST | /parse-cv-stacks | Extract stack/seniority/direction from texts |
| POST | /build-embeddings | Generate AI vectors for semantic search |
| POST | /semantic-match | Semantic AI search by query |
| POST | /fuzzy-match | Fuzzy keyword matching with word_similarity |
| GET | /search | Basic keyword matching |
| GET | /sync-status | Get current sync task status (reads sync_status.txt) |
| POST | /analyze-cv | Detailed line-by-line CV vs requirements comparison |

## Key Design Decisions

1. **Background Processing**: Heavy tasks (CV downloads, embeddings) run async via FastAPI BackgroundTasks to prevent timeouts
2. **Fuzzy Search**: Uses PostgreSQL word_similarity() with pg_trgm, supporting typo tolerance
3. **Candidate Deduplication**: Multiple CVs per candidate supported; badges check across all submissions for a name
4. **Embedding Storage**: Binary format (numpy float32 tobytes) for space efficiency
5. **CV Text Extraction**: Multi-method fallback (Drive export > Docs API > PDF/DOCX parsing)
6. **Direction Detection**: Header-weighted (first 600 chars scored 5x) to prioritize job title/summary

## Common Development Tasks

### Running Backend
```
python -m uvicorn main:app --reload --port 8000
```

### Running Frontend
```
python -m streamlit run ui.py
```

### Installing Dependencies
```
pip install -r requirements.txt
```

### Syncing Data (via CLI)
```
curl -X POST http://localhost:8000/sync-excel
```

### Checking Sync Status
```
curl http://localhost:8000/sync-status
```

### Database Container
```
# Start
docker-compose up -d

# Stop
docker-compose down

# View logs
docker-compose logs db
```

## Important Notes

- **Parallelism Settings**: Environment variables in main.py disable tokenizer parallelism to prevent conflicts with NumPy threading
- **Status Tracking**: Sync progress written to sync_status.txt file, polled by frontend
- **PostgreSQL Extension**: pg_trgm required for fuzzy search; created automatically by init.sql
- **Date Parsing**: Uses pandas.to_datetime() with dayfirst=True for European date formats
- **API Timeouts**: Sync endpoints have 1200s (20 min) timeout; regular endpoints 20s
