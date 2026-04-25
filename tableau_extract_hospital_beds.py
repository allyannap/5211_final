from __future__ import annotations

import argparse
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable

import pandas as pd
from playwright.sync_api import sync_playwright


DEFAULT_VIZ_URL = (
    "https://public.tableau.com/views/"
    "GBQ_python_extract_17612198243840/HospitalBedCapacity?:showVizHome=no"
)
DEFAULT_OUTPUT_CSV = "hospital_bed_capacity.csv"
WEEKDAYS = {0, 1, 2, 3, 4}  # Monday..Friday
SUMMARY_SHEET_NAME = "Regional Bed Capacity"
DETAIL_SHEET_NAME = "Bed Capacity Details"


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    clean = df.copy()
    clean.columns = [
        " ".join(str(c).replace("\n", " ").replace("\t", " ").split())
        for c in clean.columns
    ]
    return clean


def _tableau_like_url(url: str) -> str:
    if ":showVizHome=no" in url:
        return url
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}:showVizHome=no"


def _download_crosstab_csv(page, *, sheet_name: str, target_path: Path) -> None:
    page.get_by_role("button", name="Download").click()
    page.wait_for_timeout(600)
    page.get_by_text("Crosstab", exact=True).click()
    page.wait_for_timeout(1800)

    page.get_by_text("CSV", exact=True).click()
    page.wait_for_timeout(300)
    page.get_by_text(sheet_name, exact=True).click()
    page.wait_for_timeout(300)

    with page.expect_download(timeout=45_000) as dl_info:
        page.locator("button:has-text('Download')").last.click()
    dl = dl_info.value
    target_path.parent.mkdir(parents=True, exist_ok=True)
    dl.save_as(str(target_path))


def _parse_summary_table(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, sep="\t", encoding="utf-16")
    df = _normalize_columns(df).rename(columns={"Unnamed: 0": "Region"})
    return df


def _parse_detail_table(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, sep="\t", encoding="utf-16")
    df = _normalize_columns(df).rename(
        columns={
            "Unnamed: 0": "Region",
            "Unnamed: 1": "County",
            "Unnamed: 2": "Hospital ID",
            "Unnamed: 3": "Hospital",
        }
    )
    return df


def combine_tables_for_export(
    summary_name: str,
    summary_df: pd.DataFrame,
    detail_name: str,
    detail_df: pd.DataFrame,
    scraped_at: datetime,
) -> pd.DataFrame:
    scrape_time = scraped_at.isoformat(timespec="seconds")

    summary_out = summary_df.copy()
    summary_out.insert(0, "table_type", "summary_by_region")
    summary_out.insert(1, "worksheet_name", summary_name)
    summary_out.insert(2, "scraped_at", scrape_time)

    detail_out = detail_df.copy()
    detail_out.insert(0, "table_type", "detail_by_hospital")
    detail_out.insert(1, "worksheet_name", detail_name)
    detail_out.insert(2, "scraped_at", scrape_time)

    return pd.concat([summary_out, detail_out], ignore_index=True, sort=False)


def append_or_write_csv(df: pd.DataFrame, output_csv: Path, append: bool) -> None:
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    header = not (append and output_csv.exists())
    mode = "a" if append else "w"
    df.to_csv(output_csv, index=False, mode=mode, header=header)


def run_single_capture(
    viz_url: str,
    *,
    output_csv: Path,
    timeout_ms: int,
    headless: bool,
    append: bool,
) -> pd.DataFrame:
    target_url = _tableau_like_url(viz_url)
    tmp_dir = output_csv.parent / ".tableau_downloads"
    summary_tmp = tmp_dir / "regional_bed_capacity.csv"
    detail_tmp = tmp_dir / "bed_capacity_details.csv"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()
        page.goto(target_url, wait_until="domcontentloaded", timeout=timeout_ms)
        page.wait_for_timeout(12_000)

        _download_crosstab_csv(page, sheet_name=SUMMARY_SHEET_NAME, target_path=summary_tmp)
        _download_crosstab_csv(page, sheet_name=DETAIL_SHEET_NAME, target_path=detail_tmp)

        context.close()
        browser.close()

    summary_df = _parse_summary_table(summary_tmp)
    detail_df = _parse_detail_table(detail_tmp)
    combined = combine_tables_for_export(
        SUMMARY_SHEET_NAME,
        summary_df,
        DETAIL_SHEET_NAME,
        detail_df,
        datetime.now(),
    )
    append_or_write_csv(combined, output_csv, append=append)
    return combined


def build_offsets(duration_hours: int, interval_minutes: int) -> Iterable[int]:
    total_minutes = duration_hours * 60
    return range(0, total_minutes, interval_minutes)


def ensure_weekday_run(allow_weekend: bool) -> None:
    if allow_weekend:
        return
    if datetime.now().weekday() not in WEEKDAYS:
        raise RuntimeError(
            "Today is a weekend. This dashboard updates on weekdays only. "
            "Run this on Monday-Friday, or pass --allow-weekend."
        )


def run_monitoring_window(
    viz_url: str,
    *,
    output_csv: Path,
    timeout_ms: int,
    headless: bool,
    interval_minutes: int,
    duration_hours: int,
    allow_weekend: bool,
) -> int:
    ensure_weekday_run(allow_weekend=allow_weekend)
    start = datetime.now()
    runs = 0

    for offset in build_offsets(duration_hours, interval_minutes):
        target_time = start + timedelta(minutes=offset)
        sleep_seconds = (target_time - datetime.now()).total_seconds()
        if sleep_seconds > 0:
            time.sleep(sleep_seconds)

        run_single_capture(
            viz_url,
            output_csv=output_csv,
            timeout_ms=timeout_ms,
            headless=headless,
            append=(runs > 0),
        )
        runs += 1
        print(f"[{datetime.now().isoformat(timespec='seconds')}] snapshot {runs} complete")

    return runs


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Extract NY hospital bed capacity tables from Tableau Public using "
            "automated crosstab CSV downloads."
        )
    )
    parser.add_argument("--url", default=DEFAULT_VIZ_URL, help="Tableau dashboard/view URL")
    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT_CSV,
        help="Output CSV path (default: hospital_bed_capacity.csv)",
    )
    parser.add_argument(
        "--mode",
        choices=["once", "monitor_24h"],
        default="once",
        help="Run once or monitor over a 24h weekday window.",
    )
    parser.add_argument(
        "--interval-minutes",
        type=int,
        default=120,
        help="Sampling interval for monitor_24h mode (default: 120).",
    )
    parser.add_argument(
        "--duration-hours",
        type=int,
        default=24,
        help="Monitoring duration for monitor_24h mode (default: 24).",
    )
    parser.add_argument(
        "--timeout-ms",
        type=int,
        default=90_000,
        help="Browser/network timeout for each snapshot.",
    )
    parser.add_argument(
        "--allow-weekend",
        action="store_true",
        help="Allow monitor mode to run on weekends (off by default).",
    )
    parser.add_argument(
        "--no-headless",
        action="store_true",
        help="Run browser in visible mode for debugging.",
    )
    args = parser.parse_args()

    output_csv = Path(args.output)
    headless = not args.no_headless

    if args.mode == "once":
        df = run_single_capture(
            args.url,
            output_csv=output_csv,
            timeout_ms=args.timeout_ms,
            headless=headless,
            append=False,
        )
        print(f"Wrote {len(df):,} rows to {output_csv}")
        return

    runs = run_monitoring_window(
        args.url,
        output_csv=output_csv,
        timeout_ms=args.timeout_ms,
        headless=headless,
        interval_minutes=args.interval_minutes,
        duration_hours=args.duration_hours,
        allow_weekend=args.allow_weekend,
    )
    print(f"Monitoring complete. Appended {runs} snapshots to {output_csv}")


if __name__ == "__main__":
    main()

