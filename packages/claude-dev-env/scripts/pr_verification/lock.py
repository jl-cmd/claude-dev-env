from __future__ import annotations

import os
import sys
from pathlib import Path
from types import TracebackType
from typing import Self

if sys.platform == "win32":
    import msvcrt
else:
    import fcntl

from .config.constants import (
    SUPERVISOR_LOCK_ERROR,
    SUPERVISOR_LOCK_FILE_MODE,
    SUPERVISOR_LOCK_FILENAME,
    SUPERVISOR_LOCK_IO_ERROR,
)

if sys.platform == "win32":

    def _acquire_file_lock(file_descriptor: int) -> None:
        """Acquire one nonblocking Windows lock."""
        os.lseek(file_descriptor, 0, os.SEEK_SET)
        msvcrt.locking(file_descriptor, msvcrt.LK_NBLCK, 1)

    def _release_file_lock(file_descriptor: int) -> None:
        """Release one Windows lock."""
        os.lseek(file_descriptor, 0, os.SEEK_SET)
        msvcrt.locking(file_descriptor, msvcrt.LK_UNLCK, 1)

else:

    def _acquire_file_lock(file_descriptor: int) -> None:
        """Acquire one nonblocking POSIX lock."""
        fcntl.flock(file_descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def _release_file_lock(file_descriptor: int) -> None:
        """Release one POSIX lock."""
        fcntl.flock(file_descriptor, fcntl.LOCK_UN)


class SupervisorLockError(RuntimeError):
    """Raised when the supervisor lock cannot be acquired or released."""


class SupervisorLock:
    def __init__(self, cache_root: Path) -> None:
        self.cache_root = cache_root.resolve()
        self.lock_path = self.cache_root / SUPERVISOR_LOCK_FILENAME
        self.file_descriptor: int | None = None

    def __enter__(self) -> Self:
        self.acquire()
        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.release()

    def acquire(self) -> None:
        """Acquire the operating-system lock for this cache root.

        Raises:
            SupervisorLockError: If another owner holds the lock or I/O fails.
        """
        try:
            self.cache_root.mkdir(parents=True, exist_ok=True)
            file_descriptor = os.open(
                self.lock_path,
                os.O_CREAT | os.O_RDWR,
                SUPERVISOR_LOCK_FILE_MODE,
            )
        except OSError as error:
            raise SupervisorLockError(SUPERVISOR_LOCK_IO_ERROR) from error
        try:
            _acquire_file_lock(file_descriptor)
        except (BlockingIOError, PermissionError) as error:
            _close_file_descriptor_without_raising(file_descriptor)
            raise SupervisorLockError(SUPERVISOR_LOCK_ERROR) from error
        except OSError as error:
            _close_file_descriptor_without_raising(file_descriptor)
            raise SupervisorLockError(SUPERVISOR_LOCK_IO_ERROR) from error
        self.file_descriptor = file_descriptor

    def release(self) -> None:
        """Release the operating-system lock and close its file descriptor.

        Raises:
            SupervisorLockError: If unlocking or closing the file fails.
        """
        file_descriptor = self.file_descriptor
        if file_descriptor is None:
            return
        self.file_descriptor = None
        try:
            _release_file_lock(file_descriptor)
        except OSError as error:
            raise SupervisorLockError(SUPERVISOR_LOCK_IO_ERROR) from error
        finally:
            _close_file_descriptor(file_descriptor)


def _close_file_descriptor(file_descriptor: int) -> None:
    """Close one lock file descriptor."""
    try:
        os.close(file_descriptor)
    except OSError as error:
        raise SupervisorLockError(SUPERVISOR_LOCK_IO_ERROR) from error


def _close_file_descriptor_without_raising(file_descriptor: int) -> None:
    """Close one lock file descriptor while a lock failure is already being raised."""
    try:
        os.close(file_descriptor)
    except OSError:
        return
