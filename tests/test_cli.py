"""Tests for CLI argument parsing and main function."""

import pytest


class TestCLIParsing:
    """Test CLI argument parsing."""

    def test_build_parser(self, landcover_module):
        """Test parser creation."""
        parser = landcover_module.build_parser()
        assert parser is not None
        assert parser.prog == "landcover-download"

    def test_parser_default_values(self, landcover_module):
        """Test default argument values."""
        parser = landcover_module.build_parser()
        args = parser.parse_args(["--bbox", "116", "39", "117", "40"])
        assert args.dataset == "worldcover"
        assert args.year is None
        assert args.limit == 50
        assert args.download is False
        assert args.output_dir == "./landcover_data"
        assert args.output_format == "text"
        assert args.quiet is False

    def test_parser_custom_values(self, landcover_module):
        """Test custom argument values."""
        parser = landcover_module.build_parser()
        args = parser.parse_args([
            "--dataset", "worldcover",
            "--bbox", "116", "39", "117", "40",
            "--year", "2021",
            "--limit", "10",
            "--download",
            "--output-dir", "/tmp/test",
            "--output-format", "json",
            "--quiet",
        ])
        assert args.dataset == "worldcover"
        assert args.year == 2021
        assert args.limit == 10
        assert args.download is True
        assert args.output_dir == "/tmp/test"
        assert args.output_format == "json"
        assert args.quiet is True

    def test_parser_bbox(self, landcover_module):
        """Test bbox argument."""
        parser = landcover_module.build_parser()
        args = parser.parse_args(["--bbox", "116.0", "39.0", "117.0", "40.0"])
        assert args.bbox == [116.0, 39.0, 117.0, 40.0]

    def test_parser_assets(self, landcover_module):
        """Test assets argument."""
        parser = landcover_module.build_parser()
        args = parser.parse_args([
            "--bbox", "116", "39", "117", "40",
            "--assets", "map", "input_data",
        ])
        assert args.assets == ["map", "input_data"]


class TestMainFunction:
    """Test main function behavior."""

    def test_main_missing_bbox(self, landcover_module, capsys):
        """Test main returns 2 when bbox is missing."""
        ret = landcover_module.main(["--dataset", "worldcover"])
        assert ret == 2
        captured = capsys.readouterr()
        assert "ERROR" in captured.err

    def test_main_list_datasets(self, landcover_module, capsys):
        """Test --list-datasets flag."""
        ret = landcover_module.main(["--list-datasets"])
        assert ret == 0
        captured = capsys.readouterr()
        assert "ESA WorldCover" in captured.out
        assert "FROM-GLC" in captured.out
        assert "GlobeLand30" in captured.out

    def test_main_list_classes(self, landcover_module, capsys):
        """Test --list-classes flag."""
        ret = landcover_module.main(["--list-classes"])
        assert ret == 0
        captured = capsys.readouterr()
        assert "Tree cover" in captured.out
        assert "Built-up" in captured.out


class TestOutputFormatting:
    """Test output formatting functions."""

    def test_format_results_text(self, landcover_module, sample_stac_response):
        """Test text formatting."""
        query_meta = {"dataset": "worldcover", "bbox": [116, 39, 117, 40]}
        features = sample_stac_response["features"]
        result = landcover_module.format_results_text(query_meta, features)
        assert "ESA_WorldCover" in result
        assert "found 1 tile" in result

    def test_format_results_text_empty(self, landcover_module):
        """Test text formatting with empty results."""
        query_meta = {"dataset": "worldcover"}
        result = landcover_module.format_results_text(query_meta, [])
        assert "no tiles match" in result

    def test_format_results_json(self, landcover_module, sample_stac_response):
        """Test JSON formatting."""
        query_meta = {"dataset": "worldcover", "bbox": [116, 39, 117, 40]}
        features = sample_stac_response["features"]
        result = landcover_module.format_results_json(query_meta, features)
        import json
        parsed = json.loads(result)
        assert parsed["count"] == 1
        assert parsed["tiles"][0]["id"] == "ESA_WorldCover_10m_2021_v200_N39E116"