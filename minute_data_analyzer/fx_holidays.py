# fx_holidays.py
# Deterministic offline generator of FX holiday closure windows (UTC) for a given year.
# Covers: New Year's Day (Jan 1), Good Friday (Easter - 2d), Christmas (Dec 25).
# Optional (via policy): Boxing Day (Dec 26), Easter Monday (Easter + 1d).
# Also supports extra closures from config as explicit UTC ranges.
from datetime import datetime, timedelta, timezone
import re

UTC = timezone.utc

def _easter_date(year: int):
    # Anonymous Gregorian algorithm (Meeus/Jones/Butcher)
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19*a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2*e + 2*i - h - k) % 7
    m = (a + 11*h + 22*l) // 451
    month = (h + l - 7*m + 114) // 31
    day = ((h + l - 7*m + 114) % 31) + 1
    return datetime(year, month, day, tzinfo=UTC).date()

def _full_day_utc(dateobj):
    start = datetime(dateobj.year, dateobj.month, dateobj.day, 0, 0, tzinfo=UTC)
    end   = start + timedelta(days=1)
    return (start, end)

def _parse_extra_windows(cfg_text: str):
    # Parse extra closures from config in format: "YYYY-MM-DDTHH:MM:SSZ -> YYYY-MM-DDTHH:MM:SSZ"
    wins = []
    if not cfg_text:
        return wins
    in_scoring = False
    in_ignore = False
    in_fx = False
    for ln in cfg_text.splitlines():
        if re.match(r'^\s*scoring\s*:\s*$', ln):
            in_scoring = True; in_ignore = False; in_fx = False; continue
        if in_scoring and re.match(r'^\S', ln):
            in_scoring = False
        if in_scoring and re.match(r'^\s*ignore\s*:\s*$', ln):
            in_ignore = True; in_fx = False; continue
        if in_ignore and re.match(r'^\s*fx_holiday_policy\s*:\s*$', ln):
            in_fx = True; continue
        if in_fx and re.match(r'^\s*extra_closures_utc\s*:\s*$', ln):
            continue
        if in_fx:
            m = re.match(r'^\s*-\s*"([^"]+)"\s*$', ln)
            if m:
                s = m.group(1)
                parts = [p.strip() for p in s.split("->")]
                if len(parts) == 2:
                    def parse_iso_z(x):
                        m2 = re.match(r'^(\d{4}-\d{2}-\d{2})T(\d{2}):(\d{2}):(\d{2})Z$', x)
                        if not m2: return None
                        y, mo, d, hh, mm, ss = map(int, (m2.group(1)[0:4], m2.group(1)[5:7], m2.group(1)[8:10], m2.group(2), m2.group(3), m2.group(4)))
                        return datetime(y, mo, d, hh, mm, ss, tzinfo=UTC)
                    st = parse_iso_z(parts[0]); en = parse_iso_z(parts[1])
                    if st and en and en > st:
                        wins.append((st, en))
    return wins

def fx_holiday_windows(year: int, cfg_text: str):
    # Read policy flags from cfg_text
    mode = "minimal"
    include = set()
    extended = False
    if cfg_text:
        in_scoring = False; in_ignore = False; in_fx = False
        for ln in cfg_text.splitlines():
            if re.match(r'^\s*scoring\s*:\s*$', ln):
                in_scoring = True; in_ignore = False; in_fx = False; continue
            if in_scoring and re.match(r'^\S', ln):
                in_scoring = False
            if in_scoring and re.match(r'^\s*ignore\s*:\s*$', ln):
                in_ignore = True; in_fx = False; continue
            if in_ignore and re.match(r'^\s*fx_holiday_policy\s*:\s*$', ln):
                in_fx = True; continue
            if in_fx:
                m = re.match(r'^\s*mode\s*:\s*(\w+)\s*$', ln)
                if m:
                    mode = m.group(1).lower()
                m2 = re.match(r'^\s*include\s*:\s*\[(.*)\]\s*$', ln)
                if m2:
                    items = [x.strip() for x in m2.group(1).split(",") if x.strip()]
                    include.update(items)
                m3 = re.match(r'^\s*extended\s*:\s*(true|false)\s*$', ln, flags=re.I)
                if m3:
                    extended = (m3.group(1).lower() == "true")
    if not include:
        include = {"christmas", "new_year", "good_friday"}
        if mode == "extended" or extended:
            include |= {"boxing_day", "easter_monday"}

    wins = []
    easter = _easter_date(year)
    if "good_friday" in include:
        wins.append(_full_day_utc(easter - timedelta(days=2)))
    if "easter_monday" in include:
        wins.append(_full_day_utc(easter + timedelta(days=1)))
    if "new_year" in include:
        wins.append(_full_day_utc(datetime(year, 1, 1, tzinfo=UTC).date()))
    if "christmas" in include:
        wins.append(_full_day_utc(datetime(year, 12, 25, tzinfo=UTC).date()))
    if "boxing_day" in include:
        wins.append(_full_day_utc(datetime(year, 12, 26, tzinfo=UTC).date()))

    wins.extend(_parse_extra_windows(cfg_text))
    return wins

def in_any_window(ts, windows):
    for (s, e) in windows:
        if s <= ts < e:
            return True
    return False
