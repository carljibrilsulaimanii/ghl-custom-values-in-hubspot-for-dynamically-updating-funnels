"""Email normalisation shared by scan.py and build.py.

Author:  Jibril Sulaiman
File:    backfills/tracker-import/emailfix.py
What:    clean_email() repairs the two kinds of email damage that are safe to repair;
         tld_valid() says whether an address ends in a real top-level domain.
Why:     HubSpot's importer rejects every row whose email has a fake TLD ("Invalid
         email"), and a damaged address can't be associated to its contact.
How to run: you don't. scan.py and build.py import it from this folder.

Three classes of corruption appear in the GoHighLevel / ActiveCampaign / SlickText exports:

  1. mechanical    'x@example.com555555012'  a phone number concatenated after the TLD
                   'x@example.c'            a truncated TLD
  2. bad TLD       'x@example.con'          .con/.vom/.comm/.nwt - not real TLDs, so the
                                            address is undeliverable and HubSpot rejects
                                            the row outright
  3. bad provider  'x@exampel.com'          format-valid, HubSpot accepts it, but the
                                            mailbox almost certainly does not exist

We repair 1 and 2. A wrong TLD cannot be "a different real mailbox" because the domain
does not resolve at all, so restoring it is safe and keeps the local part untouched.

We deliberately do NOT repair 3: 'hmail' sits one edit from both gmail and ymail, so any
guess would silently redirect mail to a different person. Those are reported instead.
"""
import re

VALID_TLD = set("""
com net org edu gov mil int co io me us uk ca au de fr es it nl se no dk fi ie ch at be
pt pl cz ru jp cn in br mx za ng ke gh ph sg hk nz tt jm bb bs bm vi pr gu info biz
name pro mobi tv cc ws la to gg im je eu asia xyz online site store shop app dev cloud
live life world today email tech space website digital agency media group center
solutions services consulting financial capital fund tax law health care clinic church
gr tr il ae sa eg ma dz tn ug tz zm zw bw na mu sc ci sn cm ga cg cd ao mz mw et sd ly
jo lb sy iq ir pk bd lk np mm th vn my id kh bn tw kr mn kz uz ge am az by ua md ro bg
rs hr si sk hu lt lv ee is lu mt cy mc ad sm va li fo gl re nc pf ac sh cx nf ki nr pw
ck nu tk pn ai ag aw bq cw sx tc vg vc lc gd dm kn ms ky bz gt sv hn ni cr pa cu do ht
pe bo py uy cl ar ec ve gy sr gf fk net.au com.au co.uk org.uk ac.uk co.za com.br
""".split())

def _dist(a, b):
    """Levenshtein distance, small strings only."""
    if a == b:
        return 0
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]

# distance we allow when snapping a mistyped TLD back to a real one
_SNAP = (('com', 2), ('net', 1), ('org', 1), ('edu', 1))

def fix_tld(tld):
    """Return the corrected TLD, or '' if it cannot be corrected confidently."""
    if tld in VALID_TLD:
        return tld
    best, best_d = '', 99
    for target, limit in _SNAP:
        d = _dist(tld, target)
        if d <= limit and d < best_d:
            best, best_d = target, d
    return best

def clean_email(s):
    e = (s or '').strip().lower()
    if not e or '@' not in e:
        return e
    # 1. mechanical damage
    e = re.sub(r'(\.[a-z]{2,63})\d+$', lambda m: m.group(1), e)
    e = re.sub(r'@([a-z0-9.-]+)\.c$', lambda m: '@' + m.group(1) + '.com', e)
    # 2. mistyped TLD
    local, _, dom = e.rpartition('@')
    if '.' in dom:
        base, _, tld = dom.rpartition('.')
        if tld not in VALID_TLD:
            fixed = fix_tld(tld)
            if fixed:
                e = local + '@' + base + '.' + fixed
    return e

def tld_valid(e):
    dom = (e or '').rsplit('@', 1)[-1]
    return '.' in dom and dom.rsplit('.', 1)[-1] in VALID_TLD
