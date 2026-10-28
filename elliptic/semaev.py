"""Semaev polynomial utilities for short Weierstrass curves."""

from .curve import Curve


def semaev_f3(
    x1: int,
    x2: int,
    x3: int,
    curve: Curve,
) -> int:
    """
    Evaluate the third Semaev polynomial modulo p.

    F3(x1, x2, x3) =
        (x1*x2 + x1*x3 + x2*x3 + a)^2
        - 4*(x1 + x2 + x3)*(x1*x2*x3 + b)
    """

    p = curve.p

    x1 %= p
    x2 %= p
    x3 %= p

    pair_sum = (
        x1 * x2
        + x1 * x3
        + x2 * x3
        + curve.a
    ) % p

    coordinate_sum = (
        x1 + x2 + x3
    ) % p

    product_term = (
        x1 * x2 * x3 + curve.b
    ) % p

    result = (
        pair_sum * pair_sum
        - 4 * coordinate_sum * product_term
    ) % p

    return result


def semaev_f3_symbolic():
    """
    Return a SymPy expression for F3.

    SymPy is required only for this symbolic operation.
    """

    try:
        import sympy as sp
    except ImportError as exc:
        raise RuntimeError(
            "SymPy is required for symbolic Semaev polynomials."
        ) from exc

    x1, x2, x3, a, b = sp.symbols(
        "x1 x2 x3 a b"
    )

    pair_sum = x1 * x2 + x1 * x3 + x2 * x3 + a

    coordinate_sum = x1 + x2 + x3

    product_term = x1 * x2 * x3 + b

    f3 = (
        pair_sum**2
        - 4 * coordinate_sum * product_term
    )

    return sp.expand(f3)


def verify_semaev_f3(
    x1: int,
    x2: int,
    x3: int,
    curve: Curve,
) -> bool:
    """
    Verify that F3 evaluates to zero modulo p.

    This checks the polynomial equation only. It does not by itself
    prove that the three x-coordinates correspond to valid curve
    points whose sum is the point at infinity.
    """

    return semaev_f3(
        x1,
        x2,
        x3,
        curve,
    ) == 0