"""
Cleaning pipeline for natality2024us.sas7bdat.

Run profile_natality_2024.py FIRST and review its output before trusting
the SENTINEL_CODES table below — those values are documented, honest
assumptions based on typical NCHS convention (the max value representable
in a field's digit width usually means "unknown/not stated"), not yet
confirmed against this specific 2024 file. Update SENTINEL_CODES from the
profiling output before treating this script's cleaned output as final.

What this script does:
  1. Reads the file in chunks (never loads the full 2.1GB at once).
  2. Decodes SAS byte-strings to normal Python strings.
  3. Replaces known/assumed sentinel codes with NaN, per field.
  4. Derives the preterm-birth target EMPIRICALLY: rather than trusting the
     dictionary label or an assumed code mapping, it checks which gestrec3
     code aligns with combgest < 37 weeks in the data itself, and asserts a
     high (>99%) agreement rate before proceeding. If agreement is lower
     than that, it stops and prints the mismatch rate rather than silently
     using a possibly-wrong mapping.
  5. Builds "was this value actually reported" boolean flags from the f_*
     reporting-flag columns, for every field where an imputation-vs-reported
     distinction matters to the model.
  6. Keeps dob_yy / dob_mm so this file slots directly into the multi-year
     chronological train/test design once earlier years' files are added —
     this script is written to be re-run per year, not just for 2024.
  7. Saves the cleaned result as Parquet (falls back to CSV if pyarrow is
     not installed), plus prints a sanity-check summary (preterm rate,
     row/column counts, remaining missingness) to catch problems immediately
     rather than downstream in the model.
"""

from pathlib import Path
import pandas as pd
import numpy as np

YEAR = 2024
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_PATH = DATA_DIR / "natality2024us.sas7bdat"
OUTPUT_PATH = DATA_DIR / f"natality{YEAR}us_cleaned.parquet"
OUTPUT_PATH_CSV_FALLBACK = DATA_DIR / f"natality{YEAR}us_cleaned.csv"
CHUNKSIZE = 200_000

# ---------------------------------------------------------------------------
# Column selection
# ---------------------------------------------------------------------------

TARGET_SOURCE_COLS = ["gestrec3", "combgest", "oegest_comb", "oegest_r3"]

ID_COLS = ["dob_yy", "dob_mm"]

PREDICTOR_COLS = [
    "mager", "mrace31", "mhisp_r", "meduc", "dmar",
    "precare", "previs", "cig_0", "cig_1", "cig_2", "cig_3",
    "bmi", "wtgain", "m_ht_in",
    "rf_pdiab", "rf_gdiab", "rf_phype", "rf_ghype", "rf_ehype", "rf_ppterm",
    "rf_cesar", "rf_cesarn", "rf_inftr",
    "wic", "pay_rec", "priorlive", "priordead", "priorterm",
    "sex", "dplural",
]

# Reporting-flag columns paired with the value column they qualify.
# "Reported" is derived as (flag != 0) per the dictionary's own label
# convention ("... 0 Non-Reporting"). Confirm this against
# profile_natality_2024.py's flag-crosstab output before trusting it blindly
# for every field below — a couple may use a different code scheme.
FLAG_PAIRS = [
    ("meduc", "f_meduc"),
    ("dmar", "f_mar_p"),
    ("precare", "f_mpcb"),
    ("previs", "f_tpcv"),
    ("cig_0", "f_cigs_0"), ("cig_1", "f_cigs_1"), ("cig_2", "f_cigs_2"), ("cig_3", "f_cigs_3"),
    ("bmi", "f_pwgt"),
    ("wtgain", "f_wtgain"),
    ("rf_pdiab", "f_rf_pdiab"), ("rf_gdiab", "f_rf_gdiab"),
    ("rf_phype", "f_rf_phyper"), ("rf_ghype", "f_rf_ghyper"),
    ("rf_ehype", "f_rf_eclamp"), ("rf_ppterm", "f_rf_ppb"),
    ("rf_cesar", "f_rf_cesar"),
    ("wic", "f_wic"),
    ("pay_rec", "f_pay_rec"),
]

ALL_FLAG_COLS = [flag for _, flag in FLAG_PAIRS]

READ_COLS = list(dict.fromkeys(TARGET_SOURCE_COLS + ID_COLS + PREDICTOR_COLS + ALL_FLAG_COLS))

# ---------------------------------------------------------------------------
# Sentinel codes — ASSUMED pending confirmation from profile_natality_2024.py.
# Standard NCHS convention: the max value representable in the field's digit
# width means "unknown/not stated." Update these after reviewing the
# profiling script's per-field top-value output.
# ---------------------------------------------------------------------------

SENTINEL_CODES = {
    # Confirmed against the actual 2024 file via profile_natality_2024.py:
    "precare": [99],
    "previs": [99],
    "cig_0": [99], "cig_1": [99], "cig_2": [99], "cig_3": [99],
    "bmi": [99.9],  # stored as 99.9000015258789 in the raw float — apply_sentinels below uses a tolerance match
    "wtgain": [99],
    "m_ht_in": [99],
    # Not yet directly confirmed by profiling (kept as documented assumptions):
    "meduc": [9],
    "combgest": [99],
    "oegest_comb": [99],
    # Not currently read as predictors, but confirmed if added later:
    "pwgt_r": [999],
    "dwgt_r": [999],
}

# Y/N(/U)-coded risk-factor and utilization fields. profile_natality_2024.py's
# flag crosstab surfaced a third code, 'U' (Unknown), for rf_pdiab — confirmed
# on ~7,500 rows. Treating 'U' as missing (not as a real Yes/No) across all
# fields in this family, since the same convention is likely to appear
# elsewhere even where not directly profiled.
YN_FIELDS = [
    "rf_pdiab", "rf_gdiab", "rf_phype", "rf_ghype", "rf_ehype", "rf_ppterm",
    "rf_cesar", "rf_inftr", "wic",
]


def decode_bytes_columns(df):
    for col in df.columns:
        if df[col].dtype == object:
            sample = df[col].dropna()
            if len(sample) and isinstance(sample.iloc[0], bytes):
                df[col] = df[col].apply(lambda v: v.decode("latin-1") if isinstance(v, bytes) else v)
    return df


def apply_sentinels(df, sentinel_map):
    """
    Tolerance-based match on numeric columns (bmi's sentinel is stored as
    99.9000015258789, not exactly 99.9, due to SAS float storage — an exact
    isin() match would silently miss it and let 'unknown' rows pass through
    as if they were real BMI values). Exact match for non-numeric columns.
    """
    for col, sentinels in sentinel_map.items():
        if col not in df.columns:
            continue
        s = df[col]
        if pd.api.types.is_numeric_dtype(s):
            mask = pd.Series(False, index=s.index)
            for val in sentinels:
                mask = mask | np.isclose(s, val, atol=1e-3)
            df.loc[mask, col] = np.nan
        else:
            df.loc[s.isin(sentinels), col] = np.nan
    return df


def encode_yn_fields(df, cols):
    """Y -> 1, N -> 0, anything else (including 'U' = Unknown) -> NaN."""
    mapping = {"Y": 1, "N": 0}
    for col in cols:
        if col in df.columns:
            df[col] = df[col].map(mapping).astype("Int64")
    return df


def read_all_chunks(path, columns, chunksize):
    reader = pd.read_sas(path, format="sas7bdat", chunksize=chunksize, iterator=True)
    parts = []
    total = 0
    for chunk in reader:
        available = [c for c in columns if c in chunk.columns]
        parts.append(chunk[available].copy())
        total += len(chunk)
        print(f"...read {total:,} rows", end="\r")
    print()
    return pd.concat(parts, ignore_index=True)


def derive_preterm_from_pair(df, recode_col, continuous_col, out_col, threshold=37, max_valid=90):
    """
    Empirically confirms a gestation recode's code-to-label mapping against
    its paired continuous-weeks field, rather than trusting the dictionary
    label alone, then derives a clean binary target column. Raises if
    agreement is too low to trust.
    """
    valid = df[continuous_col].notna() & (df[continuous_col] < max_valid) & df[recode_col].notna()
    continuous_preterm = df.loc[valid, continuous_col] < threshold
    recode_vals = df.loc[valid, recode_col]

    agreement_by_code = {}
    for code in recode_vals.unique():
        mask = recode_vals == code
        agreement_by_code[code] = continuous_preterm[mask].mean()

    preterm_code = max(agreement_by_code, key=lambda c: agreement_by_code[c])
    agreement_rate = agreement_by_code[preterm_code]

    print(f"\n{recode_col} code -> fraction with {continuous_col}<{threshold} weeks:")
    for code, rate in sorted(agreement_by_code.items()):
        print(f"    {recode_col}={code!r}: {rate:.4f}")
    print(f"Inferred preterm code: {recode_col}={preterm_code!r} (agreement rate {agreement_rate:.4f})")

    if agreement_rate < 0.99:
        raise ValueError(
            f"{recode_col}={preterm_code!r} only agrees with {continuous_col}<{threshold} in "
            f"{agreement_rate:.2%} of rows — below the 99% trust threshold. "
            "Stop and manually inspect before deriving the target this way."
        )

    df[out_col] = (df[recode_col] == preterm_code).astype("Int64")
    df.loc[df[recode_col].isna(), out_col] = pd.NA
    return df


def build_reported_flags(df, flag_pairs):
    for value_col, flag_col in flag_pairs:
        if value_col in df.columns and flag_col in df.columns:
            flag_vals = df[flag_col]
            reported_col = f"{value_col}_reported"
            df[reported_col] = (flag_vals.astype("float") != 0).astype("Int64")
    return df


def main():
    print(f"Reading {DATA_PATH} ...")
    df = read_all_chunks(DATA_PATH, READ_COLS, CHUNKSIZE)
    print(f"Loaded {len(df):,} rows, {len(df.columns)} columns.")

    df = decode_bytes_columns(df)
    df = apply_sentinels(df, SENTINEL_CODES)
    df = encode_yn_fields(df, YN_FIELDS)
    df = derive_preterm_from_pair(df, "gestrec3", "combgest", "preterm")
    df = derive_preterm_from_pair(df, "oegest_r3", "oegest_comb", "preterm_oe")
    df = build_reported_flags(df, FLAG_PAIRS)

    df["data_year"] = YEAR  # for the future multi-year chronological split

    # --- sanity summary ---
    print("\n" + "=" * 60)
    print("CLEANING SUMMARY")
    print("=" * 60)
    print(f"Rows: {len(df):,}   Columns: {len(df.columns)}")

    preterm_rate = df["preterm"].mean()
    preterm_oe_rate = df["preterm_oe"].mean()
    both_valid = df["preterm"].notna() & df["preterm_oe"].notna()
    disagree_rate = (df.loc[both_valid, "preterm"] != df.loc[both_valid, "preterm_oe"]).mean()
    print(f"Preterm rate (gestrec3 / LMP-based combgest):      {preterm_rate*100:.2f}%")
    print(f"Preterm rate (oegest_r3 / obstetric-estimate):     {preterm_oe_rate*100:.2f}%")
    print(f"Disagreement between the two definitions:          {disagree_rate*100:.2f}% of rows")
    print("[US national rate is commonly cited around ~10.4% — compare both figures against that "
          "and against UserGuide2023.pdf before picking a primary target definition; this is a "
          "documented methodological choice, not something to default on silently.]")

    print("\nMissingness after sentinel cleaning (top 15 by missing %):")
    miss = df.isna().mean().sort_values(ascending=False)
    for col, pct in miss.head(15).items():
        print(f"    {col:20s} {pct*100:5.2f}%")

    # --- save ---
    try:
        df.to_parquet(OUTPUT_PATH, index=False)
        print(f"\nSaved cleaned data to {OUTPUT_PATH}")
    except ImportError:
        df.to_csv(OUTPUT_PATH_CSV_FALLBACK, index=False)
        print(f"\npyarrow not available — saved cleaned data to {OUTPUT_PATH_CSV_FALLBACK} instead. "
              f"Install pyarrow (`pip install pyarrow`) for faster/smaller Parquet output next time.")


if __name__ == "__main__":
    main()
