"""End-to-end upload tests using committed fixtures."""
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from lib import snapshot_store
from lib.log_store_registry import log_store_registry

FIXTURES = Path(__file__).parent / "fixtures"


def _plot_payload(html):
    """Return the JSON object assigned to the `plot` key of the page payload."""
    start = html.find("plot: ", html.find("__MI_UPLOAD_PAGE__")) + len("plot: ")
    depth = 0
    for index, char in enumerate(html[start:]):
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return html[start:start + index + 1]
    raise AssertionError("could not delimit plot payload")


@pytest.fixture(autouse=True)
def _isolated_registry(monkeypatch, tmp_path):
    monkeypatch.setattr(snapshot_store, "LOG_STORE_DIR", str(tmp_path / "store"))
    (tmp_path / "store").mkdir(exist_ok=True)
    log_store_registry._entries.clear()
    yield
    log_store_registry._entries.clear()


class TestUploadFixtures:
    @patch("lib.logs_metrics.create_metrics_plots", return_value="")
    def test_upload_sample_log_fixture(self, _mock_plots, app_client):
        log_path = FIXTURES / "sample_mongosync.log"
        with open(log_path, "rb") as f:
            data = {"file": (f, "mongosync.log")}
            r = app_client.post(
                "/logs/uploadLogs", data=data, content_type="multipart/form-data"
            )
        assert r.status_code == 200
        assert b'id="tab-summary"' in r.data
        assert b"Summary" in r.data
        snapshots = snapshot_store.list_snapshots()
        assert len(snapshots) >= 1
        assert snapshots[0]["line_count"] > 0

    @patch("lib.logs_metrics.create_metrics_plots", return_value="")
    def test_table_traces_always_have_a_row(self, _mock_plots, app_client):
        """Plotly 3.x throws on a table trace with no rows, which blanks the page."""
        log_path = FIXTURES / "sample_mongosync.log"
        with open(log_path, "rb") as f:
            data = {"file": (f, "mongosync.log")}
            r = app_client.post(
                "/logs/uploadLogs", data=data, content_type="multipart/form-data"
            )
        assert r.status_code == 200
        figure = json.loads(_plot_payload(r.get_data(as_text=True)))
        tables = [t for t in figure["data"] if t.get("type") == "table"]
        assert tables
        for table in tables:
            for column in table["cells"]["values"]:
                assert column, f"empty column in table {table['header']['values']}"

    @patch("lib.logs_metrics.create_metrics_plots", return_value="{}")
    def test_upload_metrics_fixture(self, _mock_plots, app_client):
        metrics_path = FIXTURES / "sample_mongosync_metrics.log"
        with open(metrics_path, "rb") as f:
            data = {"file": (f, "mongosync_metrics.log")}
            r = app_client.post(
                "/logs/uploadLogs", data=data, content_type="multipart/form-data"
            )
        assert r.status_code == 200

    @patch("lib.logs_metrics.create_metrics_plots", return_value="")
    def test_search_after_upload(self, _mock_plots, app_client):
        log_path = FIXTURES / "sample_mongosync.log"
        with open(log_path, "rb") as f:
            data = {"file": (f, "mongosync.log")}
            app_client.post(
                "/logs/uploadLogs", data=data, content_type="multipart/form-data"
            )
        snapshots = snapshot_store.list_snapshots()
        store_id = snapshots[0]["log_store_id"]
        r = app_client.get(f"/logs/search_logs?store_id={store_id}&q=Replication")
        assert r.status_code == 200
        assert r.get_json()["total"] >= 1
