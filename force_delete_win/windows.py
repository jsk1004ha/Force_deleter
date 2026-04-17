"""Windows-only force deletion utilities implemented in pure Python.

The implementation uses Windows Restart Manager APIs to discover processes
currently using a target path and then terminates those processes before
retrying deletion.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wintypes
import os
import shutil
import stat
import subprocess
import time
from pathlib import Path

ERROR_MORE_DATA = 234
CCH_RM_SESSION_KEY = 32
CCH_RM_MAX_APP_NAME = 255
CCH_RM_MAX_SVC_NAME = 63


class FILETIME(ctypes.Structure):
    _fields_ = [("dwLowDateTime", wintypes.DWORD), ("dwHighDateTime", wintypes.DWORD)]


class RM_UNIQUE_PROCESS(ctypes.Structure):
    _fields_ = [("dwProcessId", wintypes.DWORD), ("ProcessStartTime", FILETIME)]


class RM_PROCESS_INFO(ctypes.Structure):
    _fields_ = [
        ("Process", RM_UNIQUE_PROCESS),
        ("strAppName", wintypes.WCHAR * (CCH_RM_MAX_APP_NAME + 1)),
        ("strServiceShortName", wintypes.WCHAR * (CCH_RM_MAX_SVC_NAME + 1)),
        ("ApplicationType", wintypes.UINT),
        ("AppStatus", wintypes.ULONG),
        ("TSSessionId", wintypes.DWORD),
        ("bRestartable", wintypes.BOOL),
    ]


def _ensure_windows() -> None:
    if os.name != "nt":
        raise OSError("force_delete_win is supported only on Windows.")


def _make_writable(func, path, _exc_info):
    """`shutil.rmtree` callback: make read-only paths writable and retry."""
    os.chmod(path, stat.S_IWRITE)
    func(path)


def _delete_path(target: Path) -> bool:
    if not target.exists() and not target.is_symlink():
        return True
    try:
        if target.is_dir() and not target.is_symlink():
            shutil.rmtree(target, onerror=_make_writable)
        else:
            target.unlink()
        return True
    except (PermissionError, OSError):
        return False


def _rm_find_locking_pids(path: str) -> set[int]:
    rstrtmgr = ctypes.WinDLL("Rstrtmgr")

    session_handle = wintypes.DWORD()
    session_key = ctypes.create_unicode_buffer(CCH_RM_SESSION_KEY + 1)

    rm_start_session = rstrtmgr.RmStartSession
    rm_start_session.argtypes = [ctypes.POINTER(wintypes.DWORD), wintypes.DWORD, wintypes.LPWSTR]
    rm_start_session.restype = wintypes.DWORD

    rm_register_resources = rstrtmgr.RmRegisterResources
    rm_register_resources.argtypes = [
        wintypes.DWORD,
        wintypes.UINT,
        ctypes.POINTER(wintypes.LPCWSTR),
        wintypes.UINT,
        ctypes.c_void_p,
        wintypes.UINT,
        ctypes.c_void_p,
    ]
    rm_register_resources.restype = wintypes.DWORD

    rm_get_list = rstrtmgr.RmGetList
    rm_get_list.argtypes = [
        wintypes.DWORD,
        ctypes.POINTER(wintypes.UINT),
        ctypes.POINTER(wintypes.UINT),
        ctypes.POINTER(RM_PROCESS_INFO),
        ctypes.POINTER(wintypes.DWORD),
    ]
    rm_get_list.restype = wintypes.DWORD

    rm_end_session = rstrtmgr.RmEndSession
    rm_end_session.argtypes = [wintypes.DWORD]
    rm_end_session.restype = wintypes.DWORD

    res = rm_start_session(ctypes.byref(session_handle), 0, session_key)
    if res != 0:
        return set()

    try:
        resource = ctypes.c_wchar_p(path)
        resources = (wintypes.LPCWSTR * 1)()
        resources[0] = resource.value

        res = rm_register_resources(session_handle.value, 1, resources, 0, None, 0, None)
        if res != 0:
            return set()

        needed = wintypes.UINT(0)
        proc_info_count = wintypes.UINT(0)
        reboot_reasons = wintypes.DWORD(0)

        res = rm_get_list(
            session_handle.value,
            ctypes.byref(needed),
            ctypes.byref(proc_info_count),
            None,
            ctypes.byref(reboot_reasons),
        )
        if res not in (0, ERROR_MORE_DATA):
            return set()

        if needed.value == 0:
            return set()

        process_info = (RM_PROCESS_INFO * needed.value)()
        proc_info_count = wintypes.UINT(needed.value)

        res = rm_get_list(
            session_handle.value,
            ctypes.byref(needed),
            ctypes.byref(proc_info_count),
            process_info,
            ctypes.byref(reboot_reasons),
        )
        if res != 0:
            return set()

        return {int(process_info[i].Process.dwProcessId) for i in range(proc_info_count.value)}
    finally:
        rm_end_session(session_handle.value)


def _terminate_processes(pids: set[int]) -> None:
    current_pid = os.getpid()
    for pid in sorted(pids):
        if pid <= 0 or pid == current_pid:
            continue
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/F", "/T"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


def force_delete_file_folder(path_to_folder_or_file: os.PathLike[str] | str, retries: int = 3) -> bool:
    """Force delete a file or folder on Windows.

    Parameters
    ----------
    path_to_folder_or_file:
        File or directory path to delete.
    retries:
        Number of kill+retry cycles after the initial delete attempt.

    Returns
    -------
    bool
        ``True`` if deletion succeeds, otherwise ``False``.
    """
    _ensure_windows()
    target = Path(path_to_folder_or_file).expanduser().resolve(strict=False)

    if _delete_path(target):
        return True

    for _ in range(max(0, retries)):
        pids = _rm_find_locking_pids(str(target))
        if pids:
            _terminate_processes(pids)
            time.sleep(0.2)
        if _delete_path(target):
            return True

    return False
