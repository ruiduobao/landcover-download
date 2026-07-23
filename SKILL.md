---
name: landcover-download
display_name: Global Land Cover Downloader
version: 0.1.0
author: rui.duobao
license: MIT-0
description: |
  Download global land cover data from multiple sources including
  ESA WorldCover (10m), FROM-GLC (30m), and GlobeLand30 (30m).
  Supports STAC search and regional bbox subsetting.
runtime: python>=3.8
tags: [gis, remote-sensing, landcover, worldcover, stac, planetary-computer, earth-observation, 下载]
---

# Global Land Cover Downloader

A powerful tool for downloading global land cover data from multiple sources.

## Features

- **Multi-Dataset Support**: ESA WorldCover (10m), FROM-GLC (30m), GlobeLand30 (30m)
- **STAC Integration**: Uses Planetary Computer STAC API for ESA WorldCover
- **Regional Download**: Support bbox for area-of-interest selection
- **Year Selection**: Choose data year for temporal analysis
- **Progress Tracking**: Visual progress bar with ETA
- **Safe Downloads**: .part file pattern prevents incomplete downloads
- **No API Keys**: All data sources are public and free

## Usage

### Basic Search

```bash
# Search ESA WorldCover tiles for a region
python landcover-download.py \
    --dataset worldcover \
    --bbox 116.0 39.0 117.0 40.0
```

### Download Data

```bash
# Download WorldCover tiles
python landcover-download.py \
    --dataset worldcover \
    --bbox 116.0 39.0 117.0 40.0 \
    --year 2021 \
    --download \
    --output-dir ./landcover_data
```

### List Available Datasets

```bash
python landcover-download.py --list-datasets
```

### List Classification Values

```bash
python landcover-download.py --list-classes
```

## Datasets

### ESA WorldCover (Default)
- **Resolution**: 10m
- **Years**: 2020, 2021
- **Source**: Planetary Computer STAC
- **Assets**: `map` (classification), `input_data`

### FROM-GLC
- **Resolution**: 30m
- **Years**: 2010, 2015, 2017
- **Source**: Tsinghua University

### GlobeLand30
- **Resolution**: 30m
- **Years**: 2000, 2010, 2020
- **Source**: National Geomatics Center of China

## WorldCover Classification Values

| Code | Class |
|------|-------|
| 10 | Tree cover |
| 20 | Shrubland |
| 30 | Grassland |
| 40 | Cropland |
| 50 | Built-up |
| 60 | Bare / sparse vegetation |
| 70 | Snow and ice |
| 80 | Permanent water bodies |
| 90 | Herbaceous wetland |
| 95 | Mangroves |
| 100 | Moss and lichen |

## CLI Options

```
--dataset {worldcover,from-glc,globeland30}
                      Dataset to download (default: worldcover)
--bbox MIN_LON MIN_LAT MAX_LON MAX_LAT
                      Geographic extent in WGS84
--year YEAR           Data year (default: latest available)
--limit LIMIT         Max tiles to return (default 50)
--assets ASSETS [ASSETS ...]
                      Assets to download (default: map for worldcover)
--download            Trigger actual download (default: search only)
--output-dir DIR      Download directory (default ./landcover_data)
--output-format {text,json}
                      Output format
--no-progress         Disable visual progress bar
--download-timeout SEC
                      Per-asset download timeout in seconds (default 600)
--list-datasets       List all available datasets and exit
--list-classes        List land cover classification values (WorldCover)
--quiet               Suppress progress + privacy notice
```

## Environment Variables

- `LANDCOVER_DOWNLOAD_QUIET=1`: Suppress progress and privacy notices
- `LANDCOVER_DOWNLOAD_USE_PROXY=1`: Use system proxy settings

## License

MIT-0. Land cover data © respective providers.

## Data Sources

- **ESA WorldCover**: Provided by ESA under Creative Commons license
- **FROM-GLC**: Provided by Tsinghua University
- **GlobeLand30**: Provided by National Geomatics Center of China