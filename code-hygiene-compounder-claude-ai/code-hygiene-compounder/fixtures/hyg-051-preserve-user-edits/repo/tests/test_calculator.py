import unittest

from app.calculator import apply_discount


class DiscountTests(unittest.TestCase):
    def test_applies_percentage_discount(self):
        self.assertEqual(apply_discount(100, 20), 80)

    def test_keeps_fractional_prices_stable(self):
        self.assertAlmostEqual(apply_discount(19.99, 10), 17.991)


if __name__ == "__main__":
    unittest.main()
