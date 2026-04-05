#!/usr/bin/env python3

import os
import platform
import subprocess
import json
import time
import uuid
import shutil

NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "claude-notifications")
NTFY_BASE_URL = f"https://ntfy.sh/{NTFY_TOPIC}"
WINDOWS_CHIMES_PATH = os.path.join(os.environ.get("SYSTEMROOT", r"C:\Windows"), "Media", "Windows Battery Critical.wav")
LINUX_NOTIFICATION_SOUND = os.environ.get("NOTIFICATION_SOUND", "/usr/share/sounds/freedesktop/stereo/message.oga")
LINUX_NOTIFICATION_TIMEOUT_MS = "3000"
TOAST_DISPLAY_DURATION_MILLISECONDS = 6000
DEFAULT_LINUX_TOAST_TITLE = "Claude Code"
DEFAULT_LINUX_TOAST_MESSAGE = "Waiting for your input"
DEBUG_LOG_PATH = "debug-4e2ac7.log"
DEBUG_SESSION_ID = "4e2ac7"

TOAST_SCRIPT_TEMPLATE = r'''
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class Win32 {{
    [DllImport("user32.dll")]
    public static extern bool SetProcessDPIAware();
    [DllImport("user32.dll")]
    public static extern bool SetWindowPos(IntPtr hWnd, IntPtr hWndInsertAfter, int X, int Y, int cx, int cy, uint uFlags);
    [DllImport("user32.dll")]
    public static extern int GetWindowLong(IntPtr hWnd, int nIndex);
    [DllImport("user32.dll")]
    public static extern int SetWindowLong(IntPtr hWnd, int nIndex, int dwNewLong);
    [DllImport("user32.dll")]
    public static extern bool SetLayeredWindowAttributes(IntPtr hwnd, uint crKey, byte bAlpha, uint dwFlags);
    public static readonly IntPtr HWND_TOPMOST = new IntPtr(-1);
    public const uint SWP_NOACTIVATE = 0x0010;
    public const uint SWP_SHOWWINDOW = 0x0040;
    public const int GWL_EXSTYLE = -20;
    public const int WS_EX_LAYERED = 0x80000;
    public const int WS_EX_TRANSPARENT = 0x20;
    public const uint LWA_ALPHA = 0x2;
}}
"@

[Win32]::SetProcessDPIAware() | Out-Null

$form = New-Object System.Windows.Forms.Form
$form.FormBorderStyle = [System.Windows.Forms.FormBorderStyle]::None
$form.Size = New-Object System.Drawing.Size(520, 110)
$form.ShowInTaskbar = $false
$form.BackColor = [System.Drawing.Color]::FromArgb(66, 135, 245)
$form.StartPosition = [System.Windows.Forms.FormStartPosition]::Manual

$screen = [System.Windows.Forms.Screen]::PrimaryScreen.WorkingArea
$x = [int]($screen.Left + ($screen.Width - 520) / 2)
$y = [int]($screen.Bottom - 110 - 50)
$form.Location = New-Object System.Drawing.Point($x, $y)

$inner = New-Object System.Windows.Forms.Panel
$inner.Size = New-Object System.Drawing.Size(514, 104)
$inner.Location = New-Object System.Drawing.Point(3, 3)
$inner.BackColor = [System.Drawing.Color]::FromArgb(45, 45, 45)
$form.Controls.Add($inner)

$titleLabel = New-Object System.Windows.Forms.Label
$titleLabel.Text = "{title}"
$titleLabel.Font = New-Object System.Drawing.Font("Segoe UI", 12, [System.Drawing.FontStyle]::Bold)
$titleLabel.ForeColor = [System.Drawing.Color]::FromArgb(120, 180, 255)
$titleLabel.AutoSize = $false
$titleLabel.Size = New-Object System.Drawing.Size(514, 30)
$titleLabel.Location = New-Object System.Drawing.Point(0, 8)
$titleLabel.TextAlign = [System.Drawing.ContentAlignment]::MiddleCenter
$inner.Controls.Add($titleLabel)

$messageLabel = New-Object System.Windows.Forms.Label
$messageLabel.Text = "{message}"
$messageLabel.Font = New-Object System.Drawing.Font("Segoe UI", 11)
$messageLabel.ForeColor = [System.Drawing.Color]::White
$messageLabel.AutoSize = $false
$messageLabel.Size = New-Object System.Drawing.Size(500, 58)
$messageLabel.Location = New-Object System.Drawing.Point(7, 40)
$messageLabel.TextAlign = [System.Drawing.ContentAlignment]::TopCenter
$inner.Controls.Add($messageLabel)

$timer = New-Object System.Windows.Forms.Timer
$timer.Interval = {toast_duration}
$timer.Add_Tick({{ $form.Close() }})
$timer.Start()

$exStyle = [Win32]::GetWindowLong($form.Handle, [Win32]::GWL_EXSTYLE)
[Win32]::SetWindowLong($form.Handle, [Win32]::GWL_EXSTYLE, $exStyle -bor [Win32]::WS_EX_LAYERED -bor [Win32]::WS_EX_TRANSPARENT)
[Win32]::SetLayeredWindowAttributes($form.Handle, 0, 230, [Win32]::LWA_ALPHA)
[Win32]::SetWindowPos($form.Handle, [Win32]::HWND_TOPMOST, $x, $y, 520, 110, [Win32]::SWP_NOACTIVATE -bor [Win32]::SWP_SHOWWINDOW)
$form.Show()
[System.Windows.Forms.Application]::Run($form)
'''


def is_wsl() -> bool:
    if platform.system() != "Linux":
        return False
    try:
        with open("/proc/version") as proc_version_file:
            return "microsoft" in proc_version_file.read().lower()
    except FileNotFoundError:
        return False


def _debug_log(run_id: str, hypothesis_id: str, location: str, message: str, data: dict) -> None:
    payload = {
        "sessionId": DEBUG_SESSION_ID,
        "id": f"log_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}",
        "timestamp": int(time.time() * 1000),
        "location": location,
        "message": message,
        "data": data,
        "runId": run_id,
        "hypothesisId": hypothesis_id,
    }
    try:
        with open(DEBUG_LOG_PATH, "a", encoding="utf-8") as debug_file:
            debug_file.write(json.dumps(payload) + "\n")
    except OSError:
        pass


def build_toast_script(title: str, message: str) -> str:
    safe_title = title.replace('"', '`"').replace("'", "`'")
    safe_message = message.replace('"', '`"').replace("'", "`'")
    return TOAST_SCRIPT_TEMPLATE.format(
        title=safe_title,
        message=safe_message,
        toast_duration=TOAST_DISPLAY_DURATION_MILLISECONDS,
    )


def notify_wsl(title: str, message: str) -> None:
    script = build_toast_script(title, message)
    try:
        subprocess.Popen(
            ["powershell.exe", "-ExecutionPolicy", "Bypass", "-Command", script],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True
        )
    except FileNotFoundError:
        pass


def notify_windows(title: str, message: str) -> None:
    script = build_toast_script(title, message)
    subprocess.Popen(
        ["powershell", "-ExecutionPolicy", "Bypass", "-Command", script],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
    )


def notify_ntfy(title: str, message: str, priority: str = "high") -> None:
    try:
        subprocess.Popen(
            [
                "curl", "-s",
                "-H", f"Priority: {priority}",
                "-H", "Tags: bell",
                "-H", f"Title: {title}",
                "-d", message,
                NTFY_BASE_URL,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
    except FileNotFoundError:
        pass


def notify_linux() -> None:
    notify_command = [
        "notify-send", "-t", LINUX_NOTIFICATION_TIMEOUT_MS,
        "-u", "normal", "-i", "dialog-warning",
        DEFAULT_LINUX_TOAST_TITLE, DEFAULT_LINUX_TOAST_MESSAGE,
    ]
    # #region agent log
    _debug_log(
        run_id="pre-fix",
        hypothesis_id="H1",
        location="hooks/notification/notification_utils.py:189",
        message="notify_linux environment snapshot",
        data={
            "notify_send_path": shutil.which("notify-send"),
            "display": os.environ.get("DISPLAY"),
            "wayland_display": os.environ.get("WAYLAND_DISPLAY"),
            "path_has_usr_bin": "/usr/bin" in os.environ.get("PATH", ""),
        },
    )
    # #endregion
    try:
        subprocess.Popen(
            notify_command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
    except FileNotFoundError as error:
        # #region agent log
        _debug_log(
            run_id="post-fix",
            hypothesis_id="H2",
            location="hooks/notification/notification_utils.py:207",
            message="notify_linux FileNotFoundError",
            data={
                "error": str(error),
                "notify_command": notify_command,
            },
        )
        # #endregion
        return


def sound_windows() -> None:
    subprocess.Popen(
        ["powershell", "-WindowStyle", "Hidden", "-Command", f"(New-Object Media.SoundPlayer '{WINDOWS_CHIMES_PATH}').PlaySync()"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
    )


def sound_wsl() -> None:
    try:
        subprocess.Popen(
            ["powershell.exe", "-WindowStyle", "Hidden", "-Command", f"(New-Object Media.SoundPlayer '{WINDOWS_CHIMES_PATH}').PlaySync()"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
    except FileNotFoundError:
        pass


def sound_linux() -> None:
    if os.path.exists(LINUX_NOTIFICATION_SOUND):
        for each_player in ["paplay", "aplay", "play"]:
            try:
                subprocess.Popen(
                    [each_player, LINUX_NOTIFICATION_SOUND],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                return
            except FileNotFoundError:
                continue
    print("\a", end="", flush=True)


def get_project_name() -> str:
    return os.path.basename(os.getcwd())
