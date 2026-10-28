import unittest

from elliptic import (
    secp256k1_curve,
    add_points,
    multiply_point,
    negate_point,
    subtract_points,
)


class TestEllipticArithmetic(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.curve, cls.G = secp256k1_curve()

    def test_zero_scalar(self):
        """0 * G должна быть точкой на бесконечности."""
        result = multiply_point(self.curve, 0, self.G)
        self.assertIsNone(result)

    def test_one_times_generator(self):
        """1 * G = G."""
        result = multiply_point(self.curve, 1, self.G)
        self.assertEqual(result, self.G)

    def test_two_times_generator(self):
        """2 * G должно совпадать с G + G."""
        doubled = multiply_point(self.curve, 2, self.G)
        added = add_points(self.curve, self.G, self.G)

        self.assertEqual(doubled, added)

    def test_three_times_generator(self):
        """3 * G = 2 * G + G."""
        two_g = multiply_point(self.curve, 2, self.G)
        three_g = multiply_point(self.curve, 3, self.G)

        self.assertEqual(
            add_points(self.curve, two_g, self.G),
            three_g,
        )

    def test_point_plus_its_negation(self):
        """P + (-P) должна быть точкой на бесконечности."""
        negative_g = negate_point(self.curve, self.G)

        result = add_points(
            self.curve,
            self.G,
            negative_g,
        )

        self.assertIsNone(result)

    def test_subtract_point_from_itself(self):
        """P - P должна быть точкой на бесконечности."""
        result = subtract_points(
            self.curve,
            self.G,
            self.G,
        )

        self.assertIsNone(result)

    def test_distributive_scalar_addition(self):
        """(a + b)G = aG + bG."""
        a = 123
        b = 456

        left = multiply_point(
            self.curve,
            a + b,
            self.G,
        )

        right = add_points(
            self.curve,
            multiply_point(self.curve, a, self.G),
            multiply_point(self.curve, b, self.G),
        )

        self.assertEqual(left, right)


if __name__ == "__main__":
    unittest.main()