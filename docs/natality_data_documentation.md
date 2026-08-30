# Natality Public-Use Data — Source Documentation & Validation Reference

**Prepared for:** Project A / Workstream W3 (Preterm Birth Risk Prediction), Revised Endeavor & Fast-Track Research Plan
**Source page:** NBER, "Vital Statistics Natality Birth Data" — https://www.nber.org/research/data/vital-statistics-natality-birth-data (last updated September 2025)
**Underlying data owner:** National Center for Health Statistics (NCHS), National Vital Statistics System (NVSS)
**DOI:** https://doi.org/10.60592/107a-5j74

This document exists to be read *before* any natality file is loaded into the modeling pipeline, and to be kept alongside the project's code as the authoritative note on what this data is, what it is not, and what has to be checked before it's trusted.

---

## 1. What the data is

Natality microdata is individual-level information abstracted from birth certificates filed in vital statistics offices of each state and the District of Columbia, compiled annually by NCHS. Each record is one live birth. Demographic fields include date of birth, parental age and educational attainment, marital status, live-birth order, race, and sex. Health fields include birthweight, gestation (the field the preterm-birth outcome is derived from), prenatal care utilization, attendant at birth, and Apgar score.

## 2. Which file to use — U.S. file vs. territory (PS) file

Since 1994, each year is published as two separate files, distinguished by filename suffix:

| Suffix | Coverage | Use for this project? |
|---|---|---|
| `natalityYYYY**us**` | 50 states + District of Columbia | **Yes — this is the file the endeavor statement describes.** |
| `natalityYYYY**ps**` | U.S. territories: Guam, Puerto Rico, U.S. Virgin Islands (from 1994); American Samoa and the Northern Marianas added 1998 | No — out of scope. A "nationally representative U.S." model built on this file would misrepresent both the data source and the endeavor statement's claim. |

**Action item:** confirm the file in hand is the `us` file before any further work. `natality2024ps.sas7bdat` is the wrong file for this project and should be replaced with `natality2024us.sas7bdat`.

## 3. Historical sampling methodology (relevant only if pulling years before 1985)

Coverage was not always complete: prior to 1972, data reflect a 50% sample of birth certificates across all states. From 1972, some states reported 100% of records while others still reported a 50% sample; the number of states reporting 100% grew from 6 in 1972 to all states and DC by 1985. Every year from 1985 forward is a complete census of births, not a sample. Since the plan's near-term data pulls target recent years (2015+), this has no practical effect now — it only matters if the external-temporal-validation work (Section 1.4, differentiator #1 in the fast-track plan) is ever extended back before 1985, at which point a sampling-weight adjustment would be needed and should be flagged explicitly in the methodology rather than treated as directly comparable to modern 100%-census years.

## 4. Geographic data: present historically, absent from 2005 forward

This is the single most consequential limitation for this project and is worth restating precisely, now sourced two ways (NBER's own page and CDC/NCHS's restricted-data page, both consistent):

> "The 2005 public use data from 2005-on does not include geographic detail due to restrictions imposed by the states. This means that the 2005-on data does not include any geographic variables such as state, county, msa, etc." — NBER

Earlier files (pre-2005) did include state, county, city (for cities of 250,000+ through 1980, 100,000+ from 1980), SMSA (from 1980), and metropolitan/non-metropolitan county classification, plus an NCHS-to-FIPS geographic crosswalk for files from 1981 forward. None of that applies to any file this project will actually use, since the endeavor is built on recent data. **No geographic or rurality variable exists in the 2024 `us` file.** This confirms and does not change the correction already made to the endeavor statement and Section 1.4 of the fast-track plan: geographic disparity analysis requires a separate NCHS restricted-use data agreement (via NAPHSIS), pursued as a distinct future-phase activity, not a near-term deliverable.

## 5. Standard birth certificate revisions and cross-year missingness

The underlying birth certificate itself has been revised multiple times (documented revisions from 1949 through the current 2003 standard certificate). States adopted the 2003 revision on a rolling basis rather than all at once, which means certain risk-factor and prenatal-care fields differ in availability, definition, or completeness depending on which certificate revision a given state was using in a given year. This directly supports — and should be cited as the specific mechanism behind — the "missing-data methodology" differentiator already planned in Section 1.4 (#5): missingness in this data is not random noise, it is structured by state-level policy timing, and documenting it that way is a real methodological point rather than a disclaimer.

## 6. Documentation, program, and codebook files by year

| Resource | Coverage | Use |
|---|---|---|
| PDF user guide | Per year | Primary narrative documentation of file layout and variable definitions |
| PDF-converted-to-text | Per year | Same content, searchable/greppable — useful for scripted lookups |
| Errata file | Cumulative | Check for known data-quality corrections before trusting an anomalous value |
| `.dct` (2018–2024) / `.do` (through 2017) | Per year | Stata column/format definitions |
| `.sas` program files | Through 2024 | SAS INPUT/FORMAT statements — use these to recover variable formats and value labels even when reading the `.sas7bdat` directly in pandas |
| `.sps` files | Through 2024 | SPSS format definitions |
| **Codebooks** | **2018–2022 only** | A dedicated codebook does not exist for 2023 or 2024 at time of writing. For the 2024 file specifically, rely on the PDF user guide plus the `.sas`/`.sps` program files for variable definitions and value labels rather than expecting a standalone codebook document. |

**Action item:** since the 2024 file has no dedicated codebook, download the 2024 PDF user guide and the corresponding `.sas` program file alongside the data file itself — the `.sas` file's FORMAT statements are the fastest way to confirm what each numeric code means without a codebook to cross-reference.

## 7. Population denominator files (contextual use, not part of the model)

Separate files (e.g., `natpop91.dat.Z`) provide population counts of U.S. women aged 15–44 — the population conventionally considered "at risk" of giving birth — broken out by state × age × race × Hispanic origin, available from 1991 forward. These are useful only for computing population-level rates for the national-importance narrative (e.g., contextual preterm birth rate trends) or for sanity-checking the model's aggregate outputs against known population figures — consistent with how CDC WONDER is already used in Section 1.2 of the fast-track plan. They are not needed for, and should not be merged into, the individual-level birth record used to train the classifier. Note also: these population files are not available for the U.S. territories, which is one more reason the `ps` file is out of scope for this project.

## 8. Citation requirement

NCHS requires that any published work using this data include a citation to NCHS, per its stated data-use rules (use of the data constitutes agreement to those rules). The required form for material derived from this data is:

> Source: National Center for Health Statistics (span of years used)

This should be applied to the eventual preprint, the open-source repository's README, and any presentation of results — not just as a courtesy, but because the endeavor statement itself commits to public dissemination under proper attribution, and an uncredited or improperly cited use of federal vital statistics data would be a real, avoidable defect in an otherwise clean methodology.

## 9. Pre-modeling validation checklist

Before writing a single line of feature-engineering code against the downloaded file, confirm each of the following and record the answer:

1. Filename confirmed as `natality2024us.sas7bdat` (not `ps`).
2. Row count is on the order of the actual annual U.S. birth count (roughly 3.6 million, per the endeavor statement) — a materially different row count means the wrong file, a truncated download, or a territory file was loaded by mistake.
3. No state/county/MSA/geographic column is present — its presence would indicate an unexpectedly older-vintage file or a documentation mismatch worth investigating, not a bonus.
4. The gestational-age field used to derive the preterm-birth outcome is present, and its coding (weeks vs. a categorical scheme) is confirmed against the 2024 PDF user guide or `.sas` program file — the field name and coding have changed across birth-certificate revisions historically (Section 5 above).
5. Missingness by state-derivable proxy (e.g., reporting-state groupings if any exist in the file's own metadata, or simply by comparing field completeness against known 2003-certificate adoption timing) is checked for the specific risk-factor fields the model will use, before assuming missing-at-random.
6. The `.sas` program file's FORMAT statements are on hand and cross-referenced for every coded categorical variable used in the model, given the absence of a 2024 codebook.

---

## 10. Update — live file review, August 2026

The project's `data` folder now contains three files, reviewed directly:

| File | Status |
|---|---|
| `natality2024us.sas7bdat` (2.1 GB) | **Correct file.** `us` suffix confirmed — this is the 50-states-plus-DC file, not the territories file. |
| `UserGuide2023.pdf` (1.8 MB) | **Use as the primary variable reference for now.** Full file layout (record length 1330, fixed format) plus detailed technical notes on every variable category and a state-specific data-quality section for 2023. Reports 2023 U.S. record counts as 3,605,081 by occurrence / 3,596,017 by residence — a real, citable anchor for the "~3.6 million annual U.S. births" figure in the endeavor statement. A 2024-specific user guide does not yet exist publicly (checked directly; not found) — variable definitions should be spot-checked against the actual 2024 file rather than assumed identical, but this is the best documentation available in the interim. |
| `program-natlterr2018.txt` (31 KB) | **Do not use as-is.** Its own header identifies it as reading "the 2017 NCHS Natality Detail U.S. Territories Data File," its SAS dataset name is `natlterr2018`, and it points at `Nat2018ps.zip` — this is the 2018 **territories** program, wrong on both year and file-family axes relative to `natality2024us.sas7bdat`. Many variable names are stable across years and file families and can be used as a rough naming guide, but its FORMAT/VALUE code definitions should not be trusted to decode the 2024 U.S. file. Replace with `natality2024us`'s own `.sas` or `.dct` program file before relying on any value-code mapping. |

**A candidate replacement (README) was reviewed and partially rejected.** A `README_DCT.txt` describing NBER's general natality-processing pipeline was submitted as a possible substitute for the missing 2024 `us` dictionary/program file. No actual `.dct` file accompanied it initially — only the README. It contradicts itself on the geographic-data cutoff year (stating both "2020+: Geographic variables removed" and "2005+: No geographical variables" in the same document), which is reason enough not to cite it as an authoritative source. **Correction to an earlier note in this log:** this document previously flagged the README's claim of `mhispx`/`fhispx` as a mismatch against the `natlterr2018` program file's `mhisp_r`/`fhisp_r`. That critique was wrong — the actual 2024 dictionary (below) shows `mhispx` and `mhisp_r` are two separate, coexisting fields, not a rename, and the 2018 file likely has `mhispx` further in than the portion originally reviewed. The README's self-contradiction on the 2005/2020 point still stands independently; the `mhispx` point does not.

**The actual `natality2024` dictionary file was then obtained and reviewed directly** (`programsdctnatality2024.txt`, Stata `.dct`-style format, "reads the 2024 natality," NBER, dated 2025-08-29). This is a real, usable source — column positions, types, and value-code descriptions for hundreds of variables — and confirms field names needed for the model, including:

- **`gestrec3`** — "Combined Gestation Recode 3: 1 = Under 37 weeks" — the standard clinical preterm-birth threshold, and the leading candidate for the model's binary target variable.
- `combgest` and `oegest_comb` — continuous gestational age in weeks, by two different estimation methods (clinical/LMP-based vs. obstetric estimate) — worth comparing rather than assuming they agree.
- `dbwt` — birthweight in grams; `apgar5` / `apgar10` — Apgar scores.
- `precare` / `previs` — prenatal care start month and visit count.
- `cig_0` through `cig_3` — cigarettes smoked by trimester; `bmi`, `wtgain` — maternal BMI and weight gain.
- `rf_pdiab`, `rf_gdiab`, `rf_phype`, `rf_ghype`, `rf_ppterm` (previous preterm birth), and other `rf_*` risk-factor flags.
- `meduc`, `mager`, `mrace31`, `mhisp_r` — core maternal demographic fields.

**Open question — provenance of this dictionary is not fully confirmed.** Unlike the `natlterr2018` file, this one's header does not explicitly say "territories," so it cannot be dismissed the same way. However, it also lists several fields near its end (`octerr`, `ocntyfips`, `ocntypop`, `mbcntry`, `mrcntry`, `mrterr`, `rcnty`, `rcnty_pop`, `rcity_pop`, `rectype`) that are explicitly geographic and, in several cases, explicitly labeled "Puerto Rico" (e.g., `ocntyfips`: "Occurrence FIPS County Puerto Rico") — which should not exist in the U.S. public-use file per the independently verified 2005+ restriction (Section 4). This may mean the dictionary is a merged reference covering both `us` and `ps` field sets, with the territory-only fields simply inapplicable to the U.S. file. **Resolution: cross-check against the real column list from `inspect_natality_2024.py`'s output.** Every clinical/demographic field name listed above that appears in the real file's columns is confirmed usable. None of the geographic fields listed in this paragraph are expected to appear in `natality2024us.sas7bdat`; if one does, treat it as a signal to stop and re-verify the file's provenance before proceeding, not as a usable variable.

`UserGuide2023.pdf` remains the primary narrative reference for interpretation and context; this dictionary file is now the primary source for exact column positions and variable names, pending the cross-check above.

**Action item:** run `inspect_natality_2024.py` (companion script in this project folder) against the real data file to get the actual 2024 column list, row count, and per-column missingness without loading the full 2.1 GB file into memory. Cross-reference the resulting column list against `UserGuide2023.pdf`'s file layout section (pages 8–40) to confirm variable names match expectations, and re-run item 2 and item 3 of the Section 9 checklist (row count on the order of 3.6 million; no state/county/geographic column present) against the actual output before writing any feature-engineering code.

---

## 11. Live validation results — `natality2024us.sas7bdat`, confirmed

`inspect_natality_2024.py` was run against the actual file. Results, and what they settle:

- **File identity:** 3,638,436 rows, 237 columns. Consistent with a full year of U.S. births (2023's comparable figure was 3,605,081) — this is the real `us` file. Checklist item 2 (Section 9) passed.
- **Geographic-field question (Section 10, prior entry) resolved.** `octerr`, `ocntyfips`, `ocntypop`, `mbcntry`, `mrcntry`, `mrterr`, `rcnty`, `rcnty_pop`, `rcity_pop`, and `rectype` all exist as column names but are **100% missing across all 3,638,436 rows — zero populated values in any of them.** This independently confirms, from the live file itself, the 2005+ geographic restriction already established from CDC/NCHS documentation (Section 4): NBER's schema appears shared across the `us`/`ps` releases, with these columns present but structurally empty in the U.S. file. Checklist item 3 passed, with direct evidence rather than only secondary documentation.
- **Target variable confirmed usable.** `gestrec3` (Combined Gestation Recode 3, "1 = Under 37 weeks" per the dictionary) is 0% missing. Sample rows show `gestrec3 = 2.0` paired with 37–39 week gestation and healthy Apgar scores, consistent with `2` = term and `1` = preterm by elimination — confirm the exact code-to-label mapping against an authoritative source before finalizing, but this is a strong, working signal for the model's binary target.
- **Core predictor fields confirmed present and populated:** `combgest`, `oegest_comb`, `dbwt`, `apgar5`, `apgar10`, `precare`, `previs`, `cig_0`–`cig_3`, `bmi`, `wtgain`, and all `rf_*` risk-factor flags are 0% missing at the column level.
- **Important modeling caveat — 0% missing does not mean genuinely complete.** These are NCHS's *edited* fields: imputation is applied before release, which is why the primary value columns show near-zero missingness. Real, honest missingness lives in the parallel `f_*` reporting-flag columns (e.g., `f_mpcb`, `f_wtgain`, `f_pay`), which record whether a value was actually reported versus imputed. The cleaning pipeline should treat these flag columns as first-class inputs to the missing-data methodology (Section 5 / fast-track plan differentiator #5), not treat the 0%-missing value columns as evidence the data has no missingness problem.
- **One genuine (non-imputed) missingness finding:** `dmar` (marital status) is 11.08% missing (402,966 of 3,638,436 rows) — real `NaN`, not an edited/imputed fill. Worth checking whether this clusters by state-derivable proxy or by certificate-revision timing (Section 5) as the cleaning work proceeds.

Checklist items 4 (gestational-age field present and coding confirmed) and 5 (missingness checked before assuming missing-at-random) are now underway rather than complete — the flag-column cross-check above is the next concrete step before feature engineering begins.

---

## 12. Cleaning pipeline — two-stage design

Two scripts implement the cleaning step, deliberately split so nothing gets hardcoded before it's confirmed:

- **`profile_natality_2024.py`** — a diagnostic-only pass. Reports the top values for every field where an "unknown/not stated" sentinel code is expected but not yet confirmed (`precare`, `previs`, `cig_0`–`cig_3`, `bmi`, `wtgain`, `meduc`, etc.), cross-tabulates a sample of `f_*` reporting flags against their value columns to confirm the "0 = Non-Reporting" convention the dictionary labels imply, and cross-tabulates `gestrec3` against `combgest < 37` to settle the exact preterm code mapping empirically. **Run this first; its output should be reviewed before trusting the sentinel-code table in the cleaning script.**
- **`clean_natality_2024.py`** — the actual cleaning pipeline: decodes SAS byte-strings, applies sentinel-to-NaN replacement (marked in-code as assumptions pending the profiling script's confirmation), derives the `preterm` target *empirically* (by checking which `gestrec3` code best agrees with `combgest < 37` in the data itself, and raising an error rather than proceeding silently if agreement falls below 99%), builds `<field>_reported` boolean flags from the `f_*` reporting columns, retains `dob_yy`/`dob_mm` and adds a `data_year` column so the output slots directly into the multi-year chronological design (Section 1.4, differentiator #1) once earlier years' files are added, and saves to Parquet (CSV fallback if `pyarrow` isn't installed).

**Action item:** run the profiling script first and share its output before treating the cleaning script's sentinel-code table as final — several of those values are documented, honest assumptions based on general NCHS convention, not yet confirmed against the actual 2024 file.

## 13. Profiling results and resulting fixes

`profile_natality_2024.py` was run against the full 3,638,436-row file. Findings:

- **Sentinel codes confirmed:** `precare`, `previs`, `cig_0`–`cig_3`, and `wtgain` all show a clean spike at `99`, matching the assumed table; `0` is a genuine value in each (e.g., "no prenatal care"), not missing.
- **Bug found and fixed:** `bmi`'s sentinel is stored as `99.9000015258789` (a float-precision artifact of SAS storage), not exactly `99.9`. The cleaning script's original exact-match (`isin`) logic would have silently failed to null it out. `apply_sentinels` now uses a tolerance-based comparison (`np.isclose`, atol=1e-3) for all numeric fields.
- **Reporting-flag convention confirmed:** across every flag pair checked, `flag=1` ("reported") dominates and `flag=0` ("non-reporting") is a small minority that still carries an imputed value — consistent with the `(flag != 0)` = reported logic already in `build_reported_flags`.
- **New finding — `rf_*` fields aren't purely binary.** `rf_pdiab` showed a third code, `'U'` (Unknown), on ~7,500 rows, beyond the expected `Y`/`N`. `encode_yn_fields` now maps `Y→1`, `N→0`, and anything else (including `U`) to missing, applied across the full `rf_*`/`wic` family since the same convention likely recurs elsewhere even where not directly profiled.
- **`gestrec3` target mapping confirmed at ~100% agreement:** `gestrec3=1` aligns with `combgest<37` in 439,401 of 439,401+ rows (no meaningful disagreement) — the code mapping is settled.
- **Open methodological question surfaced, not yet resolved:** the resulting preterm rate under `gestrec3`/`combgest` (LMP-based) is **12.09%**, notably above the commonly cited U.S. rate of ~10.4%. This is very likely because official NCHS reporting uses the *obstetric estimate* of gestation (`oegest_comb`/`oegest_r3`) rather than the LMP-based combined estimate as its standard — worth confirming directly against `UserGuide2023.pdf` rather than taking as settled. `clean_natality_2024.py` now derives **both** `preterm` (gestrec3-based) and `preterm_oe` (oegest_r3-based) targets empirically, and reports their disagreement rate, so the choice of primary target for the model is a documented decision rather than a silent default.
- **New sentinel codes identified for `pwgt_r`/`dwgt_r`** (999, per the profiling output) — added to the sentinel table for completeness even though these aren't currently read as predictors, in case they're added later.

**Action item:** review the `preterm` vs. `preterm_oe` comparison once `clean_natality_2024.py` runs, decide which definition is primary (or whether both should be reported), and document that decision explicitly in the eventual methodology write-up.

## 14. Cleaning run completed — target definition resolved

`clean_natality_2024.py` was run successfully against the full file. Results:

- **Structural check passed:** 55 columns read → 77 after derivation (55 + 19 `_reported` flag columns + `preterm` + `preterm_oe` + `data_year` = 77 exactly), confirming no silent column loss.
- **Target definition resolved:** `preterm_oe` (obstetric-estimate based, `oegest_r3`/`oegest_comb`) = **10.39%**, closely matching the commonly cited U.S. national preterm rate of ~10.4% (verify the exact figure against CDC's official "Births: Final Data" report for the relevant year before citing in any manuscript). `preterm` (LMP-based, `gestrec3`/`combgest`) = 12.08%, and the two definitions disagree on **5.25%** of records. **Recommendation: use `preterm_oe` as the primary modeling target**, retain `preterm` as a documented secondary/sensitivity measure. This comparison is itself a citable methodological contribution — a quantified disagreement between two established gestational-age conventions, with the obstetric estimate tracking the population benchmark more closely — stronger than the single-measure approach originally planned in Section 1.4.
- **Final missingness (post-cleaning) confirmed:** `dmar` 11.08% (consistent with the earlier live-file check), `wtgain` 3.00%, `bmi` 2.44%, `precare` 1.93%, `meduc` 1.91%, `previs` 1.86%, `wic` 1.19%, `cig_3` 0.98%, `m_ht_in` 0.65%, `cig_0`/`cig_1`/`cig_2` ~0.49–0.50%, `rf_inftr`/`rf_cesar`/`rf_ppterm` 0.21% each. These will need explicit handling (imputation strategy or missing-category encoding) in the modeling stage — the `_reported` flag columns are available as additional features for this purpose.
- **Output saved** as `natality2024us_cleaned.csv` (Parquet unavailable — `pyarrow` not installed on this machine; CSV works fine at this reduced column count, though installing `pyarrow` would speed up future runs).

Cleaning and validation for the 2024 file is complete.

## 15. Data access blocker — 2021–2023, and the resulting train/test design clarification

Attempts to download the 2021–2023 `us` files from NBER are currently being blocked by an anti-bot page ("Prevent Bots from data downloads"), reproduced independently by a second person on a different network — consistent with automated fetch attempts to `data.nber.org` earlier in this project also being blocked (403s on the codebook and program-directory pages), suggesting a broadly tightened bot-protection measure on that subdomain rather than a block specific to this user. Two parallel mitigation paths: (1) the original CDC/NCHS source (`https://www.cdc.gov/nchs/data_access/vitalstatsonline.htm`) as an alternate host, which provides only the raw fixed-width files and requires that year's format/program file directly from CDC; (2) direct outreach to NBER (`data@nber.org`) per their own stated process for legitimate individual research use.

**Train/test design confirmed:** per Section 1.4, differentiator #1, the correct design is to train on earlier years (2021–2023, once accessible) and hold out 2024 entirely as the external test year — 2024 being the most recent data is precisely why it belongs on the test side, mirroring the no-show project's validation against a genuinely later, unseen period rather than a random split. Any modeling work done on the 2024 file alone in the interim (e.g., an internal train/test split by birth month) is a pipeline shakedown only — useful for catching code and feature-engineering bugs early — and must not be conflated with, or reported as, the external temporal validation the endeavor statement actually commits to. The `data_year` column already added by `clean_natality_2024.py` exists specifically so the same pipeline can be re-run directly on the correct multi-year structure once 2021–2023 access is resolved.

## 16. Multi-year cleaning completed (2021–2024)

`clean_natality_multiyear.py` was run against all four years. All four passed their per-year validation gates (gestrec3/combgest and oegest_r3/oegest_comb agreement both at 100% for every year — no evidence NCHS changed this coding across 2021–2024), and each year's checkpoint CSV saved successfully:

| Year | Rows | preterm (LMP-based) | preterm_oe (obstetric-estimate) |
|---|---|---|---|
| 2021 | 3,669,928 | 12.27% | 10.48% |
| 2022 | 3,676,029 | 12.19% | 10.37% |
| 2023 | 3,605,081 | 12.22% | 10.39% |
| 2024 | 3,638,436 | 12.08% | 10.39% |

This is a strong, independent confirmation of the target-definition decision in Section 14: `preterm_oe` clusters tightly around ~10.4% every single year, while `preterm` is consistently ~1.8 points higher every year — not a 2024-specific artifact. Sentinel spot-checks (precare, previs, cig_0, bmi, wtgain) show the same code patterns across all four years as well.

**Bug found and fixed:** the script's final step — combining all four years' cleaned DataFrames via an in-memory `pd.concat()` — hit a `MemoryError` on this machine (four ~3.6M-row frames held simultaneously exceeded available RAM). This was a memory-handling bug, not a data problem; all four years' cleaning and validation had already completed and saved successfully before this step. Fixed by replacing the in-memory concat with `combine_checkpoints_streaming()`, which appends the already-saved per-year checkpoint CSVs directly to the combined output file in chunks, and computes the per-year summary the same way — never holding more than one chunk in memory at a time. A standalone `combine_cleaned_years.py` was also provided to combine the checkpoints that had already been produced, without needing to re-read the four 2.1GB raw files again.

---

*This document should be updated if a later NBER page revision changes any of the above, and should be treated as a living reference for the project's data-cleaning script, not a one-time note.*
