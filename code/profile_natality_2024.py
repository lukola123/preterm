"""
Diagnostic profiling pass over natality2024us.sas7bdat.

Purpose: before writing any cleaning/imputation logic, find out empirically
(from the real file) what this project needs to know rather than assuming it:

1. What "unknown/not stated" sentinel codes actually appear in each
   continuous/ordinal predictor field (precare, previs, cig_0-3, bmi, wtgain).
   NCHS convention is usually "all 9s for the field's digit width," but this
   should be confirmed against the real 2024 file, not assumed from memory
   or from a prior year's documentation.
2. Whether the f_* reporting-flag convention is really "0 = Non-Reporting /
   imputed, nonzero = reported," as the field labels in the dictionary imply,
   by cross-tabulating a sample of flag values against real value counts.
3. The empirical relationship between gestrec3 (the candidate preterm target)
   and combgest (continuous gestational age in weeks) — this settles the
   exact code-to-label mapping for gestrec3 using the file's own internal
   consistency, rather than relying on a possibly-incomplete label string.

Run this first. Send the printed output back before the cleaning script's
sentinel-code table gets finalized.
"""

import warnings
from pathlib import Path
import pandas as pd
from collections import Counter

warnings.filterwarnings("ignore", message="DataFrame is highly fragmented")

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_PATH = DATA_DIR / "natality2024us.sas7bdat"
CHUNKSIZE = 200_000

# Fields where an "unknown/not stated" sentinel is expected but not yet confirmed.
CANDIDATE_SENTINEL_FIELDS = [
    "precare", "previs", "cig_0", "cig_1", "cig_2", "cig_3",
    "bmi", "wtgain", "meduc", "mager", "m_ht_in", "pwgt_r", "dwgt_r",
    "combgest", "oegest_comb",
]

# A sample of reporting-flag columns paired with the value column they qualify,
# to check the "0 = Non-Reporting" assumption from the dictionary labels.
FLAG_PAIRS_TO_CHECK = [
    ("meduc", "f_meduc"),
    ("precare", "f_mpcb"),
    ("previs", "f_tpcv"),
    ("wtgain", "f_wtgain"),
    ("rf_pdiab", "f_rf_pdiab"),
]


def decode_if_bytes(series):
    if series.dtype == object:
        sample = series.dropna()
        if len(sample) and isinstance(sample.iloc[0], bytes):
            return series.apply(lambda v: v.decode("latin-1") if isinstance(v, bytes) else v)
    return series


def main():
    value_counters = {f: Counter() for f in CANDIDATE_SENTINEL_FIELDS}
    flag_crosstabs = {pair: Counter() for pair in FLAG_PAIRS_TO_CHECK}
    gestrec3_vs_combgest = Counter()  # (gestrec3, combgest_lt_37) -> count
    total_rows = 0

    reader = pd.read_sas(DATA_PATH, format="sas7bdat", chunksize=CHUNKSIZE, iterator=True)

    for chunk in reader:
        total_rows += len(chunk)

        for f in CANDIDATE_SENTINEL_FIELDS:
            if f in chunk.columns:
                value_counters[f].update(chunk[f].dropna().tolist())

        for value_col, flag_col in FLAG_PAIRS_TO_CHECK:
            if value_col in chunk.columns and flag_col in chunk.columns:
                value_series = decode_if_bytes(chunk[value_col])
                flag_series = decode_if_bytes(chunk[flag_col])
                for v, fl in zip(value_series.tolist(), flag_series.tolist()):
                    if pd.isna(v):
                        v_key = v
                    elif isinstance(v, (int, float)):
                        v_key = round(v, 0)
                    else:
                        v_key = v  # text-coded field (e.g. Y/N) — use as-is, don't try to round it
                    flag_crosstabs[(value_col, flag_col)][(fl, v_key)] += 1

        if "gestrec3" in chunk.columns and "combgest" in chunk.columns:
            for g3, cg in zip(chunk["gestrec3"].tolist(), chunk["combgest"].tolist()):
                if pd.notna(g3) and pd.notna(cg) and cg < 90:  # exclude obvious sentinel gestation codes
                    gestrec3_vs_combgest[(g3, cg < 37)] += 1

        print(f"...processed {total_rows:,} rows", end="\r")

    print(f"\n\nTotal rows processed: {total_rows:,}\n")

    print("=" * 70)
    print("TOP VALUES PER CANDIDATE-SENTINEL FIELD (look for an outlier spike")
    print("at the max possible value for that field's digit width — that's")
    print("almost always the 'unknown/not stated' sentinel)")
    print("=" * 70)
    for f, counter in value_counters.items():
        print(f"\n--- {f} ---")
        for val, cnt in counter.most_common(15):
            pct = 100 * cnt / total_rows
            print(f"    {val!r:>10}  {cnt:>10,} ({pct:5.2f}%)")

    print("\n" + "=" * 70)
    print("REPORTING-FLAG CROSSTABS (confirming '0 = Non-Reporting' meaning)")
    print("=" * 70)
    for (value_col, flag_col), counter in flag_crosstabs.items():
        print(f"\n--- {value_col} by {flag_col} (flag_value, rounded_value): count ---")
        for (fl, val), cnt in sorted(counter.items(), key=lambda kv: -kv[1])[:15]:
            print(f"    flag={fl!r:>6}  value={val!r:>10}   {cnt:>10,}")

    print("\n" + "=" * 70)
    print("GESTREC3 vs COMBGEST<37 (settles the exact code-to-label mapping)")
    print("=" * 70)
    for (g3, is_preterm_by_weeks), cnt in sorted(gestrec3_vs_combgest.items()):
        print(f"    gestrec3={g3!r}   combgest<37={is_preterm_by_weeks!s:>5}   {cnt:>10,}")


if __name__ == "__main__":
    main()