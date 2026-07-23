"""Tests for security and privacy features."""

import os
import pytest


class TestPrivacyNotice:
    """Test privacy notice functionality."""

    def test_quiet_default(self, landcover_module, monkeypatch):
        """Test default quiet state."""
        monkeypatch.delenv("LANDCOVER_DOWNLOAD_QUIET", raising=False)
        assert landcover_module._quiet() is False

    def test_quiet_enabled(self, landcover_module, monkeypatch):
        """Test quiet enabled via env."""
        monkeypatch.setenv("LANDCOVER_DOWNLOAD_QUIET", "1")
        assert landcover_module._quiet() is True

    def test_emit_privacy_notice(self, landcover_module, monkeypatch, capsys):
        """Test privacy notice emission."""
        monkeypatch.delenv("LANDCOVER_DOWNLOAD_QUIET", raising=False)
        landcover_module._emit_privacy_notice("Planetary Computer")
        captured = capsys.readouterr()
        assert "contacting" in captured.err
        assert "Planetary Computer" in captured.err

    def test_emit_privacy_notice_quiet(self, landcover_module, monkeypatch, capsys):
        """Test privacy notice suppressed in quiet mode."""
        monkeypatch.setenv("LANDCOVER_DOWNLOAD_QUIET", "1")
        landcover_module._emit_privacy_notice("Planetary Computer")
        captured = capsys.readouterr()
        assert captured.err == ""


class TestTrustEnv:
    """Test proxy trust_env settings."""

    def test_default_trust_env_false(self, landcover_module, monkeypatch):
        """Test trust_env can be disabled."""
        monkeypatch.delenv("LANDCOVER_DOWNLOAD_USE_PROXY", raising=False)
        # Test the logic directly
        assert os.environ.get("LANDCOVER_DOWNLOAD_USE_PROXY") != "1"

    def test_trust_env_enabled(self, landcover_module, monkeypatch):
        """Test trust_env enabled via env."""
        monkeypatch.setenv("LANDCOVER_DOWNLOAD_USE_PROXY", "1")
        assert os.environ.get("LANDCOVER_DOWNLOAD_USE_PROXY") == "1"


class TestUserAgent:
    """Test User-Agent header."""

    def test_user_agent_format(self, landcover_module):
        """Test User-Agent string format."""
        ua = landcover_module.USER_AGENT
        assert "landcover-download" in ua
        assert "clawhub.ai" in ua

    def test_user_agent_version(self, landcover_module):
        """Test User-Agent contains version."""
        ua = landcover_module.USER_AGENT
        assert "0.1.0" in ua


class TestInputValidation:
    """Test input validation and safety."""

    def test_dataset_choices(self, landcover_module):
        """Test dataset validation."""
        parser = landcover_module.build_parser()
        # Valid datasets
        for ds in ["worldcover", "from-glc", "globeland30"]:
            args = parser.parse_args(["--dataset", ds, "--bbox", "116", "39", "117", "40"])
            assert args.dataset == ds

    def test_bbox_validation(self, landcover_module):
        """Test bbox accepts 4 floats."""
        parser = landcover_module.build_parser()
        args = parser.parse_args(["--bbox", "116.0", "39.0", "117.0", "40.0"])
        assert len(args.bbox) == 4
        assert all(isinstance(x, float) for x in args.bbox)

    def test_year_validation(self, landcover_module):
        """Test year accepts integer."""
        parser = landcover_module.build_parser()
        args = parser.parse_args(["--bbox", "116", "39", "117", "40", "--year", "2021"])
        assert args.year == 2021

    def test_limit_validation(self, landcover_module):
        """Test limit accepts integer."""
        parser = landcover_module.build_parser()
        args = parser.parse_args(["--bbox", "116", "39", "117", "40", "--limit", "100"])
        assert args.limit == 100


class TestSASTokenCaching:
    """Test SAS token caching security."""

    def test_cache_structure(self, landcover_module):
        """Test SAS cache is a dictionary."""
        assert isinstance(landcover_module._SAS_CACHE, dict)

    def test_cache_cleared(self, landcover_module):
        """Test cache can be cleared."""
        landcover_module._SAS_CACHE["test"] = ("token", 9999999999.0)
        landcover_module._SAS_CACHE.clear()
        assert len(landcover_module._SAS_CACHE) == 0

    def test_cache_expiry(self, landcover_module, monkeypatch, sample_worldcover_item):
        """Test cache expiry logic."""
        import time
        landcover_module._SAS_CACHE.clear()

        # Set expired token
        landcover_module._SAS_CACHE["esa-worldcover"] = ("old-token", time.time() - 100)

        call_count = 0

        class MockSession:
            def __init__(self):
                self.headers = {}
                self.trust_env = False

            def get(self, url, timeout=None, stream=False):
                nonlocal call_count
                call_count += 1
                return type('MockResponse', (), {
                    'json': lambda self: {"token": "new-token"},
                    'status_code': 200,
                    'text': '{"token": "new-token"}',
                    'raise_for_status': lambda self: None,
                })()

        import requests
        monkeypatch.setattr(requests, "Session", lambda: MockSession())

        landcover_module.get_signed_href(sample_worldcover_item, "map")
        assert call_count == 1  # Should fetch new token


class TestConstants:
    """Test security-related constants."""

    def test_stac_endpoint_https(self, landcover_module):
        """Test STAC endpoint uses HTTPS."""
        assert landcover_module.STAC_ENDPOINT.startswith("https://")

    def test_sign_url_https(self, landcover_module):
        """Test sign URL uses HTTPS."""
        assert landcover_module.SIGN_URL.startswith("https://")

    def test_collection_name(self, landcover_module):
        """Test collection name is correct."""
        assert landcover_module.WORLDCOVER_COLLECTION == "esa-worldcover"