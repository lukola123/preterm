"""
Multi-year cleaning pipeline for natality2021us.sas7bdat through
natality2024us.sas7bdat — generalizes clean_natality_2024.py so the same
confirmed logic runs once per year instead of being hand-copied per file.

Design principle carried over from the 2024-only version: cleaning happens
PER YEAR, then the already-cleaned, already-normalized yearly frames are
concatenated — never the raw files. NCHS can and does revise codes/fields
between years, so each year gets its own automatic validation gate before
being trusted:

  - derive_preterm_from_pair() re-derives BOTH preterm targets for every
    year and raises if the gestrec3/combgest or oegest_r3/oegest_comb
    agreement rate drops below 99% for that year specifically — this is
    the hard stop that catches a year where NCHS changed the coding.
  - Per-year sentinel value counts are printed for the key fields
    (precare, previs, cig_0, bmi, wtgain) so a shifted sentinel location
    is visible immediately rather than silently miscoded.
  - Any column present in one year but missing in another is reported,
    not silently dropped.

Each year is saved to its own cleaned CSV/Parquet (checkpointing — if a
later year fails validation, earlier years' work isn't lost), and all years
are then concatenated into one combined file with the `data_year` column
already in place for the train-on-earlier/test-on-2024 chronological split.
"""

from pathlib import Path
import pandas as pd
import numpy as np

YEARS = [2021, 2022, 2023, 2024]
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"       # raw .sas7bdat source files
OUTPUT_DIR = PROJECT_ROOT / "output"   # cleaned per-year and combined checkpoint CSVs
CHUNKSIZE = 200_000
SENTINEL_SPOT_CHECK_FIELDS = ["precare", "previs", "cig_0", "bmi", "wtgain"]

# ---------------------------------------------------------------------------
# Column selection — identical to clean_natality_2024.py (year-agnostic;
# only the sentinel VALUES and agreement rates need re-confirming per year,
# not the column names themselves).
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

SENTINEL_CODES = {
    "precare": [99], "previs": [99],
    "cig_0": [99], "cig_1": [99], "cig_2": [99], "cig_3": [99],
    "bmi": [99.9], "wtgain": [99], "m_ht_in": [99],
    "meduc": [9], "combgest": [99], "oegest_comb": [99],
    "pwgt_r": [999], "dwgt_r": [999],
}

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
    mapping = {"Y": 1, "N": 0}
    for col in cols:
        if col in df.columns:
            df[col] = df[col].map(mapping).astype("Int64")
    return df


def read_all_chunks(path, columns, chunksize):
    reader = pd.read_sas(path, format="sas7bdat", chunksize=chunksize, iterator=True)
    parts = []
    total = 0
    seen_columns = None
    for chunk in reader:
        if seen_columns is None:
            seen_columns = set(chunk.columns)
            missing = [c for c in columns if c not in seen_columns]
            if missing:
                print(f"    WARNING: expected columns not found in this file: {missing}")
        available = [c for c in columns if c in chunk.columns]
        parts.append(chunk[available].copy())
        total += len(chunk)
        print(f"    ...read {total:,} rows", end="\r")
    print()
    return pd.concat(parts, ignore_index=True)


def derive_preterm_from_pair(df, recode_col, continuous_col, out_col, year, threshold=37, max_valid=90):
    valid = df[continuous_col].notna() & (df[continuous_col] < max_valid) & df[recode_col].notna()
    continuous_preterm = df.loc[valid, continuous_col] < threshold
    recode_vals = df.loc[valid, recode_col]

    agreement_by_code = {}
    for code in recode_vals.unique():
        mask = recode_vals == code
        agreement_by_code[code] = continuous_preterm[mask].mean()

    preterm_code = max(agreement_by_code, key=lambda c: agreement_by_code[c])
    agreement_rate = agreement_by_code[preterm_code]

    print(f"    [{year}] {recode_col} -> {continuous_col}<{threshold}: "
          f"code={preterm_code!r}, agreement={agreement_rate:.4f}")

    if agreement_rate < 0.99:
        raise ValueError(
            f"Year {year}: {recode_col}={preterm_code!r} only agrees with {continuous_col}<{threshold} "
            f"in {agreement_rate:.2%} of rows — below the 99% trust threshold. NCHS may have changed "
            f"this field's coding for {year}. Stop and manually inspect before proceeding."
        )

    df[out_col] = (df[recode_col] == preterm_code).astype("Int64")
    df.loc[df[recode_col].isna(), out_col] = pd.NA
    return df


def build_reported_flags(df, flag_pairs):
    for value_col, flag_col in flag_pairs:
        if value_col in df.columns and flag_col in df.columns:
            df[f"{value_col}_reported"] = (df[flag_col].astype("float") != 0).astype("Int64")
    return df


def sentinel_spot_check(df, year, fields):
    print(f"    [{year}] sentinel spot-check (top 3 values per field):")
    for f in fields:
        if f in df.columns:
            top = df[f].value_counts(dropna=True).head(3)
            vals = ", ".join(f"{v!r}={c:,}" for v, c in top.items())
            print(f"        {f:10s} {vals}")


def clean_one_year(year):
    path = DATA_DIR / f"natality{year}us.sas7bdat"
    print(f"\n{'='*70}\nYEAR {year}: {path}\n{'='*70}")

    df = read_all_chunks(path, READ_COLS, CHUNKSIZE)
    print(f"    Loaded {len(df):,} rows, {len(df.columns)} columns.")

    df = decode_bytes_columns(df)
    sentinel_spot_check(df, year, SENTINEL_SPOT_CHECK_FIELDS)  # BEFORE nulling, so the spike is visible
    df = apply_sentinels(df, SENTINEL_CODES)
    df = encode_yn_fields(df, YN_FIELDS)
    df = derive_preterm_from_pair(df, "gestrec3", "combgest", "preterm", year)
    df = derive_preterm_from_pair(df, "oegest_r3", "oegest_comb", "preterm_oe", year)
    df = build_reported_flags(df, FLAG_PAIRS)

    df["data_year"] = year

    preterm_rate = df["preterm"].mean()
    preterm_oe_rate = df["preterm_oe"].mean()
    print(f"    [{year}] preterm (LMP-based)={preterm_rate*100:.2f}%   "
          f"preterm_oe (obstetric-estimate)={preterm_oe_rate*100:.2f}%")

    # per-year checkpoint save
    out_path = OUTPUT_DIR / f"natality{year}us_cleaned.csv"
    df.to_csv(out_path, index=False)
    print(f"    [{year}] saved checkpoint -> {out_path}")

    return df


def combine_checkpoints_streaming(years, output_dir, chunksize=CHUNKSIZE):
    """
    Combines already-saved per-year checkpoint CSVs by streaming chunks
    straight to the output file, rather than holding every year's cleaned
    DataFrame in memory at once (that in-memory pd.concat() approach is
    what previously hit a MemoryError with four ~3.6M-row frames loaded
    simultaneously).
    """
    combined_path = output_dir / f"natality_{years[0]}_{years[-1]}_us_cleaned.csv"
    first = True
    with open(combined_path, "w", newline="", encoding="utf-8") as fout:
        for year in years:
            path = output_dir / f"natality{year}us_cleaned.csv"
            print(f"    Appending {path} ...")
            for chunk in pd.read_csv(path, chunksize=chunksize):
                chunk.to_csv(fout, header=first, index=False, lineterminator="\n")
                first = False
    print(f"Combined file written to {combined_path}")

    print("\nRows and preterm rates by year (streamed from disk, low-memory):")
    for year in years:
        path = output_dir / f"natality{year}us_cleaned.csv"
        n = 0
        preterm_sum = 0.0
        preterm_oe_sum = 0.0
        for chunk in pd.read_csv(path, usecols=["preterm", "preterm_oe"], chunksize=chunksize):
            n += len(chunk)
            preterm_sum += chunk["preterm"].sum()
            preterm_oe_sum += chunk["preterm_oe"].sum()
        print(f"    {year}: {n:,} rows   preterm={100*preterm_sum/n:.2f}%   preterm_oe={100*preterm_oe_sum/n:.2f}%")

    print(f"\nTrain/test split reminder: train on data_year in {years[:-1]}, "
          f"hold out data_year == {years[-1]} entirely as the external test year.")


def main():
    for year in YEARS:
        df_year = clean_one_year(year)
        del df_year  # free memory immediately — the combine step re-reads from the saved checkpoint CSVs

    print(f"\n{'='*70}\nCOMBINING CHECKPOINTS — {YEARS[0]}-{YEARS[-1]}\n{'='*70}")
    combine_checkpoints_streaming(YEARS, OUTPUT_DIR)


if __name__ == "__main__":
    main()
