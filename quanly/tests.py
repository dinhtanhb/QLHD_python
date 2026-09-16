from decimal import Decimal
from datetime import date
from types import SimpleNamespace

from django.test import SimpleTestCase
from django.urls import reverse

from .financial import calculate_payment_breakdown, calculate_tncn
from .document_export import _allocation_context, _date_parts
from .models import PhanCongTre


class FinancialRulesTests(SimpleTestCase):
    def test_intervention_journal_routes_are_registered(self):
        self.assertEqual(reverse("import_nhat_ky_can_thiep"), "/nhat-ky-can-thiep/import/")
        self.assertEqual(reverse("them_nhat_ky_can_thiep"), "/nhat-ky-can-thiep/them/")
        self.assertEqual(reverse("xuat_dntt_excel_nhat_ky"), "/nhat-ky-can-thiep/xuat-dntt-excel/")

    def test_contract_date_parts_keep_day_month_year_separate(self):
        parts = _date_parts(date(2026, 9, 15))
        self.assertEqual(parts["Ngay"], "15")
        self.assertEqual(parts["Thang"], "9")
        self.assertEqual(parts["Nam"], "2026")
        self.assertEqual(parts["Full"], "15/09/2026")

    def test_contract_context_uses_full_dates_only_for_full_date_fields(self):
        allocation = SimpleNamespace(so_tre_phcn=1, so_buoi_phcn=20, dinh_muc_di_lai_phcn=50000, so_tre_cs=0, so_buoi_cs=10, dinh_muc_di_lai_cs=50000)
        staff = SimpleNamespace(ma_can_bo="CB001", ho_ten="Người thử", cccd="", ngay_cap=None, noi_cap="", dia_chi="", dien_thoai="", email="", ngan_hang="", tai_khoan="")
        contract = SimpleNamespace(de_xuat=SimpleNamespace(phan_bo=allocation), so_hop_dong="HD001", ngay_ky=date(2026, 9, 15), tu_ngay=date(2026, 9, 15), den_ngay=date(2026, 9, 30), can_bo=staff, don_gia_cong=200000, gia_tri_hop_dong=5000000)
        context = _allocation_context(contract)
        self.assertEqual(context["NgayKy_Ngay"], "15")
        self.assertEqual(context["NgayKy_Thang"], "9")
        self.assertEqual(context["NgayKy_Nam"], "2026")
        self.assertEqual(context["TuNgay"], "15/09/2026")
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
