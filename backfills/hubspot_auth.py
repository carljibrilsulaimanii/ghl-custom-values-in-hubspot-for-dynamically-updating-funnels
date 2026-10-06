# -*- coding: utf-8 -*-
"""
Author:   Jibril Sulaiman
File:     backfills/hubspot_auth.py
          Imported by the other scripts in this folder: `from hubspot_auth import get_token`

What: One place to get the HubSpot token. Reads it from the HUBSPOT_TOKEN
      environment variable. Never prints or logs the value.

Why:  Every backfill script needs the same token. Keeping the lookup in one file
      means no script ever holds a token in its own code, and a missing token
      fails with a message that says how to fix it instead of a bare KeyError.

How to run: you don't run this file. Set the variable in the terminal you run
      the other scripts from (PowerShell):

          $env:HUBSPOT_TOKEN = "<your service key>"

      Check it is set without revealing it:

          python hubspot_auth.py
"""

import os
import sys


def _clean(raw):
    """Strip BOM, whitespace and stray quotes that come from pasting."""
    return raw.strip().strip('"').strip("'").strip()


def _from_env(service):
    v = os.environ.get(service.upper() + "_TOKEN")
    return _clean(v) if v else None


def get_token(service, required=True):
    """Return the token for `service` (read from <SERVICE>_TOKEN), or exit with
    instructions if it is missing.

    Held in memory only. Callers must never print it or write it to a file."""
    tok = _from_env(service)
    if tok:
        return tok
    if not required:
        return None
    sys.exit(
        "No token found for '%s'. Set it in this terminal first (PowerShell):\n"
        "    $env:%s_TOKEN = \"<your service key>\""
        % (service, service.upper())
    )


if __name__ == "__main__":
    print("HUBSPOT_TOKEN: %s" % ("set" if _from_env("hubspot") else "NOT set"))
