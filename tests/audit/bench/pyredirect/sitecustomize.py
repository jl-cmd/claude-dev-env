"""Point a child Python's home lookups at the arm's substitute home.

::

    BENCH_ARM_HOME=<run>/home   ->   Path.home() == <run>/home

The model session keeps the live home so the CLI can sign in. Every Python
the session starts loads this module first and swaps the home variables.
"""

import os

arm_home = os.environ.get("BENCH_ARM_HOME", "")
if arm_home:
    drive, tail = os.path.splitdrive(arm_home)
    os.environ["USERPROFILE"] = arm_home
    os.environ["HOME"] = arm_home
    os.environ["HOMEDRIVE"] = drive
    os.environ["HOMEPATH"] = tail
