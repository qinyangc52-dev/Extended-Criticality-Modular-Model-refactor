from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def run_simulation(
    executable: str | Path,
    seed_file: str | Path,
    run_root: str | Path = "results/runs",
    run_name: str | None = None,
    timeout: int | None = None,
) -> Path:
    """Run the C/C++ simulator in an isolated directory containing a SEED file."""
    executable = Path(executable).resolve()
    seed_file = Path(seed_file).resolve()
    if not executable.exists():
        raise FileNotFoundError(f"Simulator executable not found: {executable}")
    if not seed_file.exists():
        raise FileNotFoundError(f"Seed file not found: {seed_file}")

    name = run_name or seed_file.stem
    run_dir = Path(run_root).resolve() / name
    run_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(seed_file, run_dir / "SEED")

    completed = subprocess.run(
        [str(executable)],
        cwd=run_dir,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout,
        check=False,
    )
    (run_dir / "run.log").write_text(completed.stdout, encoding="utf-8", errors="replace")
    if completed.returncode != 0:
        raise RuntimeError(f"Simulation failed with exit code {completed.returncode}; see {run_dir / 'run.log'}")
    return run_dir

