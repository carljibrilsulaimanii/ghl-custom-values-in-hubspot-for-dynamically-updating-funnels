"""Backfill GHL free-class history into the HubSpot Free Class Registration format.

Author:  Jibril Sulaiman
File   : backfills/tracker-import/build.py   (step 2 of 4: scan -> build -> drop_overlaps -> split)
What   : Turns what scan.py harvested into one import row per person per class, in the
         column order of a HubSpot export of the Class Registrations object.
Why    : The old platform's history has to land in HubSpot as Class Registration records,
         or every report on the object starts the day the HubSpot workflows went live.
How to run (PowerShell, from this folder, after scan.py, same $env:SP):
         python build.py
Writes : hubspot_backfill.csv (every row, audit columns included) and
         hubspot_backfill_EXCLUDED.csv (rows refused, with the reason) into $env:SP.
         Reads local files only; never calls an API.

Spine  : union of (email, class tag) from every GHL contact export  (events.tsv)
Enrich : tracker sheet (per-event date/time + UTM) -> FC Reg Date/Time stamps
         -> contact-level UTM/Created from exports
Scope  : classes on/after CUTOFF (the current tag era)
"""
import csv, os, re, json, datetime
from collections import defaultdict

csv.field_size_limit(10**7)
SP = os.environ['SP']
DL = r'C:\path\to\exports'                                   # REPLACE: same folder as ROOT in scan.py
SHEET = os.path.join(DL, 'tracker.csv')                      # REPLACE: the per-event tracker sheet, exported as CSV
HS = os.path.join(DL, 'hubspot-export', 'all-records.csv')   # REPLACE: a HubSpot export of the Class Registrations object
CUTOFF = datetime.date(2025, 11, 23)                         # REPLACE: first class date of the current tag era

BS = chr(92)
PREFIX = BS + BS + '?' + BS

def longpath(p):
    p = os.path.abspath(p)
    return p if p.startswith(PREFIX) else PREFIX + p

def opencsv(p):
    for enc in ('utf-8-sig', 'cp1252', 'latin-1'):
        try:
            fh = open(longpath(p), encoding=enc, newline='')
            fh.readline(); fh.seek(0)
            return fh
        except UnicodeDecodeError:
            continue
        except OSError:
            return None
    return None

def n(s): return (s or '').strip().lower()

import sys as _sys
_sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from emailfix import clean_email, tld_valid


MONTHS = ['January','February','March','April','May','June','July','August',
          'September','October','November','December']
MON = {m.lower(): i + 1 for i, m in enumerate(MONTHS)}
ABBR = {m[:3].lower(): i + 1 for i, m in enumerate(MONTHS)}

CLASS_TAG = re.compile(
    # REPLACE: the same topic spellings as scan.py
    r'^(?P<prog>topic as?|topic b) free class '
    r'(?P<kind>registration|attendees|attended|did not attend|watched replay|upsell purchases) '
    r'\[(?P<when>[^\]]+)\]$')

def parse_when(w):
    w = w.strip().lower().replace(',', ' ')
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
    # data-specific tag typo: our January classes were labelled with last year's year.
    # Delete these two lines if your tags are clean.
    if d.year == 2025 and mo == 1:
        d = datetime.date(2026, 1, d.day)
    return d

def parse_tag(tag):
    m = CLASS_TAG.match(tag)
    if not m:
        return None
    d = parse_when(m.group('when'))
    if not d:
        return None
    fam = m.group('prog')
    prog = 'a' if fam in ('topic a', 'topic as') else 'b'
    return prog, fam, m.group('kind'), d

def ordinal(d):
    s = 'th' if 11 <= d.day % 100 <= 13 else {1: 'st', 2: 'nd', 3: 'rd'}.get(d.day % 10, 'th')
    return f'{MONTHS[d.month - 1][:3]} {d.day}{s}, {d.year}'

# REPLACE: one entry per topic key from parse_tag(). topic / ftype must be existing
# options of Class Topic / Free Class Type (README Step 2); config is the topic's Free
# Class Configuration record id, used in Registration Reference.
PROGRAM = {
    'b': dict(name="Topic B class title",
              topic="Topic B", ftype="Topic B free class",
              config='REPLACE_WITH_TOPIC_B_CONFIG_RECORD_ID'),
    'a': dict(name="Topic A class title",
              topic="Topic A", ftype="Topic A free class",
              config='REPLACE_WITH_TOPIC_A_CONFIG_RECORD_ID'),
}

# ---------------------------------------------------------------- canonical tag casing
canon = {}
def learn_casing(path, col):
    fh = opencsv(path)
    if not fh: return
    with fh:
        for r in csv.DictReader(fh):
            v = (r.get(col) or '').strip()
            if v: canon.setdefault(n(v), v)

learn_casing(HS, 'FC Status Tag')
learn_casing(SHEET, 'FC Status Tag')

FIXUP = {'diy': 'DIY'}   # REPLACE: words in your tags that must stay upper case
def cased(tag):
    if tag in canon:
        return canon[tag]
    out = []
    for w in tag.split(' '):
        core = w.strip('[]')
        lead = '[' if w.startswith('[') else ''
        trail = ']' if w.endswith(']') else ''
        out.append(lead + FIXUP.get(core, core.capitalize()) + trail)
    return ' '.join(out)

# ---------------------------------------------------------------- load harvested data
stamps = {tuple(k.split('|||')): v for k, v in json.load(open(SP + '/stamps.json')).items()}
attend = {tuple(k.split('|||')): v for k, v in json.load(open(SP + '/attend.json')).items()}
fcs = {}
for k, v in json.load(open(SP + '/fcstamps.json')).items():
    a, b, c, d_ = k.split('|||')
    fcs[(a, b, c, d_)] = v
replay_raw = json.load(open(SP + '/replay_raw.json'))
repaired = json.load(open(SP + '/repairs.json'))
ident = json.load(open(SP + '/identity.json'))
names, created = ident['names'], ident['created']
print(f'fcstamps={len(fcs)} attend={len(attend)} stamps={len(stamps)} names={len(names)} created={len(created)}', flush=True)

# ---------------------------------------------------------------- tracker sheet enrichment
UTMCOLS = ['First UTM Source','Last UTM Source','First UTM Medium','Last UTM Medium',
           'First Campaign','Last Campaign','First UTM Content','Last UTM Content',
           'First Referrer','Last Referrer','Source','FBCLID']
sheet = {}
with opencsv(SHEET) as fh:
    for r in csv.DictReader(fh):
        em, tag = clean_email(r.get('Email')), n(r.get('FC Status Tag'))
        if not em or not tag: continue
        key = (em, tag)
        if key in sheet: continue
        sheet[key] = ((r.get('Date') or '').strip(), (r.get('Time') or '').strip(),
                      [(r.get(c) or '').strip() for c in UTMCOLS])
print(f'sheet enrichment rows={len(sheet)}', flush=True)

# ---------------------------------------------------------------- contact-level UTM fallback
CUTM = ['UTM Source - First','UTM Source - Last','UTM Medium - First','UTM Medium - Last',
        'UTM Campaign - First','UTM Campaign - Last','UTM Content - First','UTM Content - Last']
cutm = {}
phones = {}

def fmt_phone(v):
    """GHL stores E.164 (+15555550123); HubSpot's export shows (555) 555-0123."""
    v = (v or '').strip()
    digits = re.sub(r'\D', '', v)
    if len(digits) == 11 and digits.startswith('1'):
        digits = digits[1:]
    if len(digits) == 10:
        return f'({digits[:3]}) {digits[3:6]}-{digits[6:]}'
    return v

files = []
for dp, dn, fn in os.walk(DL):
    for f in fn:
        if f.lower().endswith('.csv') and not f.startswith('HubSpot_FreeClass_Backfill'):
            files.append(os.path.join(dp, f))
for p in files:
    fh = opencsv(p)
    if not fh: continue
    try:
        rd = csv.DictReader(fh)
        fn2 = rd.fieldnames or []
        cols = [c for c in CUTM if c in fn2]
        if 'Email' not in fn2: continue
        haspho = 'Phone' in fn2 or 'Phone Number' in fn2
        if not cols and not haspho: continue
        for r in rd:
            em = clean_email(r.get('Email'))
            if not em: continue
            if haspho and em not in phones:
                pv = fmt_phone(r.get('Phone') or r.get('Phone Number'))
                if pv: phones[em] = pv
            vals = {c: (r.get(c) or '').strip() for c in cols}
            if not any(vals.values()): continue
            cur = cutm.setdefault(em, {})
            for c, v in vals.items():
                if v and not cur.get(c): cur[c] = v
    except Exception:
        pass
    finally:
        fh.close()
print(f'contact-level UTM emails={len(cutm)} phones={len(phones)}', flush=True)

# ---------------------------------------------------------------- group events into records
recs = defaultdict(lambda: {'kinds': {}, 'tags': {}})
inscope = skipped_old = unparsed = 0
masked_out = []        # rows refused because the address is redacted
baddom = []            # rows refused: domain not real, cannot repair
for line in open(SP + '/events.tsv', encoding='utf-8'):
    raw, tag = line.rstrip('\n').split('\t')
    em = clean_email(raw)
    if em and not tld_valid(em):
        # The domain does not exist and cannot be snapped to a real TLD, so the address
        # is undeliverable and HubSpot rejects the row. Set it aside rather than ship a
        # guaranteed import error.
        baddom.append((raw, tag))
        continue
    if '*' in em:
        # The local part has been starred out ('****@example.com'), most likely by a
        # privacy erasure. It cannot be matched to a contact, and re-importing it would
        # recreate data someone may have asked to have removed, so refuse the row.
        masked_out.append((raw, tag))
        continue
    p = parse_tag(tag)
    if not p:
        unparsed += 1; continue
    prog, fam, kind, d = p
    if d < CUTOFF:
        skipped_old += 1; continue
    inscope += 1
    r = recs[(em, prog, d)]
    r['kinds'][kind] = True
    r['tags'][kind] = tag
    r['fam'] = fam
print(f'in-scope events={inscope} pre-cutoff dropped={skipped_old} unparsed={unparsed}', flush=True)
print(f'records (email x program x class)={len(recs)}', flush=True)

# ------------------------------------------------- per-program calendar & class windows
# Registration for the NEXT class opens the evening the current class flips, and replay
# enrolment runs until the next class. So a class's window ends at the next class date.
cal = defaultdict(set)
for (em, prog, d) in recs:
    cal[prog].add(d)
cal = {p_: sorted(v) for p_, v in cal.items()}
def next_class(prog, d):
    lst = cal.get(prog, [])
    for x in lst:
        if x > d:
            return x
    return d + datetime.timedelta(days=14)   # open-ended tail for the newest class

# classes whose attendee tag was never applied - attendance is UNKNOWN, not zero
# REPLACE below: 500 = "a class big enough that zero attendees can't be real";
# 2026-08-18 = the day before your HubSpot workflows started writing attendance.
att_missing = set()
for prog, dates in cal.items():
    for d in dates:
        n_reg = sum(1 for (e, pr, dd) in recs if pr == prog and dd == d)
        n_att = sum(1 for (e, pr, dd), rr in recs.items()
                    if pr == prog and dd == d and ('attendees' in rr['kinds'] or 'attended' in rr['kinds']))
        if n_reg >= 500 and n_att == 0 and d < datetime.date(2026, 8, 18):
            att_missing.add((prog, d))
print('classes with NO attendee tag at all (attendance unknown):',
      sorted((p_, x.isoformat()) for p_, x in att_missing), flush=True)

# ---------------------------------------------------------------- existing HubSpot keys
hs_keys = set()
with opencsv(HS) as fh:
    for r in csv.DictReader(fh):
        em = clean_email(r.get('Email')); cd = (r.get('Class Date') or '').strip()
        if em and cd: hs_keys.add((em, cd))
print(f'existing HubSpot (email, class date) keys={len(hs_keys)}', flush=True)

# ---------------------------------------------------------------- emit
# HEADER copies the column order of a HubSpot export of the object (Record ID, then
# every property label alphabetically), so the importer auto-maps it. REPLACE with the
# header of your own export; columns your object lacks show as "Unmapped column".
HEADER = ["Record ID","All class registration notification recipients","Attendance Status",
 "attended","Attended At","Attribution: First Touch","Attribution: Last Touch","Class Date",
 "Class Name","Class Name/Topic","Class Status","Class Topic","completed","Completion Date",
 "Created by user ID","Cross-Registration Flag","Email","Enrolled Date","FC Status Tag",
 "First Form Submission At","Free Class Date","Free Class Source","Free Class Type",
 "Lead Source Platform","No Show","Phone number",
 "Registered At","Registration Reference","Registration Source","Registration Status",
 "Replay Watched At","Source UTM","UTM Campaign - F","UTM Campaign - L","UTM Medium - F",
 "UTM Medium - L","UTM Source - F","UTM Source - L","Watch Duration","Contact Email"]
EXTRA = ["_First Name","_Last Name","_Registered At Source","_Tag Family","_Overlaps HubSpot",
         "_Upsell Product","_Upsell At","_Data Note","_Attended At Source","_Referrer","_UTM Source Of"]

def to_dt(datestr, timestr):
    """'Nov 24 2025' + '5:55 PM' -> '2025-11-24 17:55'"""
    if not datestr: return ''
    try:
        d = datetime.datetime.strptime(datestr.strip(), '%b %d %Y').date()
    except ValueError:
        return ''
    t = ''
    ts = (timestr or '').strip()
    for f in ('%I:%M %p', '%I:%M%p', '%H:%M'):
        try:
            t = datetime.datetime.strptime(ts, f).strftime('%H:%M'); break
        except ValueError:
            continue
    return f'{d.isoformat()} {t}'.strip()

out = open(SP + '/hubspot_backfill.csv', 'w', encoding='utf-8', newline='')
w = csv.writer(out)
w.writerow(HEADER + EXTRA)

att_n = [0]; rep_n = [0]; ups_n = [0]; promoted = [0]
att_sheet_n = [0]; att_rej = [0]; att_assumed = [0]; attr_n = [0]; utm_from = defaultdict(int)
src_counter = defaultdict(int)
status_counter = defaultdict(int)
overlap = 0
written = 0

for (em, prog, d), r in recs.items():
    P = PROGRAM[prog]
    kinds = r['kinds']
    # FC Attend Date names the class that was attended, so it is direct evidence of
    # attendance whether or not the attendee tag ever fired (for one of our classes it
    # never did). Look it up first and let it promote the status.
    mon_ = MONTHS[d.month - 1][:3]
    att_raw = (attend.get((em, f'{mon_} {d.day:02d} {d.year}'))
               or attend.get((em, f'{mon_} {d.day} {d.year}')))

    if 'attendees' in kinds or 'attended' in kinds:
        status = 'Attended'
    elif att_raw:
        status = 'Attended'
        promoted[0] += 1
    elif 'watched replay' in kinds:
        status = 'Watched Replay'
    else:
        status = 'Registered'
    status_counter[status] += 1

    # FC Status Tag reflects the achieved status, mirroring HubSpot
    pref = {'Attended': ['attendees', 'attended', 'registration'],
            'Watched Replay': ['watched replay'],
            'Registered': ['registration']}[status] + ['registration', 'attendees', 'watched replay',
                                                       'upsell purchases', 'attended']
    tag = next((r['tags'][k] for k in pref if k in r['tags']), '')

    reg_tag = r['tags'].get('registration', tag)
    # ---- Registered At, layered
    # You cannot register for a class after it has happened. Attendee/replay rows carry
    # their own (later) timestamps, so any candidate past the class date is the wrong
    # event and must fall through rather than be written as a registration time.
    # Replay enrolment continues after the class, right up to the next one, so a replay
    # row may legitimately be dated after its class. Registered/Attended rows may not.
    # The class config flips to the next class late on class night ("around 10pm,
    # sometimes later"), so a signup for THIS class can be stamped the following day.
    # Allow that lag for Registered rows; an Attended row cannot have registered after
    # the class it attended; replay enrolment runs to the next class.
    if status == 'Watched Replay':
        reg_limit = next_class(prog, d)
    elif status == 'Attended':
        reg_limit = d
    else:
        reg_limit = min(d + datetime.timedelta(days=1), next_class(prog, d))

    def ok(cand):
        if not cand:
            return ''
        try:
            return cand if datetime.date.fromisoformat(cand[:10]) <= reg_limit else ''
        except ValueError:
            return ''

    at, src = '', ''
    for cand_src, raw in (
            ('FC Reg Date/Time', fcs.get((em, prog, d.isoformat(), 'reg'))),
            ('FC Reg Date/Time', stamps.get((em, reg_tag)) or stamps.get((em, tag)))):
        if at or not raw:
            continue
        ds, _, tm = raw.partition('|')
        cand = ok(to_dt(ds, tm))
        if cand:
            at, src = cand, cand_src
    if not at:
        sh = sheet.get((em, reg_tag)) or sheet.get((em, tag))
        if sh:
            cand = ok(to_dt(sh[0], sh[1]))
            if cand:
                at, src = cand, 'tracker sheet'
    if not at:
        # Last look at the tracker sheet: any tag kind logged for this class (attendee,
        # upsell, replay), earliest row. An upsell or attendance row still bounds the
        # registration from above, and the guard keeps it inside the legal window.
        cands = []
        for k_ in ('registration', 'attendees', 'watched replay', 'upsell purchases'):
            tg = r['tags'].get(k_)
            if not tg:
                continue
            sh2 = sheet.get((em, tg))
            if sh2:
                c2 = ok(to_dt(sh2[0], sh2[1]))
                if c2:
                    cands.append(c2)
        if cands:
            at, src = min(cands), 'tracker sheet (other tag)'
    if not at and em in created:
        # Created is the contact's first-ever date. For a repeat attendee it says nothing
        # about when they signed up for THIS class, so only trust it when it lands in a
        # plausible window before the class; otherwise leave the date blank.
        c = created[em][:16].replace('T', ' ')
        try:
            lag = (d - datetime.date.fromisoformat(c[:10])).days
        except ValueError:
            lag = None
        if lag is not None and 0 <= lag <= 90:
            at, src = c, 'contact Created'
        else:
            src = 'none (Created implausible)'
    if not at and not src:
        src = 'none'
    src_counter[src] += 1

    # Attended At: FC Attend Date names the class attended, so match it to this record's
    # class date directly - no reliance on which file the row came from.
    att_at = ''
    att_src = ''
    if status == 'Attended' and att_raw:
        ad, _, atm = att_raw.partition('|')
        att_at = to_dt(ad, atm)
        if att_at: att_n[0] += 1; att_src = 'FC Attend Date'
    if status == 'Attended' and not att_at:
        # FC Attend Date holds only the contact's LATEST attendance, so for an earlier
        # class it is gone. The tracker sheet logged each attendee tag as it fired, so
        # its row for THIS class's attendee tag is a genuine attendance timestamp.
        # Attendance happens on class night, so require the same day (or the next, for a
        # class running past midnight) and reject anything outside that.
        atag = r['tags'].get('attendees') or r['tags'].get('attended')
        sh_a = sheet.get((em, atag)) if atag else None
        if sh_a:
            cand = to_dt(sh_a[0], sh_a[1])
            if cand:
                try:
                    lag = (datetime.date.fromisoformat(cand[:10]) - d).days
                except ValueError:
                    lag = None
                if lag is not None and 0 <= lag <= 1:
                    att_at = cand
                    att_n[0] += 1
                    att_sheet_n[0] += 1
                    att_src = 'tracker sheet'
                else:
                    att_rej[0] += 1
    if status == 'Attended' and not att_at:
        # No measured time survives for this attendance (FC Attend Date was overwritten
        # by a later class and the tracker sheet has no row). Stamp a typical
        # class-night join time (7:27pm Eastern here; REPLACE with yours) - flagged in
        # _Attended At Source as assumed, not measured.
        att_at = f'{d.isoformat()} 19:27'
        att_src = 'assumed 19:27 EST'
        att_assumed[0] += 1

    # Replay: FC Status Tag frequently names the UPCOMING class (the config flips the
    # evening of a class), so ignore it and attribute by window instead - a replay of
    # class d is watched between d and the next class of the same program.
    rep_at = ''
    if 'watched replay' in kinds:
        raw = replay_raw.get(em)
        if raw:
            ds, _, tm = raw.partition('|')
            cand = to_dt(ds, tm)
            if cand:
                try:
                    rd_ = datetime.date.fromisoformat(cand[:10])
                except ValueError:
                    rd_ = None
                if rd_ and d <= rd_ < next_class(prog, d):
                    rep_at = cand; rep_n[0] += 1
    ups_at = ''
    fx = fcs.get((em, prog, d.isoformat(), 'upsell'))
    if fx:
        ds, _, tm = fx.partition('|')
        ups_at = to_dt(ds, tm)
        if ups_at: ups_n[0] += 1

    fst, lst = names.get(em, ('', ''))
    full = ' '.join(x for x in (fst, lst) if x).strip()

    # ---- UTM: per-event sheet values first, contact-level fallback
    # The tracker sheet is the ONLY per-event UTM snapshot: it recorded the values as
    # they stood when that registration happened. Contact-level UTM is whatever the
    # contact looks like NOW, so for an older class it is often the wrong campaign
    # entirely. Prefer the sheet, across any tag kind logged for this class, and record
    # which source won so stale attribution can be filtered out downstream.
    sv = {}
    for k_ in ('registration', 'attendees', 'watched replay', 'upsell purchases'):
        tg = r['tags'].get(k_)
        if not tg:
            continue
        sh_ = sheet.get((em, tg))
        if not sh_:
            continue
        cand = dict(zip(UTMCOLS, sh_[2]))
        if any(cand.get(c) for c in ('First UTM Source', 'Last UTM Source',
                                     'First Campaign', 'Last Campaign',
                                     'First UTM Medium', 'Last UTM Medium')):
            sv = cand
            break
        if not sv:
            sv = cand
    cv = cutm.get(em, {})
    utm_src_of = [None]

    def pick(sheet_col, contact_col):
        v = sv.get(sheet_col)
        if v:
            if utm_src_of[0] is None: utm_src_of[0] = 'tracker sheet (per-event)'
            return v
        v = cv.get(contact_col)
        if v:
            if utm_src_of[0] is None: utm_src_of[0] = 'contact-level (point-in-time)'
            return v
        return ''
    utm_sf = pick('First UTM Source', 'UTM Source - First')
    utm_sl = pick('Last UTM Source', 'UTM Source - Last')
    utm_mf = pick('First UTM Medium', 'UTM Medium - First')
    utm_ml = pick('Last UTM Medium', 'UTM Medium - Last')
    utm_cf = pick('First Campaign', 'UTM Campaign - First')
    utm_cl = pick('Last Campaign', 'UTM Campaign - Last')

    # HubSpot's attribution maps cleanly off utm_source: fb/ig -> Social media,
    # tiktok/facebook -> Paid Social. A blank source is ambiguous there (CRM UI /
    # Social media / Direct traffic all occur), so leave those blank rather than guess.
    # Mirror how HubSpot itself classified each utm_source in the live records, rather
    # than inventing categories. Only sources where its own mapping is near-unanimous
    # are included; sources HubSpot split between two categories, and blank (three-way),
    # stay unmapped so attribution reporting is not polluted with coin flips.
    # REPLACE: build this table from how YOUR live records classify each utm_source.
    ATTR = {'fb': 'Social media', 'ig': 'Social media',
            'tiktok': 'Paid Social', 'facebook': 'Paid Social',
            'slicktext': 'Direct traffic',        # SMS links carry no tracking
            'activecampaign': 'Direct traffic',
            'email': 'Email Marketing'}
    attr_f = ATTR.get(utm_sf.strip().lower(), '')
    attr_l = ATTR.get(utm_sl.strip().lower(), '')
    if attr_f: attr_n[0] += 1

    utm_from[utm_src_of[0] or 'none'] += 1

    key = (em, d.isoformat())
    dup = key in hs_keys
    if dup: overlap += 1

    row = {
        'Class Date': d.isoformat(),
        'Class Name': P['name'],
        'Class Name/Topic': f'{full} - {cased(tag)}' if full else cased(tag),
        'Class Status': status,
        'Class Topic': P['topic'],
        'Email': em,
        'FC Status Tag': cased(tag),
        'Free Class Date': ordinal(d),
        'Free Class Type': P['ftype'],
        'Lead Source Platform': 'Funnel/Website',
        'Attribution: First Touch': attr_f,
        'Attribution: Last Touch': attr_l,
        'Registered At': at,
        'Enrolled Date': at[:10],
        'Attended At': att_at,
        'Replay Watched At': rep_at,
        'Registration Reference': f'{em}-{P["config"]}-{d.isoformat()}',
        'Registration Status': 'Registered' if status == 'Registered' else '',
        'Registration Source': '' if status == 'Registered' else 'Opt-in page',
        'attended': 'true' if status == 'Attended' else '',
        'No Show': 'false' if status == 'Attended' else '',
        # GHL's tag is a generic '<program> free class upsell purchases' and does NOT name
        # the product: each topic upsells a different offer. Don't assert a purchase
        # property from it - keep the signal in the _Upsell Product audit column instead.
        # HubSpot's Source UTM is the full landing URL with query string. GHL's
        # referrer ('http://m.facebook.com') is a different thing, so it goes to an
        # audit column rather than into this field.
        'Source UTM': '',
        '_UTM Source Of': utm_src_of[0] or '',
        '_Referrer': sv.get('First Referrer') or sv.get('Last Referrer') or '',
        'UTM Source - F': utm_sf, 'UTM Source - L': utm_sl,
        'UTM Medium - F': utm_mf, 'UTM Medium - L': utm_ml,
        'UTM Campaign - F': utm_cf, 'UTM Campaign - L': utm_cl,
        'Phone number': phones.get(em, ''),
        # bare address for the Contact -> Email mapping that creates the association
        'Contact Email': em,
        '_First Name': fst, '_Last Name': lst,
        '_Registered At Source': src,
        '_Tag Family': r.get('fam', ''),
        '_Overlaps HubSpot': 'yes' if dup else '',
        '_Data Note': '; '.join(x for x in (
            ('attendee tag never fired; attendance recovered from FC Attend Date'
             if (prog, d) in att_missing else ''),
            ('email repaired from "' + repaired[em] + '"' if em in repaired else ''),
        ) if x),
        '_Attended At Source': att_src,
        '_Upsell At': ups_at,
        '_Upsell Product': ('' if 'upsell purchases' not in kinds
                            else ('Offer A' if prog == 'a' else 'Offer B')),
    }
    w.writerow([row.get(c, '') for c in HEADER + EXTRA])
    written += 1

out.close()

with open(SP + '/hubspot_backfill_EXCLUDED.csv', 'w', encoding='utf-8', newline='') as xf:
    xw = csv.writer(xf)
    xw.writerow(['Email (as found)', 'FC Status Tag', 'Reason'])
    for raw_, tg_ in masked_out:
        xw.writerow([raw_, tg_, 'email redacted at source - cannot associate to a contact'])
    for raw_, tg_ in baddom:
        xw.writerow([raw_, tg_, 'email domain is not a real TLD and cannot be repaired'])
print('')
print('EMAIL HYGIENE')
print('  bad-domain rows dropped : ' + str(len(baddom)))
print('  masked rows dropped : ' + str(len(masked_out)) + '  -> hubspot_backfill_EXCLUDED.csv')
print('  emails repaired     : ' + str(len(repaired)) + '  (annotated in _Data Note)')
for k_ in sorted(repaired):
    print('      ' + repaired[k_] + '  ->  ' + k_)

print(f'\nwrote {written} rows -> hubspot_backfill.csv', flush=True)
print('\nClass Status:')
for k, v in sorted(status_counter.items(), key=lambda x: -x[1]): print(f'   {v:8} {k}')
print('\nRegistered At provenance:')
for k, v in sorted(src_counter.items(), key=lambda x: -x[1]): print(f'   {v:8} {k}')
print(f"\nAttendance promoted from FC Attend Date (no attendee tag): {promoted[0]}")
print(f"  of which from tracker sheet: {att_sheet_n[0]} (rejected outside class night: {att_rej[0]})")
print("UTM provenance:"); [print(f"   {v:8} {k}") for k, v in sorted(utm_from.items(), key=lambda x: -x[1])]
print(f"Attribution derived from utm_source: {attr_n[0]}")
print(f"  assumed 19:27 EST fallback : {att_assumed[0]}")
print(f"Attended At populated      : {att_n[0]} of {status_counter['Attended']} attended rows")
print(f"Replay Watched At populated: {rep_n[0]} of {status_counter['Watched Replay']} replay rows")
print(f"_Upsell At populated       : {ups_n[0]}")
print(f'\nrows overlapping existing HubSpot (email, class date): {overlap}')
