"""
Author:  Jibril Sulaiman
File:    backfills/tracker-import/drop_overlaps.py   (step 3 of 4: scan -> build -> drop_overlaps -> split)
What:    Copies hubspot_backfill.csv to hubspot_backfill_IMPORT.csv without the rows
         build.py flagged `_Overlaps HubSpot = yes` (the same email and Class Date already
         exist in HubSpot), then prints an email check of what is left.
Why:     Those classes are already in HubSpot from the live workflows. Importing them
         again would double the count for every class in the cutover window.
         This step was run inline during the build; it is saved here as a file unchanged.
How to run (PowerShell, from this folder, same $env:SP as the earlier steps):
         python drop_overlaps.py
Success: "invalid TLD remaining : 0", "masked remaining : 0" and "Contact Email == Email: True".
         Local files only; never calls an API.
"""
import csv, sys, os
csv.field_size_limit(10**7)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from emailfix import tld_valid
sp = os.environ['SP']
# regenerate IMPORT from the fresh master
rd = csv.reader(open(sp + '/hubspot_backfill.csv', encoding='utf-8')); hdr = next(rd)
oi = hdr.index('_Overlaps HubSpot')
o = open(sp + '/hubspot_backfill_IMPORT.csv', 'w', encoding='utf-8', newline=''); w = csv.writer(o); w.writerow(hdr)
k = d = 0
for row in rd:
    if row[oi] == 'yes': d += 1; continue
    w.writerow(row); k += 1
o.close()
print('IMPORT rows:', k, '| overlaps dropped:', d)
rows = list(csv.DictReader(open(sp + '/hubspot_backfill_IMPORT.csv', encoding='utf-8')))
print()
print('=== EMAIL VALIDATION ===')
print('invalid TLD remaining :', sum(1 for r in rows if not tld_valid(r['Email'])))
print('masked remaining      :', sum(1 for r in rows if '*' in r['Email']))
print('Contact Email == Email:', all(r['Contact Email'] == r['Email'] for r in rows))
print('unique people         :', len({r['Email'] for r in rows}))
print('repair notes          :', sum(1 for r in rows if 'email repaired' in r['_Data Note']))
