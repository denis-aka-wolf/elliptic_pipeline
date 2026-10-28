import unittest

from elliptic import (
    secp256k1_curve,
    validate_curve,
    validate_point,
)


class TestCurve(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.curve, cls.G = secp256k1_curve()

    def test_secp256k1_parameters(self):
        """Проверяем параметры кривой secp256k1."""
        curve = self.curve

        self.assertEqual(curve.p.bit_length(), 256)
        self.assertEqual(curve.a, 0)
        self.assertEqual(curve.b, 7)

    def test_curve_validation(self):
        """Проверяем, что параметры кривой проходят валидацию."""
        validate_curve(self.curve)

    def test_generator_is_valid(self):
        """Проверяем, что генератор принадлежит кривой."""
        validate_point(self.curve, self.G)

        c = self.curve
        G = self.G

        self.assertEqual(
            (G.y * G.y - (G.x**3 + c.a * G.x + c.b)) % c.p,
            0,
        )

    def test_generator_coordinates_are_in_range(self):
        """Координаты генератора должны быть каноническими."""
        self.assertGreaterEqual(self.G.x, 0)
        self.assertLess(self.G.x, self.curve.p)

        self.assertGreaterEqual(self.G.y, 0)
        self.assertLess(self.G.y, self.curve.p)


if __name__ == "__main__":
    unittest.main()
