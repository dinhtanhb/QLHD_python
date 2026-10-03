"""Regression coverage for model immutability and hostile numeric inputs."""

from datetime import date, time
from decimal import Decimal
from io import BytesIO, StringIO
from unittest.mock import patch
from html.parser import HTMLParser

from django.contrib.auth.models import Group, User
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.files.uploadedfile import SimpleUploadedFile
import pandas as pd
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from .models import ChiTietGiaHanKhoiLuong, ChiTietKhoiLuongHopDong, NhatKyThucHien, PhanCongTre, PhuLucHopDong, ThanhLyHopDong
from .assignment_import import import_assignment_workbook
from . import views
from .parsing import parse_decimal, parse_get_int, parse_money_vnd, parse_number
from .services.payment_ledger import tao_phieu_thanh_toan
from .tests import SettlementReportingTestBase


class NumericInputReviewTests(SimpleTestCase):
    def test_get_integer_longer_than_python_conversion_limit_is_ignored(self):
        self.assertIsNone(parse_get_int("9" * 5000))
        self.assertEqual(parse_get_int("0" * 5000 + "12"), 12)
        self.assertFalse(views._is_id("0" * 5000 + "12"))

    def test_non_finite_numbers_are_rejected_by_strict_parsers(self):
        for parser in (parse_number, parse_money_vnd):
            for value in (float("nan"), float("inf"), float("-inf"), Decimal("NaN"), Decimal("sNaN"), Decimal("Infinity")):
                with self.subTest(parser=parser.__name__, value=str(value)):
                    with self.assertRaises(ValueError):
                        parser(value)

    def test_legacy_parser_returns_default_for_non_finite_values(self):
        for value in ("NaN", "Infinity", "-Infinity", Decimal("NaN"), float("inf")):
            with self.subTest(value=str(value)):
                self.assertEqual(parse_decimal(value, Decimal("17")), Decimal("17"))


class AdminRevocationReviewTests(TestCase):
    def test_username_does_not_override_revoked_admin_role(self):
        account = User.objects.create_user(username="admin", is_staff=True)
        self.client.force_login(account)
        import_url = reverse("import_don_vi")
        self.assertEqual(self.client.get(import_url).status_code, 302)

        account.groups.add(Group.objects.create(name="Admin"))
        self.assertEqual(self.client.get(import_url).status_code, 200)

        account.is_active = False
        account.save(update_fields=["is_active"])
        self.assertEqual(self.client.get(import_url).status_code, 302)


class PaidJournalModelReviewTests(SettlementReportingTestBase):
    def setUp(self):
        super().setUp()
        self.assignment = self._assignment(self.alloc1, self.child1)
        self.contract = self._contract("HD-MODEL-REVIEW", self.cb1, self.g1)
        self.journal = self._journal(
            self.contract, self.assignment, date(2026, 9, 10),
            gio_bat_dau=time(9), gio_ket_thuc=time(10), dia_diem_ct="Khác",
        )
        self.journal.refresh_from_db()
        self.voucher = tao_phieu_thanh_toan(self.cb1, self.contract, 1)
        self.journal.refresh_from_db()

    def test_note_save_after_earlier_session_preserves_paid_money(self):
        fields = ("so_luot_di_lai_cbct", "so_luot_di_lai", "thanh_tien", "lan_thanh_toan")
        original = tuple(getattr(self.journal, field) for field in fields)
        self._journal(
            self.contract, self.assignment, date(2026, 9, 10), ky=2,
            gio_bat_dau=time(8), gio_ket_thuc=time(9), dia_diem_ct="Khác",
        )
        self.journal.refresh_from_db()
        self.journal.ghi_chu = "Ghi chú sau khi lập phiếu"
        self.journal.save()
        self.journal.refresh_from_db()
        self.assertEqual(tuple(getattr(self.journal, field) for field in fields), original)
        self.assertEqual(self.journal.ghi_chu, "Ghi chú sau khi lập phiếu")
        self.assertEqual(self.voucher.chi_tiet.get().tien_cong + self.voucher.chi_tiet.get().tien_di_lai, self.journal.thanh_tien)

    def test_paid_journal_rejects_changes_to_remaining_financial_identity(self):
        for field, value in (
            ("dia_diem_ct", "Nhà"), ("nhom_hd_nguon_id", self.g12.pk),
            ("lan_thanh_toan", 99), ("thanh_tien", Decimal("1")),
            ("du_lieu_lich_su", False),
        ):
            with self.subTest(field=field):
                journal = NhatKyThucHien.objects.get(pk=self.journal.pk)
                setattr(journal, field, value)
                with self.assertRaises(ValidationError):
                    journal.save(recalculate_travel=False)


class ManagementCommandReviewTests(SettlementReportingTestBase):
    def test_setup_roles_does_not_reactivate_or_promote_admin(self):
        admin = User.objects.create_user(username="admin", is_active=False)
        output = StringIO()
        call_command("setup_roles", stdout=output)
        admin.refresh_from_db()
        self.assertFalse(admin.is_active or admin.is_staff or admin.is_superuser)
        self.assertEqual(set(Group.objects.values_list("name", flat=True)),
                         {"Admin", "DieuPhoiVien", "CBDA", "KeToan"})
        call_command("setup_roles", stdout=output)
        admin.refresh_from_db()
        self.assertFalse(admin.is_active or admin.is_staff or admin.is_superuser)
        self.assertEqual(Group.objects.count(), 4)
        self.assertEqual(output.getvalue().count("Role setup completed."), 2)

    @patch("quanly.services.contract_status.timezone.localdate", return_value=date(2026, 10, 1))
    def test_status_sync_apply_reports_the_change_it_persisted(self, _today):
        contract = self._contract("HD-STATUS-REVIEW", self.cb1, self.g1)
        output = StringIO()
        call_command("sync_trang_thai_hop_dong", apply=True, stdout=output)
        contract.refresh_from_db()
        self.assertEqual(contract.trang_thai, "DANG_THUC_HIEN")
        self.assertIn("HD-STATUS-REVIEW", output.getvalue())
        self.assertIn("1 thay đổi", output.getvalue())

    def test_status_sync_dry_run_and_apply_agree_on_liquidation_transition(self):
        contract = self._contract("HD-LIQUIDATION-REVIEW", self.cb1, self.g1)
        ThanhLyHopDong.objects.create(hop_dong=contract, ngay_thanh_ly=date(2026, 9, 30))
        output, errors = StringIO(), StringIO()
        call_command("sync_trang_thai_hop_dong", dry_run=True, stdout=output, stderr=errors)
        self.assertIn("1 thay đổi", output.getvalue())
        self.assertEqual(errors.getvalue(), "")
        contract.refresh_from_db()
        self.assertEqual(contract.trang_thai, "DA_KY")
        output = StringIO()
        call_command("sync_trang_thai_hop_dong", apply=True, stdout=output, stderr=errors)
        self.assertIn("1 thay đổi", output.getvalue())
        contract.refresh_from_db()
        self.assertEqual(contract.trang_thai, "THANH_LY")
        self.assertTrue(contract.is_locked)


class AssignmentImportReviewTests(SettlementReportingTestBase):
    def test_write_failure_reports_zero_persisted_rows_after_rollback(self):
        output = BytesIO()
        pd.DataFrame([
            {"Mã CB": self.cb1.ma_can_bo, "IDChild": child.ma_tre,
             "Nhóm HĐ": self.g1.ma_nhom_hd, "Loại dịch vụ": "VLTL",
             "Số buổi dự kiến": 20, "Đợt phân công": 1, "Kỳ phân công": 1}
            for child in (self.child1, self.child2)
        ]).to_excel(output, index=False)
        original_save = PhanCongTre.save

        def fail_second(instance, *args, **kwargs):
            if instance.tre_id == self.child2.pk:
                raise ValidationError("simulated late validation failure")
            return original_save(instance, *args, **kwargs)

        with patch.object(PhanCongTre, "save", new=fail_second):
            result = import_assignment_workbook(SimpleUploadedFile("assignments.xlsx", output.getvalue()))
        self.assertTrue(result.system_error)
        self.assertEqual((result.created, result.updated, result.unchanged, result.phan_bo_tao_moi), (0, 0, 0, 0))
        self.assertEqual(PhanCongTre.objects.count(), 0)

    def test_group_resolution_handles_malformed_numeric_references(self):
        for value in ("²", "9" * 5000):
            with self.subTest(value=value[:20]):
                self.assertIsNone(views.resolve_contract_group(value))
        self.assertEqual(views.parse_int(float("inf"), 17), 17)


class VolumeAmountReviewTests(SettlementReportingTestBase):
    def test_update_or_create_updates_persisted_contract_and_annex_amounts(self):
        contract = self._contract("HD-AMOUNT-REVIEW", self.cb1, self.g1)
        detail = ChiTietKhoiLuongHopDong.objects.create(
            hop_dong=contract, loai_dich_vu="VLTL", so_tre=1, so_buoi=20,
            don_gia_cong=Decimal("200000"), dinh_muc_di_lai=Decimal("50000"),
        )
        ChiTietKhoiLuongHopDong.objects.update_or_create(
            pk=detail.pk, defaults={"so_tre": 2},
        )
        detail.refresh_from_db()
        self.assertEqual(detail.thanh_tien, Decimal("10000000"))
        extension = PhuLucHopDong.objects.create(hop_dong=contract, loai_phu_luc="GIA_HAN_KHOI_LUONG")
        detail = ChiTietGiaHanKhoiLuong.objects.create(
            phu_luc=extension, loai_dich_vu="VLTL", so_tre_moi=1, so_buoi_moi=20,
            don_gia_cong=Decimal("200000"), dinh_muc_di_lai=Decimal("50000"),
        )
        ChiTietGiaHanKhoiLuong.objects.update_or_create(pk=detail.pk, defaults={"so_tre_moi": 2})
        detail.refresh_from_db()
        self.assertEqual(detail.thanh_tien, Decimal("10000000"))
        detail.so_tre_moi = 3
        detail.save(update_fields=[])
        detail.refresh_from_db()
        self.assertEqual(detail.thanh_tien, Decimal("10000000"))


class _InputNames(HTMLParser):
    def __init__(self):
        super().__init__()
        self.names = set()

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in {"input", "select", "textarea"} and "name" in attrs:
            self.names.add(attrs["name"])


class CatalogueFormReviewTests(SettlementReportingTestBase):
    def _rendered_payload(self, response):
        parser = _InputNames()
        parser.feed(response.content.decode())
        values = {}
        for field in response.context["form"]:
            if field.name in parser.names:
                value = field.value()
                if hasattr(value, "isoformat"):
                    value = value.isoformat()
                values[field.name] = "" if value is None else str(value)
        return values

    def test_catalogue_edits_preserve_fields_absent_from_visible_layout(self):
        self.client.force_login(self.admin)
        self.child1.ace_ruot = "Anh em fixture"
        self.child1.ghi_chu = "Ghi chú cần giữ"
        self.child1.save()
        for route, record in (("sua_tre", self.child1), ("sua_can_bo", self.cb1),
                              ("sua_don_vi", self.don_vi), ("sua_nhom_hd", self.g1)):
            for active in (True, False):
                with self.subTest(route=route, active=active):
                    type(record).objects.filter(pk=record.pk).update(is_active=active)
                    url = reverse(route, args=[record.pk])
                    response = self.client.get(url)
                    self.assertEqual(response.status_code, 200)
                    response = self.client.post(url, self._rendered_payload(response))
                    self.assertEqual(response.status_code, 302)
                    record.refresh_from_db()
                    self.assertEqual(record.is_active, active)
        self.child1.refresh_from_db()
        self.assertEqual((self.child1.ace_ruot, self.child1.ghi_chu), ("Anh em fixture", "Ghi chú cần giữ"))
