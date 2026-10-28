"""Polynomial construction, validation, and serialization."""

from __future__ import annotations

from typing import Any, Iterable

import sympy as sp


def build_polynomial(
    expression: str,
    variables: Iterable[str],
    parameters: dict[str, int] | None = None,
) -> sp.Expr:
    """
    Build and validate a polynomial expression.

    Example:
        build_polynomial("x**2 + 3*x*y + 1", ["x", "y"])
    """

    variable_names = list(variables)

    if not variable_names:
        raise ValueError("At least one polynomial variable is required.")

    if len(set(variable_names)) != len(variable_names):
        raise ValueError("Polynomial variable names must be unique.")

    symbols = {
        name: sp.Symbol(name)
        for name in variable_names
    }

    constants: dict[str, Any] = {}

    for name, value in (parameters or {}).items():
        if name in symbols:
            raise ValueError(
                f"'{name}' cannot be both a variable and a parameter."
            )

        constants[name] = sp.Integer(value)

    expression_symbols = {**symbols, **constants}

    try:
        expression = sp.sympify(
            expression,
            locals=expression_symbols,
        )
    except (sp.SympifyError, SyntaxError, TypeError) as exc:
        raise ValueError(
            f"Cannot parse polynomial expression: {expression!r}"
        ) from exc

    allowed_symbols = set(symbols.values())

    if not expression.free_symbols.issubset(allowed_symbols):
        unknown = expression.free_symbols - allowed_symbols

        raise ValueError(
            "Expression contains undeclared symbols: "
            + ", ".join(sorted(str(symbol) for symbol in unknown))
        )

    try:
        polynomial = sp.Poly(
            expression,
            *symbols.values(),
        )
    except sp.PolynomialError as exc:
        raise ValueError(
            "Expression is not a polynomial in the declared variables."
        ) from exc

    return polynomial.as_expr()


def polynomial_info(
    expression: sp.Expr,
    variables: Iterable[str | sp.Symbol],
) -> dict[str, Any]:
    """Return basic structural information about a polynomial."""

    symbols = [
        sp.Symbol(v) if isinstance(v, str) else v
        for v in variables
    ]

    polynomial = sp.Poly(expression, *symbols)

    terms = []

    for monomial, coefficient in polynomial.terms():
        terms.append({
            "powers": {
                str(symbol): int(power)
                for symbol, power in zip(symbols, monomial)
            },
            "coefficient": str(coefficient),
        })

    return {
        "expression": str(polynomial.as_expr()),
        "variables": [str(symbol) for symbol in symbols],
        "total_degree": int(polynomial.total_degree()),
        "degree_by_variable": {
            str(symbol): (
                int(polynomial.degree(symbol))
                if polynomial.degree(symbol) is not sp.S.NegativeInfinity
                else -1
            )
            for symbol in symbols
        },
        "term_count": len(terms),
        "terms": terms,
    }


def polynomial_to_json(
    expression: sp.Expr,
    variables: Iterable[str | sp.Symbol],
) -> dict[str, Any]:
    """Return a JSON-compatible polynomial description."""

    return polynomial_info(expression, variables)