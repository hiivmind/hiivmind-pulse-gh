"""Durable write-ahead journal for apply-mode repository boundaries.

``RESET_AND_REEXEC_TRANSFORM`` directs the apply driver to reset its clone
to the provisioned base and run the deterministic transformation again.
``VERIFY_REMOTE_EVIDENCE`` directs it to reconcile the boundary against
remote or live evidence without repeating it.
"""

from __future__ import annotations

import copy
import os
import tempfile
from pathlib import Path
from typing import Any

import yaml


PHASES = (
    "leased",
    "pen_ready",
    "branch_provisioned",
    "transformed",
    "validated",
    "committed",
    "pushed",
    "pr_opened",
)

RESET_AND_REEXEC_TRANSFORM = "reset-and-reexec-transform"
VERIFY_REMOTE_EVIDENCE = "verify-remote-evidence"


class JournalError(ValueError):
    """Raised when the journal cannot be safely read or written."""


class Journal:
    """A durable, repo-keyed write-ahead journal backed by one YAML file."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._data = self._load()

    def begin(self, repo: str, phase: str, token: str, **evidence: Any) -> None:
        """Persist intent for a boundary before the boundary is performed."""
        self._validate_phase(phase)
        data = copy.deepcopy(self._data)
        record = data["repos"].setdefault(repo, self._empty_record())
        if record["in_progress"] is not None:
            raise JournalError(
                f"cannot begin {phase}: {repo} is already in progress at {record['in_progress']}"
            )
        record["in_progress"] = phase
        record["token"] = token
        record["evidence"].update(evidence)
        self._write(data)
        self._data = data

    def complete(self, repo: str, phase: str, **evidence: Any) -> None:
        """Persist successful completion after the boundary has completed."""
        self._validate_phase(phase)
        data = copy.deepcopy(self._data)
        record = data["repos"].get(repo)
        if record is None or record["in_progress"] != phase:
            raise JournalError(f"cannot complete {phase}: {repo} has no matching intent")
        record["phase"] = phase
        record["in_progress"] = None
        record["evidence"].update(evidence)
        self._write(data)
        self._data = data

    def state(self, repo: str) -> dict[str, Any]:
        """Return the durable state for ``repo`` without exposing mutable storage."""
        record = self._data["repos"].get(repo, self._empty_record())
        return copy.deepcopy(record)

    def resume_action(self, repo: str) -> str:
        """Return the safe recovery directive for ``repo``'s pending boundary."""
        if self.state(repo)["in_progress"] == "transformed":
            return RESET_AND_REEXEC_TRANSFORM
        return VERIFY_REMOTE_EVIDENCE

    def _load(self) -> dict[str, dict[str, dict[str, Any]]]:
        if not self.path.exists():
            return {"repos": {}}
        try:
            loaded = yaml.safe_load(self.path.read_text())
        except (OSError, UnicodeError, yaml.YAMLError) as exc:
            raise JournalError(f"could not load journal {self.path}: {exc}") from exc
        return self._validate_data(loaded)

    def _write(self, updated: dict[str, Any]) -> None:
        temporary_name: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                "w",
                dir=self.path.parent,
                prefix=f".{self.path.name}.",
                suffix=".tmp",
                delete=False,
            ) as handle:
                temporary_name = handle.name
                yaml.safe_dump(updated, handle, sort_keys=False, allow_unicode=True)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_name, self.path)
            # Rename succeeded: nothing left to clean up on a later failure.
            temporary_name = None
            dir_fd = os.open(str(self.path.parent), os.O_RDONLY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
        except OSError as exc:
            if temporary_name:
                try:
                    Path(temporary_name).unlink()
                except OSError:
                    pass
            raise JournalError(f"could not write journal {self.path}: {exc}") from exc

    @staticmethod
    def _empty_record() -> dict[str, Any]:
        return {"phase": None, "in_progress": None, "evidence": {}, "token": None}

    @staticmethod
    def _validate_phase(phase: str) -> None:
        if phase not in PHASES:
            raise JournalError(f"unknown journal phase: {phase}")

    @classmethod
    def _validate_data(cls, loaded: Any) -> dict[str, dict[str, dict[str, Any]]]:
        if not isinstance(loaded, dict) or set(loaded) != {"repos"}:
            raise JournalError("could not load journal: expected a repos mapping")
        repos = loaded["repos"]
        if not isinstance(repos, dict) or not all(isinstance(repo, str) for repo in repos):
            raise JournalError("could not load journal: repos must be a mapping keyed by strings")
        for repo, record in repos.items():
            cls._validate_record(repo, record)
        return loaded

    @classmethod
    def _validate_record(cls, repo: str, record: Any) -> None:
        if not isinstance(record, dict) or set(record) != {
            "phase", "in_progress", "evidence", "token"
        }:
            raise JournalError(f"could not load journal: invalid record for {repo}")
        for key in ("phase", "in_progress"):
            value = record[key]
            if value is not None and value not in PHASES:
                raise JournalError(f"could not load journal: invalid {key} for {repo}")
        if not isinstance(record["evidence"], dict):
            raise JournalError(f"could not load journal: evidence must be a mapping for {repo}")
        if record["token"] is not None and not isinstance(record["token"], str):
            raise JournalError(f"could not load journal: token must be a string for {repo}")
