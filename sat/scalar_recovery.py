from __future__ import annotations

import json

from pathlib import Path
from typing import Any


def bits_to_integer(
    assignment: dict[int, bool],
    bit_variables: list[int],
) -> int:
    """Собрать целое число из битов младший -> старший."""

    value = 0

    for bit_index, variable_id in enumerate(bit_variables):
        if variable_id not in assignment:
            raise ValueError(
                f"В присваивании отсутствует переменная {variable_id}."
            )

        if assignment[variable_id]:
            value |= 1 << bit_index

    return value


def verify_polynomial_root(
    value: int,
    modulus: int,
    coefficient_a: int,
    coefficient_b: int,
    coefficient_c: int,
) -> dict[str, Any]:
    """Проверить A*x^2 + B*x + C = 0 (mod modulus)."""

    if modulus <= 1:
        raise ValueError("Модуль должен быть больше 1.")

    expression = (
        coefficient_a * value * value
        + coefficient_b * value
        + coefficient_c
    )

    remainder = expression % modulus

    return {
        "valid": remainder == 0,
        "value": value,
        "value_hex": hex(value),
        "modulus": modulus,
        "expression": expression,
        "remainder": remainder,
    }


def verify_public_point(
    scalar: int,
    curve: Any,
    generator: Any,
    target: Any,
) -> dict[str, Any]:
    """Проверить scalar*G == Q средствами elliptic.scalar_math."""

    from elliptic.scalar_math import multiply_point

    recovered = multiply_point(curve, scalar, generator)

    valid = recovered == target

    return {
        "valid": valid,
        "scalar": scalar,
        "scalar_hex": hex(scalar),
        "target": (
            None if target is None
            else {"x": target.x, "y": target.y}
        ),
        "reconstructed": (
            None if recovered is None
            else {"x": recovered.x, "y": recovered.y}
        ),
    }


def recover_from_assignment(
    assignment: dict[int, bool],
    bit_variables: list[int],
    polynomial: dict[str, int],
    output_path: str | Path,
) -> dict[str, Any]:
    """Извлечь корень и проверить полиномиальное условие.

    Важно: успешная проверка полинома не доказывает,
    что число является скаляром исходного открытого ключа.
    """

    value = bits_to_integer(
        assignment,
        bit_variables,
    )

    check = verify_polynomial_root(
        value=value,
        modulus=int(polynomial["modulus"]),
        coefficient_a=int(polynomial["A"]),
        coefficient_b=int(polynomial["B"]),
        coefficient_c=int(polynomial["C"]),
    )

    result = {
        "status": "verified_polynomial_root" if check["valid"] else "invalid",
        "polynomial_check": check,
        "public_key_check": {
            "performed": False,
            "reason": (
                "Для проверки открытого ключа необходимы кривая, "
                "генератор и целевая точка Q."
            ),
        },
    }

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as file:
        json.dump(
            result,
            file,
            indent=2,
            ensure_ascii=False,
        )
        file.write("\n")

    return result