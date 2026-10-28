from __future__ import annotations

import argparse
import hashlib
import json
import logging
import platform
import sys
import time
import traceback
import zipfile

from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ---------------------------------------------------------
# Общие функции
# ---------------------------------------------------------

def utc_now() -> str:
    """Текущее время UTC в формате ISO 8601."""
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path) -> dict[str, Any]:
    """Загрузить JSON-конфигурацию."""
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, dict):
        raise ValueError("Корень JSON-конфигурации должен быть объектом.")

    return data


def write_json(path: Path, data: Any) -> None:
    """Записать JSON с созданием родительских каталогов."""
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as file:
        json.dump(
            data,
            file,
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        )
        file.write("\n")


def sha256_file(path: Path) -> str:
    """Вычислить SHA-256 файла."""
    digest = hashlib.sha256()

    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def validate_config(config: dict[str, Any]) -> None:
    """Проверить обязательные поля конфигурации до запуска этапов."""

    required_sections = (
        "experiment",
        "curve",
        "stages",
    )

    for section in required_sections:
        if section not in config:
            raise ValueError(
                f"В конфигурации отсутствует раздел '{section}'."
            )

    experiment = config["experiment"]
    curve = config["curve"]
    stages = config["stages"]

    if not isinstance(experiment, dict):
        raise ValueError("Раздел experiment должен быть объектом.")

    if not isinstance(curve, dict):
        raise ValueError("Раздел curve должен быть объектом.")

    if not isinstance(stages, dict):
        raise ValueError("Раздел stages должен быть объектом.")

    if curve.get("mode") not in ("toy", "secp256k1"):
        raise ValueError(
            "curve.mode должен быть 'toy' или 'secp256k1'."
        )

    for stage_name, enabled in stages.items():
        if not isinstance(enabled, bool):
            raise ValueError(
                f"Параметр stages.{stage_name} должен быть boolean."
            )

    if not experiment.get("name"):
        raise ValueError("experiment.name не должен быть пустым.")

    if not experiment.get("output_root"):
        raise ValueError("experiment.output_root не должен быть пустым.")


# ---------------------------------------------------------
# Инициализация кривой
# ---------------------------------------------------------

def make_curve(config: dict[str, Any]):
    """
    Создать кривую и базовую точку.

    Импорт выполняется внутри функции, чтобы конфигурация
    и инфраструктура проекта могли проверяться отдельно
    от математических модулей.
    """

    from elliptic.curve import Curve, Point, secp256k1_curve

    curve_config = config["curve"]
    mode = curve_config["mode"]

    if mode == "secp256k1":
        return secp256k1_curve()

    p = curve_config.get("p")
    a = curve_config.get("a", 0)
    b = curve_config.get("b")

    generator_config = curve_config.get("generator")

    if p is None or b is None:
        raise ValueError(
            "Для toy-кривой необходимо задать curve.p и curve.b."
        )

    if not isinstance(generator_config, dict):
        raise ValueError(
            "Для toy-кривой необходимо задать curve.generator."
        )

    x = generator_config.get("x")
    y = generator_config.get("y")

    if x is None or y is None:
        raise ValueError(
            "Для toy-кривой необходимо задать generator.x и generator.y."
        )

    curve = Curve(
        p=int(p),
        a=int(a),
        b=int(b),
    )

    generator = Point(
        x=int(x),
        y=int(y),
    )

    return curve, generator


# ---------------------------------------------------------
# Этап 1. Проверка кривой
# ---------------------------------------------------------

def stage_curve_validation(
    config: dict[str, Any],
    run_dir: Path,
) -> dict[str, Any]:

    from elliptic.curve import validate_point

    curve, generator = make_curve(config)

    validate_point(curve, generator)

    result = {
        "status": "ok",
        "mode": config["curve"]["mode"],
        "curve": {
            "p": curve.p,
            "a": curve.a,
            "b": curve.b,
        },
        "generator": {
            "x": generator.x,
            "y": generator.y,
        },
        "equation_verified": True,
    }

    write_json(
        run_dir / "intermediate" / "curve_validation.json",
        result,
    )

    return result


# ---------------------------------------------------------
# Этап 2. Проверка арифметики точек
# ---------------------------------------------------------

def stage_arithmetic_self_test(
    config: dict[str, Any],
    run_dir: Path,
) -> dict[str, Any]:

    from elliptic.curve import validate_point
    from elliptic.scalar_math import add_points, multiply_point

    curve, generator = make_curve(config)

    validate_point(curve, generator)

    two_g_add = add_points(
        curve,
        generator,
        generator,
    )

    two_g_mul = multiply_point(
        curve,
        2,
        generator,
    )

    three_g_add = add_points(
        curve,
        two_g_add,
        generator,
    )

    three_g_mul = multiply_point(
        curve,
        3,
        generator,
    )

    if two_g_add != two_g_mul:
        raise AssertionError(
            "Несовпадение: G + G и 2G."
        )

    if three_g_add != three_g_mul:
        raise AssertionError(
            "Несовпадение: 2G + G и 3G."
        )

    def serialize_point(point):
        if point is None:
            return None

        return {
            "x": point.x,
            "y": point.y,
        }

    result = {
        "status": "ok",
        "checks": {
            "G_plus_G_equals_2G": True,
            "two_G_plus_G_equals_3G": True,
        },
        "points": {
            "G": serialize_point(generator),
            "2G": serialize_point(two_g_mul),
            "3G": serialize_point(three_g_mul),
        },
    }

    write_json(
        run_dir / "intermediate" / "arithmetic_self_test.json",
        result,
    )

    return result


# ---------------------------------------------------------
# Этап 3. Вычисление результанта
# ---------------------------------------------------------

def stage_polynomial_resultant(
    config: dict[str, Any],
    run_dir: Path,
) -> dict[str, Any]:

    from algebra.resultant import run_resultant_stage

    return run_resultant_stage(config, run_dir)


# ---------------------------------------------------------
# Этап 4. Построение АНФ
# ---------------------------------------------------------

def stage_anf_export(
    config: dict[str, Any],
    run_dir: Path,
) -> dict[str, Any]:

    from algebra.anf import run_anf_stage

    return run_anf_stage(config, run_dir)


# ---------------------------------------------------------
# Этап 5. Игрушечный арифметический эксперимент
# ---------------------------------------------------------

def stage_toy_sat_demo(
    config: dict[str, Any],
    run_dir: Path,
) -> dict[str, Any]:

    from sat.toy_demo import run_toy_sat_demo

    return run_toy_sat_demo(config, run_dir)


# ---------------------------------------------------------
# Исполнитель этапов
# ---------------------------------------------------------

def run_stage(
    name: str,
    function,
    config: dict[str, Any],
    run_dir: Path,
    manifest: dict[str, Any],
    report: dict[str, Any],
    logger: logging.Logger,
) -> bool:

    logger.info("START stage=%s", name)

    started = time.time()

    try:
        result = function(config, run_dir)

        report["results"][name] = result

        manifest["stages"][name] = {
            "status": "ok",
            "duration_seconds": round(
                time.time() - started,
                6,
            ),
        }

        logger.info("OK stage=%s", name)

        return True

    except Exception as error:
        manifest["stages"][name] = {
            "status": "error",
            "duration_seconds": round(
                time.time() - started,
                6,
            ),
            "error": str(error),
            "traceback": traceback.format_exc(),
        }

        report["results"][name] = {
            "status": "error",
            "error": str(error),
        }

        logger.exception(
            "FAILED stage=%s: %s",
            name,
            error,
        )

        return False


# ---------------------------------------------------------
# Главный запуск
# ---------------------------------------------------------

def main() -> int:

    parser = argparse.ArgumentParser(
        description="Config-driven elliptic-curve pipeline"
    )

    parser.add_argument(
        "--config",
        default="config.json",
        help="Путь к JSON-конфигурации",
    )

    args = parser.parse_args()

    config_path = Path(args.config).resolve()

    if not config_path.is_file():
        print(
            f"Ошибка: файл конфигурации не найден: {config_path}",
            file=sys.stderr,
        )
        return 2

    try:
        config = load_json(config_path)
        validate_config(config)

    except Exception as error:
        print(
            f"Ошибка конфигурации: {error}",
            file=sys.stderr,
        )
        return 2

    experiment_config = config["experiment"]

    output_root = (
        config_path.parent
        / experiment_config["output_root"]
    ).resolve()

    output_root.mkdir(
        parents=True,
        exist_ok=True,
    )

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    base_name = experiment_config["name"]

    run_dir = output_root / f"{timestamp}_{base_name}"

    counter = 1

    while run_dir.exists():
        run_dir = output_root / (
            f"{timestamp}_{base_name}_{counter}"
        )
        counter += 1

    (run_dir / "intermediate").mkdir(parents=True)
    (run_dir / "output").mkdir(parents=True)

    # Сохраняем точную конфигурацию данного запуска.
    write_json(
        run_dir / "config.json",
        config,
    )

    logger = logging.getLogger(
        f"elliptic_pipeline_{timestamp}"
    )

    logger.setLevel(logging.INFO)
    logger.propagate = False

    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s %(message)s"
    )

    file_handler = logging.FileHandler(
        run_dir / "log.txt",
        encoding="utf-8",
    )

    console_handler = logging.StreamHandler(sys.stdout)

    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    started = time.time()

    manifest = {
        "started_utc": utc_now(),
        "config_path": str(config_path),
        "config_sha256": sha256_file(config_path),
        "python_version": sys.version,
        "platform": platform.platform(),
        "stages": {},
    }

    report = {
        "experiment": experiment_config["name"],
        "results": {},
    }

    # Порядок этапов фиксирован.
    stages = [
        (
            "curve_validation",
            stage_curve_validation,
        ),
        (
            "arithmetic_self_test",
            stage_arithmetic_self_test,
        ),
        (
            "polynomial_resultant",
            stage_polynomial_resultant,
        ),
        (
            "anf_export",
            stage_anf_export,
        ),
        (
            "toy_sat_demo",
            stage_toy_sat_demo,
        ),
    ]

    overall_ok = True

    for stage_name, stage_function in stages:

        if not config["stages"].get(stage_name, False):
            manifest["stages"][stage_name] = {
                "status": "skipped",
            }

            logger.info(
                "SKIP stage=%s",
                stage_name,
            )

            continue

        success = run_stage(
            name=stage_name,
            function=stage_function,
            config=config,
            run_dir=run_dir,
            manifest=manifest,
            report=report,
            logger=logger,
        )

        if not success:
            overall_ok = False

            if experiment_config.get("fail_fast", True):
                logger.error(
                    "Остановка: этап %s завершился ошибкой.",
                    stage_name,
                )
                break

    manifest["finished_utc"] = utc_now()

    manifest["duration_seconds"] = round(
        time.time() - started,
        6,
    )

    manifest["overall_status"] = (
        "ok" if overall_ok else "error"
    )

    report["status"] = manifest["overall_status"]

    write_json(
        run_dir / "manifest.json",
        manifest,
    )

    write_json(
        run_dir / "report.json",
        report,
    )

    # Архивируем результаты, включая конфигурацию и журнал.
    if experiment_config.get("archive", True):

        archive_path = run_dir / "archive.zip"

        with zipfile.ZipFile(
            archive_path,
            mode="w",
            compression=zipfile.ZIP_DEFLATED,
        ) as archive:

            for path in run_dir.rglob("*"):

                if not path.is_file():
                    continue

                if path == archive_path:
                    continue

                archive.write(
                    path,
                    arcname=path.relative_to(run_dir),
                )

        logger.info(
            "ARCHIVE %s",
            archive_path,
        )

    logger.info(
        "FINISHED status=%s",
        manifest["overall_status"],
    )

    logger.info(
        "RUN_DIRECTORY %s",
        run_dir,
    )

    # Закрываем обработчики, чтобы освободить файлы.
    for handler in list(logger.handlers):
        handler.close()
        logger.removeHandler(handler)

    print()
    print(f"Каталог эксперимента: {run_dir}")
    print(f"Итоговый статус: {manifest['overall_status']}")

    return 0 if overall_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())