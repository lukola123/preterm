# Preterm Birth Risk Prediction — NCHS Natality Data (2021–2024)

This project builds and evaluates a machine learning model that estimates the
probability of preterm birth (delivery before 37 completed weeks of
gestation) from information available on the U.S. birth certificate. It uses
four consecutive years of National Center for Health Statistics (NCHS)
Natality public-use microdata, trains on 2021–2023, and evaluates on the
fully held-out 2024 birth year as an external chronological test set.

The end-to-end pipeline covers data acquisition and cleaning, feature
engineering, exploratory data analysis, model development and hyperparameter
tuning, a documented model-promotion gate, and a manuscript-style write-up of
the completed study. This document describes each stage, the order in which
the pieces run, and what each file in the project is for.

## Data source

Raw data are the NCHS National Vital Statistics System Natality public-use
files for birth years 2021 through 2024, distributed in fixed-format
`.sas7bdat` form and mirrored by the National Bureau of Economic Research
(NBER): https://www.nber.org/research/data/vital-statistics-natality-birth-data.
Each file represents one live birth registered in the fifty states and the
District of Columbia for that year. Per NCHS data-use terms, any use of this
data should be cited as:

> Source: National Center for Health Statistics, Natality public-use data
> files, 2021–2024.

The raw `.sas7bdat` files and the large intermediate CSV/Parquet checkpoints
produced while processing them are not included in this repository; they are
multi-gigabyte per year and are regenerated locally from the original NCHS
source files using the scripts described below. `natality_data_documentation.md`
records the data provenance investigation in detail, including field
definitions, known data-release restrictions (geographic identifiers are
suppressed from 2005 onward), and the validation checklist used to confirm
each downloaded file before it enters the pipeline.

## Pipeline stages and file map

The pipeline runs in the following order. Each stage's output is the input to
the next.

**1. Initial file inspection** — `inspect_natality_2024.py`, `profile_natality_2024.py`

Confirms a freshly downloaded `.sas7bdat` file matches its expected schema,
row count, and filename before any further processing, and profiles field
completeness. These scripts were run once per year against each raw file as
it was obtained.

**2. Per-year cleaning** — `clean_natality_2024.py`, `clean_natality_multiyear.py`

Reads a raw `.sas7bdat` file for a given year, applies dtype-compact
cleaning (categoricals, `Int8`/`Int16`/`float32` instead of pandas' wider
defaults), derives the `_reported` flags used later in the missing-not-at-random
checks, and writes a cleaned CSV checkpoint (`natalityYYYYus_cleaned.csv`).
`clean_natality_multiyear.py` generalizes the single-year script to run
across all four years without ever holding more than one year in memory at
once.

**3. Optional combined archival file** — `combine_cleaned_years.py`

Streams the four cleaned yearly CSVs to a single combined
`natality_2021_2024_us_cleaned.csv` in fixed-size chunks, for archival or
sharing purposes only. This file is never read back into memory as a whole
and is not on the path to model building — the modeling stage reads only the
specific years it needs (see below), since a four-year combined frame would
recreate the same memory pressure this design otherwise avoids.

**4. Feature engineering** — `feature_engineer_natality.py`

Reads each year's cleaned CSV directly with an explicit compact dtype map,
engineers a small set of derived features (a combined cigarette-use total, an
aggregate prior-pregnancy count, an any-reported-risk-factor flag, clinical
body-mass-index and maternal-age categories, prenatal-care-timing flags, and
a prior-preterm-birth × multiple-gestation interaction term), and writes one
compressed Parquet checkpoint per year (`natalityYYYY_features.parquet`).
Also defines the constants and helpers used throughout the rest of the
project: `TRAIN_YEARS = [2021, 2022, 2023]`, `TEST_YEAR = 2024`,
`PRIMARY_TARGET = "preterm_oe"`, `LEAKAGE_COLS` (the four gestational-age
fields used to construct either candidate outcome, always excluded from the
feature matrix), `load_years()`, and `get_model_matrix()`.

**5. Exploratory data analysis** — `01_eda_natality_preterm.ipynb`

Runs entirely against the 2021–2023 training years, with a final section
that compares marginal predictor distributions against the held-out 2024
year for descriptive drift-checking purposes only (never to guide a
modeling decision). Covers structural overview, a missingness audit against
previously documented rates, target-rate stability across years, a
missing-not-at-random check, univariate and bivariate distributions,
continuous-predictor correlations, and the train-vs-2024 drift comparison.
The notebook's closing summary connects each EDA finding to a specific,
named change carried into the model-build notebook (for example, the
discovery that six fields share an identical batch-missingness pattern
led directly to the correlation check added in Section 2 of the model
notebook).

**6. Model build notebook generator** — `build_model_notebook.py`

A Python script that programmatically constructs
`02_model_build_natality_preterm.ipynb` using `nbformat`, so that the
notebook's cell content is version-controlled as plain text and can be
regenerated deterministically. Running `python build_model_notebook.py`
rewrites the notebook from scratch (56 cells); the notebook itself is then
opened and executed normally in Jupyter.

**7. Model build and evaluation** — `02_model_build_natality_preterm.ipynb`

The core modeling notebook, run top to bottom against the full dataset
(training years: 10,951,038 rows; 2024 test year: 3,638,436 rows). In order,
it: splits the training years 80/20 into a fit set and a calibration set;
adds the prior-preterm × multiple-gestation interaction and runs a
correlation screen; imputes missing values with a custom, memory-efficient
`MedianModeImputer` that preserves native pandas categoricals for LightGBM;
addresses class imbalance via `scale_pos_weight` (with an opt-in `SMOTENC`
comparison path); tunes LightGBM hyperparameters with `RandomizedSearchCV`
on a stratified subsample, scored by AUC; runs an empirical learning-curve
check to confirm training on the full dataset is justified; refits on the
full training set; selects a decision threshold by maximizing minority-class
F1 on the calibration set, with a full sensitivity table reported alongside
it; evaluates once, and only once, on the 2024 test year; repeats that
evaluation restricted to singleton pregnancies to rule out multiple
gestation as the sole driver of aggregate performance; identifies and
quantifies a reverse-causation confound in the total prenatal-visit-count
field (`previs`), refits with that field excluded, and separately re-tunes
hyperparameters on the reduced feature set; compares against a logistic-regression
baseline; reports feature importance by gain, split count, and SHAP value;
checks decision-boundary sensitivity and a decile risk-stratification table;
runs a Population Stability Index drift check between the training years
and 2024, extended with an explicit missingness-rate drift check; and
finally applies a pre-registered model-promotion gate against
literature-grounded thresholds, logging every run and saving the promoted
model.

**8. Model artifacts**

- `champion_model.joblib` — the promoted model: LightGBM, re-tuned
  hyperparameters, `previs` excluded from the feature set.
- `reference_model_full_features.joblib` — the full-feature model, kept for
  comparison and clearly labeled as an upper-bound reference, not the
  deliverable (see the notebook's Summary section for why `previs` is
  excluded from the promoted model).
- `model_run_log.csv` — historical run log for full-feature model runs.
- `model_run_log_actionable.csv` — run log for the previs-excluded
  (actionable) model, the log actually evaluated against the promotion gate.

**9. Manuscript** — `build_manuscript.js`, `preterm_birth_manuscript.docx`

`build_manuscript.js` is a Node.js script (using the `docx` package) that
generates a manuscript-style write-up of the completed study —
introduction, data and methods, results, discussion, limitations,
conclusion, data availability statement, and references — from the verified
figures and citations produced by the notebooks above. Run with
`node build_manuscript.js` to (re)generate `preterm_birth_manuscript.docx`.
The structure follows a standard applied-science paper format so that it can
be adapted with only front-matter changes for a preprint server (e.g.
medRxiv) or a peer-reviewed journal in this topical area.

## Reproducing the pipeline

1. Obtain the four raw NCHS Natality `.sas7bdat` files (2021–2024) per the
   source and citation above, and place them in the data directory.
2. Run `inspect_natality_2024.py` / `profile_natality_2024.py` against each
   file to confirm schema and completeness before proceeding.
3. Run `clean_natality_multiyear.py` to produce a cleaned CSV checkpoint per
   year.
4. Run `feature_engineer_natality.py` to produce a features Parquet
   checkpoint per year. (`combine_cleaned_years.py` is optional and not
   required for any of the following steps.)
5. Open and run `01_eda_natality_preterm.ipynb` top to bottom.
6. Run `python build_model_notebook.py` to (re)generate
   `02_model_build_natality_preterm.ipynb`, then open and run it top to
   bottom. Runtime-control knobs (subsample size for hyperparameter search,
   number of search iterations, cross-validation folds, SHAP sample size)
   are set in the notebook's configuration cell and can be reduced for
   faster iteration on smaller hardware; the reported results in the
   manuscript reflect the full-scale settings.
7. Run `node build_manuscript.js` to generate the manuscript, then verify
   the rendered output before distribution.

## Environment and dependencies

Python 3.9+, with `pandas`, `numpy`, `scikit-learn`, `lightgbm`, `shap`,
`imbalanced-learn`, `matplotlib`, and `joblib`. Manuscript generation uses
Node.js with the `docx` npm package. No dependency beyond the Python
scientific stack and Node.js is required to reproduce any stage of this
pipeline.

## Key design decisions

A few decisions materially shape the results and are worth surfacing here
rather than only in the notebooks themselves:

- **Chronological, not random, validation.** The model is trained only on
  2021–2023 and evaluated once on the fully held-out 2024 year, which is a
  stronger test of real-world generalization than a random split of all
  four years together.
- **Leakage control.** All four fields that could be used to construct
  either candidate gestational-age outcome are excluded from the feature
  matrix in every model reported, regardless of which outcome definition is
  used.
- **The `previs` reverse-causation finding.** Total prenatal-visit count is
  a whole-pregnancy total recorded at birth, and is mechanically capped by
  how early a birth occurs. It was the single strongest predictor in the
  full-feature model, inflating apparent AUC by 0.061 without corresponding
  early-warning value. The promoted model excludes it and is re-tuned on the
  reduced feature set; the full-feature model is retained separately, and
  clearly labeled, as an upper-bound reference rather than the deliverable.
- **A pre-registered, literature-grounded promotion gate.** Promotion
  thresholds (AUC, minority-class F1, macro F1) are set against the closest
  comparable published benchmark for this kind of data before being applied,
  rather than chosen after seeing the result.
