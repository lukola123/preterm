"""
Feature-engineering pipeline for the cleaned natality checkpoint files
(natalityYYYYus_cleaned.csv, produced by clean_natality_multiyear.py).

WHY THIS SCRIPT EXISTS INSTEAD OF FEATURE-ENGINEERING OFF ONE COMBINED FILE
----------------------------------------------------------------------------
combine_cleaned_years.py / combine_checkpoints_streaming() already solved the
*writing* side of the memory problem: it streams each year's CSV in 200k-row
chunks straight to disk, so producing natality_2021_2024_us_cleaned.csv is
possible regardless of RAM (it's I/O-bound, not memory-bound). So combining
is NOT impossible.

The problem is what happens right after: the very next step would be
pd.read_csv() on that ~3.7-3.8GB combined file (four years x ~945MB each) to
do feature engineering / model building. That read pulls the full four-year
row count back into memory at once with pandas' default (wide, nullable)
dtypes — functionally the same in-memory footprint as the four-frame
pd.concat() that already produced a MemoryError on this machine (Section 16
of natality_data_documentation.md). Combining first would just move that
same crash one step downstream.

There's also a design reason to skip the combined file even if memory were
not a concern: Section 15/16 of the documentation fixes the train/test split
as train-on-2021-2023, test-on-held-out-2024. Those two groups are never
actually needed together in memory for anything this project does. A single
merged 2021-2024 file is a convenience artifact, not a modeling requirement.

WHAT THIS SCRIPT DOES INSTEAD
------------------------------
1. Reads each year's cleaned CSV directly, with an explicit compact dtype
   map passed to pd.read_csv() (categoricals + Int8/Int16/float32 instead of
   pandas' default nullable Int64/float64) — so peak memory during the read
   itself is already small, not shrunk after the fact.
2. Engineers a small set of derived features per year.
3. Saves each year to its own compressed Parquet checkpoint
   (natalityYYYY_features.parquet) — smaller and faster to reload than CSV,
   and dtype-preserving (categoricals/Int8 round-trip exactly, unlike CSV).
4. Provides load_years() so the modeling step reads ONLY the years it
   actually needs together — e.g. the three train years — instead of ever
   materializing all four in one frame. The full 2021-2024 combined CSV is
   never created or required by this path.
5. Provides get_model_matrix(), which drops the columns that mechanically
   determine the target (gestrec3/combgest/oegest_comb/oegest_r3) before
   returning X/y — preterm and preterm_oe are DERIVED from those columns
   (clean_natality_multiyear.py's derive_preterm_from_pair()), so leaving
   them in the feature set would be direct target leakage, not a real
   predictor relationship.

Run process_all_years() once per machine (or whenever the cleaned CSVs
change); after that, model-building code should call load_years() /
get_model_matrix() against the small per-year Parquet files, not the raw
cleaned CSVs and never the big combined CSV.
"""

import os
from pathlib import Path
import pandas as pd
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CLEANED_DIR = PROJECT_ROOT / "output"  # natalityYYYYus_cleaned.csv, from clean_natality_multiyear.py
DATA_DIR = PROJECT_ROOT / "data"       # where this script's own features parquet output lives
YEARS = [2021, 2022, 2023, 2024]
TRAIN_YEARS = [2021, 2022, 2023]
TEST_YEAR = 2024
PRIMARY_TARGET = "preterm_oe"  # per Section 14 of natality_data_documentation.md

# ---------------------------------------------------------------------------
# Column groups — mirrors clean_natality_multiyear.py's FLAG_PAIRS/YN_FIELDS
# so the dtype map below stays in sync with what that script actually emits.
# ---------------------------------------------------------------------------

FLAG_PAIRS = [
    ("meduc", "f_meduc"), ("dmar", "f_mar_p"),
    ("precare", "f_mpcb"), ("previs", "f_tpcv"),
    ("cig_0", "f_cigs_0"), ("cig_1", "f_cigs_1"), ("cig_2", "f_cigs_2"), ("cig_3", "f_cigs_3"),
    ("bmi", "f_pwgt"), ("wtgain", "f_wtgain"),
    ("rf_pdiab", "f_rf_pdiab"), ("rf_gdiab", "f_rf_gdiab"),
    ("rf_phype", "f_rf_phyper"), ("rf_ghype", "f_rf_ghyper"),
    ("rf_ehype", "f_rf_eclamp"), ("rf_ppterm", "f_rf_ppb"),
    ("rf_cesar", "f_rf_cesar"), ("wic", "f_wic"), ("pay_rec", "f_pay_rec"),
]
RAW_FLAG_COLS = [flag for _, flag in FLAG_PAIRS]
REPORTED_COLS = [f"{value}_reported" for value, _ in FLAG_PAIRS]
YN_FIELDS = [
    "rf_pdiab", "rf_gdiab", "rf_phype", "rf_ghype", "rf_ehype", "rf_ppterm",
    "rf_cesar", "rf_inftr", "wic",
]

# Columns that mechanically DEFINE preterm/preterm_oe. Kept in the saved
# Parquet for audit purposes, but must never be fed to a model.
LEAKAGE_COLS = ["gestrec3", "combgest", "oegest_comb", "oegest_r3"]

CATEGORY_COLS = ["mrace31", "mhisp_r", "meduc", "dmar", "pay_rec", "sex", "dplural"] + [
    c for c in LEAKAGE_COLS if c in ("gestrec3", "oegest_r3")
]
FLOAT32_COLS = ["bmi", "combgest", "oegest_comb"]
INT16_COLS = ["dob_yy", "data_year"]
# Everything else confirmed elsewhere in the pipeline to fit comfortably in
# a signed byte (max real value well under 99 in every case, since NCHS's
# own sentinel-for-unknown convention in this file family is 99/99.9 — see
# clean_natality_multiyear.py's SENTINEL_CODES) — nullable Int8 keeps NaN.
INT8_COLS = (
    ["mager", "precare", "previs", "cig_0", "cig_1", "cig_2", "cig_3",
     "wtgain", "m_ht_in", "rf_cesarn", "priorlive", "priordead", "priorterm",
     "dob_mm", "preterm", "preterm_oe"]
    + YN_FIELDS + RAW_FLAG_COLS + REPORTED_COLS
)


def build_dtype_map():
    dtype_map = {}
    for c in CATEGORY_COLS:
        dtype_map[c] = "category"
    for c in FLOAT32_COLS:
        dtype_map[c] = "float32"
    for c in INT16_COLS:
        dtype_map[c] = "Int16"
    for c in INT8_COLS:
        dtype_map[c] = "Int8"
    return dtype_map


def read_cleaned_year(year, cleaned_dir=CLEANED_DIR):
    """
    Reads one year's cleaned checkpoint CSV with a compact dtype map applied
    at parse time (not after), so the memory spike a naive pd.read_csv()
    would cause never happens in the first place. Falls back column-by-column
    if any single column's real values don't fit the assumed width (prints
    which one, rather than failing silently or crashing the whole read).
    """
    path = os.path.join(cleaned_dir, f"natality{year}us_cleaned.csv")
    dtype_map = build_dtype_map()
    try:
        df = pd.read_csv(path, dtype=dtype_map)
    except (ValueError, OverflowError) as e:
        print(f"    [{year}] strict dtype read failed ({e}); "
              f"retrying with default dtypes, then downcasting per-column.")
        df = pd.read_csv(path)
        for c, dt in dtype_map.items():
            if c not in df.columns:
                continue
            try:
                df[c] = df[c].astype(dt)
            except (ValueError, OverflowError):
                print(f"        column '{c}' does not fit {dt} — left as-is, "
                      f"inspect its real max/min before trusting memory estimates.")
    mem_mb = df.memory_usage(deep=True).sum() / 1e6
    print(f"    [{year}] loaded {len(df):,} rows x {len(df.columns)} cols, "
          f"{mem_mb:,.0f} MB in memory (compact dtypes)")
    return df


def engineer_features(df, year):
    """
    Small, documented set of derived features. NOTE on precare: per the
    profiling results (Section 13 of the documentation), 0 is a genuine
    reported value ("no prenatal care"), not a missing-value sentinel — do
    not treat precare==0 as missing anywhere in this function or downstream.
    """
    df = df.copy()

    cig_cols = ["cig_0", "cig_1", "cig_2", "cig_3"]
    present_cig = [c for c in cig_cols if c in df.columns]
    if present_cig:
        df["cig_total"] = df[present_cig].sum(axis=1, min_count=1)
        df["any_smoking_reported"] = (df["cig_total"].fillna(0) > 0).astype("Int8")

    prior_cols = ["priorlive", "priordead", "priorterm"]
    present_prior = [c for c in prior_cols if c in df.columns]
    if present_prior:
        df["prior_pregnancies_total"] = df[present_prior].sum(axis=1, min_count=1)

    rf_cols = [c for c in YN_FIELDS if c in df.columns and c != "wic"]
    if rf_cols:
        df["any_risk_factor"] = (df[rf_cols].fillna(0).astype("int8").max(axis=1) > 0).astype("Int8")

    if "bmi" in df.columns:
        bins = [-np.inf, 18.5, 25.0, 30.0, np.inf]
        labels = ["underweight", "normal", "overweight", "obese"]
        df["bmi_category"] = pd.cut(df["bmi"], bins=bins, labels=labels)

    if "mager" in df.columns:
        bins = [-np.inf, 19, 24, 29, 34, 39, np.inf]
        labels = ["<20", "20-24", "25-29", "30-34", "35-39", "40+"]
        df["mager_group"] = pd.cut(df["mager"].astype("float32"), bins=bins, labels=labels)

    if "precare" in df.columns:
        # precare is the month prenatal care began; 0 = no care at all (real
        # value), 1-3 = first trimester, >3 = late-starting care.
        df["no_prenatal_care"] = (df["precare"] == 0).astype("Int8")
        df["late_prenatal_care"] = (df["precare"] > 3).astype("Int8")

    df["data_year"] = year
    return df


def process_one_year(year, cleaned_dir=CLEANED_DIR, features_dir=DATA_DIR):
    print(f"\n{'='*70}\nYEAR {year}\n{'='*70}")
    df = read_cleaned_year(year, cleaned_dir)
    df = engineer_features(df, year)

    out_path = os.path.join(features_dir, f"natality{year}_features.parquet")
    try:
        df.to_parquet(out_path, index=False)
        print(f"    [{year}] saved -> {out_path}")
    except ImportError:
        out_path = os.path.join(features_dir, f"natality{year}_features.csv.gz")
        df.to_csv(out_path, index=False, compression="gzip")
        print(f"    [{year}] pyarrow not installed — saved compressed CSV instead -> {out_path}")
        print(f"    Run: pip install pyarrow    (then re-run this script for smaller/faster/"
              f"dtype-preserving Parquet output)")
    return out_path


def process_all_years(years=YEARS, cleaned_dir=CLEANED_DIR, features_dir=DATA_DIR):
    paths = {}
    for year in years:
        paths[year] = process_one_year(year, cleaned_dir, features_dir)
    return paths


def load_years(years, data_dir=DATA_DIR):
    """
    Loads ONLY the requested years' feature checkpoints and concatenates
    them — e.g. load_years(TRAIN_YEARS) never touches 2024, so the held-out
    test year is never in memory alongside the training years.
    """
    frames = []
    for year in years:
        parquet_path = os.path.join(data_dir, f"natality{year}_features.parquet")
        csv_path = os.path.join(data_dir, f"natality{year}_features.csv.gz")
        if os.path.exists(parquet_path):
            frames.append(pd.read_parquet(parquet_path))
        elif os.path.exists(csv_path):
            frames.append(pd.read_csv(csv_path))
        else:
            raise FileNotFoundError(
                f"No feature checkpoint found for {year} — run process_all_years() first."
            )
    df = pd.concat(frames, ignore_index=True)
    mem_mb = df.memory_usage(deep=True).sum() / 1e6
    print(f"Loaded years {years}: {len(df):,} rows, {mem_mb:,.0f} MB in memory")
    return df


def get_model_matrix(df, target=PRIMARY_TARGET, drop_leakage=True):
    """
    Returns (X, y). Drops LEAKAGE_COLS (gestrec3/combgest/oegest_comb/
    oegest_r3) by default, since those columns mechanically determine both
    preterm and preterm_oe (see derive_preterm_from_pair() in
    clean_natality_multiyear.py) — leaving them in X would make the model
    trivially "predict" the target from the field it was derived from.
    """
    other_target = "preterm_oe" if target == "preterm" else "preterm"
    drop_cols = [target, other_target]
    if drop_leakage:
        drop_cols += [c for c in LEAKAGE_COLS if c in df.columns]
    y = df[target]
    X = df.drop(columns=[c for c in drop_cols if c in df.columns])
    return X, y


def main():
    process_all_years(YEARS, CLEANED_DIR, DATA_DIR)

    print(f"\n{'='*70}\nBUILDING TRAIN SET (years {TRAIN_YEARS}) — 2024 NOT loaded\n{'='*70}")
    train_df = load_years(TRAIN_YEARS, DATA_DIR)
    X_train, y_train = get_model_matrix(train_df, target=PRIMARY_TARGET)
    print(f"X_train: {X_train.shape}, y_train positive rate: {y_train.mean():.4f}")

    print(f"\n{'='*70}\nBUILDING TEST SET (held-out year {TEST_YEAR})\n{'='*70}")
    test_df = load_years([TEST_YEAR], DATA_DIR)
    X_test, y_test = get_model_matrix(test_df, target=PRIMARY_TARGET)
    print(f"X_test: {X_test.shape}, y_test positive rate: {y_test.mean():.4f}")

    print("\nNo combined 2021-2024 CSV was created or required for this. "
          "A combined file can still be produced for archival or sharing purposes "
          "with combine_cleaned_years.py, which streams to disk and is safe to run "
          "independently — it is just not on the path to model building.")


if __name__ == "__main__":
    main()
