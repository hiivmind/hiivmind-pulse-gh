import fcntl
import os
from pathlib import Path


class ApplyLockError(Exception):
    pass


class ApplyLock:
    """Advisory file lock for same-machine apply concurrency."""

    def __init__(self, path: str | Path, blocking: bool = True) -> None:
        self.path = Path(path)
        self.blocking = blocking
        self._fd = None

    def __enter__(self) -> "ApplyLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fd = os.open(str(self.path), os.O_CREAT | os.O_RDWR)
        try:
            flags = fcntl.LOCK_EX if self.blocking else (fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(self._fd, flags)
        except BlockingIOError as exc:
            os.close(self._fd)
            self._fd = None
            raise ApplyLockError(f"apply lock in use: {self.path}") from exc
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._fd is not None:
            fcntl.flock(self._fd, fcntl.LOCK_UN)
            os.close(self._fd)
            self._fd = None
        # Leave the lock file in place; deleting creates races.
