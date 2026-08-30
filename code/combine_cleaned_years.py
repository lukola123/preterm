"""
Combines the already-cleaned per-year checkpoint CSVs
(natalityYYYYus_cleaned.csv, produced by clean_natality_multiyear.py) into
one file — WITHOUT loading all years into memory at once, which is what
crashed the original script's in-memory pd.concat().

Streams each file in chunks and appends directly to the output file, so
peak memory is bounded by one chunk, not by the full combined dataset.
Also computes the per-year preterm-rate summary the same way (streamed),
so no large in-memory DataFrame is ever created.
"""

from pathlib import Path
import pandas as pd

YEARS = [2021, 2022, 2023, 2024]
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"
CHUNKSIZE = 200_000
COMBINED_PATH = OUTPUT_DIR / f"natality_{YEARS[0]}_{YEARS[-1]}_us_cleaned.csv"


def combine():
    first = True
    with open(COMBINED_PATH, "w", newline="", encoding="utf-8") as fout:
        for year in YEARS:
            path = OUTPUT_DIR / f"natality{year}us_cleaned.csv"
            print(f"Appending {path} ...")
            for chunk in pd.read_csv(path, chunksize=CHUNKSIZE):
                chunk.to_csv(fout, header=first, index=False, lineterminator="\n")
                first = False
    print(f"\nCombined file written to {COMBINED_PATH}")


def summarize():
    print("\nRows and preterm rates by year (streamed from disk, low-memory):")
    for year in YEARS:
        path = OUTPUT_DIR / f"natality{year}us_cleaned.csv"
        n = 0
        preterm_sum = 0.0
        preterm_oe_sum = 0.0
        for chunk in pd.read_csv(path, usecols=["preterm", "preterm_oe"], chunksize=CHUNKSIZE):
            n += len(chunk)
            preterm_sum += chunk["preterm"].sum()
            preterm_oe_sum += chunk["preterm_oe"].sum()
        print(f"    {year}: {n:,} rows   preterm={100*preterm_sum/n:.2f}%   preterm_oe={100*preterm_oe_sum/n:.2f}%")

    print(f"\nTrain/test split reminder: train on data_year in {YEARS[:-1]}, "
          f"hold out data_year == {YEARS[-1]} entirely as the external test year.")


if __name__ == "__main__":
    combine()
    summarize()
