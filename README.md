# OSINT Missing Persons Canada

An open-source intelligence (OSINT) platform designed to help locate missing children in Canada. The platform ingests case data from the [Missing Children Society of Canada](https://mcsc.ca/), then layers on active investigation capabilities including digital footprint analysis, web mention scanning, and facial recognition cross-matching.

> **This tool is built to cooperate with law enforcement.** All findings are intended to be reported to police. This is not a vigilante tool.

## Live Dashboard

Once running locally, the dashboard is available at:

```
http://127.0.0.1:8000
```

The dashboard provides:
- Interactive map of all active missing children cases across Canada
- Case detail pages with photos, descriptions, and authority contact info
- OSINT investigation launcher with lead tracking
- Face detection and cross-case matching results
- Lead filtering, scoring, and review workflow

The auto-generated API documentation is available at:

```
http://127.0.0.1:8000/docs
```

---

## Current Status

| Phase | Name | Status |
|-------|------|--------|
| 1 | Data Foundation | Complete |
| 2 | Digital Footprint Engine | Complete |
| 3 | Facial Search Engine | Complete |
| 4 | Trafficking Indicator Monitor | Planned |
| 5 | Social Network Analysis | Planned |
| 6 | Abductor Tracking | Planned |
| 7 | Intelligence Hub | Planned |

---

## What Each Phase Does

### Phase 1 -- Data Foundation

Ingests all active missing children cases from the MCSC public ArcGIS API. No scraping needed; structured JSON with coordinates, photos, and case metadata.

- 83 active cases, 120 photos downloaded
- SQLite database with full case schema
- GeoJSON endpoint for map rendering
- Province/status/name/age filtering
- Background sync scheduler (configurable interval)

### Phase 2 -- Digital Footprint Engine

Generates plausible usernames from a missing person's name and checks for account existence across 15 platforms with reliable detection. Simultaneously scans public web sources for mentions.

- **Username enumeration:** GitHub, Reddit, YouTube, Twitch, Steam, Roblox, Pinterest, SoundCloud, DeviantArt, Wattpad, Medium, Linktree, Vimeo, Flickr, ASKfm
- **Web mention scanning:** Google News (RSS), Reddit search, DuckDuckGo
- **Lead scoring:** Confidence-based scoring considering platform reliability, recency, and location relevance
- **Investigation orchestrator:** Runs all modules concurrently per case

### Phase 3 -- Facial Search Engine

Extracts faces from case photos, computes 128-dimensional face encodings, and compares across all cases to find potential matches.

- Face detection via `face_recognition` (dlib) with HOG or CNN models
- Cross-case face comparison with configurable distance threshold (default 0.55)
- Face crop extraction and storage for visual review
- Upload-an-image search against all indexed faces
- Pluggable reverse image search providers (PimEyes, TinEye, Google Vision -- all optional, require paid API keys)
- Match review workflow (confirm/reject as same person)

---

## Quick Start

### Prerequisites

- Python 3.11+
- [CMake](https://cmake.org/download/) (required for building `dlib`)
- Git

### Setup

```bash
# Clone the repository
git clone https://github.com/consistentlearningguy/osint-missing-persons-ca.git
cd osint-missing-persons-ca

# Create virtual environment
python -m venv venv

# Activate it
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp .env.example .env
```

### Initial Data Sync

Pull all case data and photos from the MCSC API:

```bash
python scripts/initial_sync.py
```

This will:
- Fetch all active missing children cases
- Download case photos to `data/images/`
- Store everything in `data/db.sqlite`

### Index Faces

After syncing data, extract face encodings from all photos:

```bash
python scripts/index_faces.py --match
```

Options:
- `--force` -- Re-index photos that already have encodings
- `--match` -- Run cross-case face matching after indexing
- `--case 8037` -- Index only a specific case
- `--threshold 0.5` -- Custom match distance threshold

### Start the Server

```bash
python -m backend.main
```

Or with uvicorn directly:

```bash
uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

Then open **http://127.0.0.1:8000** in your browser.

---

## Project Structure

```
osint-missing-persons-ca/
├── backend/
│   ├── main.py                         # FastAPI app entrypoint
│   ├── core/
│   │   ├── config.py                   # Settings from environment variables
│   │   ├── database.py                 # SQLAlchemy engine + session setup
│   │   └── scheduler.py               # Background sync scheduler
│   ├── ingestion/
│   │   └── mcsc_client.py              # MCSC ArcGIS API client + photo downloader
│   ├── analysis/
│   │   ├── username_search.py          # Username enumeration across 15 platforms
│   │   ├── web_mentions.py             # Web mention scanner (News, Reddit, DDG)
│   │   ├── lead_scoring.py             # Confidence scoring for leads
│   │   ├── investigate.py              # Investigation orchestrator
│   │   ├── face_engine.py              # Face detection, encoding, matching
│   │   └── reverse_image_search.py     # Pluggable PimEyes/TinEye/Google Vision
│   ├── api/
│   │   ├── cases.py                    # Case CRUD + stats + GeoJSON
│   │   ├── sync.py                     # Manual sync trigger + history
│   │   ├── investigations.py           # Investigation lifecycle + leads
│   │   └── faces.py                    # Face index/match/search/review
│   ├── models/
│   │   ├── case.py                     # MissingCase, CasePhoto, SyncLog
│   │   ├── investigation.py            # Investigation, Lead
│   │   └── face.py                     # FaceEncoding, FaceMatch
│   ├── templates/
│   │   ├── base.html                   # Base layout (Tailwind CSS)
│   │   ├── index.html                  # Dashboard with map
│   │   └── case_detail.html            # Case detail + investigation UI
│   └── static/
│       ├── css/style.css               # Custom styles
│       └── js/app.js                   # Dashboard, map, investigation UI logic
├── scripts/
│   ├── initial_sync.py                 # One-time data sync script
│   └── index_faces.py                  # Face indexing CLI
├── data/                               # Runtime data (gitignored)
│   ├── db.sqlite                       # SQLite database
│   ├── images/                         # Downloaded case photos
│   └── faces/                          # Extracted face crops
├── .env.example                        # Environment variable template
├── .gitignore
└── requirements.txt
```

---

## API Reference

### Cases

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/cases` | List cases (filterable by province, status, search, case_status) |
| `GET` | `/api/cases/stats` | Aggregate statistics (by province, status, age, year) |
| `GET` | `/api/cases/geojson` | GeoJSON FeatureCollection for map rendering |
| `GET` | `/api/cases/{objectid}` | Single case detail with photos |

### Data Sync

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/sync` | Trigger manual sync from MCSC |
| `GET` | `/api/sync/history` | Recent sync log entries |

### Investigations

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/investigations/{case_objectid}` | Start OSINT investigation (params: `run_usernames`, `run_web`, `run_faces`) |
| `GET` | `/api/investigations/{case_objectid}` | Get investigation status and history |
| `GET` | `/api/investigations/{case_objectid}/leads` | Get leads (filterable by type, confidence, review status) |
| `PATCH` | `/api/investigations/leads/{lead_id}` | Review a lead (mark reviewed, actionable, add notes) |

### Facial Recognition

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/faces/index` | Index faces in case photos (params: `case_objectid`, `force`) |
| `GET` | `/api/faces/stats` | Face index statistics |
| `GET` | `/api/faces/case/{case_objectid}` | Get face encodings and crop paths for a case |
| `POST` | `/api/faces/match` | Run cross-case face matching (params: `case_objectid`, `threshold`) |
| `GET` | `/api/faces/matches` | List stored matches (filterable by case, review status, confidence) |
| `POST` | `/api/faces/search` | Upload an image to search against all indexed faces |
| `PATCH` | `/api/faces/matches/{match_id}` | Review a face match (confirm/reject as same person) |

Full interactive API docs available at `/docs` (Swagger UI) and `/redoc` when the server is running.

---

## Configuration

All configuration is via environment variables (see `.env.example`):

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite:///data/db.sqlite` | Database connection string |
| `MCSC_FEATURE_SERVER_URL` | *(MCSC ArcGIS URL)* | Data source endpoint |
| `SYNC_INTERVAL_MINUTES` | `60` | Background sync frequency |
| `HOST` | `127.0.0.1` | Server bind address |
| `PORT` | `8000` | Server port |
| `DEBUG` | `true` | Enable hot reload |
| `FACE_DETECTION_MODEL` | `hog` | `hog` (fast/CPU) or `cnn` (accurate/GPU) |
| `FACE_MATCH_THRESHOLD` | `0.55` | Face distance threshold (lower = stricter) |
| `FACE_UPSAMPLE_COUNT` | `1` | Image upsampling for smaller face detection |
| `FACE_CROP_PADDING` | `0.25` | Padding around face crops (%) |
| `PIMEYES_API_KEY` | *None* | Optional: PimEyes reverse image search |
| `GOOGLE_VISION_API_KEY` | *None* | Optional: Google Vision reverse image search |
| `TINEYE_API_KEY` | *None* | Optional: TinEye reverse image search |

---

## Tech Stack

- **Backend:** Python 3.11+, FastAPI, SQLAlchemy, SQLite
- **Frontend:** Jinja2 templates, Tailwind CSS (CDN), Leaflet.js
- **Face Recognition:** face_recognition (dlib), Pillow, NumPy
- **HTTP Client:** httpx (async)
- **Scheduler:** APScheduler
- **Logging:** Loguru

---

## Data Source

All case data comes from the **Missing Children Society of Canada (MCSC)** public ArcGIS FeatureServer API. This is publicly accessible structured data provided by a Canadian non-profit organization. No scraping, no authentication, no terms of service violations.

---

## Legal and Ethical Notes

- This platform is designed to **assist law enforcement**, not replace it. All leads should be reported to the appropriate police authority listed on each case.
- **Do not** use this tool for vigilante action, harassment, or any purpose that could endanger a missing person's safety.
- Case data is sourced from a public government-adjacent API. Photos and descriptions are published by MCSC specifically to increase public awareness.
- Username enumeration and web mention scanning use only publicly accessible endpoints and do not bypass any authentication or access controls.
- Face matching is performed locally. No biometric data is transmitted to external services unless optional reverse image search API keys are configured.

---

## Contributing

This project is in active development. If you are a law enforcement professional, data scientist, or developer interested in helping locate missing children, please open an issue or reach out.

---

## License

This project is intended for humanitarian use in cooperation with law enforcement. Please use responsibly.
