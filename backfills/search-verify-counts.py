# -*- coding: utf-8 -*-
# Author:   Jibril Sulaiman
# File:     backfills/search-verify-counts.py - run from this folder
#
# What: Cross-checks per-day registration counts you got from HubSpot's
#       reporting engine (a report, a dashboard, or an AI connector's report
#       query) against the HubSpot SEARCH API total, before the figures go
#       into a message. Read-only.
#
# Why:  On this object the reporting engine has run well above the search API
#       for the same filter, and two reporting cuts agreeing with each other
#       proves nothing - they inflate together. Only the search API settles
#       absolute scale.
#
#       Windows are Eastern days expressed as UTC bounds (EDT = UTC-4, so a day
#       starts at T04:00:00Z; in winter EST = UTC-5, T05:00:00Z), because the
#       search API filters dates in UTC while reporting uses the portal's time
#       zone - the same day filter otherwise gives different counts.
#
# Token: hubspot_auth.get_token("hubspot") reads HUBSPOT_TOKEN.
#        Needs crm.objects.custom.read. Held in memory, never printed.

import json
import urllib.error
import urllib.request

from hubspot_auth import get_token

OBJECT = "REPLACE_WITH_OBJECT_TYPE_ID"     # Class Registrations object type id, e.g. 2-12345678
URL = "https://api.hubapi.com/crm/v3/objects/%s/search" % OBJECT
TOKEN = get_token("hubspot")
HEADERS = {"Authorization": "Bearer " + TOKEN, "Content-Type": "application/json"}

# (label, gte, lt, reporting-engine figure to check)
# REPLACE: your days, and the figure your report gave for each one.
DAYS = [
    ("Sep 14", "2026-09-14T04:00:00Z", "2026-09-15T04:00:00Z", 1000),
    ("Sep 15", "2026-09-15T04:00:00Z", "2026-09-16T04:00:00Z", 1000),
    ("Sep 16", "2026-09-16T04:00:00Z", "2026-09-17T04:00:00Z", 1000),
]


def search_total(gte, lt):
    body = {"limit": 1, "filterGroups": [{"filters": [
        {"propertyName": "class_status", "operator": "EQ", "value": "Registered"},
        {"propertyName": "registered_at", "operator": "GTE", "value": gte},
        {"propertyName": "registered_at", "operator": "LT", "value": lt},
        # REPLACE: the same filters your report used. Here: Meta (fb, ig, an = Audience Network).
        {"propertyName": "utm_source__l", "operator": "IN", "values": ["fb", "ig", "an"]},
    ]}]}
    req = urllib.request.Request(URL, data=json.dumps(body).encode(),
                                 headers=HEADERS, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)["total"]
    except urllib.error.HTTPError as e:
        raise SystemExit("HTTP %s\n%s" % (e.code, e.read().decode("utf-8", "replace")[:300]))


print("Registrations - search API vs reporting engine")
print("")
print("  day        search   reporting    reporting/search")
print("  " + "-" * 50)
ts = tr = 0
for label, gte, lt, rep in DAYS:
    t = search_total(gte, lt)
    ts += t
    tr += rep
    print("  %-8s %8s %11s %15.3f" % (label, format(t, ","), format(rep, ","),
                                      (rep / t) if t else 0))
print("  " + "-" * 50)
print("  %-8s %8s %11s %15.3f" % ("TOTAL", format(ts, ","), format(tr, ","), tr / ts))
print("")
print("Ratio ~1.00 -> post the table as written.")
print("Ratio meaningfully above 1.00 -> the search column is the truth; re-derive")
print("the thread numbers from it before posting.")
