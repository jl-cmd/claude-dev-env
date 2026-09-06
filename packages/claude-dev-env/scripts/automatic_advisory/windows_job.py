from __future__ import annotations

import ctypes

from .config.constants import (
    WINDOWS_EXTENDED_LIMIT_INFORMATION_CLASS,
    WINDOWS_JOB_KILL_ON_CLOSE_LIMIT,
    WINDOWS_PROCESS_SET_QUOTA_ACCESS,
    WINDOWS_PROCESS_TERMINATE_ACCESS,
)


class _JobObjectBasicLimitInformation(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_longlong),
        ("PerJobUserTimeLimit", ctypes.c_longlong),
        ("LimitFlags", ctypes.c_uint32),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", ctypes.c_uint32),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", ctypes.c_uint32),
        ("SchedulingClass", ctypes.c_uint32),
    ]


class _IoCounters(ctypes.Structure):
    _fields_ = [
        ("ReadOperationCount", ctypes.c_ulonglong),
        ("WriteOperationCount", ctypes.c_ulonglong),
        ("OtherOperationCount", ctypes.c_ulonglong),
        ("ReadTransferCount", ctypes.c_ulonglong),
        ("WriteTransferCount", ctypes.c_ulonglong),
        ("OtherTransferCount", ctypes.c_ulonglong),
    ]


class _JobObjectExtendedLimitInformation(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", _JobObjectBasicLimitInformation),
        ("IoInfo", _IoCounters),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]


def _create_kill_on_close_job() -> int | None:
    create_job = ctypes.windll.kernel32.CreateJobObjectW
    create_job.argtypes = (ctypes.c_void_p, ctypes.c_wchar_p)
    create_job.restype = ctypes.c_void_p
    maybe_job_handle = create_job(None, None)
    if maybe_job_handle is None:
        return None
    job_handle = int(maybe_job_handle)
    if _configure_kill_on_close(job_handle):
        return job_handle
    _close_handle(job_handle)
    return None


def _configure_kill_on_close(job_handle: int) -> bool:
    job_limits = _JobObjectExtendedLimitInformation()
    job_limits.BasicLimitInformation.LimitFlags = WINDOWS_JOB_KILL_ON_CLOSE_LIMIT
    set_job_information = ctypes.windll.kernel32.SetInformationJobObject
    set_job_information.argtypes = (
        ctypes.c_void_p,
        ctypes.c_int,
        ctypes.c_void_p,
        ctypes.c_uint32,
    )
    set_job_information.restype = ctypes.c_int
    return bool(
        set_job_information(
            ctypes.c_void_p(job_handle),
            WINDOWS_EXTENDED_LIMIT_INFORMATION_CLASS,
            ctypes.byref(job_limits),
            ctypes.sizeof(job_limits),
        )
    )


def _assign_process(job_handle: int, process_identifier: int) -> bool:
    process_access = WINDOWS_PROCESS_SET_QUOTA_ACCESS | WINDOWS_PROCESS_TERMINATE_ACCESS
    open_process = ctypes.windll.kernel32.OpenProcess
    open_process.argtypes = (ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32)
    open_process.restype = ctypes.c_void_p
    maybe_process_handle = open_process(process_access, 0, process_identifier)
    if maybe_process_handle is None:
        return False
    process_handle = int(maybe_process_handle)
    try:
        return _assign_process_handle(job_handle, process_handle)
    finally:
        _close_handle(process_handle)


def _assign_process_handle(job_handle: int, process_handle: int) -> bool:
    assign_process_to_job = ctypes.windll.kernel32.AssignProcessToJobObject
    assign_process_to_job.argtypes = (ctypes.c_void_p, ctypes.c_void_p)
    assign_process_to_job.restype = ctypes.c_int
    return bool(
        assign_process_to_job(
            ctypes.c_void_p(job_handle),
            ctypes.c_void_p(process_handle),
        )
    )


def _terminate_job(job_handle: int) -> None:
    terminate_job_object = ctypes.windll.kernel32.TerminateJobObject
    terminate_job_object.argtypes = (ctypes.c_void_p, ctypes.c_uint32)
    terminate_job_object.restype = ctypes.c_int
    terminate_job_object(ctypes.c_void_p(job_handle), 1)


def _close_handle(job_handle: int) -> None:
    close_windows_handle = ctypes.windll.kernel32.CloseHandle
    close_windows_handle.argtypes = (ctypes.c_void_p,)
    close_windows_handle.restype = ctypes.c_int
    close_windows_handle(ctypes.c_void_p(job_handle))
