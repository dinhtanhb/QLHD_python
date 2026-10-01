"""Request regressions for payment validation and locked workflow boundaries."""

from datetime import date
from decimal import Decimal
from unittest.mock import patch
from io import BytesIO

import pandas as pd

from django.contrib.auth.models import Group, User
from django.db import IntegrityError
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from .models import (
    CanBo, ChiTietGiaHanKhoiLuong, ChiTietKhoiLuongHopDong, ChiTietThanhToan, DeXuatHopDong, DonVi, DotThanhToan,
    HopDong, NghiemThu, NhatKyThucHien, NhomHD, PhanBoChiTieu,
    PhanCongTre, PhieuThanhToan, PhuLucHopDong, Tre,
)
from .forms import GiaHanKhoiLuongForm, GiaHanThoiGianForm, TreForm
from .services.payment_ledger import tao_phieu_thanh_toan as create_voucher


class ReviewWorkflowTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser("workflow-review-admin", password="secret")
        self.cbda = User.objects.create_user("workflow-review-cbda", password="secret")
        self.cbda.groups.add(Group.objects.create(name="CBDA"))
        unit = DonVi.objects.create(ma_don_vi="DV-REVIEW", ten_don_vi="Đơn vị thử", nguoi_dai_dien="Người thử")
        self.staff = CanBo.objects.create(ma_can_bo="CB-REVIEW", ho_ten="Cán bộ thử", don_vi=unit)
        self.group = NhomHD.objects.create(ma_nhom_hd="REVIEW", ten_nhom_hd="Nhóm thử")
        self.child = Tre.objects.create(ma_tre="TRE-REVIEW", ho_ten="Trẻ thử", ngay_sinh=date(2015, 1, 1), gioi_tinh="Nam")
        self.allocation = PhanBoChiTieu.objects.create(can_bo=self.staff, nhom_hd=self.group, so_tre_phcn=1)
        self.assignment = PhanCongTre.objects.create(
            phan_bo=self.allocation, nhom_hd=self.group, tre=self.child,
            loai_dich_vu="VLTL", so_buoi_du_kien=20, dinh_muc_di_lai=Decimal("50000"),
        )
        proposal = DeXuatHopDong.objects.create(phan_bo=self.allocation)
        self.contract = HopDong.objects.create(
            de_xuat=proposal, can_bo=self.staff, nhom_hd=self.group, so_hop_dong="HD-REVIEW",
            tu_ngay=date(2026, 9, 1), den_ngay=date(2026, 9, 30), gia_tri_hop_dong=Decimal("5000000"),
        )
        self.journal = NhatKyThucHien.objects.create(
            hop_dong=self.contract, phan_cong=self.assignment, ngay_thuc_hien=date(2026, 9, 2),
            so_buoi_thuc_hien=1, don_gia_cong=Decimal("200000"), dinh_muc_di_lai=Decimal("50000"),
        )
        self.client.force_login(self.admin)

    def _dot_payload(self, **overrides):
        return {"nam": 2026, "thang": 9, "ngay_de_nghi": "2026-09-30", **overrides}

    def _detail_payload(self, **overrides):
        return {"nhat_ky": self.journal.pk, "so_buoi_thanh_toan": 1, "so_luot_di_lai": 0, **overrides}

    def _assignment_payload(self, **overrides):
        return {
            "phan_bo": self.allocation.pk, "nhom_hd": self.group.pk, "tre": self.child.pk,
            "loai_dich_vu": "VLTL", "so_buoi_du_kien": 20, "dinh_muc_di_lai": 50000,
            "dot_phan_cong": 1, "ky_phan_cong": 1, "trang_thai": "DANG_CAN_THIEP", **overrides,
        }

    def _journal_payload(self, **overrides):
        return {
            "hop_dong": self.contract.pk, "phan_cong": self.assignment.pk,
            "ngay_thuc_hien": "2026-09-02", "ky_can_thiep": 1, "so_buoi_thuc_hien": 1, **overrides,
        }

    def _extension(self, **overrides):
        return PhuLucHopDong.objects.create(
            hop_dong=self.contract, loai_phu_luc="GIA_HAN_THOI_GIAN",
            ngay_lap=date(2026, 9, 20), den_ngay_cu=date(2026, 9, 30), den_ngay_moi=date(2026, 10, 31),
            **{"is_signed": True, **overrides},
        )

    def _extension_payload(self, **overrides):
        return {
            "hop_dong": self.contract.pk, "ngay_lap": "2026-09-20",
            "den_ngay_moi": "2026-11-30", "is_signed": "0", **overrides,
        }

    def _voucher(self, status="CHO_CHI"):
        return PhieuThanhToan.objects.create(
            hop_dong=self.contract, can_bo=self.staff, ky_can_thiep=1, lan_thanh_toan=1,
            tong_tien_cong=Decimal("200000"), thuc_nhan=Decimal("200000"), trang_thai=status,
        )

    def test_duplicate_payment_round_returns_form_error(self):
        dot = DotThanhToan.objects.create(hop_dong=self.contract, nam=2026, thang=9)
        response = self.client.post(reverse("tao_dot_thanh_toan", args=[self.contract.pk]), self._dot_payload())
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].non_field_errors())
        self.assertContains(response, "Đợt thanh toán tháng/năm này đã tồn tại")
        self.assertEqual(DotThanhToan.objects.filter(hop_dong=self.contract).count(), 1)
        dot.refresh_from_db()
        self.assertEqual(dot.thang, 9)

    def test_valid_payment_round_is_created(self):
        response = self.client.post(reverse("tao_dot_thanh_toan", args=[self.contract.pk]), self._dot_payload())
        self.assertEqual(response.status_code, 302)
        self.assertEqual(DotThanhToan.objects.get().hop_dong_id, self.contract.pk)

    def test_payment_round_concurrent_duplicate_returns_form_error(self):
        with patch.object(DotThanhToan, "save", side_effect=IntegrityError("duplicate")):
            response = self.client.post(reverse("tao_dot_thanh_toan", args=[self.contract.pk]), self._dot_payload())
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].non_field_errors())
        self.assertEqual(DotThanhToan.objects.count(), 0)

    def test_payment_detail_rejects_excess_sessions_and_travel_without_500(self):
        dot = DotThanhToan.objects.create(hop_dong=self.contract, nam=2026, thang=9)
        for excess, field in (({"so_buoi_thanh_toan": 2}, "so_buoi_thanh_toan"), ({"so_luot_di_lai": 1}, "so_luot_di_lai")):
            with self.subTest(field=field):
                response = self.client.post(reverse("them_chi_tiet_thanh_toan", args=[dot.pk]), self._detail_payload(**excess))
                self.assertEqual(response.status_code, 200)
                self.assertIn(field, response.context["form"].errors)
                self.assertEqual(ChiTietThanhToan.objects.count(), 0)

    def test_valid_payment_detail_is_created(self):
        dot = DotThanhToan.objects.create(hop_dong=self.contract, nam=2026, thang=9)
        response = self.client.post(reverse("them_chi_tiet_thanh_toan", args=[dot.pk]), self._detail_payload())
        self.assertEqual(response.status_code, 302)
        self.assertEqual(ChiTietThanhToan.objects.get().thanh_tien, Decimal("200000"))

    def test_cbda_cannot_move_assignment_into_locked_allocation(self):
        target = PhanBoChiTieu.objects.create(can_bo=self.staff, nhom_hd=self.group, so_tre_phcn=1, is_locked=True)
        self.client.force_login(self.cbda)
        response = self.client.post(reverse("sua_phan_cong", args=[self.assignment.pk]), self._assignment_payload(phan_bo=target.pk))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].non_field_errors())
        self.assignment.refresh_from_db()
        self.assertEqual(self.assignment.phan_bo_id, self.allocation.pk)

    def test_admin_can_edit_assignment_in_locked_allocation(self):
        self.allocation.is_locked = True
        self.allocation.save(update_fields=["is_locked"])
        response = self.client.post(reverse("sua_phan_cong", args=[self.assignment.pk]), self._assignment_payload(ghi_chu="Đã sửa"))
        self.assertEqual(response.status_code, 302)
        self.assignment.refresh_from_db()
        self.assertEqual(self.assignment.ghi_chu, "Đã sửa")

    def test_cbda_cannot_move_journal_into_locked_or_liquidated_contract(self):
        self.client.force_login(self.cbda)
        for locked, status in ((True, "DA_KY"), (False, "THANH_LY")):
            with self.subTest(locked=locked, status=status):
                target = HopDong.objects.create(
                    de_xuat=self.contract.de_xuat, can_bo=self.staff, nhom_hd=self.group,
                    so_hop_dong=f"HD-LOCKED-{status}", tu_ngay=date(2026, 9, 1), den_ngay=date(2026, 9, 30),
                    gia_tri_hop_dong=Decimal("5000000"), is_locked=locked, trang_thai=status,
                )
                response = self.client.post(reverse("sua_nhat_ky_can_thiep", args=[self.journal.pk]), self._journal_payload(hop_dong=target.pk))
                self.assertEqual(response.status_code, 200)
                self.assertIn("hop_dong", response.context["form"].errors)
                self.journal.refresh_from_db()
                self.assertEqual(self.journal.hop_dong_id, self.contract.pk)

    def test_contract_journal_date_outside_term_returns_form_error(self):
        response = self.client.post(
            reverse("them_nhat_ky_thuc_hien", args=[self.contract.pk]),
            self._journal_payload(ngay_thuc_hien="2026-10-01"),
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("ngay_thuc_hien", response.context["form"].errors)
        self.assertEqual(NhatKyThucHien.objects.count(), 1)

    def test_signed_extension_cannot_be_unsigned_after_acceptance(self):
        extension = self._extension()
        NghiemThu.objects.create(hop_dong=self.contract, ngay_nghiem_thu=date(2026, 9, 20), gia_tri_nghiem_thu=Decimal("200000"))
        response = self.client.post(reverse("sua_gia_han_hop_dong", args=[extension.pk]), self._extension_payload())
        self.assertEqual(response.status_code, 302)
        extension.refresh_from_db()
        self.assertTrue(extension.is_signed)
        self.assertEqual(extension.den_ngay_moi, date(2026, 10, 31))

    def test_signed_extension_cannot_be_deleted_after_pending_or_paid_voucher(self):
        extension = self._extension()
        voucher = self._voucher()
        for status in ("CHO_CHI", "DA_CHI"):
            with self.subTest(status=status):
                PhieuThanhToan.objects.filter(pk=voucher.pk).update(trang_thai=status)
                response = self.client.post(reverse("xoa_gia_han_hop_dong", args=[extension.pk]))
                self.assertEqual(response.status_code, 302)
                self.assertTrue(PhuLucHopDong.objects.filter(pk=extension.pk).exists())

    def test_signed_extension_cannot_be_moved_to_bypass_original_voucher(self):
        extension = self._extension()
        self._voucher()
        target = HopDong.objects.create(
            can_bo=self.staff, nhom_hd=self.group, so_hop_dong="HD-MOVE-TARGET",
            tu_ngay=date(2026, 9, 1), den_ngay=date(2026, 9, 30), gia_tri_hop_dong=Decimal("5000000"),
        )
        response = self.client.post(reverse("sua_gia_han_hop_dong", args=[extension.pk]), self._extension_payload(hop_dong=target.pk))
        self.assertEqual(response.status_code, 302)
        extension.refresh_from_db()
        self.assertEqual(extension.hop_dong_id, self.contract.pk)
        self.assertTrue(extension.is_signed)

    def test_moving_signed_time_extension_restores_source_and_syncs_target(self):
        extension = self._extension()
        self.contract.den_ngay = extension.den_ngay_moi
        self.contract.save(update_fields=["den_ngay"])
        target = HopDong.objects.create(
            can_bo=self.staff, nhom_hd=self.group, so_hop_dong="HD-TIME-MOVE",
            tu_ngay=date(2026, 9, 1), den_ngay=date(2026, 12, 31), gia_tri_hop_dong=Decimal("5000000"),
        )
        response = self.client.post(
            reverse("sua_gia_han_hop_dong", args=[extension.pk]),
            self._extension_payload(hop_dong=target.pk, is_signed="1", den_ngay_moi="2027-01-31"),
        )
        self.assertEqual(response.status_code, 302)
        extension.refresh_from_db()
        self.contract.refresh_from_db()
        target.refresh_from_db()
        self.assertEqual(extension.hop_dong_id, target.pk)
        self.assertEqual(extension.den_ngay_cu, date(2026, 12, 31))
        self.assertEqual(self.contract.den_ngay, date(2026, 9, 30))
        self.assertEqual(target.den_ngay, date(2027, 1, 31))

    def test_moving_signed_volume_extension_uses_target_rates_and_restores_source(self):
        self.contract.gia_tri_hop_dong = Decimal("10000000")
        self.contract.save(update_fields=["gia_tri_hop_dong"])
        extension = PhuLucHopDong.objects.create(
            hop_dong=self.contract, loai_phu_luc="GIA_HAN_KHOI_LUONG", is_signed=True,
            ngay_lap=date(2026, 9, 20), den_ngay_cu=date(2026, 9, 30), den_ngay_moi=date(2026, 9, 30),
            tong_tien_tang_them=Decimal("5000000"), tong_tien_moi=Decimal("10000000"),
        )
        ChiTietGiaHanKhoiLuong.objects.create(
            phu_luc=extension, loai_dich_vu="VLTL", so_tre_cu=1, so_tre_moi=2,
            so_buoi_cu=20, so_buoi_moi=20, don_gia_cong=Decimal("200000"), dinh_muc_di_lai=Decimal("50000"),
        )
        ChiTietKhoiLuongHopDong.objects.create(
            hop_dong=self.contract, loai_dich_vu="VLTL", so_tre=2, so_buoi=20,
            don_gia_cong=Decimal("200000"), dinh_muc_di_lai=Decimal("50000"),
        )
        target = HopDong.objects.create(
            can_bo=self.staff, nhom_hd=self.group, so_hop_dong="HD-VOLUME-MOVE",
            tu_ngay=date(2026, 9, 1), den_ngay=date(2026, 9, 30), gia_tri_hop_dong=Decimal("1100000"),
            don_gia_cong=Decimal("100000"), dinh_muc_di_lai_phcn=Decimal("10000"),
        )
        ChiTietKhoiLuongHopDong.objects.create(
            hop_dong=target, loai_dich_vu="VLTL", so_tre=1, so_buoi=10,
            don_gia_cong=Decimal("100000"), dinh_muc_di_lai=Decimal("10000"),
        )
        response = self.client.post(reverse("sua_gia_han_hop_dong", args=[extension.pk]), {
            **self._extension_payload(hop_dong=target.pk, is_signed="1", den_ngay_moi="2026-09-30"),
            "so_tre_phcn_moi": 3, "so_buoi_phcn_moi": 10,
            "so_tre_cs_moi": 0, "so_buoi_cs_moi": 0,
        })
        self.assertEqual(response.status_code, 302)
        extension.refresh_from_db()
        self.contract.refresh_from_db()
        target.refresh_from_db()
        self.assertEqual(extension.hop_dong_id, target.pk)
        self.assertEqual(extension.tong_tien_tang_them, Decimal("2200000"))
        self.assertEqual(extension.tong_tien_moi, Decimal("3300000"))
        self.assertEqual(target.gia_tri_hop_dong, Decimal("3300000"))
        self.assertEqual(self.contract.gia_tri_hop_dong, Decimal("5000000"))
        source_detail = self.contract.chi_tiet_khoi_luong.get(loai_dich_vu="VLTL")
        self.assertEqual((source_detail.so_tre, source_detail.so_buoi), (1, 20))
        self.assertEqual(source_detail.thanh_tien, Decimal("5000000"))

    def test_time_extension_edit_renders_existing_contract_and_signed_state(self):
        extension = self._extension()
        response = self.client.get(reverse("sua_gia_han_hop_dong", args=[extension.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["form"].initial["den_ngay_cu"], date(2026, 9, 30))
        for form_class in (GiaHanThoiGianForm, GiaHanKhoiLuongForm):
            with self.subTest(form=form_class.__name__):
                form = form_class(instance=extension)
                self.assertIn('value="1" selected', str(form["is_signed"]))

    def test_html_date_input_uses_iso_value_for_existing_dates(self):
        self.assertIn('value="2015-01-01"', str(TreForm(instance=self.child)["ngay_sinh"]))

    def _allocation_preview(self, **overrides):
        row = {"MaCBCT": self.staff.ma_can_bo, "NhomHD": self.group.ma_nhom_hd,
               "SoTrePHCN": 1, "SoBuoiPHCN": 20, "SoTreCS": 0, "SoBuoiCS": 0,
               "NgayLap": "2026-09-01", **overrides}
        output = BytesIO()
        pd.DataFrame([row]).to_excel(output, index=False)
        return self.client.post(reverse("import_phan_bo"), {
            "excel_file": SimpleUploadedFile("allocations.xlsx", output.getvalue()),
        })

    def test_allocation_preview_rejects_negative_counts(self):
        response = self._allocation_preview(SoTrePHCN=-1)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["valid_count"], 0)
        self.assertEqual(response.context["invalid_count"], 1)
        self.assertEqual(self.client.session["import_phan_bo_valid_data"], [])

    def test_allocation_confirmation_revalidates_stale_foreign_keys(self):
        self._allocation_preview()
        session = self.client.session
        data = session["import_phan_bo_valid_data"]
        data[0]["can_bo_id"] = 2147483647
        session["import_phan_bo_valid_data"] = data
        session.save()
        count = PhanBoChiTieu.objects.count()
        response = self.client.post(reverse("confirm_import_phan_bo"))
        self.assertRedirects(response, reverse("import_phan_bo"))
        self.assertEqual(PhanBoChiTieu.objects.count(), count)

    def test_allocation_confirmation_integrity_error_returns_feedback(self):
        self._allocation_preview()
        count = PhanBoChiTieu.objects.count()
        with patch.object(PhanBoChiTieu.objects, "bulk_create", side_effect=IntegrityError("competing update")):
            response = self.client.post(reverse("confirm_import_phan_bo"), follow=True)
        self.assertContains(response, "toàn bộ dữ liệu đã được hoàn tác")
        self.assertEqual(PhanBoChiTieu.objects.count(), count)

    def test_failed_upload_clears_previous_allocation_preview(self):
        self._allocation_preview()
        self.assertTrue(self.client.session["import_phan_bo_valid_data"])
        self.client.post(reverse("import_phan_bo"), {"excel_file": SimpleUploadedFile("invalid.xlsx", b"invalid")})
        self.assertNotIn("import_phan_bo_valid_data", self.client.session)

    def _batch_contracts(self):
        self.contract.trang_thai = "DA_KY"
        self.contract.save(update_fields=["trang_thai"])
        other = HopDong.objects.create(
            de_xuat=self.contract.de_xuat, can_bo=self.staff, nhom_hd=self.group,
            so_hop_dong="HD-BATCH-REVIEW", tu_ngay=date(2026, 9, 1), den_ngay=date(2026, 9, 30),
            gia_tri_hop_dong=Decimal("5000000"), trang_thai="DA_KY",
        )
        other_journal = NhatKyThucHien.objects.create(
            hop_dong=other, phan_cong=self.assignment, ngay_thuc_hien=date(2026, 9, 3),
            so_buoi_thuc_hien=1, don_gia_cong=Decimal("200000"), dinh_muc_di_lai=Decimal("50000"),
        )
        return other, other_journal

    def test_batch_passes_complete_locked_journal_scope_and_excludes_late_row(self):
        other, other_journal = self._batch_contracts()
        calls, late_rows = [], []

        def create_after_prelock(staff, contract, period, user, *, locked_journal_ids):
            calls.append((contract.pk, locked_journal_ids))
            if not late_rows:
                late_rows.append(NhatKyThucHien.objects.create(
                    hop_dong=self.contract, phan_cong=self.assignment, ngay_thuc_hien=date(2026, 9, 4),
                    so_buoi_thuc_hien=1, don_gia_cong=Decimal("200000"), dinh_muc_di_lai=Decimal("50000"),
                ))
            return create_voucher(staff, contract, period, user, locked_journal_ids=locked_journal_ids)

        with patch("quanly.views.tao_phieu_thanh_toan_service", side_effect=create_after_prelock):
            response = self.client.post(reverse("tao_phieu_thanh_toan"), {"nhom_hd": self.group.pk, "ky": 1})
        self.assertEqual(response.status_code, 302)
        expected_scope = sorted([self.journal.pk, other_journal.pk])
        self.assertEqual(calls, [(self.contract.pk, expected_scope), (other.pk, expected_scope)])
        self.assertEqual(PhieuThanhToan.objects.count(), 2)
        self.assertEqual(sum(voucher.chi_tiet.count() for voucher in PhieuThanhToan.objects.all()), 2)
        self.assertFalse(late_rows[0].chi_tiet_phieu_thanh_toan.exists())

    def test_batch_rolls_back_first_voucher_if_later_contract_fails(self):
        other, _journal = self._batch_contracts()

        def fail_second(staff, contract, period, user, *, locked_journal_ids):
            if contract.pk == other.pk:
                raise ValidationError("Simulated later contract conflict")
            return create_voucher(staff, contract, period, user, locked_journal_ids=locked_journal_ids)

        with patch("quanly.views.tao_phieu_thanh_toan_service", side_effect=fail_second):
            response = self.client.post(reverse("tao_phieu_thanh_toan"), {"nhom_hd": self.group.pk, "ky": 1}, follow=True)
        self.assertContains(response, "Không tạo phiếu nào")
        self.assertEqual(PhieuThanhToan.objects.count(), 0)
        self.assertFalse(self.journal.chi_tiet_phieu_thanh_toan.exists())
