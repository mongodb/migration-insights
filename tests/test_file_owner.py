"""Owner isolation for saved log analyses."""
import base64
import json
import os
import time
import uuid

from lib import snapshot_store
from lib.file_owner import OWNER_COOKIE_NAME, kanopy_subject_from_token


def _jwt(sub):
    header = base64.urlsafe_b64encode(b'{"alg":"none"}').decode().rstrip("=")
    payload = base64.urlsafe_b64encode(
        json.dumps({"sub": sub, "groups": ["ts-mf"]}).encode()
    ).decode().rstrip("=")
    return f"{header}.{payload}.sig"


class TestCookieOwner:
    def test_list_load_and_delete_are_private(self, app_client):
        alice = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
        bob = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
        alice_id = str(uuid.uuid4())
        bob_id = str(uuid.uuid4())
        snapshot_store.save_snapshot(alice_id, "alice.log", 1, 1, str(uuid.uuid4()), {}, owner=alice)
        snapshot_store.save_snapshot(bob_id, "bob.log", 1, 1, str(uuid.uuid4()), {}, owner=bob)
        snapshot_store.save_snapshot(str(uuid.uuid4()), "legacy.log", 1, 1, str(uuid.uuid4()), {})

        app_client.set_cookie(OWNER_COOKIE_NAME, alice)
        listed = app_client.get("/logs/list_snapshots")
        assert listed.status_code == 200
        assert [row["snapshot_id"] for row in listed.get_json()] == [alice_id]

        other = app_client.get(f"/logs/load_snapshot/{bob_id}")
        assert b"Snapshot Not Found" in other.data
        assert os.path.exists(snapshot_store._snapshot_path(bob_id))

        denied = app_client.delete(f"/logs/delete_snapshot/{bob_id}")
        assert denied.status_code == 404
        assert os.path.exists(snapshot_store._snapshot_path(bob_id))

        removed = app_client.delete(f"/logs/delete_snapshot/{alice_id}")
        assert removed.status_code == 200
        assert not os.path.exists(snapshot_store._snapshot_path(alice_id))

    def test_home_sets_owner_cookie(self, app_client):
        response = app_client.get("/logs/")
        assert response.status_code == 200
        cookie = response.headers.get("Set-Cookie", "")
        assert OWNER_COOKIE_NAME in cookie
        assert "HttpOnly" in cookie


class TestKanopyOwner:
    def test_subject_from_fixture_jwt(self):
        assert kanopy_subject_from_token(_jwt("jane.doe")) == "jane.doe"

    def test_routes_use_sub_and_reject_other_owners(self, app_client, monkeypatch):
        monkeypatch.setenv("MI_KANOPY_IDENTITY", "true")
        jane_id = str(uuid.uuid4())
        other_id = str(uuid.uuid4())
        snapshot_store.save_snapshot(jane_id, "jane.log", 1, 1, str(uuid.uuid4()), {}, owner="jane.doe")
        snapshot_store.save_snapshot(other_id, "other.log", 1, 1, str(uuid.uuid4()), {}, owner="other.user")
        headers = {"X-Kanopy-Internal-Authorization": _jwt("jane.doe")}

        listed = app_client.get("/logs/list_snapshots", headers=headers)
        assert [row["snapshot_id"] for row in listed.get_json()] == [jane_id]

        empty = app_client.get("/logs/list_snapshots")
        assert empty.get_json() == []

        missing = app_client.delete(f"/logs/delete_snapshot/{jane_id}")
        assert missing.status_code == 401
        assert os.path.exists(snapshot_store._snapshot_path(jane_id))

        foreign = app_client.delete(f"/logs/delete_snapshot/{other_id}", headers=headers)
        assert foreign.status_code == 404
        assert os.path.exists(snapshot_store._snapshot_path(other_id))

        loaded = app_client.get(f"/logs/load_snapshot/{other_id}", headers=headers)
        assert b"Snapshot Not Found" in loaded.data

        upload = app_client.post("/logs/uploadLogs", data={}, content_type="multipart/form-data")
        assert upload.status_code == 401


class TestAgeCleanupIgnoresOwner:
    def test_expired_snapshot_of_another_owner_is_deleted(self, tmp_path, monkeypatch):
        monkeypatch.setattr(snapshot_store, "LOG_STORE_DIR", str(tmp_path))
        snapshot_id = str(uuid.uuid4())
        snapshot_store.save_snapshot(
            snapshot_id, "old.log", 1, 1, str(uuid.uuid4()), {}, owner="someone.else"
        )
        path = snapshot_store._snapshot_path(snapshot_id)
        old = time.time() - (48 * 3600)
        os.utime(path, (old, old))
        snapshot_store.cleanup_old_snapshots(str(tmp_path), max_age_hours=24)
        assert not os.path.exists(path)
        assert not os.path.exists(snapshot_store._snapshot_meta_path(snapshot_id))
