# Patched helpers.py with strict template rendering and deterministic tar.gz
from __future__ import annotations
from typing import Dict, List
import io, gzip, tarfile

def write_gzip_deterministic(data: bytes, compresslevel: int = 9) -> bytes:
    """Return gzip bytes with mtime=0 for reproducible hashes."""
    buf = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=buf, compresslevel=compresslevel, mtime=0) as gz:
        gz.write(data)
    return buf.getvalue()

def make_tar_gz_deterministic(base_dir: str, paths: List[str], dst_path: str,
                              mtime: int = 0, uid: int = 0, gid: int = 0,
                              uname: str = "root", gname: str = "root",
                              mode: int = 0o644, compresslevel: int = 9) -> None:
    """Pack files into tar.gz deterministically (fixed metadata + gzip mtime=0)."""
    import os
    buf = io.BytesIO()
    with tarfile.open(mode="w", fileobj=buf, format=tarfile.GNU_FORMAT) as tar:
        for rel in sorted(paths):
            full = os.path.join(base_dir, rel)
            ti = tar.gettarinfo(full, arcname=rel)
            ti.mtime = mtime
            ti.uid = uid
            ti.gid = gid
            ti.uname = uname
            ti.gname = gname
            ti.mode = mode
            with open(full, "rb") as rf:
                tar.addfile(ti, rf)
    gz_bytes = write_gzip_deterministic(buf.getvalue(), compresslevel=compresslevel)
    with open(dst_path, "wb") as f:
        f.write(gz_bytes)

def render_template_file(template_path: str, output_path: str, context: Dict[str, str]) -> None:
    """Simple {{key}} replacement for Markdown templates."""
    with open(template_path, "r", encoding="utf-8") as f:
        txt = f.read()
    for k, v in context.items():
        txt = txt.replace("{{"+k+"}}", str(v))
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(txt)

def render_template_file_strict(template_path: str, output_path: str, context: Dict[str, str]) -> None:
    """Same as render_template_file, but asserts there are no unresolved {{...}} placeholders."""
    render_template_file(template_path, output_path, context)
    import re
    with open(output_path, "r", encoding="utf-8") as f:
        out = f.read()
    leftovers = re.findall(r"\{\{[^}]+\}\}", out)
    if leftovers:
        raise ValueError(f"Unresolved placeholders in {output_path}: {sorted(set(leftovers))}")


def save_svg_deterministic(fig, path: str) -> None:
    """Save Matplotlib figure to SVG with deterministic settings."""
    import matplotlib
    # Deterministic SVG settings
    matplotlib.rcParams['svg.hashsalt'] = ''
    matplotlib.rcParams['svg.fonttype'] = 'none'
    matplotlib.rcParams['path.simplify'] = False
    fig.savefig(path, format='svg')

def write_svgz_deterministic(svg_bytes: bytes, dst_path: str) -> None:
    """Write .svgz with gzip mtime=0 for reproducible hash."""
    buf = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=buf, compresslevel=9, mtime=0) as gz:
        gz.write(svg_bytes)
    with open(dst_path, "wb") as f:
        f.write(buf.getvalue())


# --- Time window helpers (UTC) for deterministic slicing ---
def quarter_bounds(year: int, q: int):
    """Return (start_utc, end_utc) for quarter q in year, as ISO8601 strings."""
    import datetime as _dt, pytz as _tz
    if q not in (1,2,3,4):
        raise ValueError("q must be 1..4")
    start_month = 3*(q-1) + 1
    end_year = year + (1 if q==4 else 0)
    end_month = 1 if q==4 else start_month + 3
    tz = _tz.UTC
    start = _dt.datetime(year, start_month, 1, 0, 0, 0, tzinfo=tz)
    end = _dt.datetime(end_year, end_month, 1, 0, 0, 0, tzinfo=tz)
    return start, end

def month_bounds(year: int, month: int):
    """Return (start_utc, end_utc) for month in year, as ISO8601 strings."""
    import datetime as _dt, pytz as _tz, calendar as _cal
    if not (1 <= month <= 12):
        raise ValueError("month must be 1..12")
    tz = _tz.UTC
    last_day = _cal.monthrange(year, month)[1]
    start = _dt.datetime(year, month, 1, 0, 0, 0, tzinfo=tz)
    if month == 12:
        end = _dt.datetime(year+1, 1, 1, 0, 0, 0, tzinfo=tz)
    else:
        end = _dt.datetime(year, month+1, 1, 0, 0, 0, tzinfo=tz)
    return start, end
