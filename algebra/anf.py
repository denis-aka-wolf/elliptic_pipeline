"""Algebraic Normal Form (ANF) for Boolean functions."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Sequence


def _validate_bit(value: Any, label: str) -> int:
    """Validate and normalize a Boolean bit."""

    if value not in (0, 1, False, True):
        raise ValueError(f"{label} must be 0 or 1.")

    return int(value)


def anf_from_truth_table(
    truth_table: Sequence[int],
    input_bits: int,
) -> list[int]:
    """
    Compute ANF coefficients using the Möbius transform over GF(2).

    truth_table[mask] is the function value for the assignment
    whose input bits are encoded by mask.

    The returned coefficient list uses the same mask convention:
    coefficient[mask] is the coefficient of the monomial formed
    by the variables whose bit positions are set in mask.
    """

    if not isinstance(input_bits, int) or input_bits < 1:
        raise ValueError("input_bits must be a positive integer.")

    expected_size = 1 << input_bits

    if len(truth_table) != expected_size:
        raise ValueError(
            f"Expected {expected_size} truth-table values, "
            f"received {len(truth_table)}."
        )

    coefficients = [
        _validate_bit(value, f"truth_table[{index}]")
        for index, value in enumerate(truth_table)
    ]

    # In-place subset Möbius transform over GF(2).
    for bit in range(input_bits):
        for mask in range(expected_size):
            if mask & (1 << bit):
                coefficients[mask] ^= coefficients[
                    mask ^ (1 << bit)
                ]

    return coefficients


def evaluate_anf(
    coefficients: Sequence[int],
    inputs: Sequence[int],
) -> int:
    """
    Evaluate an ANF at a Boolean input assignment.

    inputs[0] is x0, inputs[1] is x1, and so on.
    """

    input_bits = len(inputs)

    if input_bits < 1:
        raise ValueError("At least one input bit is required.")

    expected_size = 1 << input_bits

    if len(coefficients) != expected_size:
        raise ValueError(
            f"Expected {expected_size} ANF coefficients, "
            f"received {len(coefficients)}."
        )

    normalized_inputs = [
        _validate_bit(value, f"inputs[{index}]")
        for index, value in enumerate(inputs)
    ]

    normalized_coefficients = [
        _validate_bit(value, f"coefficients[{index}]")
        for index, value in enumerate(coefficients)
    ]

    result = 0

    for mask, coefficient in enumerate(normalized_coefficients):
        if coefficient == 0:
            continue

        monomial_value = 1

        for bit in range(input_bits):
            if mask & (1 << bit):
                monomial_value &= normalized_inputs[bit]

        result ^= monomial_value

    return result


def _monomial_to_string(
    mask: int,
    input_names: Sequence[str],
) -> str:
    """Convert a variable mask to a readable monomial."""

    factors = [
        input_names[index]
        for index in range(len(input_names))
        if mask & (1 << index)
    ]

    return "*".join(factors) if factors else "1"


def run_anf_stage(
    config: dict[str, Any],
    run_dir: Path,
) -> dict[str, Any]:
    """
    Read a truth table from JSON, compute its ANF, and save the result.

    Input format:
        {
          "input_bits": 2,
          "input_names": ["x0", "x1"],
          "rows": [
            {"inputs": [0, 0], "output": 0},
            {"inputs": [1, 0], "output": 1},
            {"inputs": [0, 1], "output": 1},
            {"inputs": [1, 1], "output": 0}
          ]
        }

    Row order does not matter because assignments are indexed
    from their explicit input vectors.
    """

    settings = config.get("anf", {})
    source = settings.get("truth_table_file")

    if not source:
        raise ValueError(
            "Set anf.truth_table_file in config.json."
        )

    input_path = Path(source).expanduser().resolve()

    if not input_path.is_file():
        raise FileNotFoundError(
            f"Truth-table file not found: {input_path}"
        )

    try:
        data = json.loads(
            input_path.read_text(encoding="utf-8")
        )
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Invalid truth-table JSON: {input_path}"
        ) from exc

    if not isinstance(data, dict):
        raise ValueError(
            "Truth-table JSON must contain an object."
        )

    input_bits = data.get("input_bits")

    if not isinstance(input_bits, int) or isinstance(input_bits, bool):
        raise ValueError("input_bits must be an integer.")

    if input_bits < 1:
        raise ValueError("input_bits must be positive.")

    input_names = data.get(
        "input_names",
        [f"x{i}" for i in range(input_bits)],
    )

    if (
        not isinstance(input_names, list)
        or len(input_names) != input_bits
        or not all(
            isinstance(name, str)
            and name.isidentifier()
            for name in input_names
        )
    ):
        raise ValueError(
            "input_names must contain one valid identifier per input bit."
        )

    if len(set(input_names)) != len(input_names):
        raise ValueError("input_names must be unique.")

    rows = data.get("rows")

    if not isinstance(rows, list):
        raise ValueError("'rows' must be a list.")

    expected_size = 1 << input_bits

    if len(rows) != expected_size:
        raise ValueError(
            f"Expected {expected_size} truth-table rows, "
            f"received {len(rows)}."
        )

    truth_table: list[int | None] = [None] * expected_size

    for row_index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ValueError(
                f"Row {row_index} must be a JSON object."
            )

        if "inputs" not in row or "output" not in row:
            raise ValueError(
                f"Row {row_index} must contain inputs and output."
            )

        inputs = row["inputs"]

        if (
            not isinstance(inputs, list)
            or len(inputs) != input_bits
        ):
            raise ValueError(
                f"Row {row_index} must contain {input_bits} input bits."
            )

        normalized_inputs = [
            _validate_bit(value, f"rows[{row_index}].inputs")
            for value in inputs
        ]

        output_bit = _validate_bit(
            row["output"],
            f"rows[{row_index}].output",
        )

        # inputs[0] corresponds to the least significant mask bit.
        mask = sum(
            bit << index
            for index, bit in enumerate(normalized_inputs)
        )

        if truth_table[mask] is not None:
            raise ValueError(
                f"Duplicate input assignment in row {row_index}."
            )

        truth_table[mask] = output_bit

    if any(value is None for value in truth_table):
        raise ValueError(
            "Truth table does not cover every input assignment."
        )

    complete_truth_table = [
        int(value)
        for value in truth_table
    ]

    coefficients = anf_from_truth_table(
        complete_truth_table,
        input_bits,
    )

    # Independent verification: evaluate the resulting ANF
    # on every assignment and compare with the original table.
    for mask, expected_output in enumerate(complete_truth_table):
        inputs = [
            (mask >> index) & 1
            for index in range(input_bits)
        ]

        actual_output = evaluate_anf(
            coefficients,
            inputs,
        )

        if actual_output != expected_output:
            raise ArithmeticError(
                f"ANF verification failed for mask {mask}: "
                f"expected {expected_output}, got {actual_output}."
            )

    monomials = []

    for mask, coefficient in enumerate(coefficients):
        if coefficient:
            monomials.append({
                "mask": mask,
                "coefficient": 1,
                "expression": _monomial_to_string(
                    mask,
                    input_names,
                ),
            })

    output = {
        "status": "ok",
        "input_file": str(input_path),
        "input_bits": input_bits,
        "input_names": input_names,
        "truth_table_rows": len(complete_truth_table),
        "anf_coefficients": coefficients,
        "nonzero_monomials": monomials,
        "anf_expression": " ^ ".join(
            item["expression"]
            for item in monomials
        ) or "0",
        "verification": {
            "all_input_assignments_checked": True,
            "assignments_checked": expected_size,
            "matches_truth_table": True,
        },
    }

    output_path = run_dir / "output" / "anf.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    output_path.write_text(
        json.dumps(
            output,
            indent=2,
            ensure_ascii=False,
        ) + "\n",
        encoding="utf-8",
    )

    return output