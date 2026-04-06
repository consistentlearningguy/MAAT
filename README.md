# MAAT — Truth from Chaos

OSINT intelligence platform for Canadian missing children cases. Named after Ma'at, the Egyptian concept of truth and order — because finding missing children means extracting truth from chaos.

**The end goal: find the missing kids and notify authority so we can actually help.**

## What MAAT does

1. **Gathers** public case data from the Missing Children Society of Canada ArcGIS feed
2. **Sweeps** multiple OSINT connectors (news, archives, social, official registries) for leads
3. **Scores** each lead with transparent confidence ratings and rationale
4. **Clusters** leads thematically — sighting reports, media coverage, official updates
5. **Detects patterns** — geographic clusters, temporal bursts, cold trails
6. **Synthesizes** actionable intelligence — situation summaries, authority briefs, priority recommendations
7. **Routes** discoveries to the listed investigating authority or MCSC

## Safety position

- Official facts and inferred context are separated.
- The public site is for awareness and lawful public-lead triage only.
- Use only lawful, public, non-authenticated sources.
- No scraping behind logins, no doxxing, no contacting relatives, no vigilante action.
- Every lead should be reported to the listed authority or the Missing Children Society of Canada.
- MAAT generates intelligence — humans and authorities make decisions.

## Monorepo structure

```text
/
  docs/                         # Main public product, static-first, GitHub Pages compatible
    assets/
    data/
    app/
      components/
      views/
      lib/
      state/
      styles/
  backend/                      # Optional FastAPI backend for local sync/export/investigator mode
    api/
    core/
    ingestion/
    enrichment/
    osint/
      connectors/
      scoring/
      normalization/
      synthesis.py              # MAAT intelligence synthesis engine
    models/
    services/
  shared/                       # Shared schemas, constants, and utilities
    schemas/
    constants/
    utils/
  scripts/                      # Local sync/export/build entrypoints
  data/                         # Local cache, exports, public reference layers
  tests/
```

**[VIEW LIVE DASHBOARD](https://consistentlearningguy.github.io/osint-missing-persons-ca/)**

## What changed from the old repo

Kept and migrated:
- ArcGIS ingestion intent and SQLite-first local workflow.
- FastAPI as the optional backend surface.
- Static deployment path via `docs/`.

Replaced:
- Railway-first deployment assumptions.
- Jinja-backed public dashboard flow.
- Direct coupling between the public site and backend runtime.
- Monolithic `analysis/` behavior in favor of adapterized, feature-flagged OSINT connectors.

Downgraded to optional:
- Face workflows.
- Reverse image workflows.
- SpiderFoot, SearXNG, theHarvester, Ahmia, Recon-ng, OnionSearch, and other integrations.

## Required vs optional

Required for the free public dashboard:
- `docs/`
- `docs/data/public-cases.json` or live ArcGIS browser fetch
- No secrets
- No backend

Optional for developer/investigator mode:
- `backend/`
- SQLite database in `data/db.sqlite`
- Sync/export scripts
- Feature-flagged connector setup

## Quick start

### 1. Install base dependencies

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

### 2. Use the static dashboard only

Open `docs/index.html` locally or deploy `docs/` directly to GitHub Pages / Cloudflare Pages.

The bundled `docs/data/public-cases.json` is a sample export for offline preview. Replace it with a live export using the scripts below, or use the in-browser live-source toggle.

### 3. Optional backend mode

```bash
python -m scripts.sync_cases
python -m scripts.export_public_data
python -m backend.main
```

Backend endpoints:
- `/healthz`
- `/api/cases`
- `/api/cases/stats`
- `/api/exports/public.json`
- `/api/exports/public.csv`
- `/api/sync/cases`
- `/api/sync/public-export`
- `/api/investigations/...` when `ENABLE_INVESTIGATOR_MODE=true`

## Static deployment on GitHub Pages

1. Push the repo to GitHub.
2. In repository settings, open `Pages`.
3. Choose `Deploy from a branch`.
4. Select branch `main` and folder `/docs`.
5. Save.

The public site does not need backend secrets. If you want fresher static data, run:

```bash
python -m scripts.sync_cases
python -m scripts.build_docs
```

Then commit the updated `docs/data/` files.

## Optional connector setup

All connectors are disabled by default.

Feature flags:
- `ENABLE_INVESTIGATOR_MODE=true`
- `ENABLE_CLEAR_WEB_CONNECTORS=true`
- `ENABLE_PUBLIC_PROFILE_CHECKS=true`
- `ENABLE_REVERSE_IMAGE_HOOKS=true`
- `ENABLE_LOCAL_FACE_WORKFLOW=true`
- `ENABLE_DARK_WEB_CONNECTORS=true`
- `ENABLE_EXPERIMENTAL_CONNECTORS=true`

Environment hooks:
- `SEARXNG_URL`
- `GDELT_DOC_API_URL`
- `SPIDERFOOT_URL`
- `THEHARVESTER_BINARY`
- `RECONNG_BINARY`
- `ONIONSEARCH_BINARY`
- `TOR_PROXY_URL`
- `AHMIA_SEARCH_URL`

Current adapter status:
- `searxng`: working HTTP connector when a SearXNG instance is configured, now using grouped social/profile/timeline query pivots.
- `gdelt-doc`: working passive news/timeline connector using the GDELT DOC 2.0 article API.
- `ahmia`: conservative lawful index/search connector, disabled by default.
- `spiderfoot`: scaffold only.
- `theharvester`: scaffold only.
- `recon-ng`: legacy/experimental scaffold only.
- `onionsearch`: experimental scaffold only.
- `mock-public-search`: disabled by default and intended for explicit offline verification/tests only.
- `resource-pack`: investigator-mode case playbook with category coverage, official cross-checks, news/archive pivots, geo open-data pivots, and reverse-image launch points.

## Intelligence Synthesis (MAAT Engine)

After an investigation run, the synthesis endpoint (`/api/investigations/runs/{id}/synthesis`) produces:

- **Situation summary** — plain-language assessment of the intelligence landscape
- **Lead clusters** — thematic groups (sighting reports, media coverage, official updates) by similarity and geography
- **Intelligence timeline** — source-attributed chronological events from all connectors
- **Geographic patterns** — location clusters, dispersal analysis, distance from case origin
- **Temporal patterns** — activity bursts, cold trail detection, recent activity
- **Actionable recommendations** — prioritized next steps (CRITICAL / HIGH / MEDIUM)
- **Authority brief** — ready-to-forward text summary for investigating authorities

## Scripts

- `python -m scripts.sync_cases`: pull open cases from the public MCSC ArcGIS feed into SQLite.
- `python -m scripts.export_public_data`: write JSON/CSV exports.
- `python -m scripts.build_docs`: regenerate `docs/data/public-cases.json` and `docs/data/reference-layers.json`.
- `python -m scripts.refresh_osint_cache <case_id>`: run enabled investigator-mode connectors for one case.

## Tests

```bash
pytest
```

Current tests cover:
- ArcGIS normalization
- lead scoring rationale
- timeline derivation
- investigator query planning
- resource-pack generation

## Public app behavior

The static dashboard supports:
- live case count
- province and city filters
- fuzzy name search
- min/max age filter
- sorting by recency, age, status, and risk rank
- map/list/grid interplay
- case detail panel with facts vs inference separation
- source attribution badges
- recently updated panel
- printable packet workflow
- shareable filtered URLs
- province, age, status, and trend charts
- authority contact links
- safe-help guidance and reporting checklists
- border/transit/highway/youth-service context indicators from bundled public reference layers

## Migration notes from Railway-oriented app

- Railway config is no longer part of the core architecture.
- The main product is now `docs/`, not the backend runtime.
- Backend mode is local/optional and can be hosted separately if needed.
- Old monolithic analysis behavior is replaced by `backend/osint/connectors/` plus feature flags.
- Public hosting is free-static first; backend secrets are not required for the public product.

