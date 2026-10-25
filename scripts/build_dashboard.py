"""Render docs/index.html from docs/data/. Every number on the page comes from those CSV files.

Usage: python3 scripts/build_dashboard.py
"""

import csv
import json

from common import OUT, ROOT


def read(name):
    with open(OUT / f"{name}.csv", newline="") as f:
        return list(csv.DictReader(f))


def main():
    data = {
        "summary": json.loads((OUT / "summary.json").read_text()),
        "paymasters": read("paymasters"),
        "tokens": read("erc20-tokens"),
        "daily": read("daily"),
    }
    template = (ROOT / "scripts" / "dashboard-template.html").read_text()
    html = template.replace("/*__DATA__*/null", json.dumps(data, separators=(",", ":")))
    (ROOT / "docs" / "index.html").write_text(html)
    print(f"wrote docs/index.html ({len(html)} bytes)")


if __name__ == "__main__":
    main()
