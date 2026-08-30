"""
Lightweight structural inspection of natality2024us.sas7bdat.

Reads the file in chunks (never loads all 2GB+ into memory at once),
and writes a small JSON summary — column names, dtypes, total row count,
per-column missing counts, and a 5-row sample — to the same data folder.

Run this locally (e.g. in Anaconda / Jupyter / a plain terminal with
`python inspect_natality_2024.py`). It does not require any package
beyond pandas, which reads .sas7bdat natively.
"""

import json
from pathlib import Path
import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_PATH = DATA_DIR / "natality2024us.sas7bdat"
OUT_PATH = DATA_DIR / "natality2024us_inspect.json"
CHUNKSIZE = 200_000

def main():
    reader = pd.read_sas(DATA_PATH, format="sas7bdat", chunksize=CHUNKSIZE, iterator=True)

    total_rows = 0
    columns = None
    dtypes = None
    sample_rows = None
    missing_counts = None

    for chunk in reader:
        if columns is None:
            columns = list(chunk.columns)
            dtypes = {c: str(chunk[c].dtype) for c in columns}
            sample_rows = chunk.head(5).to_dict(orient="records")
            missing_counts = {c: 0 for c in columns}
        for c in columns:
            missing_counts[c] += int(chunk[c].isna().sum())
        total_rows += len(chunk)
        print(f"...processed {total_rows:,} rows", end="\r")

    result = {
        "file": DATA_PATH,
        "n_columns": len(columns),
        "columns": columns,
        "dtypes": dtypes,
        "total_rows": total_rows,
        "missing_counts": missing_counts,
        "sample_rows_first_chunk": sample_rows,
    }

    with open(OUT_PATH, "w") as f:
        json.dump(result, f, indent=2, default=str)

    print(f"\nDone. Wrote summary to {OUT_PATH}")
    print(f"Total rows: {total_rows:,}")
    print(f"Total columns: {len(columns)}")

if __name__ == "__main__":
    main()
