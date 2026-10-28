import unittest

import sympy as sp

from algebra.polynomial import (
    build_polynomial,
    polynomial_info,
)
from algebra.resultant import compute_resultant


class TestPolynomial(unittest.TestCase):

    def test_build_polynomial(self):
        """Проверяем построение полинома."""
        result = build_polynomial(
            "x**2 + 2*x + 1",
            ["x"],
        )

        x = sp.Symbol("x")

        self.assertEqual(
            sp.expand(result - (x + 1)**2),
            0,
        )

    def test_build_polynomial_with_parameter(self):
        """Проверяем подстановку параметра."""
        result = build_polynomial(
            "x**2 + a*x",
            ["x"],
            parameters={"a": 3},
        )

        x = sp.Symbol("x")

        self.assertEqual(
            sp.expand(result - (x**2 + 3*x)),
            0,
        )

    def test_polynomial_info(self):
        """Проверяем метаданные полинома."""
        x = sp.Symbol("x")
        expression = x**2 + 2*x + 1

        info = polynomial_info(expression, ["x"])

        self.assertEqual(info["total_degree"], 2)
        self.assertEqual(info["degree_by_variable"]["x"], 2)
        self.assertEqual(info["term_count"], 3)

    def test_resultant(self):
        """Проверяем вычисление результанта по переменной z."""
        x, z = sp.symbols("x z")

        f = z**2 - x
        g = z - 1

        result = compute_resultant(
            f,
            g,
            "z",
            ["x", "z"],
        )

        self.assertEqual(
            sp.expand(result - (1 - x)),
            0,
        )

        self.assertNotIn(z, result.free_symbols)

    def test_unknown_variable_rejected(self):
        """Необъявленная переменная должна приводить к ошибке."""
        with self.assertRaises(ValueError):
            build_polynomial(
                "x**2 + y",
                ["x"],
            )


if __name__ == "__main__":
    unittest.main()