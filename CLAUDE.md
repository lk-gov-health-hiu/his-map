# HIS Map — Project Handover for Claude

## What this project is
An interactive web map showing **Hospital Information System (HIS) deployment status** across all health institutions in Sri Lanka, published on GitHub Pages for the Ministry of Health.

**Live map:** https://lk-gov-health-hiu.github.io/his-map/  
**GitHub repo:** https://github.com/lk-gov-health-hiu/his-map  
**Local folder:** `C:\Users\buddhika\OneDrive\01 Ministry of Health\HIS\HIS Map`  
**GitHub org:** `lk-gov-health-hiu` (logged in as `buddhika75`)  

---

## File structure

```
HIS Map/
├── index.html                      # The map (Leaflet.js — single file, no build step)
├── institutions_final.json         # Generated — all 1,955 institutions with coords + HIS
├── unmapped_institutions.json      # Generated — institutions without GPS coordinates
│
├── build_map_data.py               # ★ DATA PIPELINE — run this when source data changes
├── his_overrides.csv               # ★ MANUAL HIS MAPPINGS — edit when KML changes
│
├── updated institution list 2024.csv   # Source: MoH institution registry (master list)
├── gis hospital.csv                    # Source: GIS coordinates (5,972 rows, primary coord source)
├── HHIMSHIMSOPEN MRS.kmz               # Source: Google My Maps (HIS assignments)
├── kml_data.json                       # Extracted from KMZ (auto-generated, do not edit)
├── osm_facilities.json                 # OpenStreetMap data (used early, superseded by gis hospital.csv)
│
└── CLAUDE.md                       # This file
```

---

## How to update data

### When the institution list changes (`updated institution list 2024.csv`)
1. Replace the CSV file with the new one (keep the same filename)
2. Run the pipeline: `python build_map_data.py`
3. Commit and push: `git add institutions_final.json unmapped_institutions.json && git commit -m "Update institution data" && git push`

### When HIS deployment status changes (new hospitals get HHIMS/HIMS/OpenMRS)
Two options:

**Option A — Update the KMZ (preferred)**
- The KMZ is a NetworkLink to this Google My Maps: https://www.google.com/maps/d/kml?mid=1HPLMzmsRajKbVsTQDsADzk5ECXQTv-4
- Update the Google My Maps to add the new hospital to the right layer
- Then re-download the KMZ and replace `HHIMSHIMSOPEN MRS.kmz`
- Re-extract KML: the pipeline does this automatically via the WebFetch call (see pipeline notes)
- Run `python build_map_data.py`

**Option B — Add to his_overrides.csv (quick fix)**
- Open `his_overrides.csv` in Excel or Notepad
- Add a row: `KML hospital name, health_inst_no from CSV column B, HIS system name`
- Valid HIS names: `HHMIS`, `HIMS`, `OpenMRS`, `HHIMS (Planned)`
- Run `python build_map_data.py`

### After any data update
```bash
python build_map_data.py
git add institutions_final.json unmapped_institutions.json his_overrides.csv
git commit -m "Update data: describe what changed"
git push origin master
```
GitHub Pages redeploys automatically in ~2 minutes.

---

## Data pipeline explained (`build_map_data.py`)

### Sources and priority
1. **`updated institution list 2024.csv`** — master list of all 1,955 institutions (name, type, RDHS division)
2. **`gis hospital.csv`** — GPS coordinates for ~5,927 institutions (primary coord source)
3. **`kml_data.json`** — HIS system assignments from Google My Maps (HHMIS/HIMS/OpenMRS/Planned)
4. **`his_overrides.csv`** — manual mappings for hospitals where auto-matching fails

### Matching logic (hybrid approach)
**Coordinate matching** (GIS CSV → institution list):
- Step 1: Exact `institute_code` ↔ `health_inst_no` match → 1,290 matched
- Step 2: Trigram-indexed fuzzy name match (fast, threshold 0.82) → +266 matched
- Total: **1,567 institutions with GPS coordinates**

**HIS assignment** (KML → institution list):
- Step 1: `his_overrides.csv` exact code match → 33 applied
- Step 2: Trigram-indexed fuzzy name match (threshold 0.82) → remaining
- MOH offices in KML are **skipped** (they have HIS access but are not hospitals — excluded from counts)

### Current results (as of May 2026)
| HIS System | Hospitals |
|---|---|
| HHMIS | 219 |
| OpenMRS | 36 |
| HIMS | 17 |
| HHIMS (Planned) | 16 |
| **Total with HIS** | **288** |

| Hospital Type | HIS | No HIS | Total | Coverage |
|---|---|---|---|---|
| National / Teaching | 17 | 6 | 23 | 74% |
| Base Hospital | 62 | 19 | 81 | 77% |
| District / Base | 13 | 12 | 25 | 52% |
| Divisional Hospital | 41 | 447 | 488 | 8% |
| Primary Care (PMCU) | 25 | 532 | 557 | 5% |
| Specialized | 3 | 10 | 13 | 23% |

---

## Hospital classification scheme

### type_atomic (from CSV column E — exact)
`National Hospital`, `Teaching Hospital`, `Specialized Teaching Hospital`,
`Board Managed Hospital (Tertiary Care)`, `Board Managed Hospital (Secondary Care)`,
`District General Hospital`, `Base Hospital-Type A`, `Base Hospital-Type B`,
`Divisional Hospital-Type A/B/C`, `Primary Medical Care Unit`, `PMCU & MH`,
`Other Specialized Hospital`, `MOH`, `RDHS`, `PDHS`, `ADC`, `NTS`,
`CDC`, `STD Clinic`, `Chest Clinic`,
`Army Hospital`, `Navy Hospital`, `Air Force Hospital`, `Police Hospital`, `Prison Hospital`

### type_group (derived — used for map tabs)
| type_group | Includes |
|---|---|
| National / Teaching Hospital | National, Teaching, Specialized Teaching, Board Managed Tertiary |
| District / Base Hospital | DGH, Board Managed Secondary, Other Hospital |
| Base Hospital | Base Hospital-Type A, Base Hospital-Type B |
| Divisional Hospital | DH Type A, B, C |
| Primary Care (PMCU) | PMCU, PMCU & MH |
| Specialized Hospital | Other Specialized Hospital |
| MOH / Admin Office | MOH, RDHS, PDHS, ADC, NTS |
| Clinic / Outpatient | CDC, STD Clinic, Chest Clinic |
| Defence / Police Hospital | Army, Navy, Air Force, Police, Prison |

### level (derived — used for map colouring)
| level | Includes |
|---|---|
| DDG and Above | National, Teaching, Specialized Teaching, DGH, Other Specialized |
| BH and Below | Base A/B, Divisional A/B/C, PMCU |
| Other | Everything else |

---

## Map design (`index.html`)

### Technology
- **Leaflet.js 1.9.4** + **Leaflet.MarkerCluster 1.5.3** (loaded from CDN)
- Single HTML file — no build process, no Node.js, no server needed for editing
- Reads `institutions_final.json` via `fetch()` — requires HTTP server to run locally

### Running locally
```bash
cd "C:\Users\buddhika\OneDrive\01 Ministry of Health\HIS\HIS Map"
python -m http.server 8080
# Open http://localhost:8080
```

### Map UI structure
- **Header tabs** — filter map to a hospital type (All / National-Teaching / DGH / Base Hospital / Divisional / PMCU / Specialized)
- **Green 🟢 dots** — hospitals WITH HIS in place
- **Red 🔴 dots** — hospitals WITHOUT HIS
- **HIS / No-HIS toggle buttons** — show/hide each group
- **Coverage table** — HIS count, No HIS count, Total, % bar per type group (clicking a row filters map)
- **HIS system breakdown panel** — HHMIS / HIMS / OpenMRS / Planned counts
- **Search box** — search by name, shows HIS status in results
- **Unmapped drawer** — table of all institutions without GPS coordinates

### Key JS functions in index.html
| Function | What it does |
|---|---|
| `renderMap()` | Clears and redraws all markers for current type filter |
| `buildSummaryTable()` | Rebuilds coverage table in sidebar |
| `selectType(type)` | Called when a tab or table row is clicked |
| `updateHISDetail()` | Updates the HIS system breakdown panel |
| `buildUnmapped(data)` | Populates the unmapped institutions drawer |

---

## his_overrides.csv format

```csv
kml_name,health_inst_no,his_name
Teaching Hospital Jaffna,LJF0000786,HIMS
Dompe Divisional Hospital-A,PGP0005728,HHMIS
...
```

- `kml_name` — exact name as it appears in the KML (from Google My Maps)
- `health_inst_no` — institution code from column B of `updated institution list 2024.csv`
- `his_name` — one of: `HHMIS`, `HIMS`, `OpenMRS`, `HHIMS (Planned)`
- Leave `health_inst_no` blank if institution is in KML but not in CSV (rare)

---

## Known issues / future improvements

1. **~388 institutions still have no GPS coordinates** — shown in the unmapped drawer. Could be geocoded using Google Geocoding API (requires API key) or manually.

2. **One likely wrong match** — `Teaching Hospital - Anuradhapura` in HHMIS matched to `Anuradhapura` (which may be the Teaching Hospital, but verify). Code: `LAN0000034`.

3. **Gallassa Maternity Hospital (Kalutara)** — in KML as HHMIS but not found in CSV by any name. May be listed under a different name in the registry. Currently shows on map via KML coords but not linked to a CSV row.

4. **Dompe** — two rows in CSV both named "Dompe" (codes `PGP0005728` and `PGP0006387`). Override uses `PGP0005728` (Type A). Verify if correct.

5. **RDHS filter** — removed from map by user request. Can be re-added to sidebar if needed.

6. **Colour scheme** — currently green=HIS, red=No HIS. Could add a third view mode showing HIS system type (HHMIS blue / OpenMRS green / HIMS purple).
