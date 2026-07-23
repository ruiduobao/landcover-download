"""Tests for download functionality."""

import os
import pytest
import tempfile


class TestDownloadAsset:
    """Test download_asset function."""

    def test_download_asset_success(self, landcover_module, tmp_path):
        """Test successful download."""
        dest = str(tmp_path / "test.tif")

        class MockResponse:
            def __init__(self):
                self.headers = {"Content-Length": "10"}
                self.status_code = 200

            def raise_for_status(self):
                pass

            def iter_content(self, chunk_size=1):
                yield b"0123456789"

            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

        import requests
        original_get = requests.get
        requests.get = lambda *args, **kwargs: MockResponse()

        try:
            ok, msg = landcover_module.download_asset(
                "https://example.com/test.tif",
                dest,
                show_progress=False,
            )
            assert ok is True
            assert msg == "ok"
            assert os.path.exists(dest)
            assert not os.path.exists(dest + ".part")
        finally:
            requests.get = original_get

    def test_download_asset_already_exists(self, landcover_module, tmp_path):
        """Test skip when file already exists."""
        dest = str(tmp_path / "existing.tif")
        with open(dest, "wb") as f:
            f.write(b"existing data")

        ok, msg = landcover_module.download_asset(
            "https://example.com/test.tif",
            dest,
            show_progress=False,
        )
        assert ok is True
        assert "already exists" in msg

    def test_download_asset_failure(self, landcover_module, tmp_path):
        """Test download failure handling."""
        dest = str(tmp_path / "fail.tif")

        import requests
        original_get = requests.get
        requests.get = lambda *args, **kwargs: (_ for _ in ()).throw(
            requests.RequestException("Connection failed")
        )

        try:
            ok, msg = landcover_module.download_asset(
                "https://example.com/test.tif",
                dest,
                show_progress=False,
            )
            assert ok is False
            assert "Connection failed" in msg
            assert not os.path.exists(dest)
            assert not os.path.exists(dest + ".part")
        finally:
            requests.get = original_get

    def test_download_asset_progress(self, landcover_module, tmp_path, capsys):
        """Test progress display."""
        dest = str(tmp_path / "progress.tif")

        class MockResponse:
            def __init__(self):
                self.headers = {"Content-Length": "1000"}
                self.status_code = 200

            def raise_for_status(self):
                pass

            def iter_content(self, chunk_size=1):
                for i in range(10):
                    yield b"x" * 100

            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

        import requests
        original_get = requests.get
        requests.get = lambda *args, **kwargs: MockResponse()

        try:
            ok, msg = landcover_module.download_asset(
                "https://example.com/test.tif",
                dest,
                show_progress=True,
            )
            assert ok is True
        finally:
            requests.get = original_get


class TestDownloadTile:
    """Test download_tile function."""

    def test_download_tile_success(self, landcover_module, tmp_path, sample_worldcover_item):
        """Test successful tile download."""
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
                assets=["map"],
                output_dir=str(tmp_path),
                dataset="worldcover",
                show_progress=False,
            )
            assert result["ok"] is True
            assert result["tile_id"] == "ESA_WorldCover_10m_2021_v200_N39E116"
            assert len(result["files"]) == 1
        finally:
            requests.get = original_get

    def test_download_tile_missing_asset(self, landcover_module, tmp_path, sample_worldcover_item):
        """Test tile download with missing asset."""
        result = landcover_module.download_tile(
            sample_worldcover_item,
            assets=["nonexistent"],
            output_dir=str(tmp_path),
            dataset="worldcover",
            show_progress=False,
        )
        assert result["ok"] is False
        assert result["files"][0]["ok"] is False

    def test_download_tile_creates_directory(self, landcover_module, tmp_path, sample_worldcover_item):
        """Test that tile download creates output directory."""
        output_dir = str(tmp_path / "new_dir")

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
            landcover_module.download_tile(
                sample_worldcover_item,
                assets=["map"],
                output_dir=output_dir,
                dataset="worldcover",
                show_progress=False,
            )
            assert os.path.exists(output_dir)
        finally:
            requests.get = original_get


class TestHumanBytes:
    """Test _human_bytes helper."""

    def test_bytes(self, landcover_module):
        assert landcover_module._human_bytes(100) == "100 B"

    def test_kilobytes(self, landcover_module):
        assert landcover_module._human_bytes(1024) == "1.0 KB"

    def test_megabytes(self, landcover_module):
        assert landcover_module._human_bytes(1024 * 1024) == "1.0 MB"

    def test_gigabytes(self, landcover_module):
        assert landcover_module._human_bytes(1024 * 1024 * 1024) == "1.0 GB"


class TestProgressRendering:
    """Test progress bar rendering."""

    def test_render_progress_with_total(self, landcover_module):
        line = landcover_module._render_progress(500, 1000, 100.0, 5.0)
        assert "50.0%" in line
        assert "500" in line or "0.5 KB" in line

    def test_render_progress_without_total(self, landcover_module):
        line = landcover_module._render_progress(500, None, 100.0, None)
        assert "?" in line

    def test_render_progress_eta(self, landcover_module):
        line = landcover_module._render_progress(500, 1000, 100.0, 125.0)
        assert "2:05" in line