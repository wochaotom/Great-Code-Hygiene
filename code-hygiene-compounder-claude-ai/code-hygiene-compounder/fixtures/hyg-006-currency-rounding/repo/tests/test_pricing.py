import unittest

from app.pricing import total_cents


class PricingTests(unittest.TestCase):
    def test_whole_dollar_total(self):
        self.assertEqual(total_cents("10.00", 2), 2000)

    def test_fractional_cents_do_not_truncate(self):
        self.assertEqual(total_cents("0.29", 3), 87)

    def test_rounds_total_after_multiplying_quantity(self):
        self.assertEqual(total_cents("0.335", 3), 101)

    def test_decimal_ties_round_half_up(self):
        self.assertEqual(total_cents("1.005", 1), 101)
        self.assertEqual(total_cents("2.665", 1), 267)


if __name__ == "__main__":
    unittest.main()
