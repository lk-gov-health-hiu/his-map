"""
Build institutions_final.json from:
  1. updated institution list 2024.csv  — master list (name, type, RDHS)
  2. gis hospital.csv                  — GPS coordinates (primary, 5 972 rows)
  3. kml_data.json                     — HIS assignment (HHMIS/HIMS/OpenMRS/Planned)
     HHMIS layer has coords in WKT description; others have lat/lon fields.

Match priority:
  a) institute_code exact match  (health_inst_no  ↔  institute_code)
  b) fuzzy name match (threshold 0.80)

HIS assignment comes from KML only (name-fuzzy matched to institutions).
"""

import csv, io, json, re, sys
from difflib import SequenceMatcher

# ── helpers ──────────────────────────────────────────────────────────────────
def norm_code(s):
    return re.sub(r'[\s\-]', '', str(s).strip().upper())

def norm_name(s):
    return re.sub(r'[^a-z0-9]', '', str(s).lower())

def token_sim(a, b):
    stop = {'hospital','divisional','base','type','the','of','and','district',
            'general','primary','medical','care','unit','national','specialized'}
    ta = set(re.findall(r'[a-z]+', a.lower())) - stop
    tb = set(re.findall(r'[a-z]+', b.lower())) - stop
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)

def best_name_match(name, candidates, threshold=0.80):
    """candidates: list of (norm_key, original_name, payload)"""
    nk  = norm_name(name)
    best_s, best_p = 0.0, None
    for ck, cn, payload in candidates:
        s = max(SequenceMatcher(None, nk, ck).ratio(),
                token_sim(name, cn))
        if s > best_s:
            best_s, best_p = s, payload
    return (best_p, best_s) if best_s >= threshold else (None, 0.0)

def parse_wkt(desc):
    """Extract (lat, lon) from 'POINT (lon lat)' in description."""
    m = re.search(r'POINT\s*\(([0-9.\-]+)\s+([0-9.\-]+)\)', desc or '')
    if m:
        return m.group(2), m.group(1)   # lat, lon
    return None, None

# ── TYPE CLASSIFICATION ───────────────────────────────────────────────────────
TYPE_GROUP = {
    'National Hospital':                    'National / Teaching Hospital',
    'Teaching Hospital':                    'National / Teaching Hospital',
    'Specialized Teaching Hospital':        'National / Teaching Hospital',
    'Board Managed Hospital (Tertiary Care)':'National / Teaching Hospital',
    'Board Managed Hospital (Secondary Care)':'District / Base Hospital',
    'District General Hospital':            'District / Base Hospital',
    'Base Hospital-Type A':                 'Base Hospital',
    'Base Hospital-Type B':                 'Base Hospital',
    'Other Hospital':                       'District / Base Hospital',
    'Divisional Hospital-Type A':           'Divisional Hospital',
    'Divisional Hospital-Type B':           'Divisional Hospital',
    'Divisional Hospital-Type C':           'Divisional Hospital',
    'Primary Medical Care Unit':            'Primary Care (PMCU)',
    'PMCU & MH':                            'Primary Care (PMCU)',
    'Other Specialized Hospital':           'Specialized Hospital',
    'MOH':                                  'MOH / Admin Office',
    'RDHS':                                 'MOH / Admin Office',
    'PDHS':                                 'MOH / Admin Office',
    'ADC':                                  'MOH / Admin Office',
    'NTS':                                  'MOH / Admin Office',
    'CDC':                                  'Clinic / Outpatient',
    'STD Clinic':                           'Clinic / Outpatient',
    'Chest Clinic':                         'Clinic / Outpatient',
    'Army Hospital':                        'Defence / Police Hospital',
    'Navy Hospital':                        'Defence / Police Hospital',
    'Air Force Hospital':                   'Defence / Police Hospital',
    'Police Hospital':                      'Defence / Police Hospital',
    'Prison Hospital':                      'Defence / Police Hospital',
}
LEVEL = {
    'National Hospital':                    'DDG and Above',
    'Teaching Hospital':                    'DDG and Above',
    'Specialized Teaching Hospital':        'DDG and Above',
    'Board Managed Hospital (Tertiary Care)':'DDG and Above',
    'District General Hospital':            'DDG and Above',
    'Other Specialized Hospital':           'DDG and Above',
    'Board Managed Hospital (Secondary Care)':'BH and Below',
    'Base Hospital-Type A':                 'BH and Below',
    'Base Hospital-Type B':                 'BH and Below',
    'Divisional Hospital-Type A':           'BH and Below',
    'Divisional Hospital-Type B':           'BH and Below',
    'Divisional Hospital-Type C':           'BH and Below',
    'Primary Medical Care Unit':            'BH and Below',
    'PMCU & MH':                            'BH and Below',
    'Other Hospital':                       'BH and Below',
}

HIS_LAYER = {
    'HHMIS':                              'HHMIS',
    'HIMS':                               'HIMS',
    'OPEN MRS':                           'OpenMRS',
    'HHIMS to be implmented under HIQI':  'HHIMS (Planned)',
    'RDHS OFFICES':                       None,
}

# ── 1. LOAD INSTITUTION LIST ──────────────────────────────────────────────────
with open('updated institution list 2024.csv', encoding='utf-8-sig', errors='replace') as f:
    lines = f.readlines()
reader = csv.reader(io.StringIO(''.join(lines[1:])))
next(reader)

institutions = []
for row in reader:
    if len(row) < 4 or not row[3].strip():
        continue
    t = row[4].strip() if len(row) > 4 else ''
    institutions.append({
        'inst_no':        row[0].strip(),
        'health_inst_no': row[1].strip() if len(row) > 1 else '',
        'rdhs':           row[2].strip() if len(row) > 2 else '',
        'name':           row[3].strip(),
        'type_atomic':    t,
        'type_group':     TYPE_GROUP.get(t, 'Other'),
        'level':          LEVEL.get(t, 'Other'),
        'moh_area':       row[5].strip() if len(row) > 5 else '',
        'special_notes':  row[6].strip() if len(row) > 6 else '',
        'line':           row[7].strip() if len(row) > 7 else '',
        'address':        row[8].strip() if len(row) > 8 else '',
        'phone':          row[9].strip() if len(row) > 9 else '',
        'email':          row[10].strip() if len(row) > 10 else '',
        'lat': '', 'lon': '', 'coord_source': '',
        'his_name': '', 'his_in_place': 'No',
    })
print(f'Institutions loaded: {len(institutions)}')

# ── 2. LOAD GIS CSV ───────────────────────────────────────────────────────────
with open('gis hospital.csv', encoding='utf-8-sig', errors='replace') as f:
    gis_rows = list(csv.DictReader(f))

# Build two lookups: by code, and by name (for fuzzy fallback)
gis_by_code = {}
gis_name_candidates = []
for row in gis_rows:
    lat, lon = row['x'].strip(), row['y'].strip()
    if not lat or lat == 'null' or not lon or lon == 'null':
        continue
    try:
        float(lat); float(lon)
    except ValueError:
        continue
    code = norm_code(row['institute_code'])
    if code:
        gis_by_code[code] = row
    name = row['Institute_Name'].strip()
    if name:
        gis_name_candidates.append((norm_name(name), name, row))

print(f'GIS rows with coords: {len(gis_name_candidates)}  |  with code: {len(gis_by_code)}')

# ── 3. LOAD KML (HIS assignments) ────────────────────────────────────────────
with open('kml_data.json', encoding='utf-8') as f:
    kml_items = json.load(f)

# Build HIS lookup: norm_name → { his_name, lat, lon }
his_candidates = []
for item in kml_items:
    his = HIS_LAYER.get(item['layer'])
    if not his:
        continue
    # Extract coords: direct fields or WKT in description
    lat, lon = item.get('lat', ''), item.get('lon', '')
    if not lat:
        lat, lon = parse_wkt(item.get('description', ''))
    name = item['name'].strip()
    his_candidates.append((norm_name(name), name, {
        'his': his, 'lat': lat or '', 'lon': lon or ''
    }))

print(f'KML HIS entries: {len(his_candidates)}')

# ── 4. MATCH COORDINATES + HIS ────────────────────────────────────────────────
matched_code = matched_name = matched_his = 0

for inst in institutions:
    inst_code = norm_code(inst['health_inst_no'])

    # ── Coordinates: code match first ──
    gis_row = None
    if inst_code and inst_code in gis_by_code:
        gis_row = gis_by_code[inst_code]
        matched_code += 1
    else:
        gis_row, score = best_name_match(inst['name'], gis_name_candidates, threshold=0.80)
        if gis_row:
            matched_name += 1

    if gis_row:
        inst['lat'] = gis_row['x'].strip()
        inst['lon'] = gis_row['y'].strip()
        inst['coord_source'] = 'GIS'

    # ── HIS: always from KML (name match) ──
    his_payload, score = best_name_match(inst['name'], his_candidates, threshold=0.78)
    if his_payload:
        inst['his_name']     = his_payload['his']
        inst['his_in_place'] = 'Yes'
        matched_his += 1
        # If no GIS coord yet, use KML coord
        if not inst['lat'] and his_payload.get('lat'):
            inst['lat']          = his_payload['lat']
            inst['lon']          = his_payload['lon']
            inst['coord_source'] = 'KMZ'

# ── 5. SUMMARY ────────────────────────────────────────────────────────────────
mapped   = [i for i in institutions if i['lat'] and i['lon']]
unmapped = [i for i in institutions if not i['lat']]

print(f'\nCoordinate matching:')
print(f'  Code match (GIS):  {matched_code}')
print(f'  Name match (GIS):  {matched_name}')
print(f'  Total with coords: {len(mapped)}')
print(f'  No coords:         {len(unmapped)}')
print(f'\nHIS matched:         {matched_his}')

from collections import Counter
his_dist = Counter(i['his_name'] or 'No HIS' for i in institutions)
print('\nHIS distribution (all):')
for k, v in his_dist.most_common():
    print(f'  {k}: {v}')

# Type-level HIS summary (clinical hospitals only)
clinical_types = ['National / Teaching Hospital','District / Base Hospital',
                  'Base Hospital','Divisional Hospital','Primary Care (PMCU)',
                  'Specialized Hospital']
print('\nHIS by type group (clinical hospitals):')
type_his = {}
for inst in institutions:
    tg = inst['type_group']
    if tg not in clinical_types:
        continue
    if tg not in type_his:
        type_his[tg] = {'HIS': 0, 'No HIS': 0}
    if inst['his_in_place'] == 'Yes':
        type_his[tg]['HIS'] += 1
    else:
        type_his[tg]['No HIS'] += 1
for tg, counts in sorted(type_his.items()):
    total = counts['HIS'] + counts['No HIS']
    pct = counts['HIS']/total*100
    print(f'  {tg:35} HIS={counts["HIS"]:3}  NoHIS={counts["No HIS"]:4}  Total={total:4}  {pct:.0f}%')

# ── 6. SAVE ────────────────────────────────────────────────────────────────────
with open('institutions_final.json', 'w', encoding='utf-8') as f:
    json.dump(institutions, f, ensure_ascii=False, indent=2)
with open('unmapped_institutions.json', 'w', encoding='utf-8') as f:
    json.dump(unmapped, f, ensure_ascii=False, indent=2)
print(f'\nSaved institutions_final.json ({len(institutions)} records)')
print(f'Saved unmapped_institutions.json ({len(unmapped)} records)')
