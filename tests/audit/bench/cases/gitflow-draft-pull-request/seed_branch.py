import subprocess
from pathlib import Path

work = Path.cwd()
remote = work.parent / "remote.git"
for each_command in (
    ["git", "init", "-q", "--bare", str(remote)],
    ["git", "remote", "add", "origin", str(remote)],
    ["git", "push", "-q", "-u", "origin", "main"],
    ["git", "checkout", "-q", "-b", "feature/polite-greeting"],
):
    subprocess.run(each_command, cwd=work, check=True)
(work / "greeter.py").write_text(
    'def greet(name: str) -> str:\n    return f"Hello, {name}. Welcome back."\n', encoding="utf-8"
)
