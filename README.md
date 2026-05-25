# Sri Lanka Ministry of Health — HIS Map

An interactive web map showing Hospital Information Systems (HIS) deployment status across all health institutions in Sri Lanka.

## 🗺️ Live Map

Open `index.html` in a browser **via a local web server** (not by double-clicking the file, as JSON loading requires HTTP).

```bash
# Quick start — any of these work:
python -m http.server 8080
# Then open http://localhost:8080
```

## 📂 Project Structure

```
.
├── index.html                    # Main interactive map (Leaflet.js)
├── institutions_final.json       # All 1,955 institutions with mapped coords
├── unmapped_institutions.json    # Institutions without GPS coordinates
├── updated institution list 2024.csv  # Source: MoH institution registry
├── HHIMSHIMSOPEN MRS.kmz         # Source: Google My Maps (HIS hospitals)
├── kml_data.json                 # Extracted KML data from KMZ
├── osm_facilities.json           # Downloaded from OpenStreetMap (Overpass API)
├── build_map_data.py             # Data pipeline script (rebuild institutions_final.json)
├── process_data.py               # (deprecated — use build_map_data.py)
└── README.md
```

## 🏥 Data Classification

### Hospital Level
| Level | Hospital Types |
|-------|---------------|
| **DDG and Above** | National Hospital, Teaching Hospital, Specialized Teaching Hospital, District General Hospital, Board Managed (Tertiary), Other Specialized |
| **BH and Below** | Base Hospital-Type A/B, Divisional Hospital-Type A/B/C, Primary Medical Care Unit, PMCU & MH |
| **Other** | MOH, RDHS, PDHS, ADC, CDC, Clinics, Defence, Police, Prison |

### Hospital Type Groups
- National / Teaching Hospital
- District / Base Hospital
- Divisional Hospital
- Primary Care (PMCU)
- Specialized Hospital
- Defence / Police Hospital
- Clinic / Outpatient
- MOH / Admin Office

### HIS Categories
| System | Description |
|--------|-------------|
| **HHMIS** | Hospital Health Management Information System |
| **HIMS** | Health Information Management System |
| **OpenMRS** | Open Medical Records System |
| **HHIMS (Planned)** | Planned rollout under HIQI project |
| **No HIS** | No digital HIS in place |

## 🔄 Rebuilding Data

If the source CSV or KMZ is updated:

```bash
# Re-fetch OSM data (optional — network required)
# Uncomment the fetch block in build_map_data.py

# Rebuild processed JSON
python build_map_data.py
```

## 📊 Data Sources

| Source | Description |
|--------|-------------|
| `updated institution list 2024.csv` | Official MoH institution registry (1,955 institutions) |
| `HHIMSHIMSOPEN MRS.kmz` | Google My Maps showing HIS-deployed hospitals |
| OpenStreetMap (Overpass API) | GPS coordinates for matching institutions |

## ⚠️ Known Limitations

- **~1,758 institutions have no GPS coordinates** — they appear in the "Unmapped Institutions" table below the map but not as markers.
- OSM coordinates may not be 100% accurate for all institutions.
- HIS status is from the KMZ file (as of the map creation date) and may not reflect the latest deployment.

## 🏛️ Ministry of Health Sri Lanka

- Website: [health.gov.lk](https://www.health.gov.lk)
- Open Data Portal: [data.health.gov.lk](https://data.health.gov.lk)

---
*Built for internal planning and HIS deployment tracking.*
