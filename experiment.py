from __future__ import annotations

import argparse
import json
import logging
import shutil
import sys
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

from elliptic.curve import Curve, Point, validate_curve, validate_point
from elliptic.scalar_math import multiply_point
from sat.cnf_builder import CNFFormula
from sat.cryptominisat_runner import run_cryptominisat


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, dict):
        raise ValueError("Корень JSON должен быть объектом.")
    return data


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def create_run_dir(config: dict[str, Any], config_path: Path) -> Path:
    output_cfg = config.get("output", {})
    root = Path(output_cfg.get("directory", "experiments"))
    if not root.is_absolute():
        root = config_path.parent / root

    run_name = config.get("experiment", {}).get("run_name")
    if not run_name:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        curve_name = config.get("curve", {}).get("name", "toy_curve")
        run_name = f"{stamp}_{curve_name}_scalar_recovery"

    run_dir = root / run_name
    if run_dir.exists():
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        run_dir = root / f"{run_name}_{stamp}"

    for name in ("intermediate", "generated", "output"):
        (run_dir / name).mkdir(parents=True, exist_ok=True)
    return run_dir


def build_toy_cnf(
    curve: Curve,
    generator: Point,
    target: Point,
    scalar_bits: int,
) -> tuple[CNFFormula, list[int], list[int]]:
    """
    Build a bounded truth-table CNF for the toy curve.

    This deliberately enumerates the configured k range and adds one
    blocking clause for each k that does not satisfy k*G == Q. It is a
    transparent end-to-end demo, not an efficient discrete-log algorithm.
    """
    if not 1 <= scalar_bits <= 20:
        raise ValueError(
            "Для этой демонстрационной модели scalar_bits должен быть 1..20."
        )

    formula = CNFFormula()
    bit_vars = [
        formula.new_variable(f"k_{i}")
        for i in range(scalar_bits)
    ]
    candidates = []

    for k in range(1 << scalar_bits):
        if multiply_point(curve, k, generator) == target:
            candidates.append(k)
            continue

        # Block precisely this bit assignment.
        clause = [
            -var if ((k >> i) & 1) else var
            for i, var in enumerate(bit_vars)
        ]
        formula.add_clause(clause)

    if not candidates:
        raise ValueError(
            f"Нет k в диапазоне 0..{(1 << scalar_bits) - 1}, "
            "для которого k*G=Q. Проверь точку Q и scalar_bits."
        )

    return formula, bit_vars, candidates


def decode_k(assignment: dict[int, bool], bit_vars: list[int]) -> int:
    value = 0
    for i, var in enumerate(bit_vars):
        if var not in assignment:
            raise ValueError(f"В ответе SAT отсутствует переменная {var}.")
        if assignment[var]:
            value |= 1 << i
    return value


def make_archive(run_dir: Path) -> Path:
    archive = run_dir / "archive.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in run_dir.rglob("*"):
            if path.is_file() and path != archive:
                zf.write(path, path.relative_to(run_dir))
    return archive


def run_experiment(config_path: Path) -> int:
    config = load_json(config_path)
    curve_cfg = config["curve"]
    experiment_cfg = config.get("experiment", {})
    solver_cfg = config.get("solver", {})
    output_cfg = config.get("output", {})

    curve = Curve(
        p=int(curve_cfg["p"]),
        a=int(curve_cfg.get("a", 0)),
        b=int(curve_cfg["b"]),
    )
    validate_curve(curve)

    generator = Point(int(curve_cfg["G"]["x"]), int(curve_cfg["G"]["y"]))
    target = Point(int(curve_cfg["Q"]["x"]), int(curve_cfg["Q"]["y"]))
    validate_point(curve, generator)
    validate_point(curve, target)

    scalar_bits = int(experiment_cfg.get("scalar_bits", curve.p.bit_length()))
    run_dir = create_run_dir(config, config_path)
    generated_dir = run_dir / "generated"
    intermediate_dir = run_dir / "intermediate"
    output_dir = run_dir / "output"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    shutil.copy2(config_path, run_dir / "config.json")
    logging.info("Каталог эксперимента: %s", run_dir)
    logging.info(
        "Кривая %s: p=%d, G=(%d,%d), Q=(%d,%d)",
        curve_cfg.get("name", "custom"),
        curve.p, generator.x, generator.y, target.x, target.y,
    )

    formula, bit_vars, candidates = build_toy_cnf(
        curve, generator, target, scalar_bits
    )
    cnf_path = generated_dir / "scalar_recovery.cnf"
    formula.save_dimacs(str(cnf_path))

    write_json(intermediate_dir / "cnf_manifest.json", {
        "cnf_file": "generated/scalar_recovery.cnf",
        "num_variables": formula.num_vars,
        "num_clauses": len(formula.clauses),
        "scalar_bits": scalar_bits,
        "scalar_bit_variables_lsb_first": bit_vars,
        "encoding": "bounded_toy_truth_table_blocking_clauses",
        "candidate_values_found_during_encoding": candidates,
        "warning": (
            "The toy CNF generator enumerates candidate k values to construct "
            "the formula. This demonstrates the pipeline but is not a scalable "
            "discrete-log algorithm."
        ),
    })

    executable = solver_cfg.get("executable")
    if executable:
        exe_path = Path(executable)
        if not exe_path.is_absolute() and (config_path.parent / exe_path).is_file():
            executable = str((config_path.parent / exe_path).resolve())

    logging.info(
        "CNF создан: %s; переменных=%d, клауз=%d",
        cnf_path, formula.num_vars, len(formula.clauses),
    )

    solver_result = run_cryptominisat(
        cnf_path=cnf_path,
        output_dir=output_dir / "solver",
        executable=executable,
        timeout_seconds=solver_cfg.get("timeout_seconds", 300),
        extra_args=solver_cfg.get("extra_args"),
    )
    status = solver_result["status"]
    logging.info("CryptoMiniSat status: %s", status)

    result: dict[str, Any] = {
        "status": status,
        "curve": curve_cfg.get("name", "custom"),
        "p": curve.p,
        "G": {"x": generator.x, "y": generator.y},
        "Q": {"x": target.x, "y": target.y},
        "scalar_bits": scalar_bits,
        "cnf": {
            "path": "generated/scalar_recovery.cnf",
            "num_variables": formula.num_vars,
            "num_clauses": len(formula.clauses),
        },
        "solver_result": solver_result,
        "encoding_warning": (
            "Bounded toy truth-table encoding, not suitable for large curves."
        ),
    }

    exit_code = 0
    if status == "SAT":
        raw_assignment = solver_result.get("assignment")
        if raw_assignment is None:
            result["verification_error"] = "CryptoMiniSat не вернул SAT assignment."
            exit_code = 1
        else:
            assignment = {int(k): bool(v) for k, v in raw_assignment.items()}
            try:
                k = decode_k(assignment, bit_vars)
                reconstructed = multiply_point(curve, k, generator)
                valid = reconstructed == target
                result["recovery"] = {
                    "k": k,
                    "k_hex": hex(k),
                    "public_point_check": {
                        "valid": valid,
                        "reconstructed": (
                            None if reconstructed is None
                            else {"x": reconstructed.x, "y": reconstructed.y}
                        ),
                        "target": {"x": target.x, "y": target.y},
                    },
                }
                logging.info("Найден кандидат k=%d (0x%x)", k, k)
                logging.info("Независимая проверка k*G=Q: %s", valid)
                if not valid:
                    exit_code = 1
            except Exception as exc:
                result["verification_error"] = str(exc)
                logging.exception("Ошибка реконструкции/проверки скаляра")
                exit_code = 1
    elif status == "UNSAT":
        result["message"] = "Решения в заданном диапазоне скаляра нет."
    else:
        result["message"] = f"CryptoMiniSat завершился со статусом {status}."
        exit_code = 1

    write_json(output_dir / "experiment_result.json", result)
    write_json(run_dir / "manifest.json", {
        "config": "config.json",
        "intermediate": ["intermediate/cnf_manifest.json"],
        "generated": ["generated/scalar_recovery.cnf"],
        "output": [
            "output/solver/solver_result.json",
            "output/experiment_result.json",
        ],
        "status": status,
    })

    if output_cfg.get("archive", True):
        archive = make_archive(run_dir)
        logging.info("Архив эксперимента: %s", archive)

    return exit_code


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Запуск SAT-эксперимента на игрушечной эллиптической кривой"
    )
    parser.add_argument(
        "--config",
        default="config499.json",
        help="Путь к JSON-конфигурации",
    )
    args = parser.parse_args()
    config_path = Path(args.config).resolve()

    if not config_path.is_file():
        print(f"Конфигурация не найдена: {config_path}", file=sys.stderr)
        return 2

    try:
        return run_experiment(config_path)
    except Exception as exc:
        logging.exception("Ошибка эксперимента: %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
