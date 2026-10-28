"""Elliptic curves over prime fields."""

from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class Curve:
    """Short Weierstrass curve over a prime field."""

    p: int
    a: int
    b: int

    def __post_init__(self) -> None:
        if self.p <= 3:
            raise ValueError("Field modulus p must be greater than 3.")

        if self.p % 2 == 0:
            raise ValueError("Field modulus p must be odd.")

        object.__setattr__(self, "a", self.a % self.p)
        object.__setattr__(self, "b", self.b % self.p)


@dataclass(frozen=True)
class Point:
    """Affine point. The point at infinity is represented by None."""

    x: int
    y: int


@lru_cache(maxsize=32)
def is_probable_prime(n: int) -> bool:
    """
    Miller-Rabin primality test.

    Deterministic for n < 2**64 with the chosen bases.
    For larger n, this is a strong probable-prime test,
    not a formal primality certificate.
    """

    if n < 2:
        return False

    small_primes = (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37)

    for prime in small_primes:
        if n == prime:
            return True
        if n % prime == 0:
            return False

    d = n - 1
    s = 0

    while d % 2 == 0:
        d //= 2
        s += 1

    bases = (
        2, 325, 9375, 28178, 450775,
        9780504, 1795265022,
    )

    for base in bases:
        a = base % n

        if a == 0:
            continue

        x = pow(a, d, n)

        if x == 1 or x == n - 1:
            continue

        for _ in range(s - 1):
            x = pow(x, 2, n)

            if x == n - 1:
                break
        else:
            return False

    return True


def validate_curve(curve: Curve, check_prime: bool = True) -> None:
    """Validate the field modulus and nonsingularity of the curve."""

    if check_prime and not is_probable_prime(curve.p):
        raise ValueError(
            "p is not prime, or failed the Miller-Rabin test."
        )

    # Discriminant condition:
    # 4*a^3 + 27*b^2 != 0 (mod p).
    discriminant = (
        4 * pow(curve.a, 3, curve.p)
        + 27 * pow(curve.b, 2, curve.p)
    ) % curve.p

    if discriminant == 0:
        raise ValueError(
            "Singular curve: 4*a^3 + 27*b^2 == 0 modulo p."
        )


def validate_point(curve: Curve, point: Point) -> None:
    """Raise ValueError if the point is not on the curve."""

    if not isinstance(point, Point):
        raise TypeError("Expected a Point instance.")

    if not (0 <= point.x < curve.p):
        raise ValueError("Point x-coordinate must satisfy 0 <= x < p.")

    if not (0 <= point.y < curve.p):
        raise ValueError("Point y-coordinate must satisfy 0 <= y < p.")

    lhs = pow(point.y, 2, curve.p)

    rhs = (
        pow(point.x, 3, curve.p)
        + curve.a * point.x
        + curve.b
    ) % curve.p

    if lhs != rhs:
        raise ValueError(
            f"Point is not on curve: y^2={lhs}, "
            f"x^3+a*x+b={rhs} modulo p."
        )


def secp256k1_curve() -> tuple[Curve, Point]:
    """Return the standard secp256k1 curve and generator G."""

    p = int(
        "FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF"
        "FFFFFFFFFFFFFFFFFFFFFFFEFFFFFC2F",
        16,
    )

    n = int(
        "FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFE"
        "BAAEDCE6AF48A03BBFD25E8CD0364141",
        16,
    )

    gx = int(
        "79BE667EF9DCBBAC55A06295CE870B070"
        "29BFCDB2DCE28D959F2815B16F81798",
        16,
    )

    gy = int(
        "483ADA7726A3C4655DA4FBFC0E1108A8"
        "FD17B448A68554199C47D08FFB10D4B8",
        16,
    )

    curve = Curve(p=p, a=0, b=7)
    generator = Point(gx, gy)

    validate_curve(curve)
    validate_point(curve, generator)

    return curve, generator