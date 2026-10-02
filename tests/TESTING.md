# Migration Insights — Automated Test Report

**Scope:** `tests/`  
**Framework:** pytest (with some `unittest.TestCase` classes)  
**CI:** [`.github/workflows/migration-insights-tests.yml`](../.github/workflows/migration-insights-tests.yml) — runs `python -m pytest tests/ -q` on Python 3.11  
**Total:** **485 tests** across **19 test files** (+ `conftest.py` shared fixtures)

---

## Summary by Area

| Area | Files | Tests | What is validated |
|------|------:|------:|-------------------|
| App config & bootstrap | 4 | 104 | Env parsing, endpoint URLs, host allowlist, sessions, app factory |
| Security | 1 | 5 | Connection string sanitization |
| Live monitoring | 5 | 169 | Progress/verifier API clients, routes, dashboard, metadata, formatting, toolbar badges |
| Migration metadata UI | 8 | 116 | Verification mode, index building, filters, natural order, phases |
| Migration verifier | 1 | 91 | MongoDB verifier queries, badges, payloads, manual summary, mismatch downloads |
| **Total** | **19** | **485** | |

---

## How to Run

```bash
pip install -r requirements.txt -r requirements-dev.txt
python3 -m pytest tests/ -q          # all 485 tests
python3 -m pytest tests/ --collect-only -q   # list without running (verify current count)
python3 -m pytest tests/test_live_routes.py -v  # single file
```

---

## Test Files (detail)

### 1. App config & bootstrap (104 tests)

| File | Tests | Validates |
|------|------:|-----------|
| `test_app_config.py` | 92 | `MI_*` env vars, progress/verifier endpoint URL building, host allowlist, in-memory sessions, DB name resolution, connection validation |
| `test_create_app.py` | 7 | Flask app creation, live blueprint registration, monitoring setup at `/`, security headers |
| `test_session_support.py` | 3 | Session create/update, cookie name |
| `test_connection_cache.py` | 2 | MongoDB client/internal DB cache clearing on validation failure |

### 2. Security (5 tests)

| File | Tests | Validates |
|------|------:|-----------|
| `test_connection_validator.py` | 5 | Strips credentials from URIs, HTML-escapes hosts, fallback for malformed URIs |

### 3. Live monitoring (169 tests)

| File | Tests | Validates |
|------|------:|-----------|
| `test_live_monitoring.py` | 54 | `fetch_progress` / `fetch_summary` / verifier progress (timeouts, redirects, host allowlist), state badges, display builders, duration hover titles |
| `test_live_routes.py` | 47 | `/live` home, unified monitor POST, routing (migration/dashboard/verifier), dashboard routes, progress monitor |
| `test_live_metadata_status.py` | 26 | Lag time, write-blocking mode, sync phase normalization, progress gating (index/verification), partition byte totals |
| `test_data_sources.py` | 6 | Progress API / Metadata toolbar badges when endpoint/metadata configured or unavailable |
| `test_utils.py` | 36 | Count/lag/ratio formatting helpers, seconds hover titles, replication lag resolution |

### 4. Migration metadata UI (116 tests)

| File | Tests | Validates |
|------|------:|-----------|
| `test_verification_mode.py` | 33 | Embedded verifier mode descriptions, info vs progress cards, toolbar badges, persistence fallback display |
| `test_index_building_info.py` | 10 | `buildIndexes` policy descriptions, info card vs live progress precedence |
| `test_index_correction_totals.py` | 28 | Index correction rollups, destination index verification, CEA phase gating, metadata vs progress precedence |
| `test_index_build_destination_cache.py` | 8 | Collection UUID keys, scan throttling, cache hit/miss for extra-built indexes |
| `test_filtered_migration.py` | 13 | Namespace inclusion/exclusion filters, active detection, display cards |
| `test_natural_order.py` | 8 | `copyInNaturalOrder` filter parsing and display |
| `test_phase_start_times.py` | 8 | Phase transition timestamps from metadata, sync card integration |
| `test_verifier_persistence_fallback.py` | 8 | CV phase rollup from MongoDB persistence, fallback when progress endpoint unavailable |

### 5. Migration verifier (91 tests)

| File | Tests | Validates |
|------|------:|-----------|
| `test_migration_verifier.py` | 91 | Generation naming/lookup, metadata version warnings, failed tasks, namespace stats, completeness rules, state badges (pass/mismatches/in-progress), metadata/progress/summary payloads, manual summary run/cooldown, mismatch download streams, lean mode, partial failure resilience |

---

## Shared Test Infrastructure

`conftest.py` provides:

- **`app_client`** — isolated Flask test client with a temp application log file
- **`sample_progress`** — mock mongosync progress JSON
- **`sample_metadata`** — mock mongosync metadata
- **`mongo_mock_db`** — minimal mock pymongo database

---

## Full Test Inventory (485 tests)

Per-file totals (run `python3 -m pytest tests/ --collect-only -q` to verify):

| File | Tests |
|------|------:|
| `test_app_config.py` | 92 |
| `test_connection_cache.py` | 2 |
| `test_connection_validator.py` | 5 |
| `test_create_app.py` | 7 |
| `test_data_sources.py` | 6 |
| `test_filtered_migration.py` | 13 |
| `test_index_build_destination_cache.py` | 8 |
| `test_index_building_info.py` | 10 |
| `test_index_correction_totals.py` | 28 |
| `test_live_metadata_status.py` | 26 |
| `test_live_monitoring.py` | 54 |
| `test_live_routes.py` | 47 |
| `test_migration_verifier.py` | 91 |
| `test_natural_order.py` | 8 |
| `test_phase_start_times.py` | 8 |
| `test_session_support.py` | 3 |
| `test_utils.py` | 36 |
| `test_verification_mode.py` | 33 |
| `test_verifier_persistence_fallback.py` | 8 |
| **Total** | **485** |

### Notable test classes (by file)

**`test_app_config.py`** — `TestParseEnvInt`, `TestProgressEndpointUrl`, `TestVerifierHeavyApiTimeout`, `TestEndpointHostAllowlist`, `TestProbeMetadataDatabases`, `TestValidateApiEndpointUrl`

**`test_live_monitoring.py`** — `TestFetchProgress`, `TestEndpointRedirectAndValidation`, `TestFetchSummary`, `TestStreamVerifierMismatches`, `TestBuildHelpers`

**`test_live_routes.py`** — `TestMonitorClassification`, `TestDashboardRoutes`, `TestVerifierRoutes`

**`test_migration_verifier.py`** — `TestVerifierRunSummaryResponse`, `TestProgressAllowsSummaryRun`, `TestVerifierProgressEndpointPayload`, `TestBuildVerifierMetadataPayload`

---

## Examples of What Is Tested

### Connection string sanitization (`test_connection_validator.py`)

Validates that MongoDB connection strings are safely shown in the UI without leaking credentials:

- Username/password are removed; hosts and database name remain visible
- Malicious hostnames like `host<script>` are escaped to `&lt;script&gt;`
- Invalid or empty URIs return `"[Connection String Provided]"` instead of crashing or exposing raw input

### Toolbar badges (`test_data_sources.py`)

Validates Progress API / Metadata toolbar badges on live dashboards:

- Endpoint-only, metadata-only, and both configured
- Custom labels and unavailable status defaults
- No hostnames or connection strings in badge payloads
