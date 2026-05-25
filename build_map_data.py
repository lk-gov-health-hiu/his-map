"""
Build institutions_final.json — HYBRID APPROACH
================================================
Sources:
  1. updated institution list 2024.csv  — master institution list
  2. gis hospital.csv                  — GPS coordinates (5,972 rows)
  3. kml_data.json                     — HIS system assignments
  4. his_overrides.csv                 — manual overrides for hard-to-match names

Coordinate matching (priority order):
  a) institute_code exact match  (health_inst_no == institute_code)
  b) Smarter fuzzy: strip hospital-type words, match on location name only
  c) Full-name fuzzy (threshold 0.82)

HIS assignment (priority order):
  a) his_overrides.csv  — exact health_inst_no or exact KML name match
  b) institute_code match to KML (for any KML item with a code)
  c) Smarter fuzzy on KML names (threshold 0.78)

MOH offices in KML (OpenMRS layer) are tagged as HIS=OpenMRS but
  type_group='MOH / Admin Office' so they are excluded from hospital counts.
"""

import csv, io, json, re
from difflib import SequenceMatcher

# ── Helpers ────────────────────────────────────────────────────────────────────
def norm_code(s):
    return re.sub(r'[\s\-]', '', str(s).strip().upper())

# Hospital-type words to strip before location-name matching
TYPE_WORDS = re.compile(
    r'\b(divisional|base|teaching|district|general|national|specialized|'
    r'primary|medical|care|unit|hospital|government|regional|provincial|'
    r'maternity|rural|type|tract)\b', re.I)

def location_key(s):
    """Strip type words, keep only the distinctive location part."""
    s2 = TYPE_WORDS.sub('', str(s).lower())
    return re.sub(r'[^a-z0-9]', '', s2)

def full_key(s):
    return re.sub(r'[^a-z0-9]', '', str(s).lower())

def token_sim(a, b):
    stop = {'hospital','divisional','base','teaching','general','district',
            'national','specialized','primary','medical','care','unit',
            'the','of','and','government','regional','type','provincial'}
    ta = set(re.findall(r'[a-z]+', str(a).lower())) - stop
    tb = set(re.findall(r'[a-z]+', str(b).lower())) - stop
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)

def trigrams(s):
    """Return set of character trigrams for fast pre-filtering."""
    return {s[i:i+3] for i in range(len(s)-2)} if len(s) >= 3 else set(s)

def build_index(candidates):
    """Build trigram index: trigram -> list of candidate indices."""
    idx = {}
    for i, (fk, lk, name, payload) in enumerate(candidates):
        for tg in trigrams(lk) | trigrams(fk):
            idx.setdefault(tg, []).append(i)
    return idx

def best_match(name, candidates, index, loc_threshold=0.85, full_threshold=0.82):
    """
    candidates: list of (full_key, location_key, original_name, payload)
    index: trigram index built with build_index()
    Returns (payload, score) or (None, 0)
    """
    lk = location_key(name)
    fk = full_key(name)
    # Use trigram index to find candidate shortlist
    tgs = trigrams(lk) | trigrams(fk)
    hits = {}
    for tg in tgs:
        for i in index.get(tg, []):
            hits[i] = hits.get(i, 0) + 1
    if not hits:
        return None, 0.0
    # Only score top candidates by overlap count (max 60 to keep it fast)
    top = sorted(hits, key=hits.__getitem__, reverse=True)[:60]
    best_s, best_p = 0.0, None
    for i in top:
        ck_full, ck_loc, cname, payload = candidates[i]
        s_loc  = SequenceMatcher(None, lk, ck_loc).ratio() if lk and ck_loc else 0.0
        s_full = max(SequenceMatcher(None, fk, ck_full).ratio(), token_sim(name, cname))
        score  = max(s_loc, s_full)
        if score > best_s:
            best_s, best_p = score, payload
    if best_s >= loc_threshold or best_s >= full_threshold:
        return best_p, best_s
    return None, 0.0

def parse_wkt(desc):
    m = re.search(r'POINT\s*\(([0-9.\-]+)\s+([0-9.\-]+)\)', desc or '')
    if m:
        return m.group(2), m.group(1)   # lat, lon  (WKT order is lon lat)
    return None, None

# ── MOH office KML names to exclude from hospital HIS count ──────────────────
# These are in OpenMRS but are MOH admin offices, not hospitals
MOH_KML_NAMES = {
    'moh office - thalawa', 'moh office galnewa', 'moh office dambulla',
    'moh galewela', 'moh - laggala', 'moh - laggala',
}

# ── Type classification ────────────────────────────────────────────────────────
TYPE_GROUP = {
    'National Hospital':                     'National / Teaching Hospital',
    'Teaching Hospital':                     'National / Teaching Hospital',
    'Specialized Teaching Hospital':         'National / Teaching Hospital',
    'Board Managed Hospital (Tertiary Care)':'National / Teaching Hospital',
    'Board Managed Hospital (Secondary Care)':'District / Base Hospital',
    'District General Hospital':             'District / Base Hospital',
    'Base Hospital-Type A':                  'Base Hospital',
    'Base Hospital-Type B':                  'Base Hospital',
    'Other Hospital':                        'District / Base Hospital',
    'Divisional Hospital-Type A':            'Divisional Hospital',
    'Divisional Hospital-Type B':            'Divisional Hospital',
    'Divisional Hospital-Type C':            'Divisional Hospital',
    'Primary Medical Care Unit':             'Primary Care (PMCU)',
    'PMCU & MH':                             'Primary Care (PMCU)',
    'Other Specialized Hospital':            'Specialized Hospital',
    'MOH':                                   'MOH / Admin Office',
    'RDHS':                                  'MOH / Admin Office',
    'PDHS':                                  'MOH / Admin Office',
    'ADC':                                   'MOH / Admin Office',
    'NTS':                                   'MOH / Admin Office',
    'CDC':                                   'Clinic / Outpatient',
    'STD Clinic':                            'Clinic / Outpatient',
    'Chest Clinic':                          'Clinic / Outpatient',
    'Army Hospital':                         'Defence / Police Hospital',
    'Navy Hospital':                         'Defence / Police Hospital',
    'Air Force Hospital':                    'Defence / Police Hospital',
    'Police Hospital':                       'Defence / Police Hospital',
    'Prison Hospital':                       'Defence / Police Hospital',
}
LEVEL = {
    'National Hospital':                     'DDG and Above',
    'Teaching Hospital':                     'DDG and Above',
    'Specialized Teaching Hospital':         'DDG and Above',
    'Board Managed Hospital (Tertiary Care)':'DDG and Above',
    'District General Hospital':             'DDG and Above',
    'Other Specialized Hospital':            'DDG and Above',
    'Board Managed Hospital (Secondary Care)':'BH and Below',
    'Base Hospital-Type A':                  'BH and Below',
    'Base Hospital-Type B':                  'BH and Below',
    'Divisional Hospital-Type A':            'BH and Below',
    'Divisional Hospital-Type B':            'BH and Below',
    'Divisional Hospital-Type C':            'BH and Below',
    'Primary Medical Care Unit':             'BH and Below',
    'PMCU & MH':                             'BH and Below',
    'Other Hospital':                        'BH and Below',
}
HIS_LAYER = {
    'HHMIS':                             'HHMIS',
    'HIMS':                              'HIMS',
    'OPEN MRS':                          'OpenMRS',
    'HHIMS to be implmented under HIQI': 'HHIMS (Planned)',
}

# ── 1. Load institution list ────────────────────────────────────────────────────
with open('updated institution list 2024.csv', encoding='utf-8-sig', errors='replace') as f:
    lines = f.readlines()
reader = csv.reader(io.StringIO(''.join(lines[1:])))
next(reader)

institutions = []
code_to_inst = {}   # norm_code -> inst dict
for row in reader:
    if len(row) < 4 or not row[3].strip():
        continue
    t = row[4].strip() if len(row) > 4 else ''
    inst = {
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
    }
    institutions.append(inst)
    c = norm_code(inst['health_inst_no'])
    if c:
        code_to_inst[c] = inst

print(f'Institutions: {len(institutions)}  |  with code: {len(code_to_inst)}')

# ── 2. Load his_overrides.csv ─────────────────────────────────────────────────
# Build two lookups: by health_inst_no code, and by exact KML name
overrides_by_code = {}   # norm_code -> his_name
overrides_by_kml  = {}   # norm full kml name -> (health_inst_no, his_name)

with open('his_overrides.csv', encoding='utf-8-sig') as f:
    for row in csv.DictReader(f):
        kml  = row['kml_name'].strip()
        code = norm_code(row['health_inst_no'])
        his  = row['his_name'].strip()
        overrides_by_kml[full_key(kml)] = (code, his)
        if code:
            overrides_by_code[code] = his

print(f'Overrides: {len(overrides_by_kml)} entries')

# ── 3. Load GIS CSV ────────────────────────────────────────────────────────────
with open('gis hospital.csv', encoding='utf-8-sig', errors='replace') as f:
    gis_rows = list(csv.DictReader(f))

gis_by_code    = {}
gis_candidates = []
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
        gis_candidates.append((full_key(name), location_key(name), name, row))

print(f'GIS rows with coords: {len(gis_candidates)}  |  with code: {len(gis_by_code)}')

# ── 4. Load KML ───────────────────────────────────────────────────────────────
with open('kml_data.json', encoding='utf-8') as f:
    kml_items = json.load(f)

his_candidates = []   # for fuzzy HIS matching
for item in kml_items:
    his = HIS_LAYER.get(item['layer'])
    if not his:
        continue
    # Skip MOH offices — they have HIS access but are not hospitals
    name_lower = item['name'].strip().lower()
    if name_lower in MOH_KML_NAMES or name_lower.startswith('moh ') or name_lower.startswith('moh-'):
        print(f'  Skipping MOH office from HIS count: {item["name"].encode("ascii","replace").decode()}')
        continue
    lat, lon = item.get('lat', ''), item.get('lon', '')
    if not lat:
        lat, lon = parse_wkt(item.get('description', ''))
    his_candidates.append((
        full_key(item['name']), location_key(item['name']),
        item['name'],
        {'his': his, 'lat': lat or '', 'lon': lon or ''}
    ))

print(f'KML HIS hospital entries (excl. MOH offices): {len(his_candidates)}')

# ── Build trigram indexes for fast matching ────────────────────────────────────
gis_index = build_index(gis_candidates)
his_index  = build_index(his_candidates)
print('Trigram indexes built.')

# ── 5. Apply overrides first ──────────────────────────────────────────────────
override_applied = 0
for inst in institutions:
    code = norm_code(inst['health_inst_no'])
    if code and code in overrides_by_code:
        inst['his_name']     = overrides_by_code[code]
        inst['his_in_place'] = 'Yes'
        override_applied += 1

print(f'Overrides applied by code: {override_applied}')

# Also apply overrides by KML name → find institution by code, apply HIS
# (for overrides where the code was found via the override table)
for kml_norm, (code, his) in overrides_by_kml.items():
    if code and code in code_to_inst:
        inst = code_to_inst[code]
        if inst['his_in_place'] != 'Yes':   # don't overwrite already applied
            inst['his_name']     = his
            inst['his_in_place'] = 'Yes'

# ── 6. Match coordinates + remaining HIS via fuzzy ───────────────────────────
matched_code = matched_fuzzy = his_fuzzy = his_override_kml = 0

for inst in institutions:
    code = norm_code(inst['health_inst_no'])

    # ── Coordinates ──
    gis_row = None
    if code and code in gis_by_code:
        gis_row = gis_by_code[code]
        matched_code += 1
    else:
        payload, score = best_match(inst['name'], gis_candidates, gis_index,
                                    loc_threshold=0.85, full_threshold=0.82)
        if payload:
            gis_row = payload
            matched_fuzzy += 1

    if gis_row:
        inst['lat']          = gis_row['x'].strip()
        inst['lon']          = gis_row['y'].strip()
        inst['coord_source'] = 'GIS'

    # ── HIS (only if not already set by override) ──
    if inst['his_in_place'] == 'Yes':
        # Already set — but fill coords from KML if no GIS coord yet
        if not inst['lat']:
            # Try to find this in his_candidates for coords
            payload, score = best_match(inst['name'], his_candidates, his_index,
                                        loc_threshold=0.80, full_threshold=0.78)
            if payload and payload.get('lat'):
                inst['lat']          = payload['lat']
                inst['lon']          = payload['lon']
                inst['coord_source'] = 'KMZ'
        continue

    # Fuzzy HIS match
    payload, score = best_match(inst['name'], his_candidates, his_index,
                                loc_threshold=0.85, full_threshold=0.82)
    if payload:
        inst['his_name']     = payload['his']
        inst['his_in_place'] = 'Yes'
        his_fuzzy += 1
        if not inst['lat'] and payload.get('lat'):
            inst['lat']          = payload['lat']
            inst['lon']          = payload['lon']
            inst['coord_source'] = 'KMZ'

# ── 7. Summary ─────────────────────────────────────────────────────────────────
mapped   = [i for i in institutions if i['lat'] and i['lon']]
unmapped = [i for i in institutions if not i['lat']]

print(f'\nCoordinate matching:')
print(f'  Code match (GIS):     {matched_code}')
print(f'  Fuzzy match (GIS):    {matched_fuzzy}')
print(f'  Total with coords:    {len(mapped)}')
print(f'  No coords:            {len(unmapped)}')

from collections import Counter
his_dist = Counter(i['his_name'] or 'No HIS' for i in institutions)
print(f'\nHIS distribution (all institutions):')
for k, v in his_dist.most_common():
    print(f'  {k}: {v}')

# Clinical hospital summary (the important one)
CLINICAL = ['National / Teaching Hospital', 'District / Base Hospital',
            'Base Hospital', 'Divisional Hospital',
            'Primary Care (PMCU)', 'Specialized Hospital']

print(f'\nHIS coverage by hospital type:')
print(f'  {"Type":<35} {"HIS":>5} {"No HIS":>7} {"Total":>6} {"Coverage":>9}')
print(f'  {"-"*65}')
grand_his = grand_no = 0
for tg in CLINICAL:
    rows = [i for i in institutions if i['type_group'] == tg]
    if not rows:
        continue
    his  = sum(1 for i in rows if i['his_in_place'] == 'Yes')
    nohis = len(rows) - his
    pct  = his / len(rows) * 100 if rows else 0
    grand_his += his; grand_no += nohis
    print(f'  {tg:<35} {his:>5} {nohis:>7} {len(rows):>6} {pct:>8.1f}%')
grand_total = grand_his + grand_no
print(f'  {"-"*65}')
print(f'  {"TOTAL":<35} {grand_his:>5} {grand_no:>7} {grand_total:>6} {grand_his/grand_total*100:>8.1f}%')

# ── 8. Save ───────────────────────────────────────────────────────────────────
with open('institutions_final.json', 'w', encoding='utf-8') as f:
    json.dump(institutions, f, ensure_ascii=False, indent=2)
with open('unmapped_institutions.json', 'w', encoding='utf-8') as f:
    json.dump(unmapped, f, ensure_ascii=False, indent=2)

print(f'\nSaved institutions_final.json  ({len(institutions)} records, {len(mapped)} mapped)')
print(f'Saved unmapped_institutions.json ({len(unmapped)} records)')
