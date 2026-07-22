"""
Unit tests for the JSON-backed profile storage shared across workers.

These tests verify that profile state written through one ProfileStorage
instance is visible to a second instance over the same directory (the
multi-worker case), that the legacy single-file marker is migrated into
the per-profile store, that writes land atomically as valid JSON, and
that the in-memory cache behaves as expected on hits and misses.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from src.api.profile_storage import ProfileStorage
from src.models.user_profile import ContactInfo, UserProfile


def _make_profile(name: str = "Jane Doe") -> UserProfile:
    """Build a minimal valid UserProfile for storage tests.

    Args:
        name: Full name to set on the profile.

    Returns:
        A UserProfile with only the required fields populated.
    """
    return UserProfile(
        name=name,
        contact=ContactInfo(email="jane@example.com", location="Singapore"),
    )


def _make_entry(name: str = "Jane Doe") -> Dict[str, Any]:
    """Build a profile store entry in the shape the routes use.

    Args:
        name: Full name to set on the embedded profile.

    Returns:
        Entry dict with profile, resume metadata, and timestamps.
    """
    return {
        "profile": _make_profile(name),
        "resume_path": "/tmp/resume.pdf",
        "original_filename": "resume.pdf",
        "created_at": datetime(2026, 1, 1, 12, 0, 0),
        "updated_at": datetime(2026, 1, 2, 12, 0, 0),
    }


class TestCrossWorkerVisibility:
    """Two instances over one directory simulate two uvicorn workers."""

    def test_write_visible_to_second_instance(self, tmp_path: Path):
        """A write through instance A is readable through instance B."""
        worker_a = ProfileStorage(tmp_path)
        worker_b = ProfileStorage(tmp_path)

        worker_a.profiles["p1"] = _make_entry()
        worker_a.active_id.set("p1")

        assert "p1" in worker_b.profiles
        assert bool(worker_b.active_id)
        assert str(worker_b.active_id) == "p1"
        entry = worker_b.profiles["p1"]
        assert entry["profile"].name == "Jane Doe"
        assert entry["resume_path"] == "/tmp/resume.pdf"
        assert entry["created_at"] == datetime(2026, 1, 1, 12, 0, 0)

    def test_persist_active_propagates_updates(self, tmp_path: Path):
        """persist_active() re-serializes in-place edits for other workers."""
        worker_a = ProfileStorage(tmp_path)
        worker_a.profiles["p1"] = _make_entry()
        worker_a.active_id.set("p1")

        worker_a.profiles["p1"]["profile"].name = "Updated Name"
        worker_a.profiles["p1"]["updated_at"] = datetime(2026, 2, 1, 12, 0, 0)
        worker_a.persist_active()

        worker_b = ProfileStorage(tmp_path)
        assert worker_b.profiles["p1"]["profile"].name == "Updated Name"
        assert worker_b.profiles["p1"]["updated_at"] == datetime(2026, 2, 1, 12, 0, 0)


class TestLegacyMigration:
    """The legacy single-file marker is migrated into the per-profile store."""

    def test_legacy_marker_migrated_on_load(self, tmp_path: Path):
        """load() converts an old active_profile.json into a store file."""
        legacy_payload = {
            "active_profile_id": "legacy1",
            "resume_path": "/tmp/old.pdf",
            "original_filename": "old.pdf",
            "created_at": "2026-01-01T00:00:00",
            "updated_at": "2026-01-02T00:00:00",
            "profile": _make_profile("Legacy User").model_dump(mode="json"),
        }
        (tmp_path / "active_profile.json").write_text(json.dumps(legacy_payload))

        storage = ProfileStorage(tmp_path)
        assert not (tmp_path / "store" / "legacy1.json").exists()

        storage.load()

        assert (tmp_path / "store" / "legacy1.json").exists()
        assert storage.profiles["legacy1"]["profile"].name == "Legacy User"
        assert storage.profiles["legacy1"]["resume_path"] == "/tmp/old.pdf"

    def test_load_without_marker_is_noop(self, tmp_path: Path):
        """load() on an empty directory leaves the storage empty."""
        storage = ProfileStorage(tmp_path)
        storage.load()
        assert not storage.active_id
        assert len(storage.profiles) == 0


class TestAtomicWrites:
    """Writes land as complete, valid JSON files with no temp files left."""

    def test_written_files_are_valid_json(self, tmp_path: Path):
        """Store and marker files parse as JSON after the atomic rename."""
        storage = ProfileStorage(tmp_path)
        storage.profiles["p1"] = _make_entry()
        storage.active_id.set("p1")

        store_payload = json.loads((tmp_path / "store" / "p1.json").read_text())
        marker_payload = json.loads((tmp_path / "active_profile.json").read_text())

        assert store_payload["active_profile_id"] == "p1"
        assert store_payload["profile"]["name"] == "Jane Doe"
        assert marker_payload["active_profile_id"] == "p1"
        assert not (tmp_path / "store" / "p1.json.tmp").exists()
        assert not (tmp_path / "active_profile.json.tmp").exists()


class TestCacheBehaviour:
    """The in-memory cache serves hits and hydrates misses from disk."""

    def test_cache_hit_avoids_disk(self, tmp_path: Path):
        """A cached entry is served even if the backing file is removed."""
        storage = ProfileStorage(tmp_path)
        storage.profiles["p1"] = _make_entry()

        (tmp_path / "store" / "p1.json").unlink()

        assert storage.profiles["p1"]["profile"].name == "Jane Doe"

    def test_cache_miss_hydrates_from_disk(self, tmp_path: Path):
        """A cold instance hydrates a profile written by another instance."""
        writer = ProfileStorage(tmp_path)
        writer.profiles["p1"] = _make_entry()

        reader = ProfileStorage(tmp_path)
        entry = reader.profiles["p1"]

        assert entry["profile"].name == "Jane Doe"
        assert "p1" in reader.profiles._cache

    def test_contains_checks_disk_without_hydrating(self, tmp_path: Path):
        """Membership checks see other workers' files without caching them."""
        writer = ProfileStorage(tmp_path)
        writer.profiles["p1"] = _make_entry()

        reader = ProfileStorage(tmp_path)
        assert "p1" in reader.profiles
        assert "p1" not in reader.profiles._cache
