from decimal import Decimal
from datetime import date, time
from types import SimpleNamespace

from unittest.mock import patch

from django.test import RequestFactory, SimpleTestCase
from django.urls import reverse

from .financial import FinancialConfig, calculate_payment_breakdown, calculate_tncn, calculate_travel_flags, journal_conflict_types
from .document_export import _allocation_context, _date_parts, _payment_statement_total
from .models import PhanCongTre
from .payment_export import _blank_zero, _group_journal_payment_rows, _payment_note, _selection_context
from . import views


class FinancialRulesTests(SimpleTestCase):
    def test_service_codes_accept_vietnamese_and_ascii_variants(self):
        self.assertEqual(views.normalize_service_code("GDĐB"), "GDDB")
        self.assertEqual(views.normalize_service_code("GDDB"), "GDDB")
        self.assertEqual(views.normalize_service_code("Giáo dục đặc biệt"), "GDDB")
        self.assertEqual(views.normalize_service_code("Vật lý trị liệu"), "VLTL")

    def test_import_occurrences_do_not_collapse_repeated_assignments(self):
        first = object()
        second = object()
        cache = {}
        occurrences = {}
        loader = lambda: [first, second]

        self.assertIs(views.take_import_occurrence(cache, occurrences, "same-key", loader)[0], first)
        self.assertIs(views.take_import_occurrence(cache, occurrences, "same-key", loader)[0], second)
        self.assertIsNone(views.take_import_occurrence(cache, occurrences, "same-key", loader)[0])

    def test_journal_occurrences_preserve_repeated_source_rows(self):
        first = object()
        second = object()
        cache = {}
        occurrences = {}
        loader = lambda: [first, second]

        self.assertIs(views.take_import_occurrence(cache, occurrences, "journal-key", loader)[0], first)
        self.assertIs(views.take_import_occurrence(cache, occurrences, "journal-key", loader)[0], second)
        self.assertIsNone(views.take_import_occurrence(cache, occurrences, "journal-key", loader)[0])

    def test_journal_import_identity_separates_period_service_and_location(self):
        args = (1, 2, "GDDB", 3, 13, date(2026, 7, 25), time(7, 30), time(8, 30), "Trường")
        base = views.journal_import_identity_key(*args)
        self.assertNotEqual(base, views.journal_import_identity_key(*args[:4], 14, *args[5:]))
        self.assertNotEqual(base, views.journal_import_identity_key(1, 2, "NNTL", *args[3:]))
        self.assertNotEqual(base, views.journal_import_identity_key(*args[:-1], "Nhà"))

    def test_reference_keys_accept_geo_names_without_ids(self):
        self.assertIn("dong nai", views.normalized_reference_keys("Tỉnh Đồng Nai", ("tỉnh",)))
        self.assertIn("ha noi", views.normalized_reference_keys("Hà Nội"))
        self.assertIn("tran bien", views.normalized_reference_keys("Phường Trấn Biên", ("phường",)))

    def test_intervention_journal_routes_are_registered(self):
        self.assertEqual(reverse("import_nhat_ky_can_thiep"), "/nhat-ky-can-thiep/import/")
        self.assertEqual(reverse("them_nhat_ky_can_thiep"), "/nhat-ky-can-thiep/them/")
        self.assertEqual(reverse("sua_nhat_ky_can_thiep", args=[7]), "/nhat-ky-can-thiep/7/sua/")
        self.assertEqual(reverse("xoa_nhat_ky_can_thiep", args=[7]), "/nhat-ky-can-thiep/7/xoa/")
        self.assertEqual(reverse("xuat_dntt_excel_nhat_ky"), "/nhat-ky-can-thiep/xuat-dntt-excel/")

    def test_contract_date_parts_keep_day_month_year_separate(self):
        parts = _date_parts(date(2026, 9, 15))
        self.assertEqual(parts["Ngay"], "15")
        self.assertEqual(parts["Thang"], "9")
        self.assertEqual(parts["Nam"], "2026")
        self.assertEqual(parts["Full"], "15/09/2026")

    def test_contract_download_filename_is_windows_safe_and_keeps_vietnamese(self):
        filename = (
            f"HDDV - {views.safe_download_component('214-26/HĐDV-VH')} - "
            f"{views.safe_download_component('ADN0116')}_"
            f"{views.safe_download_component('Phan Thị Hằng')}.docx"
        )
        self.assertEqual(filename, "HDDV - 214-26_HĐDV-VH - ADN0116_Phan Thị Hằng.docx")
        header = views.content_disposition_filename(filename)
        self.assertIn('filename="HDDV - 214-26_HDDV-VH - ADN0116_Phan Thi Hang.docx"', header)
        self.assertIn("filename*=UTF-8''HDDV%20-%20214-26_H%C4%90DV-VH%20-%20ADN0116_Phan%20Th%E1%BB%8B%20H%E1%BA%B1ng.docx", header)

    def test_payment_statement_total_adds_current_request_without_double_counting(self):
        payment_details = [
            SimpleNamespace(nhat_ky_id=10, thanh_tien=Decimal("1000000")),
            SimpleNamespace(nhat_ky_id=20, thanh_tien=Decimal("2000000")),
        ]
        total = _payment_statement_total(
            payment_details,
            current_journal_ids={20},
            current_amount=Decimal("7500000"),
        )
        self.assertEqual(total, Decimal("8500000"))

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

    def test_schedule_conflicts_distinguish_child_and_cbct(self):
        current = SimpleNamespace(child_id="T2", cb_id="CB1", service="CSXH", date=date(2026, 7, 4), start=__import__("datetime").time(10), end=__import__("datetime").time(11))
        other = SimpleNamespace(child_id="T1", cb_id="CB1", service="VLTL", date=current.date, start=__import__("datetime").time(10), end=__import__("datetime").time(11))
        self.assertEqual(journal_conflict_types(current, [other]), ["Trùng CBCT"])
        other.child_id = "T2"
        self.assertEqual(journal_conflict_types(current, [other]), ["Trùng lịch CT"])

    def test_adjacent_sessions_are_not_conflicts_and_travel_is_separate(self):
        current = SimpleNamespace(child_id="T2", cb_id="CB1", ace="A", service="CSXH", date=date(2026, 7, 4), start=__import__("datetime").time(11), end=__import__("datetime").time(12), location="Khác", record_id=2)
        other = SimpleNamespace(child_id="T1", cb_id="CB1", ace="B", service="VLTL", date=current.date, start=__import__("datetime").time(10), end=__import__("datetime").time(11), location="Khác", record_id=1)
        self.assertEqual(journal_conflict_types(current, [other]), [])
        travel = calculate_travel_flags(current, [other])
        self.assertEqual(travel, {"so_luot_di_lai_cbct": 1, "so_luot_di_lai_ph": 1})

    def test_school_session_keeps_excel_time_and_only_counts_parent_travel(self):
        self.assertEqual(views.parse_time("07:30:00"), time(7, 30))
        self.assertEqual(views.parse_time("08:30:00"), time(8, 30))
        current = SimpleNamespace(
            child_id="CBP2341", cb_id="ABP0609", ace="", service="GDDB",
            date=date(2026, 7, 25), start=time(7, 30), end=time(8, 30),
            location="Trường", record_id=None,
        )
        self.assertEqual(
            calculate_travel_flags(current, []),
            {"so_luot_di_lai_cbct": 0, "so_luot_di_lai_ph": 1},
        )

    def test_intervention_period_choices_cover_requested_range(self):
        self.assertEqual(list(FinancialConfig.KY_CAN_THIEP_CHOICES), list(range(1, 31)))
        self.assertEqual(list(FinancialConfig.NAM_CAN_THIEP_CHOICES), list(range(2024, 2031)))

    def test_payment_excel_groups_sessions_by_staff_and_assignment(self):
        staff = SimpleNamespace(pk=1, ho_ten="CBCT A")
        contract = SimpleNamespace(pk=10, so_hop_dong="HD-01", can_bo=staff)
        child = SimpleNamespace(pk=20, ho_ten="Trẻ A")
        assignment = SimpleNamespace(
            pk=30, tre=child, loai_dich_vu="NNTL", dia_diem_ct="Nhà",
            so_buoi_du_kien=25,
        )
        journals = [
            SimpleNamespace(
                hop_dong=contract, hop_dong_id=10, phan_cong=assignment,
                phan_cong_id=30, dia_diem_ct="Nhà", so_buoi_thuc_hien=1, so_luot_di_lai_cbct=1,
                don_gia_cong=Decimal("200000"), dinh_muc_di_lai=Decimal("50000"), ghi_chu="",
            ),
            SimpleNamespace(
                hop_dong=contract, hop_dong_id=10, phan_cong=assignment,
                phan_cong_id=30, dia_diem_ct="Nhà", so_buoi_thuc_hien=1, so_luot_di_lai_cbct=0,
                don_gia_cong=Decimal("200000"), dinh_muc_di_lai=Decimal("50000"), ghi_chu="",
            ),
        ]
        grouped = _group_journal_payment_rows(journals)
        self.assertEqual(len(grouped), 1)
        self.assertEqual(len(grouped[0]["details"]), 1)
        self.assertEqual(grouped[0]["actual_home"], 2)
        self.assertEqual(grouped[0]["actual_travel"], 1)
        self.assertEqual(grouped[0]["labor"], Decimal("400000"))
        self.assertEqual(grouped[0]["travel"], Decimal("50000"))

    def test_payment_excel_hides_zero_and_import_technical_notes(self):
        self.assertIsNone(_blank_zero(0))
        self.assertIsNone(_blank_zero(Decimal("0")))
        self.assertEqual(_blank_zero(200000), 200000)
        self.assertEqual(
            _payment_note("Ghi chú nghiệp vụ\nDữ liệu lịch sử: chưa có hợp đồng"),
            "Ghi chú nghiệp vụ",
        )

    @patch("quanly.payment_export._location_for_group", return_value="Đồng Nai")
    def test_payment_excel_uses_selected_dates_not_journal_dates(self, _location):
        journal = SimpleNamespace(
            ky_can_thiep=14,
            ngay_thuc_hien=date(2026, 7, 25),
            nhom_hd_hieu_luc=SimpleNamespace(ma_nhom_hd="24"),
        )
        context = _selection_context(
            [journal],
            ky="14",
            tu_ngay="01/08/2026",
            den_ngay="31/08/2026",
        )
        self.assertEqual(context["TuNgay"], "01/08/2026")
        self.assertEqual(context["DenNgay"], "31/08/2026")


class DashboardViewTests(SimpleTestCase):
    def test_homepage_returns_response_after_login(self):
        class EmptyQuerySet:
            def __iter__(self):
                return iter(())

            def count(self):
                return 0

            def aggregate(self, **kwargs):
                return {key: 0 for key in kwargs}

            def filter(self, **kwargs):
                return self

        empty = EmptyQuerySet()
        expected = object()
        with (
            patch.object(views.PhanBoChiTieu.objects, "all", return_value=empty),
            patch.object(views.PhanCongTre.objects, "filter", return_value=empty),
            patch.object(views.HopDong.objects, "all", return_value=empty),
            patch.object(views.Tre.objects, "filter", return_value=empty),
            patch.object(views.CanBo.objects, "filter", return_value=empty),
            patch.object(views.DonVi.objects, "filter", return_value=empty),
            patch.object(views.NhomHD.objects, "filter", return_value=empty),
            patch.object(views.DeXuatHopDong.objects, "count", return_value=0),
            patch.object(views, "render", return_value=expected),
        ):
            response = views.trang_chu.__wrapped__(RequestFactory().get("/"))
        self.assertIs(response, expected)
