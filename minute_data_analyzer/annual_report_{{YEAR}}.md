# EURUSD 1m — Annual Report {{YEAR}}

## Inputs used (hashes)
- DAT_ASCII CSV: {{INPUT_CSV_SHA256}}
- HistData TXT: {{INPUT_TXT_SHA256}}
- Calendar CSV: {{CALENDAR_CSV_SHA256}}
- Defaults SHA-256: {{DEFAULTS_SHA256}}
- RUN_ID: {{RUN_ID}}

**Input files (names + SHA-256):**
{{inputs_table_md}}

---
## 1) {{gaps_classification_header_md}}
{{gap_classification_md}}

## 2) Durations (micro/medium/large)
{{durations_section_md}}

## 3) Sessions (UTC)
{{sessions_table_md}}

## 4) Monthly statistics
{{monthly_table_md}}

## 5) Extreme candles
{{extreme_table_md}}

## 6) Cross-check with CME/EBS maintenance windows
{{maintenance_table_md}}

## 7) Visualizations
{{visuals_list_md}}

## Scorecard (0–100)
{{scorecard_md}}


## 9) Full list of ❗ anomalies
{{gaps_pointer_md}}

## 10) SVG with ❗ anomalies
{{svg_pointer_md}}

---
Transparency footer
— Manifest SHA-256: {{MANIFEST_SHA256}}
— Report generated with the help of ChatGPT ({{model_name}}).
