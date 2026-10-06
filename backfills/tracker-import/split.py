"""Build the HubSpot import set: one file per class month, splitting only the months
that are too large to upload.

Author: Jibril Sulaiman
File:   backfills/tracker-import/split.py   (step 4 of 4: scan -> build -> drop_overlaps -> split)
Why:    One month at ~34 MB failed HubSpot's upload ("There was an issue with the file
        upload") while months up to ~28 MB went through. Only oversized months get
        parts - everything else stays a single file so the month-by-month import
        sequence is unchanged, and a failed file names the month to retry.
How to run (PowerShell, from this folder, same $env:SP as the earlier steps):
        python split.py
Writes: OUT/<yyyy-mm>_<Mon><yyyy>_free_class_registrations.csv (one per month) and FLAT
        (every month in one file). Deletes any .csv already in OUT first. Local files only.

Two audit columns are dropped from the import copies because HubSpot's mapper silently
guesses them onto real contact properties:
    _Referrer       -> Referrer Name
    _UTM Source Of  -> utm_source
The master hubspot_backfill.csv in $env:SP keeps every column for auditing.
"""
import csv, os

csv.field_size_limit(10 ** 7)
SP = os.environ['SP']
SRC = os.path.join(SP, 'hubspot_backfill_IMPORT.csv')
OUT = r'C:\path\to\HubSpot_Import_Monthly'              # REPLACE: output folder (its .csv files are deleted first)
FLAT = r'C:\path\to\HubSpot_FreeClass_Backfill_IMPORT.csv'   # REPLACE: the all-months copy
DROP = ['_Referrer', '_UTM Source Of']

# months that must be split, and into how many parts. REPLACE after a month fails to
# upload, e.g. {'2026-04': 2}. Leave it empty until one does.
SPLIT = {}

MONTH = {'01': 'Jan', '02': 'Feb', '03': 'Mar', '04': 'Apr', '05': 'May', '06': 'Jun',
         '07': 'Jul', '08': 'Aug', '09': 'Sep', '10': 'Oct', '11': 'Nov', '12': 'Dec'}

os.makedirs(OUT, exist_ok=True)
for f in os.listdir(OUT):
    if f.lower().endswith('.csv'):
        os.remove(os.path.join(OUT, f))

with open(SRC, encoding='utf-8', newline='') as fh:
    rd = csv.reader(fh)
    hdr = next(rd)
    keep = [i for i, h in enumerate(hdr) if h not in DROP]
    new_hdr = [hdr[i] for i in keep]
    ci = new_hdr.index('Class Date')

    flat = open(FLAT, 'w', encoding='utf-8', newline='')
    fw = csv.writer(flat)
    fw.writerow(new_hdr)

    months = {}
    for row in rd:
        row = [row[i] for i in keep]
        fw.writerow(row)
        months.setdefault(row[ci][:7], []).append(row)
    flat.close()

def write(name, rows):
    path = os.path.join(OUT, name)
    with open(path, 'w', encoding='utf-8', newline='') as h:
        w = csv.writer(h)
        w.writerow(new_hdr)
        w.writerows(rows)
    return len(rows), os.path.getsize(path) / 1e6

written = 0
print(f"{'file':58}{'rows':>8}{'MB':>7}")
for ym in sorted(months):
    rows = months[ym]
    y, m = ym.split('-')
    parts = SPLIT.get(ym, 1)
    if parts == 1:
        n, mb = write(f'{ym}_{MONTH[m]}{y}_free_class_registrations.csv', rows)
        written += n
        print(f'{ym + "_" + MONTH[m] + y + "_free_class_registrations.csv":58}{n:8}{mb:7.1f}')
    else:
        per = -(-len(rows) // parts)
        for i in range(parts):
            chunk = rows[i * per:(i + 1) * per]
            if not chunk:
                continue
            name = f'{ym}_{MONTH[m]}{y}_part{i + 1}of{parts}_free_class_registrations.csv'
            n, mb = write(name, chunk)
            written += n
            print(f'{name:58}{n:8}{mb:7.1f}')

src_rows = sum(1 for _ in open(SRC, encoding='utf-8')) - 1
files = sorted(f for f in os.listdir(OUT) if f.endswith('.csv'))
sizes = {f: os.path.getsize(os.path.join(OUT, f)) / 1e6 for f in files}
print()
print('files              :', len(files))
print('rows written       :', written)
print('source rows        :', src_rows)
print('all rows preserved :', written == src_rows)
print('columns per file   :', len(new_hdr))
bad = [f for f in files if next(csv.reader(open(os.path.join(OUT, f), encoding='utf-8',
                                               newline=''))) != new_hdr]
print('headers identical  :', not bad, bad)
over = {f: round(s, 1) for f, s in sizes.items() if s > 10}
print('files over 10 MB   :', over if over else 'none')
