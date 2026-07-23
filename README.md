# Global Land Cover Downloader · 全球土地覆盖下载器

> 下载全球 **土地覆盖分类**数据。
> 支持 **ESA WorldCover**（10m）、FROM-GLC（30m）、GlobeLand30（30m）。
> MIT-0 开源。

[English](#quickstart) | 中文

## 为什么做这个

土地覆盖数据是生态、城市规划、碳循环、气候变化研究的基础数据。
ESA WorldCover 提供 10m 分辨率的全球覆盖产品，通过 Planetary Computer
可公开访问。本 skill 一键搜索和下载，无需手动选择瓦片。

## Quickstart / 快速开始

```bash
# 安装依赖
pip install 'requests>=2.28.0'

# 搜索 WorldCover 数据
python landcover-download.py search \
    --bbox 116.0 39.0 117.0 40.0 \
    --dataset worldcover \
    --year 2021

# 下载土地覆盖数据
python landcover-download.py download \
    --bbox 116.0 39.0 117.0 40.0 \
    --dataset worldcover \
    --year 2021 \
    --output-dir ./landcover_data
```

## 数据源 / Data Source

| 数据集 | 分辨率 | 来源 | 凭证 |
|---|---|---|---|
| **ESA WorldCover**（默认） | 10m | Planetary Computer | 无 |
| FROM-GLC | 30m | Tsinghua University | 无 |
| GlobeLand30 | 30m | NGCC (中国) | 无 |

> **License** — ESA WorldCover 由 ESA 发布，**CC-BY 4.0** 开放。

## 支持的数据集 / Supported Datasets

| 数据集 | 年份 | 分辨率 | 分类体系 |
|---|---|---|---|
| `worldcover` | 2020, 2021 | 10m | 11 类（树木、草地、水体等） |
| `from-glc` | 2010, 2015, 2017 | 30m | 10 类 |
| `globeland30` | 2000, 2010, 2020 | 30m | 10 类 |

## 参数一览 / Parameters

| 参数 | 说明 | 必填 |
|---|---|---|
| `--bbox` | 地理范围 `[minLon minLat maxLon maxLat]` | ✅ |
| `--dataset` | `worldcover` / `from-glc` / `globeland30` | ❌ |
| `--year` | 年份 | ❌ |
| `--download` | 触发实际下载 | ❌ |
| `--output-dir` | 下载目录（默认 `./landcover_data`） | ❌ |

## License

MIT-0（详见 [LICENSE](./LICENSE)）。
ESA WorldCover © ESA，CC-BY 4.0。
