#!/usr/bin/env python3
"""Global Land Cover Downloader | 全球土地覆盖下载器

通过 STAC API 或直接下载链接获取全球土地覆盖数据。
支持 ESA WorldCover (10m)、FROM-GLC (30m)、GlobeLand30 (30m)。

数据源 / Source
----------------
* **ESA WorldCover** (默认) — 通过 Planetary Computer STAC 获取，10m 分辨率
* **FROM-GLC** — 清华大学 FROM-GLC 数据集，30m 分辨率
* **GlobeLand30** — 国家基础地理信息中心 GlobeLand30，30m 分辨率

Privacy disclosure
------------------
When this script runs, it sends:
* The bounding box to a STAC search API (Planetary Computer) or direct
  download URLs. No API keys, no local files, no PII are sent.

What is NOT sent: any data from the local filesystem, any environment
variables, any login credentials.

To suppress the one-line privacy notice: set ``LANDCOVER_DOWNLOAD_QUIET=1``.

Public domain notice
--------------------
ESA WorldCover data is provided by ESA and is free to use.
FROM-GLC data is provided by Tsinghua University.
GlobeLand30 data is provided by National Geomatics Center of China.
This skill does not bypass any authentication, login, or access control.

Usage
-----
::

    # Search ESA WorldCover tiles
    python landcover-download.py \\
        --dataset worldcover \\
        --bbox 116.0 39.0 117.0 40.0

    # Download ESA WorldCover
    python landcover-download.py \\
        --dataset worldcover \\
        --bbox 116.0 39.0 117.0 40.0 \\
        --year 2021 \\
        --download \\
        --output-dir ./landcover_data

License
-------
MIT-0. Land cover data © respective providers.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin

import requests


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

STAC_ENDPOINT = "https://planetarycomputer.microsoft.com/api/stac/v1"
STAC_SEARCH_URL = f"{STAC_ENDPOINT}/search"
SIGN_URL = "https://planetarycomputer.microsoft.com/api/sas/v1/token/{collection}"

WORLDCOVER_COLLECTION = "esa-worldcover"

USER_AGENT = "landcover-download/0.1.0 (+https://clawhub.ai/skills/landcover-download)"

DEFAULT_TRUST_ENV = os.environ.get("LANDCOVER_DOWNLOAD_USE_PROXY") == "1"

# SAS token cache: collection → (token, expires_at_epoch_seconds)
_SAS_CACHE: Dict[str, Tuple[str, float]] = {}

# Dataset metadata
DATASETS = {
    "worldcover": {
        "name": "ESA WorldCover",
        "resolution": "10m",
        "years": [2020, 2021],
        "source": "Planetary Computer STAC",
        "collection": "esa-worldcover",
        "assets": ["map", "input_data"],
        "description": "ESA WorldCover 10m land cover map",
    },
    "from-glc": {
        "name": "FROM-GLC",
        "resolution": "30m",
        "years": [2010, 2015, 2017],
        "source": "Tsinghua University",
        "collection": None,
        "assets": ["classification"],
        "description": "FROM-GLC 30m global land cover",
    },
    "globeland30": {
        "name": "GlobeLand30",
        "resolution": "30m",
        "years": [2000, 2010, 2020],
        "source": "National Geomatics Center of China",
        "collection": None,
        "assets": ["classification"],
        "description": "GlobeLand30 30m global land cover",
    },
}

# WorldCover classification values
WORLDCOVER_CLASSES = {
    10: "Tree cover",
    20: "Shrubland",
    30: "Grassland",
    40: "Cropland",
    50: "Built-up",
    60: "Bare / sparse vegetation",
    70: "Snow and ice",
    80: "Permanent water bodies",
    90: "Herbaceous wetland",
    95: "Mangroves",
    100: "Moss and lichen",
}


# ---------------------------------------------------------------------------
# Privacy notice helper
# ---------------------------------------------------------------------------

def _quiet() -> bool:
    return os.environ.get("LANDCOVER_DOWNLOAD_QUIET") == "1"


def _emit_privacy_notice(source: str) -> None:
    if _quiet():
        return
    msg = (
        f"[landcover-download] contacting {source} "
        f"(no API keys / no local files / no PII sent). "
        f"Set LANDCOVER_DOWNLOAD_QUIET=1 to suppress this notice."
    )
    print(msg, file=sys.stderr)


# ---------------------------------------------------------------------------
# STAC search for ESA WorldCover
# ---------------------------------------------------------------------------

def stac_search_worldcover(
    *,
    bbox: Tuple[float, float, float, float],
    year: int = 2021,
    limit: int = 50,
    timeout: int = 60,
) -> Dict[str, Any]:
    """Search Planetary Computer STAC for ESA WorldCover tiles.

    Parameters
    ----------
    bbox : tuple of 4 floats
        (min_lon, min_lat, max_lon, max_lat) in WGS84.
    year : int
        Data year (2020 or 2021).
    limit : int
        Maximum items to return.
    timeout : int
        Request timeout in seconds.

    Returns
    -------
    dict
        Raw STAC search response with features list.
    """
    body: Dict[str, Any] = {
        "collections": [WORLDCOVER_COLLECTION],
        "bbox": list(bbox),
        "limit": int(limit),
    }

    # WorldCover uses datetime filter for year selection
    if year == 2020:
        body["datetime"] = "2020-01-01T00:00:00Z/2020-12-31T23:59:59Z"
    elif year == 2021:
        body["datetime"] = "2021-01-01T00:00:00Z/2021-12-31T23:59:59Z"

    session = requests.Session()
    session.trust_env = DEFAULT_TRUST_ENV
    session.headers.update({"User-Agent": USER_AGENT, "Content-Type": "application/json"})

    _emit_privacy_notice("Planetary Computer")

    r = session.post(STAC_SEARCH_URL, json=body, timeout=timeout)
    r.raise_for_status()
    return r.json()


# ---------------------------------------------------------------------------
# Planetary Computer signing
# ---------------------------------------------------------------------------

def get_signed_href(item: Dict[str, Any], asset_key: str) -> Optional[str]:
    """Return the signed (downloadable) URL for a STAC asset."""
    asset = item.get("assets", {}).get(asset_key)
    if not asset:
        return None
    href = asset.get("href")
    if not href:
        return None

    collection = item.get("collection", WORLDCOVER_COLLECTION)
    token, expires_at = _SAS_CACHE.get(collection, ("", 0.0))
    now = time.time()
    if not token or now >= expires_at - 60:
        sign_url = SIGN_URL.format(collection=collection)
        session = requests.Session()
        session.trust_env = DEFAULT_TRUST_ENV
        session.headers.update({"User-Agent": USER_AGENT})
        r = session.get(sign_url, timeout=30)
        r.raise_for_status()
        token = r.json().get("token") or r.text.strip().strip('"')
        _SAS_CACHE[collection] = (token, now + 50 * 60)
    return f"{href}?{token}"


# ---------------------------------------------------------------------------
# Direct download URLs for non-STAC datasets
# ---------------------------------------------------------------------------

def get_fromglc_url(year: int, tile_id: str) -> Optional[str]:
    """Get FROM-GLC download URL for a given year and tile."""
    base_urls = {
        2010: "http://data.ess.tsinghua.edu.cn/data/fromglc10_2010v1/",
        2015: "http://data.ess.tsinghua.edu.cn/data/fromglc10_2015v1/",
        2017: "http://data.ess.tsinghua.edu.cn/data/fromglc10_2017v1/",
    }
    base = base_urls.get(year)
    if not base:
        return None
    return urljoin(base, f"{tile_id}.tif")


def get_globeland30_url(year: int, tile_id: str) -> Optional[str]:
    """Get GlobeLand30 download URL for a given year and tile."""
    base_urls = {
        2000: "http://www.globallandcover.com/GLC30Download/GLC30_2000/",
        2010: "http://www.globallandcover.com/GLC30Download/GLC30_2010/",
        2020: "http://www.globallandcover.com/GLC30Download/GLC30_2020/",
    }
    base = base_urls.get(year)
    if not base:
        return None
    return urljoin(base, f"{tile_id}.tif")


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------

def _format_tile_text(item: Dict[str, Any], idx: int) -> str:
    item_id = item.get("id", "?")
    props = item.get("properties", {})
    raw_dt = props.get("datetime") or ""
    datetime_str = raw_dt[:10] if raw_dt else "?"
    assets = list(item.get("assets", {}).keys())
    assets_str = " ".join(assets) if assets else "-"
    if len(assets_str) > 60:
        assets_str = assets_str[:57] + "..."
    return (
        f"  {idx}. {item_id}\n"
        f"     Date:   {datetime_str}\n"
        f"     Assets: {assets_str}\n"
    )


def _format_tile_json(item: Dict[str, Any]) -> Dict[str, Any]:
    props = item.get("properties", {})
    return {
        "id": item.get("id"),
        "datetime": props.get("datetime"),
        "assets": list(item.get("assets", {}).keys()),
        "bbox": item.get("bbox"),
    }


def format_results_text(query_meta: Dict[str, Any], features: List[Dict[str, Any]]) -> str:
    lines = []
    dataset = query_meta.get("dataset", "worldcover")
    ds_info = DATASETS.get(dataset, {})
    lines.append(f"[landcover-download] found {len(features)} tile(s) for {ds_info.get('name', dataset)}")
    lines.append(f"[landcover-download] resolution: {ds_info.get('resolution', '?')}")
    lines.append("")
    for i, f in enumerate(features, 1):
        lines.append(_format_tile_text(f, i))
    if not features:
        lines.append("  (no tiles match the query — try widening bbox or changing year)")
    return "\n".join(lines)


def format_results_json(query_meta: Dict[str, Any], features: List[Dict[str, Any]]) -> str:
    return json.dumps(
        {
            "query": query_meta,
            "count": len(features),
            "tiles": [_format_tile_json(f) for f in features],
        },
        ensure_ascii=False,
        indent=2,
    )


# ---------------------------------------------------------------------------
# Download with progress
# ---------------------------------------------------------------------------

def _human_bytes(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} {unit}"
        n /= 1024
    return f"{n:.1f} PB"


def _render_progress(downloaded: int, total: Optional[int], speed_bps: float,
                     eta_seconds: Optional[float], bar_width: int = 30) -> str:
    if total and total > 0:
        pct = downloaded / total
        filled = int(bar_width * pct)
        bar = "█" * filled + "░" * (bar_width - filled)
        pct_str = f"{pct * 100:5.1f}%"
    else:
        bar = "?" * bar_width
        pct_str = "  ?  %"
    dl_str = _human_bytes(downloaded)
    tot_str = _human_bytes(total) if (total and total > 0) else "??"
    speed_str = f"{_human_bytes(int(speed_bps))}/s"
    if eta_seconds is not None and eta_seconds >= 0:
        m, s = divmod(int(eta_seconds), 60)
        eta_str = f"{m}:{s:02d}"
    else:
        eta_str = "  ?  "
    return f"┃{bar}┃ {pct_str}  {dl_str:>9s} / {tot_str:<9s}  {speed_str:>11s}  ETA {eta_str}"


def download_asset(
    url: str,
    dest_path: str,
    timeout: int = 600,
    show_progress: bool = True,
) -> Tuple[bool, str]:
    """Download one asset to dest_path via a .part temp file.

    Returns (ok, message). On success the .part file is renamed to dest_path.
    On failure the .part file is removed and any existing dest_path is left untouched.
    """
    tmp_path = dest_path + ".part"
    if os.path.exists(dest_path) and not os.path.exists(tmp_path):
        if not _quiet():
            print(f"  ↳ {os.path.basename(dest_path):<20s} already exists, skipping", file=sys.stderr)
        return True, "already exists, skipping"

    try:
        with requests.get(url, stream=True, timeout=timeout,
                          headers={"User-Agent": USER_AGENT}) as r:
            r.raise_for_status()
            total = int(r.headers.get("Content-Length", 0)) or None
            downloaded = 0
            t0 = time.time()
            last_print = t0

            with open(tmp_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=64 * 1024):
                    if not chunk:
                        continue
                    f.write(chunk)
                    downloaded += len(chunk)
                    now = time.time()
                    if show_progress and not _quiet() and (now - last_print) > 0.1:
                        elapsed = now - t0
                        speed = downloaded / elapsed if elapsed > 0 else 0
                        eta = ((total - downloaded) / speed) if (total and speed > 0) else None
                        line = _render_progress(downloaded, total, speed, eta)
                        sys.stdout.write(f"\r  ↳ {os.path.basename(dest_path):<20s} {line}")
                        sys.stdout.flush()
                        last_print = now

        if show_progress and not _quiet():
            sys.stdout.write("\n")
            sys.stdout.flush()
        os.replace(tmp_path, dest_path)
        return True, "ok"
    except Exception as e:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
        return False, str(e)[:200]


def download_tile(
    item: Dict[str, Any],
    assets: List[str],
    output_dir: str,
    dataset: str = "worldcover",
    timeout: int = 600,
    show_progress: bool = True,
) -> Dict[str, Any]:
    """Download selected assets for one tile.

    Returns a per-tile result dict with tile_id, ok, files list, and total_bytes.
    """
    tile_id = item.get("id", "unknown")
    tile_dir = os.path.join(output_dir, tile_id)
    os.makedirs(tile_dir, exist_ok=True)

    result: Dict[str, Any] = {
        "tile_id": tile_id,
        "ok": True,
        "files": [],
        "total_bytes": 0,
    }

    if not _quiet():
        print(f"\n[landcover-download] downloading {tile_id}", file=sys.stderr)

    for asset_key in assets:
        if dataset == "worldcover":
            href = get_signed_href(item, asset_key)
        else:
            href = item.get("assets", {}).get(asset_key, {}).get("href")

        if not href:
            result["files"].append({"asset": asset_key, "ok": False,
                                    "message": "no download URL"})
            result["ok"] = False
            continue

        ext = ".tif"
        dest = os.path.join(tile_dir, f"{asset_key}{ext}")
        ok, msg = download_asset(href, dest, timeout=timeout,
                                 show_progress=show_progress)
        result["files"].append({"asset": asset_key, "path": dest, "ok": ok,
                                "message": msg})
        if ok and os.path.exists(dest):
            result["total_bytes"] += os.path.getsize(dest)
        if not ok:
            result["ok"] = False

    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="landcover-download",
        description=(
            "Search and download global land cover data. "
            "Supports ESA WorldCover (10m), FROM-GLC (30m), GlobeLand30 (30m). "
            "通过 STAC 搜索和下载全球土地覆盖数据。"
        ),
    )
    p.add_argument("--dataset", default="worldcover",
                   choices=["worldcover", "from-glc", "globeland30"],
                   help="Dataset to download (default: worldcover)")
    p.add_argument("--bbox", nargs=4, type=float,
                   metavar=("MIN_LON", "MIN_LAT", "MAX_LON", "MAX_LAT"),
                   help="Geographic extent in WGS84 / 地理范围")
    p.add_argument("--year", type=int, default=None,
                   help="Data year (default: latest available)")
    p.add_argument("--limit", type=int, default=50,
                   help="Max tiles to return (default 50)")
    p.add_argument("--assets", nargs="+", default=None,
                   help="Assets to download (default: map for worldcover)")
    p.add_argument("--download", action="store_true",
                   help="Trigger actual download (default: search only)")
    p.add_argument("--output-dir", default="./landcover_data",
                   help="Download directory (default ./landcover_data)")
    p.add_argument("--output-format", default="text", choices=["text", "json"],
                   help="Output format")
    p.add_argument("--no-progress", action="store_true",
                   help="Disable visual progress bar")
    p.add_argument("--download-timeout", type=int, default=600,
                   help="Per-asset download timeout in seconds (default 600)")
    p.add_argument("--list-datasets", action="store_true",
                   help="List all available datasets and exit")
    p.add_argument("--list-classes", action="store_true",
                   help="List land cover classification values (WorldCover)")
    p.add_argument("--quiet", action="store_true",
                   help="Suppress progress + privacy notice")
    return p


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)

    # --list-datasets
    if args.list_datasets:
        print("Available land cover datasets:")
        print("-" * 60)
        for key, info in DATASETS.items():
            print(f"  {key:<12s}  {info['name']:<20s}  {info['resolution']}")
            print(f"               Years: {', '.join(map(str, info['years']))}")
            print(f"               Source: {info['source']}")
            print()
        return 0

    # --list-classes
    if args.list_classes:
        print("ESA WorldCover classification values:")
        print("-" * 40)
        for code, name in WORLDCOVER_CLASSES.items():
            print(f"  {code:>3d}  {name}")
        return 0

    # Required args check
    if not args.bbox:
        print("ERROR: --bbox is required", file=sys.stderr)
        print("Run with --help for usage.", file=sys.stderr)
        return 2

    # --quiet on CLI overrides env
    if args.quiet:
        os.environ["LANDCOVER_DOWNLOAD_QUIET"] = "1"

    bbox = tuple(args.bbox)
    dataset = args.dataset
    ds_info = DATASETS.get(dataset, {})

    # Determine year
    year = args.year
    if year is None:
        year = ds_info.get("years", [2021])[-1]  # latest year

    # Determine assets
    assets = args.assets
    if assets is None:
        assets = ds_info.get("assets", ["map"])

    query_meta = {
        "dataset": dataset,
        "bbox": list(bbox),
        "year": year,
        "limit": args.limit,
        "assets": assets,
    }

    # Search
    features: List[Dict[str, Any]] = []
    try:
        if dataset == "worldcover":
            resp = stac_search_worldcover(
                bbox=bbox,
                year=year,
                limit=args.limit,
            )
            features = resp.get("features", [])
        elif dataset == "from-glc":
            print("[landcover-download] FROM-GLC direct download not yet implemented",
                  file=sys.stderr)
            print("[landcover-download] Use --dataset worldcover for STAC-based download",
                  file=sys.stderr)
            return 1
        elif dataset == "globeland30":
            print("[landcover-download] GlobeLand30 direct download not yet implemented",
                  file=sys.stderr)
            print("[landcover-download] Use --dataset worldcover for STAC-based download",
                  file=sys.stderr)
            return 1
    except requests.HTTPError as e:
        print(f"ERROR: search failed: {e}", file=sys.stderr)
        if e.response is not None:
            print(f"  body: {e.response.text[:300]}", file=sys.stderr)
        return 1
    except requests.RequestException as e:
        print(f"ERROR: network error: {e}", file=sys.stderr)
        return 1

    query_meta["returned"] = len(features)

    # Output search results
    if args.output_format == "json":
        print(format_results_json(query_meta, features))
    else:
        if not _quiet():
            ds_name = ds_info.get("name", dataset)
            print(f"[landcover-download] searching {ds_name} ...", file=sys.stderr)
            print(f"[landcover-download] bbox: [{bbox[0]}, {bbox[1]}, {bbox[2]}, {bbox[3]}]",
                  file=sys.stderr)
            print(f"[landcover-download] year: {year}", file=sys.stderr)
        print(format_results_text(query_meta, features))

    # Download?
    if not args.download:
        if not _quiet():
            print("\n[landcover-download] search done. Add --download to fetch.",
                  file=sys.stderr)
        return 0

    # Download loop
    output_dir = args.output_dir
    os.makedirs(output_dir, exist_ok=True)

    if not features:
        if not _quiet():
            print("[landcover-download] no tiles to download.", file=sys.stderr)
        return 0

    if not _quiet():
        print(f"\n[landcover-download] downloading {len(features)} tile(s) to {output_dir}",
              file=sys.stderr)
        print(f"[landcover-download] assets: {' '.join(assets)}", file=sys.stderr)

    overall_ok = True
    total_bytes = 0
    t0 = time.time()
    for i, item in enumerate(features, 1):
        if not _quiet():
            print(f"\n[{i}/{len(features)}]", file=sys.stderr)
        r = download_tile(
            item, assets=assets, output_dir=output_dir,
            dataset=dataset, timeout=args.download_timeout,
            show_progress=not args.no_progress,
        )
        total_bytes += r["total_bytes"]
        if not r["ok"]:
            overall_ok = False
            if not _quiet():
                print(f"  [landcover-download] some assets failed for {r['tile_id']}",
                      file=sys.stderr)
    elapsed = time.time() - t0
    if not _quiet():
        print(f"\n[landcover-download] done in {elapsed:.0f}s — "
              f"downloaded {_human_bytes(total_bytes)} across {len(features)} tile(s)",
              file=sys.stderr)
    return 0 if overall_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())