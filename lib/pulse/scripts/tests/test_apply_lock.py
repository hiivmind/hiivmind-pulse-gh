"""Tests for the same-machine advisory apply lock."""

import importlib
import multiprocessing
from concurrent.futures import ProcessPoolExecutor

import pytest


MODULE = "lib.pulse.scripts.apply_lock"


def _acquire_lock(path, blocking=True):
    apply_lock = importlib.import_module(MODULE)
    with apply_lock.ApplyLock(path, blocking=blocking):
        return True


def _spawn_pool():
    return ProcessPoolExecutor(mp_context=multiprocessing.get_context("spawn"))


def test_second_process_nonblocking_lock_raises_while_first_holds(tmp_path):
    apply_lock = importlib.import_module(MODULE)
    lock_path = tmp_path / "apply.lock"

    with apply_lock.ApplyLock(lock_path):
        with _spawn_pool() as pool:
            future = pool.submit(_acquire_lock, lock_path, False)
            with pytest.raises(apply_lock.ApplyLockError, match="apply lock in use"):
                future.result(timeout=5)


def test_second_process_can_acquire_after_first_releases(tmp_path):
    apply_lock = importlib.import_module(MODULE)
    lock_path = tmp_path / "apply.lock"

    with apply_lock.ApplyLock(lock_path):
        pass

    with _spawn_pool() as pool:
        assert pool.submit(_acquire_lock, lock_path, False).result(timeout=5) is True


def test_default_blocking_lock_works_in_subprocess_without_hanging(tmp_path):
    lock_path = tmp_path / "apply.lock"

    with _spawn_pool() as pool:
        assert pool.submit(_acquire_lock, lock_path).result(timeout=5) is True
