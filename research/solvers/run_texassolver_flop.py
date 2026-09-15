#!/usr/bin/env python3
"""Time a TexasSolver full-range flop solve under a hard wall-clock bound.

Why this exists: RESOURCES_SOLVERS.md claims a full three-street flop tree is
not a decision-time solve on this laptop. That claim needs a number anyone can
reproduce, so this script runs the exact command file beside it, stops the
solver at a fixed deadline, and prints the iterations reached together with the
wall-clock and CPU time actually used.

Usage:
    python3 run_texassolver_flop.py <path-to-console_solver-dir> [seconds]

The directory is the unpacked TexasSolver v0.2.0 macOS release (it must contain
`console_solver`); the solver is not vendored into this repository. The command
file `texassolver_flop_full_ranges.txt` is copied in beside the binary because
TexasSolver resolves its dump path relative to its working directory.
"""

import os
import re
import resource
import shutil
import signal
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
COMMANDS = os.path.join(HERE, "texassolver_flop_full_ranges.txt")


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    solver_dir = os.path.abspath(sys.argv[1])
    deadline = float(sys.argv[2]) if len(sys.argv) > 2 else 600.0
    binary = os.path.join(solver_dir, "console_solver")
    if not os.path.exists(binary):
        print(f"no console_solver in {solver_dir}")
        return 2

    shutil.copy(COMMANDS, os.path.join(solver_dir, "flop_full_ranges.txt"))
    log_path = os.path.join(solver_dir, "flop_run.log")

    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    started = time.monotonic()
    with open(log_path, "wb") as log:
        proc = subprocess.Popen(
            [binary, "-i", "flop_full_ranges.txt"],
            cwd=solver_dir,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        while proc.poll() is None and time.monotonic() - started < deadline:
            time.sleep(1.0)
        killed = proc.poll() is None
        if killed:
            os.kill(proc.pid, signal.SIGKILL)
        status = proc.wait()
    wall = time.monotonic() - started
    after = resource.getrusage(resource.RUSAGE_CHILDREN)

    with open(log_path, "rb") as log:
        text = log.read().decode("utf-8", "replace").replace("\r", "\n")
    iterations = [int(m) for m in re.findall(r"^Iter: (\d+)", text, re.M)]
    exploit = re.findall(r"^Total exploitability ([0-9.]+) precent", text, re.M)

    cpu = (after.ru_utime - before.ru_utime) + (after.ru_stime - before.ru_stime)
    print(f"command file:  {COMMANDS}")
    print(f"solver:        {binary}")
    print(f"threads:       as set in the command file (set_thread_num)")
    print(f"stopped by:    {'deadline' if killed else 'solver itself'}")
    print(f"wall:          {wall:.1f} s")
    print(f"cpu:           {cpu:.1f} s  ({cpu / wall:.2f} cores busy on average)")
    print(f"max rss:       {after.ru_maxrss / (1024 ** 3):.2f} GiB")
    print(f"iterations:    {iterations}")
    print(f"exploitability (% of pot, in order): {exploit}")
    print(f"exit status:   {status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
