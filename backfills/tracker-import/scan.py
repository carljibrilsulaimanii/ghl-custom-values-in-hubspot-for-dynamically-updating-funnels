"""
Author:  Jibril Sulaiman
File:    backfills/tracker-import/scan.py   (step 1 of 4: scan -> build -> drop_overlaps -> split)
What:    Walks every contact-export CSV under ROOT (any file with Email and Tags columns)
         and harvests each (email, class tag) pair plus every timestamp it can find for it:
         FC Reg / Attend / Replay / Upsell Date + Time, names, Created dates, repaired emails.
Why:     The old platform (GoHighLevel) kept class history only as contact tags and
         "latest value" fields. No single export holds it all, so the history has to be
         rebuilt from every export you have before it can become one record per person
         per class in HubSpot.
How to run (PowerShell, from this folder):
         $env:SP = "C:/path/to/work-folder"      # where the intermediate files go
         python scan.py
Writes:  events.tsv, stamps.json, attend.json, fcstamps.json, replay_raw.json,
         repairs.json, identity.json into $env:SP. Reads local files only; never calls an API.
"""
import csv, os, re, sys, json
from collections import Counter, defaultdict
csv.field_size_limit(10**7)
ROOT = r'C:\path\to\exports'   # REPLACE: folder holding every contact-export CSV (searched recursively)
BS = chr(92)
PREFIX = BS + BS + '?' + BS          # \\?\

def longpath(p):
    p = os.path.abspath(p)
    return p if p.startswith(PREFIX) else PREFIX + p

def opencsv(p):
    for enc in ('utf-8-sig', 'cp1252', 'latin-1'):
        try:
            fh = open(longpath(p), encoding=enc, newline='')
            fh.readline(); fh.seek(0)
            return fh, enc
        except UnicodeDecodeError:
            continue
        except OSError:
            return None, None
    return None, None

def n(s): return (s or '').strip().lower()

import sys as _sys
_sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from emailfix import clean_email, tld_valid


CLASS_TAG = re.compile(
    # REPLACE: every spelling your tags used for each topic (tag_class() maps them to a topic key)
    r'^(?P<prog>topic as?|topic b)\s+free class\s+'
    r'(?P<kind>registration|attendees|attended|did not attend|watched replay|upsell purchases)\s*'
    r'\[(?P<when>[^\]]+)\]\s*$')
LEGACY = re.compile(r'free webinar|open house|bootcamp')   # REPLACE: tags from older funnels to report but not import

import datetime
MONTHS = ['January','February','March','April','May','June','July','August',
          'September','October','November','December']
MON = {m.lower(): i + 1 for i, m in enumerate(MONTHS)}
ABBR = {m[:3].lower(): i + 1 for i, m in enumerate(MONTHS)}

def parse_when(w):
    w = (w or '').strip().lower().replace(',', ' ')
    m = re.match(r'^([a-z]+)\s+(\d{1,2})(?:st|nd|rd|th)?\s+(\d{4})$', w)
    if not m:
        return None
    mo = MON.get(m.group(1)) or ABBR.get(m.group(1)[:3])
    if not mo:
        return None
    try:
        d = datetime.date(int(m.group(3)), mo, int(m.group(2)))
    except ValueError:
        return None
    if d.year == 2025 and mo == 1:        # data-specific: our January tags carried last year's year. Delete for clean tags
        d = datetime.date(2026, 1, d.day)
    return d

def tag_class(tag):
    """'topic a free class registration [aug 23rd 2026]' -> ('a', date(2026,8,23))"""
    m = CLASS_TAG.match(n(tag))
    if not m:
        return None
    d = parse_when(m.group('when'))
    if not d:
        return None
    fam = m.group('prog')
    return ('a' if fam in ('topic a', 'topic as') else 'b'), d

def plain_date(s):
    """'Aug 21 2026' -> date"""
    s = (s or '').strip()
    for f in ('%b %d %Y', '%B %d %Y'):
        try:
            return datetime.datetime.strptime(s, f).date()
        except ValueError:
            continue
    return None

files = []
for dp, dn, fn in os.walk(ROOT):
    for f in fn:
        if f.lower().endswith('.csv') and not f.startswith('HubSpot_FreeClass_Backfill'):
            files.append(os.path.join(dp, f))

pairs = set()
tagcount = Counter()
legacy = Counter()
unparsed = Counter()
skipped = []
scanned = 0
names = {}
created = {}
stamps = {}
# 'FC Attend Date' names the class that was attended, so it is self-attributing:
# key attendance timestamps on (email, attend date) rather than trusting a filename.
attend = {}
fcstamps = {}
replay_raw = {}
rejected = Counter()
repairs = {}   # cleaned email -> the corrupted form it was read as

for p in files:
    fh, enc = opencsv(p)
    if fh is None:
        skipped.append((p, 'open')); continue
    try:
        rd = csv.DictReader(fh)
        fnames = rd.fieldnames or []
        if 'Email' not in fnames or 'Tags' not in fnames:
            continue
        scanned += 1
        has_stamp = all(c in fnames for c in ('FC Status Tag', 'FC Reg Date', 'FC Reg Time'))
        has_att = 'FC Attend Date' in fnames and 'FC Attend Time' in fnames
        # FC Status Tag names a class; every FC <x> Date refers to that class's event.
        # Guards below reject values that can't belong to it (the tag is only the LATEST
        # event, so a stale reg/replay date can survive from a different class).
        fcjobs = [(kind, dc, tc) for kind, dc, tc in
                  (('reg', 'FC Reg Date', 'FC Reg Time'),
                   ('replay', 'FC Replay Date', 'FC Replay Time'),
                   ('upsell', 'FC Upsell Date', 'FC Upsell Time'))
                  if dc in fnames and 'FC Status Tag' in fnames]
        for r in rd:
            raw_em = (r.get('Email') or '').strip().lower()
            em = clean_email(raw_em)
            if em != raw_em and raw_em:
                repairs.setdefault(em, raw_em)
            if not em: continue
            fst = (r.get('First Name') or '').strip()
            lst = (r.get('Last Name') or '').strip()
            if fst or lst:
                cur = names.get(em)
                if not cur or len(fst) + len(lst) > len(cur[0]) + len(cur[1]):
                    names[em] = (fst, lst)
            cr = (r.get('Created') or '').strip()
            if cr and (em not in created or cr < created[em]):
                created[em] = cr
            for t in [n(x) for x in (r.get('Tags') or '').split(',') if x.strip()]:
                if CLASS_TAG.match(t):
                    pairs.add((em, t)); tagcount[t] += 1
                elif LEGACY.search(t):
                    legacy[t] += 1
                elif 'free class' in t or 'offer a' in t or 'offer b' in t:   # REPLACE: your offer names
                    unparsed[t] += 1
            if has_stamp:
                fs = n(r.get('FC Status Tag'))
                d = (r.get('FC Reg Date') or '').strip()
                tm = (r.get('FC Reg Time') or '').strip()
                if fs and d and CLASS_TAG.match(fs):
                    stamps.setdefault((em, fs), d + '|' + tm)
            if has_att:
                ad = (r.get('FC Attend Date') or '').strip()
                at = (r.get('FC Attend Time') or '').strip()
                if ad:
                    attend.setdefault((em, ad), ad + '|' + at)
            if 'FC Replay Date' in fnames:
                rv = (r.get('FC Replay Date') or '').strip()
                if rv:
                    replay_raw.setdefault(em, rv + '|' + (r.get('FC Replay Time') or '').strip())
            if fcjobs:
                cls = tag_class(r.get('FC Status Tag'))
                if cls:
                    prog, cd = cls
                    for kind, dcol, tcol in fcjobs:
                        dv = plain_date(r.get(dcol))
                        if not dv:
                            continue
                        # you register on/before the class; you watch a replay on/after it
                        if kind == 'reg' and dv > cd:
                            rejected[kind] += 1; continue
                        if kind == 'replay' and dv < cd:
                            rejected[kind] += 1; continue
                        key = (em, prog, cd.isoformat(), kind)
                        fcstamps.setdefault(key, (r.get(dcol) or '').strip() + '|'
                                            + (r.get(tcol) or '').strip())
    except Exception as e:
        skipped.append((p, type(e).__name__))
    finally:
        fh.close()

print('csv files found        :', len(files))
print('scanned (Email+Tags)   :', scanned)
print('skipped                :', len(skipped))
for p, why in skipped[:12]:
    print('   ', why, os.path.basename(p)[:70])
print()
print('modern class-tag events (email,tag):', len(pairs))
print('distinct modern class tags        :', len(tagcount))
print('emails with a modern class tag    :', len({e for e, _ in pairs}))
print('timestamps harvested              :', len(stamps))
print('attendance timestamps harvested   :', len(attend))
fck = Counter(k[3] for k in fcstamps)
print('FC-tag-attributed stamps          :', len(fcstamps), dict(fck))
print('  rejected by date guard          :', dict(rejected))
print('raw replay timestamps (by email)  :', len(replay_raw))
print('emails repaired                  :', len(repairs))
print('names known                       :', len(names))
print('created dates known               :', len(created))
print()
kinds = Counter(); progs = Counter()
for e, t in pairs:
    m = CLASS_TAG.match(t)
    kinds[m.group('kind')] += 1
    progs[m.group('prog')] += 1
print('by kind:')
for k, v in kinds.most_common(): print(f'   {v:8} {k}')
print('by program:')
for k, v in progs.most_common(): print(f'   {v:8} {k}')
print()
print('legacy / pre-free-class tags (top 12):')
for k, v in legacy.most_common(12): print(f'   {v:8} {k}')
print()
print('free-class-ish but UNPARSED (top 25):')
for k, v in unparsed.most_common(25): print(f'   {v:8} {k}')

out = os.environ['SP']
json.dump({f'{k[0]}|||{k[1]}': v for k, v in stamps.items()}, open(out + '/stamps.json', 'w'))
json.dump({f'{k[0]}|||{k[1]}': v for k, v in attend.items()}, open(out + '/attend.json', 'w'))
json.dump({'|||'.join(map(str, k)): v for k, v in fcstamps.items()}, open(out + '/fcstamps.json', 'w'))
json.dump(replay_raw, open(out + '/replay_raw.json', 'w'))
json.dump(repairs, open(out + '/repairs.json', 'w'))
json.dump({'names': names, 'created': created}, open(out + '/identity.json', 'w'))
with open(out + '/events.tsv', 'w', encoding='utf-8') as fh:
    for e, t in sorted(pairs):
        fh.write(e + '\t' + t + '\n')
print()
print('wrote events.tsv, stamps.json, identity.json')
