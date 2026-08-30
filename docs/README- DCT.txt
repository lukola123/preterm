Natality Data Dictionary Files (DCT)
This folder contains Stata dictionary files (.dct) for processing natality data from the National Center for Health Statistics (NCHS). These files define the structure and variable definitions for birth data spanning from 1968 to 2024.

Overview
The natality data processing pipeline converts raw fixed-width text files from NCHS into multiple formats (Stata .dta, CSV, SAS) for research use. The dictionary files are essential components that define how the raw data should be parsed and structured.

Data Source
Source: Centers for Disease Control and Prevention (CDC) Vital Statistics
Data Type: Birth records from all 50 US states and territories
Time Period: 1968-2024 (continuous annual data)
Original Format: Fixed-width text files in ZIP archives
Contact: data@nber.org
File Structure
Dictionary Files
Format: Stata dictionary files (.dct)
Naming Convention: natalityYYYY.dct where YYYY is the year
Coverage: 1968-2024 (with some gaps in early years)
Data Types
Each year typically includes two data types:

US: United States (50 states + DC)
PS: Puerto Rico and other territories
Data Processing Pipeline
1. Raw Data Input
Raw data files are stored in /natality/inputs/raw/YYYY/
Files are compressed ZIP archives containing fixed-width text files
Naming: NatYYYYus.zip and NatYYYYps.zip
2. Dictionary Application
The dictionary files define:

Variable names and positions in the fixed-width file
Data types (string, float, byte, etc.)
Variable labels and value labels
Missing value codes
3. Processing Scripts
Main Script: natalityGenerateFiles.do (processes multiple years)
Individual Scripts: natlYYYY.do for specific years
Location: /natality/programs/dofiles/
4. Output Formats
Processed data is saved in multiple formats:

Stata: /natality/dta/YYYY/natalityYYYYus.dta
CSV: /natality/csv/YYYY/natalityYYYYus.csv
SAS: /natality/sas/YYYY/natalityYYYYus.sas7bdat
Codebooks: /natality/programs/codebooks/natalityYYYYus.html
Key Variables
The dictionary files define hundreds of variables including:

Demographics
dob_yy, dob_mm, dob_tt: Birth date and time
mager, fagecomb: Mother’s and father’s age
mrace31, frace31: Race/ethnicity (31 categories)
mhispx, fhispx: Hispanic origin
meduc, feduc: Education level
Health & Pregnancy
precare: Month prenatal care began
previs: Number of prenatal visits
cig_0, cig_1, cig_2, cig_3: Smoking during pregnancy
bmi: Body mass index
wtgain: Weight gain during pregnancy
Medical Conditions
rf_pdiab: Pre-pregnancy diabetes
rf_gdiab: Gestational diabetes
rf_phype: Pre-pregnancy hypertension
rf_ghype: Gestational hypertension
Birth Outcomes
dbwt: Birth weight
gestrec3: Gestational age
apgar5: 5-minute APGAR score
sex: Infant sex
Data Quality Features
Imputation Flags
mage_impflg: Mother’s age imputation flag
mraceimp: Mother’s race imputation flag
mar_imp: Marital status imputation flag
Reporting Flags
f_meduc: Education reporting flag
f_cigs_0: Smoking reporting flag
f_bfacil: Birth facility reporting flag
Important Notes
Variable Changes Over Time
2018+: New Hispanic origin variables (mhispx, fhispx)
2020+: Geographic variables removed
2003: Major revision in variable structure
2005+: No geographical variables (available in WONDER platform)
Data Limitations
Some variables have reporting flags indicating missing data
Imputation is used for certain demographic variables
Geographic detail varies by year
Puerto Rico data (PS) has additional geographical variables
Usage
Processing New Data
Place raw ZIP files in /natality/inputs/raw/YYYY/ and the user guide PDF in inputs/pdf/YYYY/.
Layout check: Compare the new yearâ€™s guide to the prior year. Update natalityYYYY.dct if positions or variables changed (see ../README_NVSS.md Â§ â€œNew release yearâ€).
Ensure programs/pdf_txt/natalityYYYY.txt exists if you use read_data.py to generate the dictionary from the guide.
Run processing: natalityGenerateFiles.do (edit forvalues year) or python read_data.py natality --years YYYY.
Check output in /natality/dta/, /natality/csv/, /natality/sas/ and record dictionary changes in CHANGELOG.md.
Reading Data
use "/natality/dta/2024/natality2024us.dta", clear
Maintenance
Updates
Dictionary files are updated annually when new data is released
Variable changes are documented in CHANGELOG.md
Processing scripts are maintained to handle format changes
Quality Control
Data validation checks are performed during processing
Missing data patterns are monitored
Variable consistency across years is verified
Related Documentation
Overview: README_natality.md
Changelog: CHANGELOG.md
Errata: errata_natality.txt
Codebooks: programs/codebooks/
Contact
For questions about the data or processing:

Email: data@nber.org
NBER Data Repository: https://www.nber.org/research/data/vital-statistics-natality-birth-data
CDC Source: https://www.cdc.gov/nchs/data_access/vitalstatsonline.htm#Births