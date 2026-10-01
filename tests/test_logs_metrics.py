"""Tests for log parsing helpers in lib/logs_metrics.py."""
import io
import json

import pytest

from lib.logs_metrics import (
    INFO_PHASE_TO_CANONICAL,
    _classify_partition_init_type,
    _extract_progress_flag_events,
    _is_crud_events_rate_log,
    _merge_phase_events,
    _phase_event_from_in_memory,
    _phase_event_from_info,
    _phase_events_from_api,
    cea_stage_drain_intervals,
    detect_mime_type,
    extract_cea_stage_series,
)
from lib.utils import resolve_replication_lag


class TestDetectMimeType:
    @pytest.mark.parametrize(
        "sample,filename,expected",
        [
            (b"\x1f\x8b\x08", "file.gz", "application/gzip"),
            (b"PK\x03\x04", "file.zip", "application/zip"),
            (b"BZh9", "file.bz2", "application/x-bzip2"),
            (b"x" * 300 + b"ustar" + b"x" * 10, "file.tar", "application/x-tar"),
            (b'{"level":"info"}', "data.json", "application/json"),
            (b"plain log line\n", "mongosync.log", "text/plain"),
            (b"\x00\x01\x02\xff", "unknown.bin", "application/octet-stream"),
        ],
    )
    def test_detect_mime_type(self, sample, filename, expected):
        assert detect_mime_type(sample, filename) == expected


class TestPhaseEventFromInfo:
    @pytest.mark.parametrize(
        "message,canonical",
        [
            (msg, canonical)
            for msg, canonical in INFO_PHASE_TO_CANONICAL.items()
        ],
    )
    def test_maps_info_messages(self, message, canonical):
        obj = {"time": "2026-01-01T12:00:00.123456Z", "message": message}
        event = _phase_event_from_info(obj)
        assert event is not None
        assert event[1] == canonical

    def test_unknown_message_returns_none(self):
        assert _phase_event_from_info({"time": "2026-01-01T12:00:00Z", "message": "other"}) is None

    @pytest.mark.parametrize(
        "message,canonical",
        [
            ("Starting collection copy phase.", "collection copy"),
            ("Starting change event application phase.", "change event application"),
            ("Starting initializing partitions phase.", "initializing partitions"),
        ],
    )
    def test_maps_info_messages_with_trailing_period(self, message, canonical):
        obj = {"time": "2026-01-01T12:00:00.123456Z", "message": message}
        event = _phase_event_from_info(obj)
        assert event is not None
        assert event[1] == canonical


class TestPhaseEventFromInMemory:
    def test_parses_phase_update(self):
        obj = {
            "time": "2026-01-01T12:00:00.123456Z",
            "message": "Updating the in-memory phase from `collection copy` to `change event application`.",
        }
        event = _phase_event_from_in_memory(obj)
        assert event[1] == "change event application"

    def test_excludes_uninitialized(self):
        obj = {
            "time": "2026-01-01T12:00:00.123456Z",
            "message": "Updating the in-memory phase from `foo` to `uninitialized`.",
        }
        assert _phase_event_from_in_memory(obj) is None


class TestPhaseEventsFromApi:
    def test_converts_phase_transitions(self):
        api = [{"Phase": "Collection Copy", "Ts": {"T": 1700000000}}]
        events = _phase_events_from_api(api)
        assert len(events) == 1
        assert events[0][1] == "collection copy"

    def test_skips_missing_timestamp(self):
        api = [{"Phase": "Collection Copy", "Ts": {}}]
        assert _phase_events_from_api(api) == []


class TestMergePhaseEvents:
    def test_earliest_timestamp_wins_per_phase(self):
        info = [
            {
                "time": "2026-01-02T12:00:00.123456Z",
                "message": "Starting collection copy phase",
            }
        ]
        debug = [
            {
                "time": "2026-01-01T12:00:00.123456Z",
                "message": "Updating the in-memory phase from `x` to `collection copy`.",
            }
        ]
        merged = _merge_phase_events(info, debug)
        labels = [label for _, label in merged]
        assert labels == ["collection copy"]
        assert merged[0][0].startswith("2026-01-01")

    def test_api_source_included(self):
        api = [{"Phase": "change event application", "Ts": {"T": 1700000100}}]
        merged = _merge_phase_events([], [], api_transitions=api)
        assert merged[0][1] == "change event application"

    def test_info_messages_with_trailing_period(self):
        info = [
            {
                "time": "2026-07-20T17:53:11.775615Z",
                "message": "Starting collection copy phase.",
            },
            {
                "time": "2026-07-21T03:49:22.808282Z",
                "message": "Starting change event application phase.",
            },
        ]
        merged = _merge_phase_events(info, [])
        by_phase = {label: ts for ts, label in merged}
        assert "collection copy" in by_phase
        assert "change event application" in by_phase
        assert by_phase["change event application"].startswith("2026-07-21T03:49:22")


class TestExtractProgressFlagEvents:
    def test_tracks_commit_and_write_transitions(self):
        responses = [
            {
                "time": "2026-01-01T12:00:00.123456Z",
                "body": json.dumps({"progress": {"canCommit": False, "canWrite": False}}),
            },
            {
                "time": "2026-01-01T12:01:00.123456Z",
                "body": json.dumps({"progress": {"canCommit": True, "canWrite": True}}),
            },
        ]
        events = _extract_progress_flag_events(responses)
        labels = [label for _, label in events]
        assert "Can Commit is True" in labels
        assert "Can Write is True" in labels

    def test_skips_invalid_json_body(self):
        responses = [{"time": "2026-01-01T12:00:00Z", "body": "not-json"}]
        assert _extract_progress_flag_events(responses) == []


class TestReplicationLagFromLogEntry:
    def test_legacy_log_entry(self):
        result = resolve_replication_lag({"lagTimeSeconds": 42})
        assert result["overall"] == 42
        assert result["has_breakdown"] is False

    def test_new_log_entry_with_breakdown(self):
        entry = {
            "lag": {
                "overallLagSeconds": 10,
                "crudLagSeconds": 5,
                "ddlLagSeconds": 10,
            },
            "lagTimeSeconds": 10,
        }
        result = resolve_replication_lag(entry)
        assert result["overall"] == 10
        assert result["crud"] == 5
        assert result["ddl"] == 10
        assert result["has_breakdown"] is True


class TestIsCrudEventsRateLog:
    @pytest.mark.parametrize(
        "json_obj,expected",
        [
            (
                {
                    "message": "Average Source CRUD events rate.",
                    "srcCRUDEventsPerSec": "12.50",
                },
                True,
            ),
            (
                {
                    "message": "Average Source CRUD events rate",
                    "srcCRUDEventsPerSec": "12.50",
                },
                True,
            ),
            (
                {
                    "message": "Estimated average rate of CRUD events on the source.",
                    "srcCRUDEventsPerSec": "42.00",
                },
                True,
            ),
            (
                {
                    "message": "Estimated average rate of CRUD events on the source",
                    "srcCRUDEventsPerSec": "42.00",
                },
                True,
            ),
            (
                {
                    "message": "Average Source CRUD events rate.",
                },
                False,
            ),
            (
                {
                    "message": "Replication progress.",
                    "eventApplicationRatePerSecond": 100,
                },
                False,
            ),
            (
                {
                    "message": "Some other log line",
                    "srcCRUDEventsPerSec": "1.00",
                },
                False,
            ),
        ],
    )
    def test_is_crud_events_rate_log(self, json_obj, expected):
        assert _is_crud_events_rate_log(json_obj) is expected


class TestClassifyPartitionInitType:
    @pytest.mark.parametrize(
        "reason,expected",
        [
            ("Selected for natural order collection reads.", "Natural Order"),
            ("Capped collection.", "Capped"),
            ("Small collection.", "Small"),
            ("", "Single partition"),
            (None, "Single partition"),
            ("Something unexpected", "Single partition"),
        ],
    )
    def test_classify_partition_init_type(self, reason, expected):
        assert _classify_partition_init_type(reason) == expected


class TestExtractCeaStageSeries:
    def test_merges_replication_and_sent_response_preferring_replication(self):
        replication = [
            {
                "time": "2026-09-16T10:00:00.000000Z",
                "ceaStage": "collection copy drain",
            },
            {
                "time": "2026-09-16T10:01:00.000000Z",
                "ceaStage": "n/a",
            },
            {
                "time": "2026-09-16T10:02:00.000000Z",
                "ceaStage": "steady state",
            },
        ]
        sent = [
            {
                "time": "2026-09-16T10:00:00.000000Z",
                "body": json.dumps(
                    {"progress": {"ceaStage": "steady state"}}
                ),
            },
            {
                "time": "2026-09-16T10:03:00.000000Z",
                "body": json.dumps(
                    {"progress": {"ceaStage": "steady state"}}
                ),
            },
        ]
        times, stages = extract_cea_stage_series(replication, sent)
        assert [t.isoformat() for t in times] == [
            "2026-09-16T10:00:00",
            "2026-09-16T10:02:00",
            "2026-09-16T10:03:00",
        ]
        assert stages == [
            "collection copy drain",
            "steady state",
            "steady state",
        ]

    def test_pre_1_22_logs_yield_empty_series(self):
        replication = [
            {"time": "2026-01-01T10:00:00.000000Z", "lagTimeSeconds": 12},
        ]
        sent = [
            {
                "time": "2026-01-01T10:00:00.000000Z",
                "body": json.dumps({"progress": {"state": "RUNNING"}}),
            }
        ]
        assert extract_cea_stage_series(replication, sent) == ([], [])


class TestCeaStageDrainIntervals:
    def test_builds_intervals_until_next_stage(self):
        from datetime import datetime

        times = [
            datetime(2026, 9, 16, 10, 0, 0),
            datetime(2026, 9, 16, 10, 1, 0),
            datetime(2026, 9, 16, 10, 2, 0),
            datetime(2026, 9, 16, 10, 3, 0),
        ]
        stages = [
            "collection copy drain",
            "collection copy drain",
            "steady state",
            "steady state",
        ]
        intervals = cea_stage_drain_intervals(times, stages)
        assert intervals == [
            (datetime(2026, 9, 16, 10, 0, 0), datetime(2026, 9, 16, 10, 2, 0)),
        ]

    def test_skips_zero_width_terminal_point(self):
        from datetime import datetime

        times = [datetime(2026, 9, 16, 10, 0, 0)]
        stages = ["collection copy drain"]
        assert cea_stage_drain_intervals(times, stages) == []
