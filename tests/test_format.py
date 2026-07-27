"""Tests for the --format (categories statistics) flag."""
import json
import os
import csv
import pytest


class TestFormatFlagParser:
    """Verify --format / --format-output exist and behave correctly."""

    def test_help_lists_format(self, landcover_module):
        import subprocess
        out = subprocess.run(
            [sys.executable,
             os.path.join(os.path.dirname(__file__), "..", "landcover-download.py"),
             "--help"],
            capture_output=True, text=True, timeout=10,
        )
        text = out.stdout + out.stderr
        assert "--format" in text
        assert "geojson" in text
        assert "csv" in text
        assert "--format-output" in text

    def test_default_format_is_none(self, landcover_module):
        parser = landcover_module.build_parser()
        args = parser.parse_args(["--bbox", "116", "39", "117", "40"])
        assert args.format is None
        assert args.format_output == "./landcover_categories"

    def test_format_geojson_choice(self, landcover_module):
        parser = landcover_module.build_parser()
        args = parser.parse_args([
            "--bbox", "116", "39", "117", "40",
            "--format", "geojson",
        ])
        assert args.format == "geojson"

    def test_format_csv_choice(self, landcover_module):
        parser = landcover_module.build_parser()
        args = parser.parse_args([
            "--bbox", "116", "39", "117", "40",
            "--format", "csv",
        ])
        assert args.format == "csv"


class TestWriteCategoriesStats:
    """Direct unit tests for write_categories_stats()."""

    @pytest.fixture
    def tmp(self, tmp_path):
        yield str(tmp_path)

    def test_geojson_categories_file(self, landcover_module, tmp):
        out = os.path.join(tmp, "cats.geojson")
        landcover_module.write_categories_stats(
            "geojson", out,
            bbox=(116.0, 39.0, 117.0, 40.0),
            dataset="worldcover", year=2021,
            counts={10: 100, 20: 50, 30: 0, 40: 0, 50: 0,
                    60: 0, 70: 0, 80: 0, 90: 0, 95: 0, 100: 0},
        )
        assert os.path.exists(out)
        with open(out, encoding="utf-8") as f:
            d = json.load(f)
        assert d["type"] == "FeatureCollection"
        # One feature per WorldCover class
        assert len(d["features"]) == len(landcover_module.WORLDCOVER_CLASSES)
        # Verify percentages sum to 100
        total_pct = sum(f["properties"]["percent"] for f in d["features"])
        assert abs(total_pct - 100.0) < 1e-6
        # Verify a known class
        tree = next(f for f in d["features"] if f["properties"]["class_code"] == 10)
        assert tree["properties"]["class_name"] == "Tree cover"
        assert tree["properties"]["count"] == 100

    def test_csv_categories_file(self, landcover_module, tmp):
        out = os.path.join(tmp, "cats.csv")
        landcover_module.write_categories_stats(
            "csv", out,
            bbox=(116.0, 39.0, 117.0, 40.0),
            dataset="worldcover", year=2021,
            counts={10: 50, 20: 50},
        )
        assert os.path.exists(out)
        with open(out, encoding="utf-8", newline="") as f:
            rows = list(csv.reader(f))
        assert rows[0][0] == "dataset"
        # Each class has its own row
        assert len(rows) == 1 + len(landcover_module.WORLDCOVER_CLASSES)

    def test_geojson_with_no_counts_uses_zero(self, landcover_module, tmp):
        out = os.path.join(tmp, "cats.geojson")
        landcover_module.write_categories_stats(
            "geojson", out,
            bbox=(116.0, 39.0, 117.0, 40.0),
            dataset="worldcover", year=2021,
            counts=None,
        )
        with open(out, encoding="utf-8") as f:
            d = json.load(f)
        for feat in d["features"]:
            assert feat["properties"]["count"] == 0

    def test_geojson_non_worldcover_resets_counts(self, landcover_module, tmp):
        out = os.path.join(tmp, "cats.geojson")
        landcover_module.write_categories_stats(
            "geojson", out,
            bbox=(116.0, 39.0, 117.0, 40.0),
            dataset="from-glc", year=2015,
            counts={10: 999},
        )
        with open(out, encoding="utf-8") as f:
            d = json.load(f)
        for feat in d["features"]:
            assert feat["properties"]["dataset"] == "from-glc"
            assert feat["properties"]["count"] == 0

    def test_invalid_format_raises(self, landcover_module, tmp):
        out = os.path.join(tmp, "x.txt")
        with pytest.raises(ValueError):
            landcover_module.write_categories_stats(
                "xml", out,
                bbox=(116.0, 39.0, 117.0, 40.0),
                dataset="worldcover", year=2021,
            )


class TestFormatIntegration:
    """End-to-end: --format produces a file alongside the search output."""

    def test_format_csv_with_mocked_search(self, landcover_module, tmp_path, mock_requests,
                                            monkeypatch, capsys):
        import os
        out_path = str(tmp_path / "lc_cats")
        monkeypatch.setenv("LANDCOVER_DOWNLOAD_QUIET", "1")
        ret = landcover_module.main([
            "--bbox", "116", "39", "117", "40",
            "--format", "csv",
            "--format-output", out_path,
        ])
        # Search returns 0 features but the format file is still written
        assert ret == 0
        produced = out_path + ".csv"
        assert os.path.exists(produced)
        with open(produced, encoding="utf-8", newline="") as f:
            rows = list(csv.reader(f))
        # Header + 11 WorldCover classes
        assert len(rows) == 1 + len(landcover_module.WORLDCOVER_CLASSES)

    def test_format_geojson_with_mocked_search(self, landcover_module, tmp_path, mock_requests,
                                                monkeypatch):
        out_path = str(tmp_path / "lc_cats")
        monkeypatch.setenv("LANDCOVER_DOWNLOAD_QUIET", "1")
        ret = landcover_module.main([
            "--bbox", "116", "39", "117", "40",
            "--format", "geojson",
            "--format-output", out_path,
        ])
        assert ret == 0
        produced = out_path + ".geojson"
        assert os.path.exists(produced)
        with open(produced, encoding="utf-8") as f:
            d = json.load(f)
        assert d["type"] == "FeatureCollection"
        # The bbox should match what we requested
        assert d["bbox"] == [116.0, 39.0, 117.0, 40.0]


# Late imports to avoid pulling sys at module top
import sys
