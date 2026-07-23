"""Integration tests for landcover-download."""

import json
import os
import pytest


class TestIntegrationSearch:
    """Integration tests for search functionality."""

    def test_search_worldcover(self, landcover_module, mock_requests, sample_stac_response):
        """Integration test: search WorldCover with mocked network."""
        mock_requests.post = lambda url, json=None, timeout=None: type('Response', (), {
            'json': lambda self: sample_stac_response,
            'status_code': 200,
            'raise_for_status': lambda self: None,
        })()

        result = landcover_module.stac_search_worldcover(
            bbox=(116.0, 39.0, 117.0, 40.0),
            year=2021,
            limit=10,
        )
        assert "features" in result
        assert len(result["features"]) > 0
        assert result["features"][0]["id"] == "ESA_WorldCover_10m_2021_v200_N39E116"

    def test_search_and_format(self, landcover_module, mock_requests, sample_stac_response):
        """Integration test: search and format results."""
        mock_requests.post = lambda url, json=None, timeout=None: type('Response', (), {
            'json': lambda self: sample_stac_response,
            'status_code': 200,
            'raise_for_status': lambda self: None,
        })()

        resp = landcover_module.stac_search_worldcover(
            bbox=(116.0, 39.0, 117.0, 40.0),
            year=2021,
        )
        features = resp.get("features", [])
        query_meta = {"dataset": "worldcover", "bbox": [116, 39, 117, 40]}

        text_output = landcover_module.format_results_text(query_meta, features)
        assert "ESA_WorldCover" in text_output
        assert "found 1 tile" in text_output

        json_output = landcover_module.format_results_json(query_meta, features)
        parsed = json.loads(json_output)
        assert parsed["count"] == 1

    def test_search_with_different_years(self, landcover_module, mock_requests, sample_stac_response):
        """Integration test: search with different years."""
        captured_json = {}

        def mock_post(url, json=None, timeout=None):
            captured_json.update(json or {})
            return type('Response', (), {
                'json': lambda self: sample_stac_response,
                'status_code': 200,
                'raise_for_status': lambda self: None,
            })()

        mock_requests.post = mock_post

        # Test 2020
        landcover_module.stac_search_worldcover(
            bbox=(116.0, 39.0, 117.0, 40.0),
            year=2020,
        )
        assert "2020" in captured_json.get("datetime", "")

        # Test 2021
        landcover_module.stac_search_worldcover(
            bbox=(116.0, 39.0, 117.0, 40.0),
            year=2021,
        )
        assert "2021" in captured_json.get("datetime", "")


class TestIntegrationDownload:
    """Integration tests for download functionality."""

    def test_download_workflow(self, landcover_module, tmp_path, sample_worldcover_item, mock_requests):
        """Integration test: complete download workflow."""
        class MockResponse:
            def __init__(self):
                self.headers = {"Content-Length": "100"}
                self.status_code = 200

            def raise_for_status(self):
                pass

            def iter_content(self, chunk_size=1):
                yield b"test data"

            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

        import requests
        original_get = requests.get
        requests.get = lambda *args, **kwargs: MockResponse()

        try:
            # Download tile
            result = landcover_module.download_tile(
                sample_worldcover_item,
                assets=["map"],
                output_dir=str(tmp_path),
                dataset="worldcover",
                show_progress=False,
            )

            assert result["ok"] is True
            assert result["tile_id"] == "ESA_WorldCover_10m_2021_v200_N39E116"
            assert len(result["files"]) == 1
            assert result["files"][0]["ok"] is True

            # Check file exists
            tile_dir = tmp_path / "ESA_WorldCover_10m_2021_v200_N39E116"
            assert tile_dir.exists()
            assert (tile_dir / "map.tif").exists()
        finally:
            requests.get = original_get

    def test_download_multiple_assets(self, landcover_module, tmp_path, sample_worldcover_item, mock_requests):
        """Integration test: download multiple assets."""
        class MockResponse:
            def __init__(self):
                self.headers = {"Content-Length": "100"}
                self.status_code = 200

            def raise_for_status(self):
                pass

            def iter_content(self, chunk_size=1):
                yield b"test data"

            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

        import requests
        original_get = requests.get
        requests.get = lambda *args, **kwargs: MockResponse()

        try:
            result = landcover_module.download_tile(
                sample_worldcover_item,
                assets=["map", "input_data"],
                output_dir=str(tmp_path),
                dataset="worldcover",
                show_progress=False,
            )

            assert result["ok"] is True
            assert len(result["files"]) == 2
            assert all(f["ok"] for f in result["files"])
        finally:
            requests.get = original_get

    def test_download_skip_existing(self, landcover_module, tmp_path, sample_worldcover_item, mock_requests):
        """Integration test: skip existing files."""
        # Create existing file
        tile_dir = tmp_path / "ESA_WorldCover_10m_2021_v200_N39E116"
        tile_dir.mkdir(parents=True)
        (tile_dir / "map.tif").write_bytes(b"existing data")

        result = landcover_module.download_tile(
            sample_worldcover_item,
            assets=["map"],
            output_dir=str(tmp_path),
            dataset="worldcover",
            show_progress=False,
        )

        assert result["ok"] is True
        assert result["files"][0]["message"] == "already exists, skipping"


class TestIntegrationCLI:
    """Integration tests for CLI main function."""

    def test_main_search_only(self, landcover_module, mock_requests, sample_stac_response, capsys):
        """Integration test: main function search only."""
        mock_requests.post = lambda url, json=None, timeout=None: type('Response', (), {
            'json': lambda self: sample_stac_response,
            'status_code': 200,
            'raise_for_status': lambda self: None,
        })()

        ret = landcover_module.main([
            "--dataset", "worldcover",
            "--bbox", "116", "39", "117", "40",
            "--year", "2021",
            "--quiet",
        ])
        assert ret == 0
        captured = capsys.readouterr()
        assert "ESA_WorldCover" in captured.out

    def test_main_search_json(self, landcover_module, mock_requests, sample_stac_response, capsys):
        """Integration test: main function JSON output."""
        mock_requests.post = lambda url, json=None, timeout=None: type('Response', (), {
            'json': lambda self: sample_stac_response,
            'status_code': 200,
            'raise_for_status': lambda self: None,
        })()

        ret = landcover_module.main([
            "--dataset", "worldcover",
            "--bbox", "116", "39", "117", "40",
            "--output-format", "json",
            "--quiet",
        ])
        assert ret == 0
        captured = capsys.readouterr()
        parsed = json.loads(captured.out)
        assert parsed["count"] == 1

    def test_main_download(self, landcover_module, tmp_path, mock_requests, sample_stac_response):
        """Integration test: main function with download."""
        class MockResponse:
            def __init__(self):
                self.headers = {"Content-Length": "100"}
                self.status_code = 200

            def raise_for_status(self):
                pass

            def iter_content(self, chunk_size=1):
                yield b"test data"

            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

        import requests
        original_get = requests.get
        requests.get = lambda *args, **kwargs: MockResponse()

        def mock_post(url, json=None, timeout=None):
            return type('Response', (), {
                'json': lambda self: sample_stac_response,
                'status_code': 200,
                'raise_for_status': lambda self: None,
            })()

        mock_requests.post = mock_post

        try:
            ret = landcover_module.main([
                "--dataset", "worldcover",
                "--bbox", "116", "39", "117", "40",
                "--year", "2021",
                "--download",
                "--output-dir", str(tmp_path / "output"),
                "--quiet",
            ])
            assert ret == 0
            assert (tmp_path / "output").exists()
        finally:
            requests.get = original_get


class TestEndToEnd:
    """End-to-end tests simulating real usage."""

    def test_search_list_classes(self, landcover_module, capsys):
        """E2E: list datasets then classes."""
        ret1 = landcover_module.main(["--list-datasets"])
        assert ret1 == 0

        ret2 = landcover_module.main(["--list-classes"])
        assert ret2 == 0
        captured = capsys.readouterr()
        assert "Tree cover" in captured.out
        assert "Built-up" in captured.out

    def test_search_format_switch(self, landcover_module, mock_requests, sample_stac_response, capsys):
        """E2E: switch between text and JSON formats."""
        mock_requests.post = lambda url, json=None, timeout=None: type('Response', (), {
            'json': lambda self: sample_stac_response,
            'status_code': 200,
            'raise_for_status': lambda self: None,
        })()

        # Text format
        landcover_module.main([
            "--bbox", "116", "39", "117", "40",
            "--output-format", "text",
            "--quiet",
        ])
        text_out = capsys.readouterr().out
        assert "found" in text_out

        # JSON format
        landcover_module.main([
            "--bbox", "116", "39", "117", "40",
            "--output-format", "json",
            "--quiet",
        ])
        json_out = capsys.readouterr().out
        parsed = json.loads(json_out)
        assert "count" in parsed