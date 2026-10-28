"""GLV decomposition and endomorphism for secp256k1."""

from dataclasses import dataclass

from .curve import Curve, Point, secp256k1_curve, validate_point
from .scalar_math import add_points, multiply_point


@dataclass(frozen=True)
class GLVParameters:
    p: int
    n: int
    beta: int
    lam: int

    a1: int
    b1: int
    a2: int
    b2: int


def secp256k1_glv_parameters() -> GLVParameters:
    """Return the standard secp256k1 GLV parameters."""

    curve, _ = secp256k1_curve()

    p = curve.p

    n = int(
        "FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFE"
        "BAAEDCE6AF48A03BBFD25E8CD0364141",
        16,
    )

    beta = int(
        "7AE96A2B657C07106E64479EAC3434E99C"
        "F0497512F58995C1396C28719501EE",
        16,
    )

    lam = int(
        "5363AD4CC05C30E0A5261C028812645A"
        "122E22EA20816678DF02967C1B23BD72",
        16,
    )

    # Lattice basis. Each vector (a_i, b_i) satisfies:
    # a_i + b_i * lambda == 0 (mod n).
    a1 = int(
        "3086D221A7D46BCDE86C90E49284EB15",
        16,
    )

    b1 = -int(
        "E4437ED6010E88286F547FA90ABFE4C3",
        16,
    )

    a2 = int(
        "114CA50F7A8E2F3F657C1108D9D44CFD8",
        16,
    )

    b2 = a1

    params = GLVParameters(
        p=p,
        n=n,
        beta=beta,
        lam=lam,
        a1=a1,
        b1=b1,
        a2=a2,
        b2=b2,
    )

    validate_glv_parameters(params)

    return params


def validate_glv_parameters(
    params: GLVParameters,
) -> None:
    """Check the defining algebraic identities of the GLV parameters."""

    if pow(params.beta, 3, params.p) != 1:
        raise ValueError("GLV beta does not satisfy beta^3 = 1 mod p.")

    if params.beta % params.p == 1:
        raise ValueError("GLV beta must not equal 1.")

    if pow(params.lam, 3, params.n) != 1:
        raise ValueError("GLV lambda does not satisfy lambda^3 = 1 mod n.")

    if params.lam % params.n == 1:
        raise ValueError("GLV lambda must not equal 1.")

    if (
        params.a1 + params.b1 * params.lam
    ) % params.n != 0:
        raise ValueError("First GLV lattice vector is invalid.")

    if (
        params.a2 + params.b2 * params.lam
    ) % params.n != 0:
        raise ValueError("Second GLV lattice vector is invalid.")

    determinant = (
        params.a1 * params.b2
        - params.a2 * params.b1
    )

    if abs(determinant) != params.n:
        raise ValueError(
            "GLV lattice basis determinant does not equal subgroup order."
        )


def glv_endomorphism(
    curve: Curve,
    point: Point,
    params: GLVParameters | None = None,
) -> Point:
    """Compute phi(P) = (beta * x_P, y_P)."""

    if params is None:
        params = secp256k1_glv_parameters()

    if curve.p != params.p:
        raise ValueError("GLV parameters do not match curve modulus.")

    if curve.a != 0 or curve.b != 7:
        raise ValueError("This GLV endomorphism is for secp256k1.")

    validate_point(curve, point)

    result = Point(
        x=(params.beta * point.x) % curve.p,
        y=point.y,
    )

    validate_point(curve, result)

    return result


def _round_div(numerator: int, denominator: int) -> int:
    """Round a rational number to the nearest integer."""

    if denominator == 0:
        raise ZeroDivisionError("Denominator cannot be zero.")

    if denominator < 0:
        numerator = -numerator
        denominator = -denominator

    if numerator >= 0:
        return (2 * numerator + denominator) // (2 * denominator)

    return -((2 * (-numerator) + denominator) // (2 * denominator))


def glv_decompose(
    scalar: int,
    params: GLVParameters | None = None,
) -> tuple[int, int]:
    """
    Decompose scalar k into k1, k2 such that:

        k == k1 + lambda*k2 (mod n)

    The components are computed using nearest-plane rounding
    with the secp256k1 GLV lattice basis.
    """

    if not isinstance(scalar, int):
        raise TypeError("Scalar must be an integer.")

    if params is None:
        params = secp256k1_glv_parameters()

    k = scalar % params.n

    determinant = (
        params.a1 * params.b2
        - params.a2 * params.b1
    )

    # Coefficients for the nearest lattice point.
    c1 = _round_div(k * params.b2, determinant)
    c2 = _round_div(-k * params.b1, determinant)

    k1 = k - c1 * params.a1 - c2 * params.a2
    k2 = -c1 * params.b1 - c2 * params.b2

    if (k1 + params.lam * k2 - k) % params.n != 0:
        raise ArithmeticError(
            "GLV decomposition failed its modular identity check."
        )

    return k1, k2


def glv_multiply(
    curve: Curve,
    scalar: int,
    point: Point,
    params: GLVParameters | None = None,
) -> Point | None:
    """
    Compute scalar * point using the GLV decomposition.

    The result is checked against ordinary scalar multiplication.
    That independent check is useful for validation, although it
    removes much of the performance advantage of GLV.
    """

    if params is None:
        params = secp256k1_glv_parameters()

    if curve.p != params.p:
        raise ValueError("GLV parameters do not match curve modulus.")

    if curve.a != 0 or curve.b != 7:
        raise ValueError("GLV multiplication is restricted to secp256k1.")

    validate_point(curve, point)

    k1, k2 = glv_decompose(scalar, params)

    phi_point = glv_endomorphism(
        curve,
        point,
        params,
    )

    first = multiply_point(
        curve,
        k1,
        point,
    )

    second = multiply_point(
        curve,
        k2,
        phi_point,
    )

    result = add_points(
        curve,
        first,
        second,
    )

    # Independent correctness check.
    reference = multiply_point(
        curve,
        scalar,
        point,
    )

    if result != reference:
        raise ArithmeticError(
            "GLV result differs from ordinary scalar multiplication."
        )

    return result