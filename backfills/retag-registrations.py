# -*- coding: utf-8 -*-
# Author:   Jibril Sulaiman
# File:     backfills/retag-registrations.py
#           Run from this folder (needs hubspot_auth.py next to it).
#
# What: Re-tags Class Registration records that carry the PREVIOUS session's
#       registration tag (OLD_TAG) and class session (OLD_SESSION) but the NEXT
#       class's Class Date, so they count toward the class they actually
#       registered for. Only Class Status = Registered is touched.
#
# Why:  After a flip to a different topic, registrations for the next class can
#       arrive while a branch still reads the old topic's values: the Class Date
#       is right, but the tag, topic and session come from the stale config, so
#       those people fall out of the next class's count.
#
#       Default run is a DRY RUN: pulls the records, writes a backup CSV of
#       every current value, and prints the plan. Pass --apply to write.
#       WRITES TO HUBSPOT only with --apply.
#
# Token: hubspot_auth.get_token("hubspot") reads HUBSPOT_TOKEN. Needs
#        crm.objects.custom.read and, for --apply, crm.objects.custom.write.
#        Held in memory, never printed.

import csv
import json
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from hubspot_auth import get_token

OBJECT = "REPLACE_WITH_OBJECT_TYPE_ID"     # Class Registrations object type id, e.g. 2-12345678
BASE = "https://api.hubapi.com/crm/v3/objects/%s" % OBJECT
HEADERS = {"Authorization": "Bearer " + get_token("hubspot"),
           "Content-Type": "application/json"}

# REPLACE every value below. Copy NEW_* from a correctly written record of the
# class these people registered for, character for character.
OLD_TAG = "Topic B Free Class Registration [Sep 10th 2026]"
OLD_SESSION = "2026-09-17 - Topic B"     # the stale session label on the records to fix
NEW_TAG = "Topic A Free Class Registration [Sep 17th 2026]"
NEW_VALUES = {
    "fc_status_tag": NEW_TAG,
    "class_topic": "Topic A",
    "class_session": "2026-09-17 - Topic A",
    "free_class_date": "Sep 17th, 2026",
}
PROPS = ["class_registration_name", "fc_status_tag", "class_topic",
         "class_session", "free_class_date", "class_date", "class_status",
         "enrolled_date", "email", "utm_campaign__l"]

APPLY = "--apply" in sys.argv
HERE = Path(__file__).resolve().parent


def call(method, url, body=None):
    for attempt in range(6):
        req = urllib.request.Request(url, method=method, headers=HEADERS,
                                     data=json.dumps(body).encode() if body else None)
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(2 ** attempt)
                continue
            raise SystemExit("HTTP %s\n%s" % (e.code, e.read().decode("utf-8", "replace")[:500]))
    raise SystemExit("Gave up after repeated 429s")


def fetch():
    rows, after = [], None
    while True:
        body = {"limit": 200, "properties": PROPS, "filterGroups": [{"filters": [
            {"propertyName": "fc_status_tag", "operator": "EQ", "value": OLD_TAG},
            {"propertyName": "class_session", "operator": "EQ", "value": OLD_SESSION},
            {"propertyName": "class_status", "operator": "EQ", "value": "Registered"},
        ]}]}
        if after:
            body["after"] = after
        page = call("POST", BASE + "/search", body)
        rows += page["results"]
        after = page.get("paging", {}).get("next", {}).get("after")
        if not after:
            return rows
        time.sleep(0.4)


rows = fetch()
print("Matched records: %d" % len(rows))
if not rows:
    raise SystemExit("Nothing to do.")

stamp = datetime.now().strftime("%Y-%m-%d_%H%M")
backup = HERE / ("backup_before_retag_%s.csv" % stamp)
with backup.open("w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["id"] + PROPS)
    for r in rows:
        w.writerow([r["id"]] + [r["properties"].get(p) or "" for p in PROPS])
print("Backup written: %s" % backup)

dates = Counter(r["properties"].get("enrolled_date") for r in rows)
print("Enrolled dates:", dict(sorted(dates.items(), key=lambda x: str(x[0]))))
print("class_date values:", dict(Counter(r["properties"].get("class_date") for r in rows)))


def new_name(old):
    return (old or "").replace(OLD_TAG, NEW_TAG)


updates = [{"id": r["id"], "properties": dict(NEW_VALUES, class_registration_name=
            new_name(r["properties"].get("class_registration_name")))} for r in rows]
print("Example rename: %r -> %r" % (rows[0]["properties"].get("class_registration_name"),
                                     updates[0]["properties"]["class_registration_name"]))

if not APPLY:
    print("\nDRY RUN - nothing written. Re-run with --apply to update.")
    raise SystemExit(0)

done = 0
for i in range(0, len(updates), 100):
    call("POST", BASE + "/batch/update", {"inputs": updates[i:i + 100]})
    done += len(updates[i:i + 100])
    print("Updated %d / %d" % (done, len(updates)))
    time.sleep(0.4)
print("Done.")
