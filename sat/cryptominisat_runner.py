from __future__ import annotations

import json
import shutil
import subprocess
import time

from pathlib import Path
from typing import Any


def find_solver(executable: str | None = None) -> str:
    """Найти исполняемый файл CryptoMiniSat."""

    candidates = []

    if executable:
        candidates.append(executable)

    candidates.extend([
        "cryptominisat5",
        "cryptominisat5.exe",
        "cryptominisat",
    ])

    for candidate in candidates:
        resolved = shutil.which(candidate)

        if resolved:
            return resolved

        path = Path(candidate)

        if path.is_file():
            return str(path.resolve())

    raise FileNotFoundError(
        "CryptoMiniSat не найден. Передай путь к "
        "cryptominisat5.exe через параметр executable."
    )


def parse_solver_output(output: str) -> dict[str, Any]:
    """Разобрать статус и присваивание из стандартного вывода."""

    status = "UNKNOWN"
    assignment: dict[int, bool] = {}
    conflicts: list[str] = []

    for raw_line in output.splitlines():
        line = raw_line.strip()

        if not line:
            continue

        if line.startswith("s "):
            token = line[2:].strip().upper()

            if "UNSATISFIABLE" in token:
                status = "UNSAT"
            elif "SATISFIABLE" in token:
                status = "SAT"

        elif line.startswith("v "):
            for token in line[2:].split():
                try:
                    literal = int(token)
                except ValueError:
                    continue

                if literal == 0:
                    continue

                assignment[abs(literal)] = literal > 0

        elif "ERROR" in line.upper():
            conflicts.append(line)

    return {
        "status": status,
        "assignment": assignment if status == "SAT" else None,
        "errors": conflicts,
    }


def run_cryptominisat(
    cnf_path: str | Path,
    output_dir: str | Path,
    executable: str | None = None,
    timeout_seconds: int | None = None,
    extra_args: list[str] | None = None,
) -> dict[str, Any]:
    """Запустить CryptoMiniSat и сохранить результаты."""

    cnf_path = Path(cnf_path).resolve()
    output_dir = Path(output_dir).resolve()

    if not cnf_path.is_file():
        raise FileNotFoundError(f"CNF-файл не найден: {cnf_path}")

    output_dir.mkdir(parents=True, exist_ok=True)

    solver = find_solver(executable)

    command = [solver]

    if extra_args:
        command.extend(extra_args)

    command.append(str(cnf_path))

    started = time.monotonic()

    try:
        process = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            check=False,
        )

        elapsed = time.monotonic() - started
        combined_output = (
            process.stdout
            + "\n--- STDERR ---\n"
            + process.stderr
        )

        (output_dir / "solver_stdout.txt").write_text(
            process.stdout,
            encoding="utf-8",
        )

        (output_dir / "solver_stderr.txt").write_text(
            process.stderr,
            encoding="utf-8",
        )

        parsed = parse_solver_output(combined_output)

        result = {
            "status": parsed["status"],
            "return_code": process.returncode,
            "elapsed_seconds": round(elapsed, 6),
            "command": command,
            "cnf_path": str(cnf_path),
            "assignment": (
                {
                    str(k): v
                    for k, v in parsed["assignment"].items()
                }
                if parsed["assignment"] is not None
                else None
            ),
            "errors": parsed["errors"],
        }

    except subprocess.TimeoutExpired as error:
        elapsed = time.monotonic() - started

        stdout = error.stdout or ""
        stderr = error.stderr or ""

        if isinstance(stdout, bytes):
            stdout = stdout.decode("utf-8", errors="replace")

        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", errors="replace")

        (output_dir / "solver_stdout.txt").write_text(
            stdout,
            encoding="utf-8",
        )

        (output_dir / "solver_stderr.txt").write_text(
            stderr,
            encoding="utf-8",
        )

        result = {
            "status": "TIMEOUT",
            "elapsed_seconds": round(elapsed, 6),
            "command": command,
            "cnf_path": str(cnf_path),
            "assignment": None,
            "errors": ["Превышено время ожидания CryptoMiniSat."],
        }

    with (output_dir / "solver_result.json").open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            result,
            file,
            indent=2,
            ensure_ascii=False,
        )
        file.write("\n")

    return result