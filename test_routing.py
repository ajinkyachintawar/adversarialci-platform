"""
Graph routing self-check.  Run: .venv/bin/python test_routing.py

Guards the AGENTS_V2 scrape skip: v2 sessions must not pay for the
research_data scrape they never read, but sourcing mode exists to scrape
and must keep working when the flag is on.
"""
import os
from main import needs_scraping

STALE = {"mode": "buyer", "new_companies": ["X"], "stale_companies": ["Y"]}


def run():
    os.environ["AGENTS_V2"] = "1"
    assert needs_scraping(STALE) == "verify", "v2 must skip the scrape"
    assert needs_scraping({**STALE, "mode": "sourcing"}) == "scrape", \
        "sourcing mode exists to scrape — the flag must not disable it"

    os.environ["AGENTS_V2"] = "0"
    assert needs_scraping(STALE) == "scrape", "v1 still scrapes stale vendors"
    assert needs_scraping({"mode": "buyer"}) == "verify", \
        "nothing new or stale -> no scrape, flag or not"

    print("✅ routing self-check passed")


if __name__ == "__main__":
    run()
