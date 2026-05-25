"""
Build final map data by merging:
- updated institution list 2024.csv (all institutions)
- kml_data.json (HIS hospitals with GPS from Google My Maps)
- osm_facilities.json (OSM hospitals with GPS)

Output: institutions_final.json (for map) + unmatched.json
"""
import csv, io, json, re
from difflib import SequenceMatcher

def norm(s):
    """Normalize name for matching: lowercase, remove non-alphanum."""
    return re.sub(r'[^a-z0-9]', '', str(s).lower())

def token_sim(a, b):
    """Jaccard similarity on word tokens."""
    ta = set(re.findall(r'[a-z]+', a.lower())) - {'hospital', 'divisional', 'base', 'type', 'the', 'of', 'and'}
    tb = set(re.findall(r'[a-z]+', b.lower())) - {'hospital', 'divisional', 'base', 'type', 'the', 'of', 'and'}
    if not ta or not tb:
        return 0
    return len(ta & tb) / len(ta | tb)

def best_match(name, lookup_items, threshold=0.75):
    """Find best matching name from a list, returns (score, matched_item) or (0, None)."""
    key = norm(name)
    best_score = 0
    best_item = None
    for item_key, item_val in lookup_items:
        s1 = SequenceMatcher(None, key, item_key).ratio()
        s2 = token_sim(name, item_val.get('_name', ''))
        score = max(s1, s2)
        if score > best_score:
            best_score = score
            best_item = item_val
    if best_score >= threshold:
        return best_score, best_item
    return 0, None

# ============================================================
# 1. Load institutions from CSV
# ============================================================
with open('updated institution list 2024.csv', encoding='utf-8-sig', errors='replace') as f:
    lines = f.readlines()

reader = csv.reader(io.StringIO(''.join(lines[1:])))
_ = next(reader)  # skip headers
institutions = []
for row in reader:
    if len(row) < 4 or not row[3].strip():
        continue
    institutions.append({
        'inst_no':       row[0].strip() if len(row) > 0 else '',
        'health_inst_no': row[1].strip() if len(row) > 1 else '',
        'rdhs':          row[2].strip() if len(row) > 2 else '',
        'name':          row[3].strip() if len(row) > 3 else '',
        'type_atomic':   row[4].strip() if len(row) > 4 else '',
        'moh_area':      row[5].strip() if len(row) > 5 else '',
        'special_notes': row[6].strip() if len(row) > 6 else '',
        'line':          row[7].strip() if len(row) > 7 else '',
        'address':       row[8].strip() if len(row) > 8 else '',
        'phone':         row[9].strip() if len(row) > 9 else '',
        'email':         row[10].strip() if len(row) > 10 else '',
        'lat': '', 'lon': '', 'coord_source': '',
        'his_name': '', 'his_in_place': 'No',
        'type_group': '', 'level': '',
    })

print(f'CSV: {len(institutions)} institutions loaded')

# ============================================================
# 2. Classify hospital types
# ============================================================
TYPE_GROUP = {
    'National Hospital': 'National / Teaching Hospital',
    'Teaching Hospital': 'National / Teaching Hospital',
    'Specialized Teaching Hospital': 'National / Teaching Hospital',
    'Board Managed Hospital (Tertiary Care)': 'National / Teaching Hospital',
    'Board Managed Hospital (Secondary Care)': 'District / Base Hospital',
    'District General Hospital': 'District / Base Hospital',
    'Base Hospital-Type A': 'District / Base Hospital',
    'Base Hospital-Type B': 'District / Base Hospital',
    'Other Hospital': 'District / Base Hospital',
    'Divisional Hospital-Type A': 'Divisional Hospital',
    'Divisional Hospital-Type B': 'Divisional Hospital',
    'Divisional Hospital-Type C': 'Divisional Hospital',
    'Primary Medical Care Unit': 'Primary Care',
    'PMCU & MH': 'Primary Care',
    'Other Specialized Hospital': 'Specialized Hospital',
    'MOH': 'MOH / Admin Office',
    'RDHS': 'MOH / Admin Office',
    'PDHS': 'MOH / Admin Office',
    'ADC': 'MOH / Admin Office',
    'NTS': 'MOH / Admin Office',
    'CDC': 'Clinic / Outpatient',
    'STD Clinic': 'Clinic / Outpatient',
    'Chest Clinic': 'Clinic / Outpatient',
    'Army Hospital': 'Defence / Police Hospital',
    'Navy Hospital': 'Defence / Police Hospital',
    'Air Force Hospital': 'Defence / Police Hospital',
    'Police Hospital': 'Defence / Police Hospital',
    'Prison Hospital': 'Defence / Police Hospital',
}

LEVEL = {
    'National Hospital': 'DDG and Above',
    'Teaching Hospital': 'DDG and Above',
    'Specialized Teaching Hospital': 'DDG and Above',
    'Board Managed Hospital (Tertiary Care)': 'DDG and Above',
    'District General Hospital': 'DDG and Above',
    'Other Specialized Hospital': 'DDG and Above',
    'Board Managed Hospital (Secondary Care)': 'BH and Below',
    'Base Hospital-Type A': 'BH and Below',
    'Base Hospital-Type B': 'BH and Below',
    'Divisional Hospital-Type A': 'BH and Below',
    'Divisional Hospital-Type B': 'BH and Below',
    'Divisional Hospital-Type C': 'BH and Below',
    'Primary Medical Care Unit': 'BH and Below',
    'PMCU & MH': 'BH and Below',
    'Other Hospital': 'BH and Below',
}

for inst in institutions:
    t = inst['type_atomic']
    inst['type_group'] = TYPE_GROUP.get(t, 'Other')
    inst['level'] = LEVEL.get(t, 'Other')

# ============================================================
# 3. Load KMZ / KML data
# ============================================================
HIS_LAYER_MAP = {
    'OPEN MRS': 'OpenMRS',
    'HHMIS': 'HHMIS',
    'HIMS': 'HIMS',
    'RDHS OFFICES': None,
    'HHIMS to be implmented under HIQI': 'HHIMS (Planned)',
}

with open('kml_data.json', encoding='utf-8') as f:
    kml_raw = json.load(f)

kml_items = []
for item in kml_raw:
    if item.get('lat') and item.get('lon'):
        his = HIS_LAYER_MAP.get(item['layer'])
        kml_items.append((
            norm(item['name']),
            {'_name': item['name'], 'lat': item['lat'], 'lon': item['lon'],
             'his': his or '', 'layer': item['layer']}
        ))

print(f'KMZ: {len(kml_items)} geo-referenced items')

# ============================================================
# 4. Load OSM data
# ============================================================
with open('osm_facilities.json', encoding='utf-8') as f:
    osm_raw = json.load(f)

osm_items = []
for el in osm_raw:
    tags = el.get('tags', {})
    name = tags.get('name', tags.get('name:en', ''))
    if name and el.get('lat'):
        osm_items.append((
            norm(name),
            {'_name': name, 'lat': str(el['lat']), 'lon': str(el['lon'])}
        ))

print(f'OSM: {len(osm_items)} geo-referenced items')

# ============================================================
# 5. Match and assign coordinates
# ============================================================
matched_kmz = 0
matched_osm = 0
unmatched = 0

for inst in institutions:
    name = inst['name']

    # --- Try KMZ first (has HIS info) ---
    score, match = best_match(name, kml_items, threshold=0.75)
    if match:
        inst['lat'] = match['lat']
        inst['lon'] = match['lon']
        inst['coord_source'] = 'KMZ/GoogleMyMaps'
        if match['his']:
            inst['his_name'] = match['his']
            inst['his_in_place'] = 'Yes'
        matched_kmz += 1
        continue

    # --- Try OSM ---
    score, match = best_match(name, osm_items, threshold=0.78)
    if match:
        inst['lat'] = match['lat']
        inst['lon'] = match['lon']
        inst['coord_source'] = 'OpenStreetMap'
        matched_osm += 1
        continue

    unmatched += 1

print(f'\nCoordinate matching results:')
print(f'  Matched via KMZ (HIS data): {matched_kmz}')
print(f'  Matched via OSM:            {matched_osm}')
print(f'  No coordinates found:       {unmatched}')
print(f'  Total:                      {len(institutions)}')

# HIS summary
his_counts = {}
for inst in institutions:
    h = inst['his_name'] if inst['his_name'] else 'No HIS'
    his_counts[h] = his_counts.get(h, 0) + 1
print(f'\nHIS distribution:')
for k, v in sorted(his_counts.items()):
    print(f'  {k}: {v}')

# ============================================================
# 6. Save outputs
# ============================================================
# Institutions with coordinates (for map)
mapped = [i for i in institutions if i['lat'] and i['lon']]
unmapped = [i for i in institutions if not i['lat']]

with open('institutions_final.json', 'w', encoding='utf-8') as f:
    json.dump(institutions, f, ensure_ascii=False, indent=2)

with open('unmapped_institutions.json', 'w', encoding='utf-8') as f:
    json.dump(unmapped, f, ensure_ascii=False, indent=2)

print(f'\nSaved:')
print(f'  institutions_final.json  ({len(institutions)} total)')
print(f'  unmapped_institutions.json ({len(unmapped)} without coords)')
print(f'  Map will show: {len(mapped)} institutions with markers')
