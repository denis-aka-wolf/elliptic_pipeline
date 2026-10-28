"""Point arithmetic over prime fields."""

from .curve import Curve, Point, validate_point


def negate_point(
    curve: Curve,
    point: Point | None,
) -> Point | None:
    """Return -P. The point at infinity is its own negative."""

    if point is None:
        return None

    validate_point(curve, point)

    return Point(
        x=point.x,
        y=(-point.y) % curve.p,
    )


def add_points(
    curve: Curve,
    p1: Point | None,
    p2: Point | None,
) -> Point | None:
    """Add two points on a short Weierstrass curve."""

    if p1 is None:
        if p2 is not None:
            validate_point(curve, p2)
        return p2

    if p2 is None:
        validate_point(curve, p1)
        return p1

    validate_point(curve, p1)
    validate_point(curve, p2)

    p = curve.p

    # P + (-P) = O.
    if p1.x == p2.x and (p1.y + p2.y) % p == 0:
        return None

    if p1 == p2:
        # A point with y = 0 doubles to the point at infinity.
        if p1.y == 0:
            return None

        numerator = (
            3 * p1.x * p1.x + curve.a
        ) % p

        denominator = (2 * p1.y) % p

    else:
        numerator = (p2.y - p1.y) % p
        denominator = (p2.x - p1.x) % p

    # Since p is prime, a nonzero denominator has an inverse.
    if denominator == 0:
        raise ArithmeticError(
            "Unexpected zero denominator during point addition."
        )

    slope = (
        numerator * pow(denominator, -1, p)
    ) % p

    x3 = (
        slope * slope - p1.x - p2.x
    ) % p

    y3 = (
        slope * (p1.x - x3) - p1.y
    ) % p

    result = Point(x3, y3)

    validate_point(curve, result)

    return result


def subtract_points(
    curve: Curve,
    p1: Point | None,
    p2: Point | None,
) -> Point | None:
    """Return P - Q = P + (-Q)."""

    return add_points(
        curve,
        p1,
        negate_point(curve, p2),
    )


def multiply_point(
    curve: Curve,
    scalar: int,
    point: Point,
) -> Point | None:
    """
    Compute scalar * point using binary double-and-add.

    Negative scalars are supported.
    A scalar of zero returns the point at infinity.
    """

    if not isinstance(scalar, int):
        raise TypeError("Scalar must be an integer.")

    validate_point(curve, point)

    if scalar < 0:
        return multiply_point(
            curve,
            -scalar,
            negate_point(curve, point),
        )

    result = None
    addend = point
    k = scalar

    while k > 0:
        if k & 1:
            result = add_points(
                curve,
                result,
                addend,
            )

        k >>= 1

        if k:
            addend = add_points(
                curve,
                addend,
                addend,
            )

    return result