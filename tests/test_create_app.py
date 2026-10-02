"""Tests for Flask app factory."""
from unittest.mock import patch


class TestCreateApp:
    @patch("lib.app_config.validate_config", return_value=True)
    @patch("lib.app_config.setup_logging")
    def test_create_app_returns_flask_app(self, mock_log, _validate):
        mock_log.return_value = __import__("logging").getLogger("test")
        from migration_insights import create_app

        app = create_app()
        assert app is not None

    @patch("lib.app_config.validate_config", return_value=True)
    @patch("lib.app_config.setup_logging")
    def test_blueprints_registered(self, mock_log, _validate):
        mock_log.return_value = __import__("logging").getLogger("test")
        from migration_insights import create_app

        app = create_app()
        rules = {rule.rule for rule in app.url_map.iter_rules()}
        assert "/live/" in rules
        assert "/logs/" not in rules

    def test_home_is_monitoring_setup(self, app_client):
        r = app_client.get("/")
        assert r.status_code == 200
        assert b"Migration monitoring setup" in r.data
        assert b"Open log analyzer" not in r.data

    def test_live_home_still_available(self, app_client):
        r = app_client.get("/live/")
        assert r.status_code == 200
        assert b"Migration monitoring setup" in r.data

    def test_health_route(self, app_client):
        r = app_client.get("/health")
        assert r.status_code == 200
        assert r.get_data(as_text=True) == "ok"


class TestSecurityHeaders:
    def test_img_src_does_not_allow_arbitrary_remote_hosts(self, app_client):
        """Blanket https: in img-src would leave an exfiltration beacon open."""
        csp = app_client.get("/").headers["Content-Security-Policy"]
        img_src = next(
            part.strip()
            for part in csp.split(";")
            if part.strip().startswith("img-src")
        )
        assert img_src == "img-src 'self' data: blob:"

    def test_script_src_does_not_allow_plotly_cdn(self, app_client):
        csp = app_client.get("/").headers["Content-Security-Policy"]
        script_src = next(
            part.strip()
            for part in csp.split(";")
            if part.strip().startswith("script-src")
        )
        assert "cdn.plot.ly" not in script_src
