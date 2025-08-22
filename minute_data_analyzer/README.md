# EURUSD 1m — Project Guide (FLAT)

**Package generated:** 20250815_145705Z (UTC)

## Runbook (Pipeline)
# Runbook (CLEAN) — EURUSD 1m, annual pipeline (UTC+0)

**Updated:** 2025-08-15 14:20:12 UTC  
**Change:** The layer/section “Major World Events” has been completely removed. Cascade is now: 📆→🎉→⚙️→📢→❗.

## 1. Inputs
- HistData: `EURUSD_1m_{YEAR}.csv` (+ optional `EURUSD_1m_{YEAR}.txt`)
- 2025: monthly CSVs (output is still quarterly + separate July file)
- Local Economic Calendar: `calendar_{YEAR}.csv` (UTC, precision=hour; all_day=true allowed)
- Data format: `datetime_utc, open, high, low, close, volume` (volume not used)

## 2. Validation
- Pure UTC+0; chronological sort; no duplicates
- Δt between rows; expected weekend gaps; no “fill-ins” of missing data
- OHLC sanity: `0<low≤high`, `open/close∈[low,high]`, no NaN/Inf
- US holidays: rows for official holidays must not be present
- Source boundaries (year/quarter/month): no overlaps or gaps
- Special rules: 2025 (July CSV output), leap years, year boundaries
- Result: **autofix: yes/no**

## 3. Gap detection
- Gap = `Δt > 60s`
- For each gap: `start_ts, end_ts, gap_len`

## 4. Classification (cascade)
**📆 Weekends → 🎉 US Holidays → ⚙️ CME/EBS Tech Breaks → 📢 News (calendar CSV) → ❗ Anomalies**  
- ⚙️ Tech windows: described in the platform’s local TZ; convert to UTC with DST; matching rule: overlap ≥50% or center-inside; recurrence ≥8 weeks
- 📢 News: precision=hour ⇒ ±15 min windows; all_day ⇒ full UTC day

## 5. Extra checks (flags only, no data modification)
- DST effect on weekend-gap (±≈60 min near transitions)
- 5pm New York rollover as technical profile
- “Fill/resampling” detector (extra minutes/week)
- Data-glitch: candles > K×median range (K=30)

## 6. Autofix (only on validation fail)
- Generate **quarterly CSVs**: `EURUSD_1m_{YEAR}_Q1.csv.gz` … `Q4.csv.gz` (UTC+0, weekends/holidays removed, gaps preserved)
- 2025: also separate **monthly CSV for July**
- gzip with fixed mtime=0 (deterministic SHA-256)

## 7. Reports and artifacts
- `reports/annual_report_{YEAR}.md` — 10 sections (no “world events”)
- `reports/gaps_summary_{YEAR}.md`
- `reports/EURUSD_{YEAR}_anomalies.svg` — only ❗ anomalies
- (2025) `quarterly_report_2025_Q*.md`, `monthly_summary_2025-07.md`

## 8. Manifest and reproducibility
- `manifests/artifacts_{YEAR}.sha256` — SHA-256 of **all inputs and outputs**, including `calendar_{YEAR}.csv`
- At the end of reports: manifest hash and note about idempotency (rerun without changed inputs ⇒ same SHA-256)


**Deterministic analysis timestamp:** instead of actual runtime, reports insert `analysis_utc_ts = max(datetime_utc) from input CSVs`. This makes report hashes reproducible with unchanged inputs.


---

## Validation Criteria
# Validation Criteria (CLEAN) — EURUSD 1m

**Updated:** 2025-08-15 14:20:12 UTC  
**Change:** Removed all checks/sections related to “major world events.”

## A. Format and timing
- CSV UTF-8, comma, correct header, no BOM
- Columns: `datetime_utc, open, high, low, close, volume` (volume not used)
- UTC+0; sorted; no duplicates; correct 1-min granularity
- Δt distribution: visible weekend gaps; no “fill-ins”

## B. OHLC sanity
- `0<low≤high`; `open/close∈[low,high]`; no NaN/Inf
- Extra flags (not fail): high==low with active market around; sequences open==high==low==close

## C. Gap classification (without “world events”)
- Gap threshold: `Δt > 60s`
- Cascade: 📆 Weekends → 🎉 US Holidays → ⚙️ CME/EBS (TZ→UTC, DST, patterns ≥8 weeks) → 📢 Economic calendar (precision=hour ±15m; all_day = UTC-day) → ❗ Anomalies

## D. Special rules
- DST effect (±≈60 min on weekend-gap) — not anomaly
- 5pm NY rollover — technical profile
- Leap years; 31-Dec/01-Jan boundaries; 29-Feb

## E. Autofix
- Quarterly `.csv.gz` only if fail; 2025 — plus July monthly
- Deterministic gzip (mtime=0)

## F. Reports
- Annual: 10 sections (no “world events”), SVG with ❗
- Quarterly/monthly — no “world events” mentions

## G. Manifest
- SHA-256 of all **inputs and outputs** per year, including `calendar_{YEAR}.csv`; validated via `sha256sum -c`


**Deterministic analysis timestamp:** instead of actual runtime, reports insert `analysis_utc_ts = max(datetime_utc) from input CSVs`. This makes report hashes reproducible with unchanged inputs.


---

## Notes
- Flat layout: all files in one directory.
- Determinism: use `helpers.py` for gzip/SVG and content-based `analysis_utc_ts`.

## Strict slicing over period `[start, end)`
To prevent “leakage” of minutes between periods, strict interval semantics **[start, end)** are used:
- Data filtered by quarter/month strictly inside the window.
- Gaps counted **only** between consecutive rows **inside** the window (first/last minute of the period not compared to outside rows).
- Event classification (weekend/holiday/tech windows/calendar) applies only if the reference/center time falls within the window; intervals are clipped to window edges.
- For 2025-07 special rules, use `month_bounds(2025, 7)` in parallel with `quarter_bounds(2025, 3)` (extra July CSV).

In `helpers.py`:
```python
from helpers import quarter_bounds, month_bounds

start, end = quarter_bounds(YEAR, Q)        # [start, end)
mstart, mend = month_bounds(2025, 7)        # [2025-07-01, 2025-08-01)
```

### Vector outputs (SVG) for bit-for-bit reproducibility
Charts/plots are saved as **SVG** using deterministic settings (fixed `svg.hashsalt`, `svg.fonttype='none'`, `path.simplify=False`, no tight bbox).  
For compressed vector files, use `.svgz` via deterministic gzip (`mtime=0`, empty filename).  
Helpers: `save_svg_deterministic`, `write_svgz_deterministic`.

## Patched rendering flow (strict)

1. Compute `df` and `gaps`.
2. Build context via `sections.py`:
   - `build_common_blocks(df, gaps, year)`
   - `build_gaps_context(df, gaps, year)`
   - `build_monthly_context(df, gaps, year, "YYYY-MM")`
   - `build_quarterly_context(df, gaps, year, Q)`
3. Render with `helpers.render_template_file_strict(...)`.
4. Pack heavy artifacts with `helpers.make_tar_gz_deterministic(...)` for reproducibility.

Templates now contain explicit placeholders like `{{durations_section_md}}`, `{{sessions_table_md}}`. Any unresolved `{{...}}` will raise.

## Scoring model (0–100)
- Configured via `project_config.yml` → section `scoring:` (weights/targets).
- Calculated in `sections.py: compute_score(...)` and automatically added to annual report:
  - **Score (0–100)** in *Final assessment*
  - Full **Scorecard** (table) in a dedicated section.
- All computations are deterministic, no external data required.
