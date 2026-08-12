"""
Job Raider - Persistent Profile Storage

JSON-file-backed profile storage shared across uvicorn workers via the
mounted data volume. Each profile is stored as an individual JSON file
under ``data/profiles/store/`` and the active-profile marker lives in
``data/profiles/active_profile.json``.

The module exposes drop-in replacements for the historical module-level
``stored_profiles`` dict and ``active_profile_id`` string so that existing
readers keep working unchanged while reads fall through to disk, making
writes from other worker processes visible without a restart.

Author: Job Raider
Date: 2026-07-22
"""

import json
import os
from collections.abc import MutableMapping
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterator, Optional, Set

from ..models.user_profile import UserProfile
from ..utils.logger import Components, get_logger

logger = get_logger(Components.SCRAPERS)


def _parse_dt(value: Any) -> datetime:
    """Parse an ISO datetime string back into a datetime, tolerating junk.

    Args:
        value: A datetime, an ISO-8601 string, or anything else.

    Returns:
        The parsed datetime, or the current time as a fallback.
    """
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return datetime.now()
    return datetime.now()


def _atomic_write(path: Path, content: str) -> None:
    """Write content to a file atomically via a temp file and rename.

    Prevents torn reads when another uvicorn worker reads the file while
    this process is writing it.

    Args:
        path: Destination file path.
        content: Text content to write.

    Returns:
        None.
    """
    tmp_path = path.with_name(path.name + ".tmp")
    tmp_path.write_text(content)
    os.replace(tmp_path, path)


def _entry_payload(profile_id: str, entry: Dict[str, Any]) -> Dict[str, Any]:
    """Build the JSON-serializable payload for a stored profile entry.

    Uses the same shape as the legacy ``active_profile.json`` marker so the
    per-profile files and the marker remain interchangeable.

    Args:
        profile_id: Identifier of the profile being serialized.
        entry: In-memory entry with ``profile`` (UserProfile or dict),
            ``resume_path``, ``original_filename``, ``created_at`` and
            ``updated_at`` fields.

    Returns:
        A JSON-serializable dict payload.
    """
    profile = entry.get("profile")
    return {
        "active_profile_id": profile_id,
        "resume_path": entry.get("resume_path"),
        "original_filename": entry.get("original_filename"),
        "created_at": _parse_dt(entry.get("created_at")).isoformat(),
        "updated_at": _parse_dt(entry.get("updated_at")).isoformat(),
        "resume_parse": entry.get("resume_parse")
        or _resume_parse_from_profile(profile),
        "profile": (
            profile.model_dump(mode="json")
            if hasattr(profile, "model_dump")
            else profile
        ),
    }


def _resume_parse_from_profile(profile: Any) -> Optional[Dict[str, Any]]:
    """
    Extract resume_parse metadata from a UserProfile when present.

    Args:
        profile: UserProfile instance or dict.

    Returns:
        Parse metadata dict, or None.
    """
    metadata = None
    if hasattr(profile, "metadata"):
        metadata = profile.metadata
    elif isinstance(profile, dict):
        metadata = profile.get("metadata")
    if not isinstance(metadata, dict):
        return None
    resume_parse = metadata.get("resume_parse")
    return dict(resume_parse) if isinstance(resume_parse, dict) else None


def _entry_from_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Rebuild an in-memory profile entry from its JSON payload.

    Args:
        payload: Dict previously produced by :func:`_entry_payload`.

    Returns:
        Entry dict with a validated UserProfile and parsed datetimes.
    """
    return {
        "profile": UserProfile.model_validate(payload["profile"]),
        "resume_path": payload.get("resume_path"),
        "original_filename": payload.get("original_filename"),
        "created_at": _parse_dt(payload.get("created_at")),
        "updated_at": _parse_dt(payload.get("updated_at")),
        "resume_parse": payload.get("resume_parse")
        or _resume_parse_from_profile(payload.get("profile")),
    }


class _ProfileStoreMapping(MutableMapping):
    """Dict-like profile store backed by per-profile JSON files.

    Keeps an in-memory cache for fast repeated access and falls back to
    ``{store_dir}/{profile_id}.json`` on cache misses, so profiles written
    by another uvicorn worker are visible to this process. Writes update
    the cache and persist the file atomically.
    """

    def __init__(self, store_dir: Path) -> None:
        """Initialize the mapping over a directory of per-profile files.

        Args:
            store_dir: Directory holding one ``{profile_id}.json`` file per
                stored profile. Created if missing.
        """
        self._store_dir = Path(store_dir)
        self._store_dir.mkdir(parents=True, exist_ok=True)
        self._cache: Dict[str, Dict[str, Any]] = {}

    @staticmethod
    def _key(key: Any) -> str:
        """Normalize a lookup key to a plain string.

        Accepts the :class:`_ActiveProfileId` wrapper transparently.

        Args:
            key: Lookup key, typically a profile id string.

        Returns:
            The key as a plain string.
        """
        return str(key)

    def _path_for(self, key: str) -> Path:
        """Return the per-profile JSON path for a normalized key.

        Args:
            key: Normalized profile id.

        Returns:
            Path to ``{store_dir}/{key}.json``.
        """
        return self._store_dir / f"{key}.json"

    def _all_keys(self) -> Set[str]:
        """Collect the union of cached and on-disk profile ids.

        Returns:
            Set of all known profile ids.
        """
        keys = set(self._cache)
        keys.update(p.stem for p in self._store_dir.glob("*.json"))
        return keys

    def __getitem__(self, key: Any) -> Dict[str, Any]:
        """Return the entry for a profile id, hydrating from disk on miss.

        Args:
            key: Profile id (string or string-like wrapper).

        Returns:
            The stored profile entry.

        Raises:
            KeyError: If no such profile exists or its file is unreadable.
        """
        normalized = self._key(key)
        if normalized in self._cache:
            return self._cache[normalized]
        path = self._path_for(normalized)
        if path.exists():
            try:
                entry = _entry_from_payload(json.loads(path.read_text()))
            except Exception as exc:
                logger.warning(f"Failed to load profile {normalized}: {exc}")
                raise KeyError(normalized) from exc
            self._cache[normalized] = entry
            return entry
        raise KeyError(normalized)

    def __setitem__(self, key: Any, value: Dict[str, Any]) -> None:
        """Store a profile entry in the cache and persist it to disk.

        Persistence failures are logged and swallowed so storage never
        breaks the request that triggered the write.

        Args:
            key: Profile id (string or string-like wrapper).
            value: Entry dict (see :func:`_entry_payload`).

        Returns:
            None.
        """
        normalized = self._key(key)
        self._cache[normalized] = value
        try:
            _atomic_write(
                self._path_for(normalized),
                json.dumps(_entry_payload(normalized, value)),
            )
        except Exception as exc:
            logger.warning(f"Failed to persist profile {normalized}: {exc}")

    def __delitem__(self, key: Any) -> None:
        """Remove a profile entry from the cache and disk.

        Args:
            key: Profile id (string or string-like wrapper).

        Raises:
            KeyError: If no such profile exists.
        """
        normalized = self._key(key)
        existed = self._cache.pop(normalized, None) is not None
        path = self._path_for(normalized)
        if path.exists():
            path.unlink()
            existed = True
        if not existed:
            raise KeyError(normalized)

    def __iter__(self) -> Iterator[str]:
        """Iterate over all known profile ids (cache and disk).

        Returns:
            Iterator of profile id strings.
        """
        return iter(self._all_keys())

    def __len__(self) -> int:
        """Return the number of known profiles (cache and disk).

        Returns:
            Count of distinct profile ids.
        """
        return len(self._all_keys())

    def __contains__(self, key: object) -> bool:
        """Check membership without hydrating the entry.

        Args:
            key: Profile id (string or string-like wrapper).

        Returns:
            True if the profile is cached or has a file on disk.
        """
        normalized = self._key(key)
        return normalized in self._cache or self._path_for(normalized).exists()


class _ActiveProfileId:
    """String-like wrapper over the active-profile marker file.

    Reads ``active_profile.json`` on every boolean, comparison, and string
    conversion so that an active profile set by another uvicorn worker is
    visible to this process immediately. Hashing is constant; equality does
    the real work, so the wrapper can be used as a mapping key.
    """

    def __init__(self, marker_path: Path, profiles: _ProfileStoreMapping) -> None:
        """Initialize the wrapper.

        Args:
            marker_path: Path to the ``active_profile.json`` marker file.
            profiles: The profile store mapping used by :meth:`set` to embed
                the active entry payload in the marker (legacy format).
        """
        self._marker_path = Path(marker_path)
        self._profiles = profiles

    def read(self) -> Optional[str]:
        """Read the current active profile id from the marker file.

        Returns:
            The active profile id, or None if no marker exists or it is
            unreadable.
        """
        try:
            if not self._marker_path.exists():
                return None
            payload = json.loads(self._marker_path.read_text())
            pid = payload.get("active_profile_id")
            return str(pid) if pid else None
        except Exception as exc:
            logger.warning(f"Failed to read active profile marker: {exc}")
            return None

    def set(self, value: str) -> None:
        """Persist a new active profile id to the marker file.

        Embeds the full entry payload when the profile is present in the
        store, preserving the legacy marker format. Failures are logged and
        swallowed.

        Args:
            value: Profile id to mark as active.

        Returns:
            None.
        """
        pid = str(value)
        entry = self._profiles.get(pid)
        payload = (
            _entry_payload(pid, entry)
            if entry is not None
            else {"active_profile_id": pid}
        )
        try:
            _atomic_write(self._marker_path, json.dumps(payload))
        except Exception as exc:
            logger.warning(f"Failed to persist active profile marker: {exc}")

    def __bool__(self) -> bool:
        """Return True when an active profile id is set.

        Returns:
            True if the marker file yields a non-empty id.
        """
        return self.read() is not None

    def __eq__(self, other: object) -> bool:
        """Compare the current marker value against another value.

        Args:
            other: A string, another wrapper, or None.

        Returns:
            True if the current id equals the other value.
        """
        current = self.read()
        if isinstance(other, _ActiveProfileId):
            return current == other.read()
        return current == other

    def __hash__(self) -> int:
        """Return a constant hash so the wrapper is usable as a key.

        Equality (which reads the live value) decides key identity.

        Returns:
            Constant hash for all wrapper instances.
        """
        return hash(_ActiveProfileId.__name__)

    def __str__(self) -> str:
        """Return the current active profile id as a string.

        Returns:
            The id, or an empty string when none is set.
        """
        return self.read() or ""

    def __repr__(self) -> str:
        """Return a debug representation with the current value.

        Returns:
            Representation string including the live id.
        """
        return f"_ActiveProfileId({self.read()!r})"


class ProfileStorage:
    """Persistent storage for user profiles, shared across workers.

    Owns the per-profile JSON store and the active-profile marker. Exposes
    them as ``profiles`` (a MutableMapping) and ``active_id`` (a string-like
    wrapper) so existing readers keep working unchanged.
    """

    def __init__(self, upload_dir: Path) -> None:
        """Initialize the storage rooted at the profiles upload directory.

        Args:
            upload_dir: Directory containing ``active_profile.json``; the
                per-profile store is created in its ``store/`` subdirectory.
        """
        self._upload_dir = Path(upload_dir)
        self._marker_path = self._upload_dir / "active_profile.json"
        self.profiles = _ProfileStoreMapping(self._upload_dir / "store")
        self.active_id = _ActiveProfileId(self._marker_path, self.profiles)

    def load(self) -> None:
        """Hydrate the active profile from disk at startup.

        Migrates the legacy single-file marker (which embeds the full
        profile payload) into a per-profile file so cross-worker lookups
        through the store mapping work. A missing or unreadable marker is
        ignored.

        Returns:
            None.
        """
        pid = self.active_id.read()
        if not pid:
            return
        if pid in self.profiles:
            # Warm the cache so the first read is cheap.
            try:
                self.profiles[pid]
                logger.info(f"Restored persisted profile {pid} from store")
            except KeyError:
                pass
            return
        # Legacy layout: the entry only exists inside the marker file.
        try:
            payload = json.loads(self._marker_path.read_text())
            self.profiles[pid] = _entry_from_payload(payload)
            logger.info(
                f"Migrated legacy active profile {pid} from {self._marker_path}"
            )
        except Exception as exc:
            logger.warning(f"Failed to load persisted profile: {exc}")

    def persist_active(self) -> None:
        """Rewrite the active profile's file and the marker.

        Re-serializes the active entry so in-place mutations (for example
        from the profile update endpoint) reach disk, then refreshes the
        marker payload. Failures are logged and swallowed.

        Returns:
            None.
        """
        pid = self.active_id.read()
        if not pid or pid not in self.profiles:
            return
        self.profiles[pid] = self.profiles[pid]
        self.active_id.set(pid)
