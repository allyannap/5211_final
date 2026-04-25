# 5211_final

## Hospital Bed Capacity Scraper

This repo includes `tableau_extract_hospital_beds.py`, a scraper for the NY Department of Health Tableau dashboard that exports:

- regional summary bed capacity table
- detailed hospital-by-county bed capacity table

Both tables are combined into one CSV output file.

Dashboard source:

- [https://public.tableau.com/app/profile/oia.doh/viz/GBQ_python_extract_17612198243840/HospitalBedCapacity](https://public.tableau.com/app/profile/oia.doh/viz/GBQ_python_extract_17612198243840/HospitalBedCapacity)

## Setup

Run these commands in this repo:

```bash
python3 -m pip install -r requirements.txt
python3 -m playwright install chromium
```

## Run For Monday 24-Hour Collection

```bash
python3 tableau_extract_hospital_beds.py --mode monitor_24h --output hospital_bed_capacity_monday.csv
```

This command runs for 24 hours from the time you start it (2-hour snapshots), then exits automatically.

## Check That The Automatic Job Is Loaded

```bash
launchctl list | awk '/com\.allyanna\.hospital_bed_capacity_monday/'
```

If the label appears in output, the launch agent is loaded.