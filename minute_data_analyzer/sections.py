from __future__ import annotations
from typing import Dict, List, Tuple
import re
import numpy as np
import pandas as pd
import fx_holidays
from pathlib import Path
from datetime import datetime, timedelta, timezone


def _load_calendar_df(year: int) -> pd.DataFrame | None:
    """
    Load calendar_YEAR.csv with columns: datetime_utc, event, impact/importance (case-insensitive).
    Returns DataFrame tz-aware UTC or None if file is missing/empty.
    """
    path_opts = [Path(f"calendar_{year}.csv"), Path("/mnt/data")/f"calendar_{year}.csv"]
    for p in path_opts:
        if p.exists():
            try:
                df = pd.read_csv(p)
                # normalize columns
                cols = {c.lower(): c for c in df.columns}
                if 'datetime_utc' not in cols and 'datetime' in cols:
                    df.rename(columns={cols['datetime']: 'datetime_utc'}, inplace=True)
                if 'datetime_utc' not in df.columns:
                    # try parse from first column
                    df.columns = [str(c) for c in df.columns]
                    key = list(df.columns)[0]
                    df.rename(columns={key: 'datetime_utc'}, inplace=True)
                # event/impact aliases
                if 'impact' not in df.columns and 'importance' in df.columns:
                    df.rename(columns={'importance': 'impact'}, inplace=True)
                if 'event' not in df.columns:
                    df['event'] = ''
                # parse ts in UTC
                ts = pd.to_datetime(df['datetime_utc'], utc=True, errors='coerce')
                df = df.loc[ts.notna()].copy()
                df['datetime_utc'] = ts.dt.tz_convert('UTC')
                # keep only High-impact
                def _is_high(x):
                    s = str(x).strip().lower()
                    return s in ('high','3','high impact','very-high','high (usd)','high (us)') or 'high' in s
                if 'impact' in df.columns:
                    df = df.loc[df['impact'].apply(_is_high)]
                # sort & unique per timestamp
                df = df.sort_values('datetime_utc').drop_duplicates(subset=['datetime_utc'])
                df = df[['datetime_utc','event'] + ([c for c in df.columns if c not in ('datetime_utc','event')])]
                return df.reset_index(drop=True)
            except Exception:
                return None
    return None

def _match_calendar_high(tagged: pd.DataFrame, cal_df: pd.DataFrame | None, window_sec: int = 60) -> tuple[pd.DataFrame, dict]:
    """
    For each gap, mark calendar_high=True if any High-impact event falls into [gap_start - w, gap_end + w].
    Returns (tagged_with_column, metrics_dict), where metrics include:
      - total_high_events
      - matched_high_events (unique event timestamps matched by any (anomaly) gap)
      - coverage (0..1) computed on anomalies only (reason isna())
    """
    if cal_df is None or len(cal_df) == 0 or tagged is None or len(tagged) == 0:
        t = 0 if cal_df is None else len(cal_df)
        out = tagged.copy()
        out['calendar_high'] = False
        return out, {'total_high_events': t, 'matched_high_events': 0, 'coverage': 0.0}

    w = pd.to_timedelta(window_sec, unit='s')
    out = tagged.copy()
    out['calendar_high'] = False

    # Work on anomalies subset for coverage, but mark column for all gaps
    anomalies_idx = out.index[out['reason'].isna()]
    matched_events = set()

    # Vectorized-ish sweep: for each event, mark overlaps
    # (len(cal_df) is small typically, loop is ok; ensures determinism with sorted timestamps)
    for ts in cal_df['datetime_utc'].sort_values():
        # mask gaps where ts in [start-w, end+w]
        m = (out['gap_start'] - w <= ts) & (ts <= out['gap_end'] + w)
        if m.any():
            out.loc[m, 'calendar_high'] = True
            # if any anomaly matches, count event into coverage
            if m.loc[anomalies_idx].any():
                matched_events.add(ts)

    total_high = int(len(cal_df))
    matched_high = int(len(matched_events))
    coverage = (matched_high / total_high) if total_high > 0 else 0.0

    return out, {'total_high_events': total_high, 'matched_high_events': matched_high, 'coverage': float(coverage)}



# ===================== TZ handling (source -> UTC) =====================

def _parse_source_tz_offset_minutes(cfg_text: str) -> int:
    m = re.search(r"(?m)^\s*source_tz\s*:\s*([^#\n]+)", cfg_text or "")
    if not m:
        return 0
    val = m.group(1).strip().strip('"\'').upper()
    if val in ("UTC","Z","+0","+00:00","UTC+0","UTC+00:00"):
        return 0
    if val in ("EST_FIXED","EST","UTC-5","-5","+(-5)"):
        return -300
    mm = re.match(r"^(?:UTC)?([+-]?)(\d{1,2})(?::?(\d{2}))?$", val)
    if mm:
        sign = -1 if mm.group(1) == '-' else 1
        hh = int(mm.group(2)); mn = int(mm.group(3) or 0)
        return sign * (hh*60 + mn)
    try:
        return int(val)
    except Exception:
        return 0

def _coerce_input_utc(df: pd.DataFrame, cfg_text: str) -> pd.DataFrame:
    if df is None or 'datetime_utc' not in df.columns or len(df) == 0:
        return df
    ser = df['datetime_utc']
    try:
        offset_min = _parse_source_tz_offset_minutes(cfg_text)
    except Exception:
        offset_min = 0
    m_force = re.search(r'(?m)^\s*force_shift_even_if_utc\s*:\s*([^#\n]+)', cfg_text or '')
    force_flag = False
    if m_force:
        val = m_force.group(1).strip().strip('\"\'')
        force_flag = val.lower() in ('1','true','yes','y','on')
    # Helper: shift naive wall-time from source_tz to UTC
    def _shift_naive_to_utc(series):
        if offset_min != 0:
            return (series + pd.to_timedelta(-offset_min, unit='m')).dt.tz_localize('UTC')
        else:
            return series.dt.tz_localize('UTC')
    # Case A: tz-naive -> interpret as source_tz and shift to UTC
    if getattr(ser.dt, 'tz', None) is None or force_flag:
        ser_naive = ser.dt.tz_localize(None) if getattr(ser.dt, 'tz', None) is not None else ser
        df = df.copy(); df['datetime_utc'] = _shift_naive_to_utc(ser_naive); return df
    # Case B: tz-aware non-UTC -> convert to UTC
    try:
        if str(ser.dt.tz) != 'UTC':
            df = df.copy(); df['datetime_utc'] = ser.dt.tz_convert('UTC')
    except Exception:
        pass
    return df

# ===================== Runtime timeframe & bars =====================

def _read_config_text() -> str:
    try:
        return Path("project_config.yml").read_text(encoding="utf-8")
    except Exception:
        try:
            return Path("/mnt/data/project_config.yml").read_text(encoding="utf-8")
        except Exception:
            return ""

def _read_runtime_timeframe(cfg_text: str) -> str:
    tf = None
    lines = cfg_text.splitlines()
    in_runtime = False
    for ln in lines:
        if re.match(r'^\s*runtime\s*:\s*$', ln):
            in_runtime = True
            continue
        if in_runtime:
            m = re.match(r'^\s*timeframe\s*:\s*([A-Za-z0-9]+)\s*$', ln)
            if m:
                tf = m.group(1).upper()
                break
        if re.match(r'^\S', ln):
            in_runtime = False
    return tf if tf in ("M1","M5","H1") else "M5"

def _resample_ohlcv(df: pd.DataFrame, tf: str) -> pd.DataFrame:
    if tf == "M1":
        return df.copy()
    rule = {"M5": "5T", "H1": "H"}[tf]
    dfr = (df.set_index("datetime_utc")
             .resample(rule, label="right", closed="right")
             .agg({"open":"first","high":"max","low":"min","close":"last","volume":"sum"}))
    dfr = dfr.dropna(subset=["open","high","low","close"]).reset_index()
    return dfr

def _bar_gaps(bars: pd.DataFrame, tf: str) -> pd.DataFrame:
    if bars.empty:
        return pd.DataFrame(columns=["gap_start","gap_end","delta_sec"])
    expect = {"M1": 60, "M5": 300, "H1": 3600}[tf]
    dsec = bars["datetime_utc"].diff().dt.total_seconds().fillna(expect).astype(int)
    idx = dsec[dsec > expect].index
    rows = []
    for i in idx:
        s = bars.loc[i-1, "datetime_utc"]; e = bars.loc[i, "datetime_utc"]
        rows.append({"gap_start": s, "gap_end": e, "delta_sec": int((e-s).total_seconds())})
    return pd.DataFrame(rows)

# ===================== Explainable windows (UTC) =====================

def _overlaps_any(s, e, wins: List[Tuple[datetime, datetime]]) -> bool:
    for (ws, we) in wins:
        if (s < we) and (e > ws):
            return True
    return False

def _parse_ignore_cfg(cfg_text: str) -> dict:
    """Parse scoring.ignore.* from YAML-like text."""
    start_tok, end_tok = 'Fri 22:00', 'Sun 22:00'
    dates = []  # list of (iso_start, iso_end)
    policy = None
    t = cfg_text or ''
    m = re.search(r'(?m)^\s*weekly_window_utc\s*:\s*"([^"]+)"', t)
    if m:
        val = m.group(1).strip()
        parts = [p.strip() for p in val.split('->')]
        if len(parts) == 2 and all(parts):
            start_tok, end_tok = parts[0], parts[1]
    block = re.search(r'(?ms)^\s*dates_utc\s*:\s*(\n(?:\s*-\s*\[[^]]+\]\s*\n?)+)', t)
    if block:
        for mm in re.finditer(r'-\s*\[\s*"([^"]+)"\s*,\s*"([^"]+)"\s*\]', block.group(1)):
            dates.append((mm.group(1), mm.group(2)))
    pol_block = re.search(r'(?ms)^\s*fx_holiday_policy\s*:\s*(\n(?:\s+.+\n?)*)', t)
    if pol_block:
        pb = pol_block.group(1)
        policy = {}
        m_mode = re.search(r'(?m)^\s*mode\s*:\s*(\w+)\s*$', pb); 
        if m_mode: policy['mode'] = m_mode.group(1)
        m_inc = re.search(r'(?m)^\s*include\s*:\s*\[(.*)\]\s*$', pb)
        if m_inc:
            items = [x.strip() for x in m_inc.group(1).split(',') if x.strip()]
            policy['include'] = items
        m_ext = re.search(r'(?m)^\s*extended\s*:\s*(true|false)\s*$', pb, flags=re.I)
        if m_ext: policy['extended'] = (m_ext.group(1).lower()=='true')
    return {'weekly_window': (start_tok, end_tok), 'dates_utc': dates, 'fx_holiday_policy': policy}

def _parse_wd_hhmm(token: str):
    dmap = {"Mon":0,"Tue":1,"Wed":2,"Thu":3,"Fri":4,"Sat":5,"Sun":6}
    token = token.strip()
    m = re.match(r'^(Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+(\d{1,2}):(\d{2})$', token)
    if not m: return None
    wd = dmap[m.group(1)]; hh = int(m.group(2)); mm = int(m.group(3))
    return wd, hh*60+mm

def _weekly_windows_for_year(year: int, start_tok: str, end_tok: str) -> List[Tuple[datetime,datetime]]:
    st = _parse_wd_hhmm(start_tok); en = _parse_wd_hhmm(end_tok)
    if not st or not en: return []
    t = datetime(year-1, 12, 25, 0, 0, tzinfo=timezone.utc)
    stop = datetime(year+1, 1, 5, 0, 0, tzinfo=timezone.utc)
    wins = []
    while t < stop:
        week_start = t - timedelta(days=t.weekday())  # Monday 00:00 UTC
        ws = week_start + timedelta(days=st[0], minutes=st[1])
        we = week_start + timedelta(days=en[0], minutes=en[1])
        if we <= ws:
            we += timedelta(days=7)
        wins.append((ws, we))
        t += timedelta(days=7)
    return wins

def _tag_explainable(bar_gaps: pd.DataFrame, cfg_text: str) -> pd.DataFrame:
    """Tag weekend/closed-hours by interval overlap; holidays later."""
    if bar_gaps.empty:
        return bar_gaps.assign(reason=pd.Series(dtype="object"))
    cfg = _parse_ignore_cfg(cfg_text)
    years = sorted(set(bar_gaps['gap_start'].dt.year.tolist()))
    wins = []
    for y in years:
        wins.extend(_weekly_windows_for_year(int(y), cfg['weekly_window'][0], cfg['weekly_window'][1]))
    bg = bar_gaps.copy()
    bg['reason'] = None
    if wins:
        m_w = bg.apply(lambda r: _overlaps_any(r['gap_start'], r['gap_end'], wins), axis=1)
        if m_w.any():
            bg.loc[m_w, 'reason'] = 'weekend/closed-hours'
    return bg

# ===================== Scoring (TF-aware) =====================

def _tf_params():
    return {
        "gap_buckets": {
            "M1": {"small_max_s": 300,   "long_min_s": 3600},
            "M5": {"small_max_s": 1800,  "long_min_s": 10800},
            "H1": {"small_max_s": 21600, "long_min_s": 86400},
        },
        "weights": {
            "M1": {"gap_mix":0.30,"hotspots":0.20,"extremes":0.15,"monthly":0.15,"sessions":0.10,"calendar":0.05,"completeness":0.05},
            "M5": {"gap_mix":0.25,"hotspots":0.20,"extremes":0.15,"monthly":0.15,"sessions":0.10,"calendar":0.05,"completeness":0.10},
            "H1": {"gap_mix":0.20,"hotspots":0.15,"extremes":0.15,"monthly":0.15,"sessions":0.10,"calendar":0.05,"completeness":0.20},
        },
        "targets": {
            "M1": {"small_share":0.40, "long_share":0.20, "extreme_rate_per_k":0.5, "monthly_cv":1.0, "session_other":0.10, "longest_gap_hours_ok":24},
            "M5": {"small_share":0.50, "long_share":0.15, "extreme_rate_per_k":1.0, "monthly_cv":1.0, "session_other":0.10, "longest_gap_hours_ok":24},
            "H1": {"small_share":0.60, "long_share":0.10, "extreme_rate_per_k":1.0, "monthly_cv":1.0, "session_other":0.10, "longest_gap_hours_ok":24},
        },
    }

def _score_tf(bars: pd.DataFrame, bar_gaps: pd.DataFrame, tf: str, year: int) -> Dict[str, float|str]:
    P = _tf_params()
    small_max = int(P["gap_buckets"][tf]["small_max_s"]); long_min = int(P["gap_buckets"][tf]["long_min_s"])
    N = len(bar_gaps)
    if N>0:
        s = bar_gaps["delta_sec"]
        p_small = ((s>{"M1":60,"M5":300,"H1":3600}[tf]) & (s<=small_max)).mean()
        p_long  = (s>long_min).mean()
    else:
        p_small = p_long = 0.0
    W = P["weights"][tf]; T = P["targets"][tf]

    comp_small = min(1.0, p_small / T["small_share"])
    comp_long  = max(0.0, 1.0 - min(1.0, p_long / T["long_share"]))
    gap_mix = 100.0*(0.6*comp_small + 0.4*comp_long)

    if N>0:
        cells = bar_gaps.assign(wd=bar_gaps["gap_start"].dt.weekday, hr=bar_gaps["gap_start"].dt.hour).groupby(["wd","hr"]).size()
        tot = cells.sum(); p = (cells/tot).values
        H = float((p*p).sum()); C = int(len(cells))
        normH = (H - 1.0/C)/(1.0 - 1.0/C) if C>1 else 1.0
        hotspots = 100.0*(1.0 - normH)
    else:
        hotspots = 100.0

    bars2 = bars.copy()
    bars2["range"] = (bars2["high"]-bars2["low"]).abs()
    p99r = float(bars2["range"].quantile(0.99)) if len(bars2) else 0.0
    ext = int((bars2["range"] > 5*p99r).sum()) if p99r>0 else 0
    per_k = 10000 if tf=="M1" else 1000
    rate_per_k = ext / (len(bars2)/per_k) if len(bars2) else 0.0
    extremes = 100.0*(1.0 - min(1.0, rate_per_k / T["extreme_rate_per_k"]))

    if len(bars2):
        bars2["Month"] = bars2["datetime_utc"].dt.to_period("M").astype(str)
        if N>0:
            g2 = bar_gaps.copy(); g2["Month"] = g2["gap_start"].dt.to_period("M").astype(str)
            monthly = (g2.groupby("Month").size()).reindex(sorted(bars2["Month"].unique()), fill_value=0)
        else:
            monthly = pd.Series([0]*len(bars2["Month"].unique()), index=sorted(bars2["Month"].unique()))
        mu = float(monthly.mean())
        cv = float((monthly.std(ddof=0)/mu)) if mu>0 else 0.0
    else:
        cv = 0.0
    monthly_score = 100.0*(1.0 - min(1.0, cv / T["monthly_cv"]))

    def _sess(ts):
        h = ts.hour + ts.minute/60.0
        asia = (0 <= h < 8); london = (7 <= h < 16); ny = (12 <= h < 21)
        if asia and london: return "Asia-London overlap"
        if london and ny:  return "London-NY overlap"
        if ny: return "NY"
        if london: return "London"
        if asia: return "Asia"
        return "Other"
    share_other = (bar_gaps["gap_start"].apply(_sess)=="Other").mean() if N>0 else 0.0
    sessions = 100.0*(1.0 - min(1.0, share_other / T["session_other"]))

        # Calendar coverage (anomalies-only) — if calendar file is absent, treat as N/A=100
    try:
        cal_df = _load_calendar_df(year)
    except Exception:
        cal_df = None
    if cal_df is None or len(cal_df)==0:
        calendar = 100.0
    else:
        tmp = bar_gaps.copy(); tmp['reason'] = None
        tagged = tmp
        # reuse tagging? anomalies already passed in `bar_gaps` to this function = filtered; so here use them directly
        _, cal_metrics = _match_calendar_high(bar_gaps.assign(reason=pd.Series([None]*len(bar_gaps))), cal_df, window_sec=60)
        coverage = cal_metrics.get('coverage', 0.0)
        # target coverage depends on TF (heuristic): more coarse TF -> higher chance to hit
        target = {'M1':0.10, 'M5':0.20, 'H1':0.30}[tf]
        calendar = 100.0 * min(1.0, coverage / target)

    longest_h = float(bar_gaps["delta_sec"].max()/3600.0) if N>0 else 0.0
    completeness = 100.0*(1.0 - min(1.0, longest_h / T["longest_gap_hours_ok"]))

    total = (W["gap_mix"]*gap_mix + W["hotspots"]*hotspots + W["extremes"]*extremes +
             W["monthly"]*monthly_score + W["sessions"]*sessions + W["calendar"]*calendar +
             W["completeness"]*completeness)

    scorecard_md = (
        f"**Score (0–100): {total:.1f}** — TF: {tf}\n\n"
        "| Component | Weight | Score |\n|---|---:|---:|\n"
        f"| Gap mix | {W['gap_mix']:.2f} | {gap_mix:.1f} |\n"
        f"| Hotspots | {W['hotspots']:.2f} | {hotspots:.1f} |\n"
        f"| Extremes | {W['extremes']:.2f} | {extremes:.1f} |\n"
        f"| Monthly stability | {W['monthly']:.2f} | {monthly_score:.1f} |\n"
        f"| Sessions | {W['sessions']:.2f} | {sessions:.1f} |\n"
        f"| Calendar | {W['calendar']:.2f} | {calendar:.1f} |\n"
        f"| Completeness | {W['completeness']:.2f} | {completeness:.1f} |\n"
    )
    return {"total": float(total), "scorecard_md": scorecard_md}

# ===================== Context builders =====================

def _session_label(ts: pd.Timestamp) -> str:
    h = ts.hour + ts.minute/60.0
    asia = (0 <= h < 8); london = (7 <= h < 16); ny = (12 <= h < 21)
    if asia and london: return "Asia-London overlap"
    if london and ny:  return "London-NY overlap"
    if ny: return "NY"
    if london: return "London"
    if asia: return "Asia"
    return "Other"

def build_common_blocks(df: pd.DataFrame, gaps: pd.DataFrame, year: int) -> Dict[str,str]:
    # normalize UTC
    cfg_text = _read_config_text()
    df = _coerce_input_utc(df, cfg_text)

    # TF and gaps
    tf = _read_runtime_timeframe(cfg_text)
    bars = _resample_ohlcv(df, tf)
    bar_g = _bar_gaps(bars, tf)

    # Tag weekend by overlap, then holidays by overlap
    tagged = _tag_explainable(bar_g, cfg_text)
    try:
        _fx_wins = fx_holidays.fx_holiday_windows(year, cfg_text)
    except Exception:
        _fx_wins = []
    if _fx_wins:
        m = tagged['reason'].isna() & tagged.apply(lambda r: _overlaps_any(r['gap_start'], r['gap_end'], _fx_wins), axis=1)
        if m.any(): tagged.loc[m, 'reason'] = 'holiday'
    filtered = tagged[tagged['reason'].isna()].drop(columns=['reason'])

    # 1) classification header (no emoji), informative only
    base_min = {"M1":1,"M5":5,"H1":60}[tf]
        # Calendar metrics
    try:
        cal_df = _load_calendar_df(year)
    except Exception:
        cal_df = None
    _, calm = _match_calendar_high(tagged, cal_df, window_sec=60)
    cov = calm.get('coverage', 0.0)
    total_high = calm.get('total_high_events', 0)
    matched_high = calm.get('matched_high_events', 0)
    gap_classification_md = (
        f"Gap classification (>{base_min} min). Weekend/holidays are excluded from scoring and lists.\n"
        f"Economic Calendar coverage: {100.0*cov:.1f}% (High={total_high}, matched={matched_high})."
    )

    # 2) durations
    s = filtered["delta_sec"] if len(filtered) else pd.Series([], dtype="int64")
    b_12 = int(((s>60)&(s<=120)).sum()) if len(s) else 0
    b_25 = int(((s>120)&(s<=300)).sum()) if len(s) else 0
    b_660 = int(((s>300)&(s<=3600)).sum()) if len(s) else 0
    b_gt = int((s>3600).sum()) if len(s) else 0
    p50 = int(s.quantile(0.5)) if len(s) else 0
    p90 = int(s.quantile(0.9)) if len(s) else 0
    p99 = int(s.quantile(0.99)) if len(s) else 0
    mx = int(s.max()) if len(s) else 0
    if len(s):
        mxrow = filtered.loc[s.idxmax()]
        longest = f"Longest gap: {mx}s (from {mxrow['gap_start'].isoformat()} to {mxrow['gap_end'].isoformat()} ; ≈{mx/3600:.2f} hours)."
    else:
        longest = "Longest gap: n/a"
    durations_section_md = (
        "**Buckets (counts)**  \n"
        f"- 1–2 min: {b_12}\n- 2–5 min: {b_25}\n- 6–60 min: {b_660}\n- >60 min: {b_gt}\n\n"
        f"**Percentiles (sec)**  p50={p50}, p90={p90}, p99={p99}, max={mx}.  \n" + longest
    )

    # 3) sessions (on anomalies only)
    if len(filtered):
        sess = filtered["gap_start"].apply(_session_label).value_counts()
        total = int(sess.sum()) or 1
        sessions_table_md = "| Session | Count | % |\n|---|---:|---:|\n" + "\n".join(
            f"| {k} | {int(v)} | {100.0*float(v)/total:.2f}% |" for k,v in sess.items()
        )
    else:
        sessions_table_md = "_No gaps_"

    # 4) monthly table (rows vs gaps in anomalies)
    bars2 = bars.copy()
    bars2["Month"] = bars2["datetime_utc"].dt.to_period("M").astype(str)
    if len(filtered):
        g2 = filtered.copy(); g2["Month"] = g2["gap_start"].dt.to_period("M").astype(str)
        monthly = (pd.DataFrame({"Rows": bars2.groupby("Month").size(),
                                 "Gaps": g2.groupby("Month").size()})
                   .fillna(0).astype(int).reset_index())
    else:
        monthly = (pd.DataFrame({"Rows": bars2.groupby("Month").size()}).reset_index())
        monthly["Gaps"] = 0
    monthly_table_md = "| Month | Rows | Gaps |\n|---|---:|---:|\n" + "\n".join(
        f"| {r['Month']} | {r['Rows']} | {r['Gaps']} |" for _, r in monthly.iterrows()
    )

    # Scorecard
    sc = _score_tf(bars, filtered, tf, year)
    scorecard_md = sc["scorecard_md"]

    return {
        "gap_classification_md": gap_classification_md,
        "durations_section_md": durations_section_md,
        "sessions_table_md": sessions_table_md,
        "monthly_table_md": monthly_table_md,
        "scorecard_md": scorecard_md,
    }

def build_gaps_context(df: pd.DataFrame, gaps: pd.DataFrame, year: int) -> Dict[str,str]:
    cfg_text = _read_config_text()
    df = _coerce_input_utc(df, cfg_text)
    tf = _read_runtime_timeframe(cfg_text)
    bars = _resample_ohlcv(df, tf)
    bar_g = _bar_gaps(bars, tf)

    tagged = _tag_explainable(bar_g, cfg_text)
    try:
        _fx_wins = fx_holidays.fx_holiday_windows(year, cfg_text)
    except Exception:
        _fx_wins = []
    if _fx_wins is not None and len(_fx_wins)>0:
        m = tagged['reason'].isna() & tagged.apply(lambda r: _overlaps_any(r['gap_start'], r['gap_end'], _fx_wins), axis=1)
        if m.any(): tagged.loc[m, 'reason'] = 'holiday'
    filtered = tagged[tagged['reason'].isna()].drop(columns=['reason'])

    # Sessions table (for anomalies only)
    if len(filtered):
        sess = filtered["gap_start"].apply(_session_label).value_counts()
        total = int(sess.sum()) or 1
        sessions_table_md = "| Session | Count | % |\n|---|---:|---:|\n" + "\n".join(
            f"| {k} | {int(v)} | {100.0*float(v)/total:.2f}% |" for k,v in sess.items()
        )
    else:
        sessions_table_md = "_No gaps_"

    # Full list
    lines = ["| # | Start UTC | End UTC | Δ sec |", "|---:|---|---|---:|"]
    if len(filtered):
        for i, r in enumerate(filtered.sort_values('gap_start').itertuples(index=False), start=1):
            lines.append(f"| {i} | {r.gap_start.isoformat()} | {r.gap_end.isoformat()} | {int(r.delta_sec)} |")
    gaps_full_table_md = "\n".join(lines)
    return {"sessions_table_md": sessions_table_md, "gaps_full_table_md": gaps_full_table_md}

def build_monthly_context(df: pd.DataFrame, gaps: pd.DataFrame, year: int, month: str) -> Dict[str,str]:
    dfm = df[df["datetime_utc"].dt.to_period("M").astype(str) == month].copy()
    # note: gaps are built in build_common_blocks; here we reuse the same logic by slicing df then calling common
    common = build_common_blocks(dfm if not dfm.empty else df, gaps, year)
    return {
        "month": month,
        "monthly_table_md": common["monthly_table_md"],
        "sessions_table_md": common["sessions_table_md"],
        "durations_section_md": common["durations_section_md"],
        "scorecard_md": common["scorecard_md"],
    }

def build_quarterly_context(df: pd.DataFrame, gaps: pd.DataFrame, year: int, q: int) -> Dict[str,str]:
    start_month = 3*(q-1) + 1
    qs = pd.Timestamp(year=year, month=start_month, day=1, tz="UTC")
    qe = pd.Timestamp(year=year + (1 if q==4 else 0), month=(1 if q==4 else start_month+3), day=1, tz="UTC")
    mask = (df["datetime_utc"]>=qs) & (df["datetime_utc"]<qe)
    dfq = df[mask].copy()
    return build_common_blocks(dfq if not dfq.empty else df, gaps, year)
