"""Rebuild data/momentum.csv from the Kenneth French data library.

Run from the repo root: python3 scripts/build_data.py

Sources (see doc/adr/0002-momentum-data-and-hold-out.md):
  - 10 portfolios formed on prior (12-2) return, value-weighted, monthly:
    the top decile ("Hi PRIOR") is the momentum portfolio
  - Fama-French research factors, monthly: Mkt-RF and RF

Output columns, all monthly returns in percent:
  month (YYYY-MM), momentum, market, rf
"""

import csv
import io
import re
import urllib.request
import zipfile
from pathlib import Path

BASE = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/"
MOMENTUM_ZIP = "10_Portfolios_Prior_12_2_CSV.zip"
FACTORS_ZIP = "F-F_Research_Data_Factors_CSV.zip"
OUT = Path(__file__).resolve().parent.parent / "data" / "momentum.csv"


def fetch_csv(name: str) -> list[str]:
    with urllib.request.urlopen(BASE + name, timeout=60) as resp:
        archive = zipfile.ZipFile(io.BytesIO(resp.read()))
    (inner,) = archive.namelist()
    return archive.read(inner).decode("latin-1").splitlines()


def monthly_section(lines: list[str], starts: str) -> dict[str, list[float]]:
    """Rows of the first section whose title line starts with `starts`."""
    rows: dict[str, list[float]] = {}
    inside = False
    for line in lines:
        s = line.strip()
        if not inside:
            inside = s.startswith(starts)
            continue
        if s.startswith(","):
            continue  # the column header
        m = re.match(r"^(\d{6}),(.*)$", s)
        if not m:
            if rows:
                break  # end of the section
            continue
        rows[m.group(1)] = [float(x) for x in m.group(2).split(",")]
    if not rows:
        raise SystemExit(f"no monthly section starting {starts!r}")
    return rows


def main() -> None:
    momentum = monthly_section(fetch_csv(MOMENTUM_ZIP), "Value Weight Returns -- Monthly")
    factors = monthly_section(fetch_csv(FACTORS_ZIP), ",Mkt-RF")

    months = sorted(set(momentum) & set(factors))
    OUT.parent.mkdir(exist_ok=True)
    with OUT.open("w", newline="") as f:
        out = csv.writer(f, lineterminator="\n")
        out.writerow(["month", "momentum", "market", "rf"])
        for ym in months:
            hi = momentum[ym][-1]  # "Hi PRIOR", the top decile
            if hi <= -99:
                raise SystemExit(f"missing momentum return for {ym}")
            mkt_rf, _smb, _hml, rf = factors[ym]
            out.writerow([f"{ym[:4]}-{ym[4:]}", f"{hi:.2f}", f"{mkt_rf + rf:.2f}", f"{rf:.2f}"])
    print(f"wrote {len(months)} months, {months[0]} to {months[-1]}, to {OUT}")


if __name__ == "__main__":
    main()
