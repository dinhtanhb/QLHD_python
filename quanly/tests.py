from decimal import Decimal

from django.test import SimpleTestCase

from .financial import calculate_payment_breakdown, calculate_tncn
from .models import PhanCongTre


class FinancialRulesTests(SimpleTestCase):
    def test_tax_uses_labor_only_below_threshold(self):
        self.assertEqual(calculate_tncn(Decimal("4999999")), Decimal("0"))
        self.assertEqual(calculate_tncn(Decimal("5000000")), Decimal("500000"))

    def test_travel_is_not_taxable_or_threshold_basis(self):
        result = calculate_payment_breakdown(Decimal("4000000"), Decimal("1000000"))
        self.assertEqual(result["thue_tncn"], Decimal("0"))
        self.assertEqual(result["thuc_linh"], Decimal("5000000"))

    def test_service_groups_are_explicit(self):
        self.assertEqual(PhanCongTre.service_group("VLTL"), "PHCN")
        self.assertEqual(PhanCongTre.service_group("HDTL"), "PHCN")
        self.assertEqual(PhanCongTre.service_group("CSYT"), "CS")
        self.assertIsNone(PhanCongTre.service_group("UNKNOWN"))
