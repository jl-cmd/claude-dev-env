#!/usr/bin/env python3
"""
SubagentStop notification hook - cross-platform (Windows/Linux/WSL)
Plays subtle sound + shows desktop notification when subagent completes.
"""

import json
import subprocess
import sys
import platform
import os
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from notification_utils import notify_discord

NTFY_TOPIC = os.environ.get("CLAUDE_NTFY_TOPIC", "")
DEFAULT_MESSAGE = "Task completed"
ACTIVITY_WEBHOOK_SECRET_ID = os.environ.get("BWS_DISCORD_ACTIVITY_SECRET_ID", "")


CACHE_DIR = os.path.join(os.path.expanduser("~"), ".claude", "cache")
LOG_FILE = os.path.join(CACHE_DIR, "subagent-notify-debug.log")


def log_debug(message: str) -> None:
    """Append debug message to log file."""
    try:
        with open(LOG_FILE, "a") as f:
            f.write(f"{datetime.now().isoformat()} - {message}\n")
    except Exception:
        pass


def get_task_info_from_stdin() -> str:
    """Extract agent type and description from session transcript."""
    try:
        stdin_data = sys.stdin.read()
        hook_input = json.loads(stdin_data)

        agent_id = hook_input.get("agent_id", "")
        transcript_path = hook_input.get("transcript_path", "")
        agent_transcript_path = hook_input.get("agent_transcript_path", "")

        log_debug(f"agent_id={agent_id}")

        # Check if this is a prompt_suggestion agent (internal, skip notification)
        if agent_transcript_path and "prompt_suggestion" in agent_transcript_path:
            log_debug("skipping prompt_suggestion agent")
            return ""  # Empty string signals to skip notification

        # Skip if agent transcript doesn't exist (ephemeral/internal agent)
        if not agent_transcript_path or not os.path.exists(agent_transcript_path):
            log_debug(f"no agent transcript file, skipping")
            return ""

        if not transcript_path or not os.path.exists(transcript_path):
            log_debug(f"transcript not found or empty path")
            return f"Agent {agent_id} completed" if agent_id else DEFAULT_MESSAGE

        # Find the Task tool call that spawned this agent (with retry for race condition)
        tool_use_id = None
        for attempt in range(3):
            with open(transcript_path, "r") as f:
                for line in f:
                    if agent_id in line and "agent_progress" in line:
                        entry = json.loads(line)
                        tool_use_id = entry.get("parentToolUseID", "")
                        log_debug(f"found agent_progress, tool_use_id={tool_use_id}")
                        break
            if tool_use_id:
                break
            log_debug(f"attempt {attempt + 1}: no agent_progress yet, waiting...")
            time.sleep(0.1)

        if not tool_use_id:
            log_debug(f"no tool_use_id found for agent {agent_id} after retries")
            return f"Agent {agent_id} completed" if agent_id else DEFAULT_MESSAGE

        # Find the Task tool input with description and subagent_type
        with open(transcript_path, "r") as f:
            for line in f:
                if tool_use_id in line and '"name":"Task"' in line:
                    entry = json.loads(line)
                    message = entry.get("message", {})
                    content = message.get("content", [])
                    for item in content:
                        if item.get("id") == tool_use_id:
                            task_input = item.get("input", {})
                            agent_type = task_input.get("subagent_type", "")
                            description = task_input.get("description", "")
                            log_debug(
                                f"found Task input: type={agent_type}, desc={description}"
                            )
                            if agent_type and description:
                                return f"{agent_type}: {description}"
                            elif description:
                                return description
                            elif agent_type:
                                return f"{agent_type} completed"
                    break

        log_debug(f"no Task tool found with id {tool_use_id}")
        return f"Agent {agent_id} completed" if agent_id else DEFAULT_MESSAGE

    except Exception as e:
        log_debug(f"exception: {type(e).__name__}: {e}")
    return DEFAULT_MESSAGE


def get_project_name() -> str:
    """Get project name from working directory."""
    return os.path.basename(os.getcwd())


def notify_ntfy(title: str, message: str, priority: str = "default") -> None:
    """Send push notification via ntfy.sh with title and message."""
    if not NTFY_TOPIC:
        return
    try:
        subprocess.Popen(
            [
                "curl",
                "-s",
                "-H",
                f"Priority: {priority}",
                "-H",
                "Tags: bell",
                "-H",
                f"Title: {title}",
                "-d",
                message,
                f"https://ntfy.sh/{NTFY_TOPIC}",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        pass


def is_wsl() -> bool:
    """Detect if running in Windows Subsystem for Linux."""
    if platform.system() != "Linux":
        return False
    try:
        with open("/proc/version", "r") as f:
            return "microsoft" in f.read().lower()
    except FileNotFoundError:
        return False


TOAST_SCRIPT_TEMPLATE = r"""
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

# Enable DPI awareness for sharp text
[Win32]::SetProcessDPIAware() | Out-Null

$form = New-Object System.Windows.Forms.Form
$form.FormBorderStyle = [System.Windows.Forms.FormBorderStyle]::None
$form.Size = New-Object System.Drawing.Size(520, 110)
$form.ShowInTaskbar = $false
$form.BackColor = [System.Drawing.Color]::FromArgb(66, 135, 245)
$form.StartPosition = [System.Windows.Forms.FormStartPosition]::Manual

# Position at bottom center of primary screen
$screen = [System.Windows.Forms.Screen]::PrimaryScreen.WorkingArea
$x = [int]($screen.Left + ($screen.Width - 520) / 2)
$y = [int]($screen.Bottom - 110 - 50)
$form.Location = New-Object System.Drawing.Point($x, $y)

# Inner panel for dark background (creates border effect)
$inner = New-Object System.Windows.Forms.Panel
$inner.Size = New-Object System.Drawing.Size(514, 104)
$inner.Location = New-Object System.Drawing.Point(3, 3)
$inner.BackColor = [System.Drawing.Color]::FromArgb(45, 45, 45)
$form.Controls.Add($inner)

# Title label (project name)
$titleLabel = New-Object System.Windows.Forms.Label
$titleLabel.Text = "{title}"
$titleLabel.Font = New-Object System.Drawing.Font("Segoe UI", 12, [System.Drawing.FontStyle]::Bold)
$titleLabel.ForeColor = [System.Drawing.Color]::FromArgb(120, 180, 255)
$titleLabel.AutoSize = $false
$titleLabel.Size = New-Object System.Drawing.Size(514, 30)
$titleLabel.Location = New-Object System.Drawing.Point(0, 8)
$titleLabel.TextAlign = [System.Drawing.ContentAlignment]::MiddleCenter
$inner.Controls.Add($titleLabel)

# Message label
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
$timer.Interval = 6000
$timer.Add_Tick({{ $form.Close() }})
$timer.Start()

# Make click-through and show without stealing focus
$exStyle = [Win32]::GetWindowLong($form.Handle, [Win32]::GWL_EXSTYLE)
[Win32]::SetWindowLong($form.Handle, [Win32]::GWL_EXSTYLE, $exStyle -bor [Win32]::WS_EX_LAYERED -bor [Win32]::WS_EX_TRANSPARENT)
[Win32]::SetLayeredWindowAttributes($form.Handle, 0, 230, [Win32]::LWA_ALPHA)
[Win32]::SetWindowPos($form.Handle, [Win32]::HWND_TOPMOST, $x, $y, 520, 110, [Win32]::SWP_NOACTIVATE -bor [Win32]::SWP_SHOWWINDOW)
$form.Show()
[System.Windows.Forms.Application]::Run($form)
"""


def build_toast_script(title: str, message: str) -> str:
    """Build PowerShell toast script with dynamic title and message."""
    safe_title = title.replace('"', '`"').replace("'", "`'")
    safe_message = message.replace('"', '`"').replace("'", "`'")
    return TOAST_SCRIPT_TEMPLATE.format(title=safe_title, message=safe_message)


def notify_windows(title: str, message: str) -> None:
    """Windows bottom-center toast notification - non-blocking, no title bar."""
    script = build_toast_script(title, message)
    subprocess.Popen(
        ["powershell", "-ExecutionPolicy", "Bypass", "-Command", script],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW
        if hasattr(subprocess, "CREATE_NO_WINDOW")
        else 0,
    )


def notify_wsl(title: str, message: str) -> None:
    """WSL bottom-center toast notification - non-blocking, no title bar."""
    script = build_toast_script(title, message)
    try:
        subprocess.Popen(
            ["powershell.exe", "-ExecutionPolicy", "Bypass", "-Command", script],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except FileNotFoundError:
        pass


def notify_linux() -> None:
    """Linux notification using notify-send."""
    subprocess.Popen(
        [
            "notify-send",
            "-t",
            "3000",
            "-i",
            "dialog-information",
            "Claude Code",
            "Subagent task completed",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def sound_windows() -> None:
    """Windows sound - play notification wav file."""
    subprocess.Popen(
        [
            "powershell",
            "-WindowStyle",
            "Hidden",
            "-Command",
            "(New-Object Media.SoundPlayer 'C:\\Windows\\Media\\Windows Battery Critical.wav').PlaySync()",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW
        if hasattr(subprocess, "CREATE_NO_WINDOW")
        else 0,
    )


def sound_wsl() -> None:
    """WSL sound - plays Windows notification wav via powershell.exe."""
    try:
        subprocess.Popen(
            [
                "powershell.exe",
                "-WindowStyle",
                "Hidden",
                "-Command",
                "(New-Object Media.SoundPlayer 'C:\\Windows\\Media\\Windows Battery Critical.wav').PlaySync()",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        pass


def sound_linux() -> None:
    """Linux sound - try multiple methods."""
    sound_file = "/usr/share/sounds/freedesktop/stereo/message.oga"

    if os.path.exists(sound_file):
        for player in ["paplay", "aplay", "play"]:
            try:
                subprocess.Popen(
                    [player, sound_file],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                return
            except FileNotFoundError:
                continue

    # Fallback: terminal bell
    print("\a", end="", flush=True)


def main() -> None:
    system = platform.system()

    project_name = get_project_name()
    task_description = get_task_info_from_stdin()

    # Skip notification for internal agents (empty description)
    if not task_description:
        return

    # Always send to phone with project context
    notify_ntfy(title=project_name, message=task_description)
    notify_discord(
        title=project_name,
        message=task_description,
        webhook_secret_id=ACTIVITY_WEBHOOK_SECRET_ID,
    )

    if system == "Windows":
        sound_windows()
        notify_windows(project_name, task_description)
    elif is_wsl():
        sound_wsl()
        notify_wsl(project_name, task_description)
    elif system == "Linux":
        sound_linux()
        notify_linux()
    else:
        # macOS or other - just print bell
        print("\a", end="", flush=True)


if __name__ == "__main__":
    main()
