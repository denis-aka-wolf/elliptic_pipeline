"""Polynomial resultants and pipeline integration."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import sympy as sp

from .polynomial import build_polynomial, polynomial_info


def compute_resultant(
    f: sp.Expr,
    g: sp.Expr,
    eliminate: str | sp.Symbol,
    variables: list[str | sp.Symbol],
) -> sp.Expr:
    """
    Compute Res_eliminate(f, g).

    Raises ValueError if the elimination variable is not declared
    or either input is not a polynomial in the declared variables.
    """

    symbols = [
        sp.Symbol(v) if isinstance(v, str) else v
        for v in variables
    ]

    if len(set(symbols)) != len(symbols):
        raise ValueError("Variable names must be unique.")

    if isinstance(eliminate, str):
        eliminate_symbol = sp.Symbol(eliminate)
    else:
        eliminate_symbol = eliminate

    if eliminate_symbol not in symbols:
        raise ValueError(
            f"Elimination variable {eliminate_symbol} is not declared."
        )

    allowed_symbols = set(symbols)

    for label, expression in (("f", f), ("g", g)):
        if not expression.free_symbols.issubset(allowed_symbols):
            unknown = expression.free_symbols - allowed_symbols

            raise ValueError(
                f"{label} contains undeclared symbols: "
                + ", ".join(sorted(str(s) for s in unknown))
            )

        try:
            sp.Poly(expression, *symbols)
        except sp.PolynomialError as exc:
            raise ValueError(
                f"{label} is not a polynomial in the declared variables."
            ) from exc

    result = sp.resultant(
        f,
        g,
        eliminate_symbol,
    )

    return sp.factor(result)


def _load_input(
    config: dict[str, Any],
) -> tuple[Path, dict[str, Any]]:
    """Load and validate the resultant input JSON."""

    settings = config.get("polynomial", {})
    input_file = settings.get("inputs_file")

    if not input_file:
        raise ValueError(
            "Set polynomial.inputs_file in config.json."
        )

    path = Path(input_file).expanduser().resolve()

    if not path.is_file():
        raise FileNotFoundError(
            f"Polynomial input file not found: {path}"
        )

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Invalid JSON in polynomial input file: {path}"
        ) from exc

    if not isinstance(data, dict):
        raise ValueError(
            "Polynomial input JSON must contain an object."
        )

    for field in ("variables", "f", "g"):
        if field not in data:
            raise ValueError(
                f"Polynomial input JSON is missing '{field}'."
            )

    if not isinstance(data["variables"], list):
        raise ValueError("'variables' must be a list of names.")

    if not all(
        isinstance(name, str) and name.isidentifier()
        for name in data["variables"]
    ):
        raise ValueError(
            "Every variable name must be a valid identifier."
        )

    return path, data


def run_resultant_stage(
    config: dict[str, Any],
    run_dir: Path,
) -> dict[str, Any]:
    """
    Run the resultant stage using polynomial.inputs_file.

    Expected input JSON:
        {
          "variables": ["x", "z"],
          "eliminate": "z",
          "f": "z**2 - x",
          "g": "z - 1"
        }

    The resultant and metadata are written to output/resultant.json.
    """

    input_path, data = _load_input(config)

    variable_names = data["variables"]

    if not variable_names:
        raise ValueError(
            "At least one polynomial variable is required."
        )

    if len(set(variable_names)) != len(variable_names):
        raise ValueError(
            "Polynomial variable names must be unique."
        )

    parameters = data.get("parameters", {})

    if not isinstance(parameters, dict):
        raise ValueError("'parameters' must be a JSON object.")

    symbols = {
        name: sp.Symbol(name)
        for name in variable_names
    }

    f = build_polynomial(
        data["f"],
        variable_names,
        parameters=parameters,
    )

    g = build_polynomial(
        data["g"],
        variable_names,
        parameters=parameters,
    )

    settings = config.get("polynomial", {})

    eliminate = settings.get(
        "resultant_variable",
        data.get("eliminate"),
    )

    if eliminate is None:
        raise ValueError(
            "Set polynomial.resultant_variable or input eliminate."
        )

    if eliminate not in symbols:
        raise ValueError(
            f"Unknown elimination variable: {eliminate}"
        )

    result = compute_resultant(
        f=f,
        g=g,
        eliminate=eliminate,
        variables=variable_names,
    )

    remaining_variables = [
        name
        for name in variable_names
        if name != eliminate
    ]

    # The resultant must not depend on the eliminated variable.
    eliminated_symbol = symbols[eliminate]

    if eliminated_symbol in result.free_symbols:
        raise ArithmeticError(
            "Resultant unexpectedly contains the eliminated variable."
        )

    if remaining_variables:
        result_info = polynomial_info(
            result,
            remaining_variables,
        )
    else:
        result_info = {
            "expression": str(result),
            "variables": [],
            "total_degree": 0,
            "term_count": 1 if result != 0 else 0,
            "terms": [],
        }

    output = {
        "status": "ok",
        "input_file": str(input_path),
        "variables": variable_names,
        "f": str(f),
        "g": str(g),
        "eliminated_variable": eliminate,
        "resultant": str(result),
        "resultant_is_zero": bool(result == 0),
        "remaining_variables": remaining_variables,
        "resultant_info": result_info,
    }

    output_path = run_dir / "output" / "resultant.json"
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