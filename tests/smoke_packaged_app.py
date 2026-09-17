from __future__ import annotations

import argparse
import os
import subprocess
import time
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("executable", type=Path)
    parser.add_argument("--seconds", type=float, default=8.0)
    args = parser.parse_args()

    executable = args.executable.resolve()
    if not executable.is_file():
        raise SystemExit(f"Packaged executable not found: {executable}")

    environment = os.environ.copy()
    environment.setdefault("QT_QPA_PLATFORM", "offscreen")
    process = subprocess.Popen(
        [str(executable)],
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        deadline = time.monotonic() + args.seconds
        while time.monotonic() < deadline:
            code = process.poll()
            if code is not None:
                stdout, stderr = process.communicate()
                raise SystemExit(
                    f"Packaged application exited early with code {code}.\n"
                    f"stdout:\n{stdout}\nstderr:\n{stderr}"
                )
            time.sleep(0.25)
        print(f"Packaged application stayed alive for {args.seconds:.1f} seconds")
        return 0
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


if __name__ == "__main__":
    raise SystemExit(main())