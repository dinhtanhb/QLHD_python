from datetime import date
from decimal import Decimal, InvalidOperation
import re

import pandas as pd
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q, Sum
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .decorators import admin_required, dashboard_required, hopdong_required, readonly_required
from .document_export import create_contract_from_proposal, export_acceptance_record, export_assignment_annex, export_contract_bundle, export_journal_payment_request, export_liquidation_record
from .payment_export import export_intervention_account_list, export_intervention_payment_request, export_journal_account_list, export_journal_commitment, export_journal_payment_request_excel, export_parent_travel_account_list, export_parent_travel_payment_request
from .financial import FinancialConfig, calculate_payment_breakdown
from .forms import (
    CanBoForm,
    DieuChuyenPhanCongForm,
    ChiTietKhoiLuongHopDongForm,
    ChiTietThanhToanForm,
    DeXuatHopDongForm,
    DotThanhToanForm,
    DonViForm,
    HopDongForm,
    NhomHDForm,
    NhatKyThucHienForm,
    NhatKyCanThiepForm,
    NghiemThuForm,
    PhanBoChiTieuForm,
    PhanCongTreForm,
    PhuLucHopDongForm,
    TreForm,
    ThanhLyHopDongForm,
    DotThanhToanDiLaiPhuHuynhForm,
    ChiTietThanhToanDiLaiPhuHuynhForm,
)
from .models import (
    CanBo,
    ChiTietKhoiLuongHopDong,
    ChiTietPhuLucPhanCong,
    DeXuatHopDong,
    DonVi,
    HopDong,
    NhomHD,
    NghiemThu,
    PhanBoChiTieu,
    PhanCongTre,
    PhuLucHopDong,
    Tre,
    Tinh,
    Xa,
    LichSuDieuChuyenPhanCong,
    NhatKyThucHien,
    ThanhLyHopDong,
    DotThanhToanDiLaiPhuHuynh,
    ChiTietThanhToanDiLaiPhuHuynh,
)


# =========================================================
# TIỆN ÍCH DỮ LIỆU
# =========================================================
def clean_empty_excel_value(value):
    """Chuẩn hóa giá trị Excel: NaN, None, NBSP và chuỗi rỗng -> None."""
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass

    text = str(value).replace("\xa0", " ").strip()
    if not text or text.lower() in {"nan", "none", "null", "nat"}:
        return None
    if re.fullmatch(r"[-+]?\d+\.0", text):
        text = text[:-2]
    return text


def parse_int(value, default=0):
    value = clean_empty_excel_value(value)
    if value is None:
        return default
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return default


def parse_decimal(value, default=Decimal("0")):
    value = clean_empty_excel_value(value)
    if value is None:
        return default
    try:
        normalized = value.replace(",", "").replace(" ", "")
        return Decimal(normalized)
    except (InvalidOperation, ValueError, TypeError):
        return default


def parse_date(value, default=None):
    value = clean_empty_excel_value(value)
    if value is None:
        return default
    try:
        return pd.to_datetime(value, errors="raise").date()
    except (ValueError, TypeError):
        return default


def normalized_columns(df):
    df = df.copy()
    df.columns = [str(col).replace("\xa0", " ").strip() for col in df.columns]
    return df


def get_excel_value(row, *names):
    lookup = {str(col).replace("\xa0", " ").strip().lower(): col for col in row.index}
    for name in names:
        col = lookup.get(str(name).replace("\xa0", " ").strip().lower())
        if col is not None:
            return row[col]
    return None


def service_is_cs(service):
    return PhanCongTre.service_group(service) == "CS"


def calculate_expected_value(so_tre_phcn, so_buoi_phcn, dm_phcn, so_tre_cs, so_buoi_cs, dm_cs):
    cong = Decimal(str(FinancialConfig.DON_GIA_CONG))
    return (
        Decimal(so_tre_phcn) * Decimal(so_buoi_phcn) * (cong + Decimal(dm_phcn))
        + Decimal(so_tre_cs) * Decimal(so_buoi_cs) * (cong + Decimal(dm_cs))
    )


# =========================================================
# DASHBOARD / AJAX
# =========================================================
@dashboard_required
def trang_chu(request):
    allocations = PhanBoChiTieu.objects.all()
    assignments = PhanCongTre.objects.all()
    contracts = HopDong.objects.all()
    allocation_value = sum(
        calculate_expected_value(
            item.so_tre_phcn,
            item.so_buoi_phcn,
            item.dinh_muc_di_lai_phcn,
            item.so_tre_cs,
            item.so_buoi_cs,
            item.dinh_muc_di_lai_cs,
        )
        for item in allocations
    )
    context = {
        "tong_tre": Tre.objects.filter(is_active=True).count(),
        "tong_can_bo": CanBo.objects.filter(is_active=True).count(),
        "tong_don_vi": DonVi.objects.filter(is_active=True).count(),
        "tong_nhom": NhomHD.objects.filter(is_active=True).count(),
        "tong_phan_bo": allocations.count(),
        "tong_phan_cong": assignments.count(),
        "tong_de_xuat": DeXuatHopDong.objects.count(),
        "tong_hop_dong": contracts.count(),
        "phcn_so_tre": allocations.aggregate(total=Sum("so_tre_phcn"))["total"] or 0,
        "phcn_so_buoi_moi_tre": allocations.aggregate(total=Sum("so_buoi_phcn"))["total"] or 0,
        "cs_so_tre": allocations.aggregate(total=Sum("so_tre_cs"))["total"] or 0,
        "cs_so_buoi_moi_tre": allocations.aggregate(total=Sum("so_buoi_cs"))["total"] or 0,
        "phcn_phan_cong": assignments.filter(loai_dich_vu__in=PhanCongTre.PHCN_SERVICE_CODES).count(),
        "cs_phan_cong": assignments.filter(loai_dich_vu__in=PhanCongTre.CS_SERVICE_CODES).count(),
        "gia_tri_phan_bo": allocation_value,
        "gia_tri_hop_dong": contracts.aggregate(total=Sum("gia_tri_hop_dong"))["total"] or 0,
    }
    return render(request, "quanly/trang_chu.html", context)


@dashboard_required
def lay_danh_sach_xa(request):
    tinh_id = request.GET.get("tinh_id")
    if not tinh_id:
        return JsonResponse([], safe=False)
    xas = Xa.objects.filter(tinh_id=tinh_id, is_active=True).values("id", "ma_xa", "ten_xa")
    return JsonResponse(list(xas), safe=False)


# =========================================================
# NHÓM HỢP ĐỒNG
# =========================================================
@hopdong_required
def danh_sach_nhom_hd(request):
    ds_nhom = NhomHD.objects.all().order_by("ma_nhom_hd")
    return render(request, "quanly/danh_sach_nhom_hd.html", {"ds_nhom": ds_nhom})


@hopdong_required
def them_nhom_hd(request):
    form = NhomHDForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Đã thêm Nhóm hợp đồng thành công.")
        return redirect("danh_sach_nhom_hd")
    return render(request, "quanly/them_nhom_hd.html", {"form": form})


@hopdong_required
def sua_nhom_hd(request, id):
    nhom = get_object_or_404(NhomHD, pk=id)
    form = NhomHDForm(request.POST or None, instance=nhom)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Đã cập nhật Nhóm hợp đồng.")
        return redirect("danh_sach_nhom_hd")
    return render(request, "quanly/sua_nhom_hd.html", {"form": form, "nhom": nhom})


@admin_required
def xoa_nhom_hd(request, id):
    if request.method != "POST":
        return redirect("danh_sach_nhom_hd")
    nhom = get_object_or_404(NhomHD, pk=id)
    try:
        nhom.delete()
        messages.success(request, "Đã xóa Nhóm hợp đồng.")
    except Exception as exc:
        messages.error(request, f"Không thể xóa nhóm: {exc}")
    return redirect("danh_sach_nhom_hd")


# =========================================================
# ĐƠN VỊ
# =========================================================
@readonly_required
def danh_sach_don_vi(request):
    query = request.GET.get("q", "").strip()
    qs = DonVi.objects.all()
    if query:
        qs = qs.filter(Q(ma_don_vi__icontains=query) | Q(ten_don_vi__icontains=query) | Q(mstdv__icontains=query))
    page_obj = Paginator(qs.order_by("ten_don_vi"), 15).get_page(request.GET.get("page"))
    return render(request, "quanly/danh_sach_don_vi.html", {"page_obj": page_obj, "query": query})


@admin_required
def them_don_vi(request):
    form = DonViForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Đã thêm Đơn vị thành công.")
        return redirect("danh_sach_don_vi")
    return render(request, "quanly/them_don_vi.html", {"form": form})


@admin_required
def sua_don_vi(request, id):
    don_vi = get_object_or_404(DonVi, pk=id)
    form = DonViForm(request.POST or None, instance=don_vi)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Đã cập nhật Đơn vị.")
        return redirect("danh_sach_don_vi")
    return render(request, "quanly/sua_don_vi.html", {"form": form, "don_vi": don_vi})


@admin_required
def xoa_don_vi(request, id):
    if request.method != "POST":
        return redirect("danh_sach_don_vi")
    don_vi = get_object_or_404(DonVi, pk=id)
    try:
        don_vi.delete()
        messages.success(request, "Đã xóa Đơn vị.")
    except Exception as exc:
        messages.error(request, f"Không thể xóa đơn vị: {exc}")
    return redirect("danh_sach_don_vi")


# =========================================================
# TRẺ
# =========================================================
@readonly_required
def danh_sach_tre(request):
    query = request.GET.get("q", "").strip()
    qs = Tre.objects.select_related("tinh", "xa")
    if query:
        qs = qs.filter(
            Q(ma_tre__icontains=query)
            | Q(ho_ten__icontains=query)
            | Q(ten_phu_huynh__icontains=query)
            | Q(dien_thoai__icontains=query)
        )
    page_obj = Paginator(qs.order_by("ma_tre"), 15).get_page(request.GET.get("page"))
    return render(request, "quanly/danh_sach_tre.html", {"page_obj": page_obj, "query": query})


@admin_required
def them_tre(request):
    form = TreForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Đã lưu hồ sơ Trẻ thành công.")
        return redirect("danh_sach_tre")
    return render(request, "quanly/them_tre.html", {"form": form})


@admin_required
def sua_tre(request, id):
    tre = get_object_or_404(Tre, pk=id)
    form = TreForm(request.POST or None, instance=tre)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"Đã cập nhật hồ sơ {tre.ho_ten}.")
        return redirect("danh_sach_tre")
    return render(request, "quanly/sua_tre.html", {"form": form, "tre": tre})


@admin_required
def xoa_tre(request, id):
    if request.method != "POST":
        return redirect("danh_sach_tre")
    tre = get_object_or_404(Tre, pk=id)
    try:
        tre.delete()
        messages.success(request, "Đã xóa hồ sơ Trẻ.")
    except Exception as exc:
        messages.error(request, f"Không thể xóa trẻ: {exc}")
    return redirect("danh_sach_tre")


@admin_required
def import_tre(request):
    if request.method != "POST" or not request.FILES.get("file_excel"):
        return render(request, "quanly/import_tre.html")

    try:
        df = normalized_columns(pd.read_excel(request.FILES["file_excel"]))
    except Exception as exc:
        messages.error(request, f"Không đọc được file Excel: {exc}")
        return render(request, "quanly/import_tre.html")

    created = updated = skipped = 0
    errors = []
    for row_no, (_, row) in enumerate(df.iterrows(), start=2):
        try:
            ma_tre = clean_empty_excel_value(get_excel_value(row, "MaTre", "Mã trẻ", "IDChild"))
            if not ma_tre:
                skipped += 1
                continue
            defaults = {
                "ho_ten": clean_empty_excel_value(get_excel_value(row, "HoTen", "Họ tên", "Tên trẻ")) or "Chưa cập nhật",
                "ngay_sinh": parse_date(get_excel_value(row, "NgaySinh", "Ngày sinh"), date(2000, 1, 1)),
                "gioi_tinh": clean_empty_excel_value(get_excel_value(row, "GioiTinh", "Giới tính")) or "Khác",
                "ten_phu_huynh": clean_empty_excel_value(get_excel_value(row, "TenPhuHuynh", "Tên phụ huynh")),
                "dien_thoai": clean_empty_excel_value(get_excel_value(row, "SdtPhuHuynh", "Điện thoại", "SĐT")),
                "ten_tai_khoan": clean_empty_excel_value(get_excel_value(row, "TenTaiKhoanPH", "Tên tài khoản")),
                "tai_khoan": clean_empty_excel_value(get_excel_value(row, "SoTaiKhoanPH", "Số tài khoản", "STK")),
                "ngan_hang": clean_empty_excel_value(get_excel_value(row, "NganHangPH", "Ngân hàng")),
                "chi_nhanh": clean_empty_excel_value(get_excel_value(row, "ChiNhanhPH", "Chi nhánh")),
            }
            obj, is_created = Tre.objects.update_or_create(ma_tre=ma_tre, defaults=defaults)
            created += int(is_created)
            updated += int(not is_created)
        except Exception as exc:
            skipped += 1
            errors.append(f"Dòng {row_no}: {exc}")

    msg = f"Import trẻ hoàn tất: thêm {created}, cập nhật {updated}, bỏ qua {skipped}."
    if errors:
        msg += " " + " | ".join(errors[:5])
    messages.success(request, msg)
    return redirect("danh_sach_tre")


# =========================================================
# CÁN BỘ
# =========================================================
@readonly_required
def danh_sach_can_bo(request):
    query = request.GET.get("q", "").strip()
    qs = CanBo.objects.select_related("don_vi", "tinh", "xa")
    if query:
        qs = qs.filter(
            Q(ma_can_bo__icontains=query)
            | Q(ho_ten__icontains=query)
            | Q(cccd__icontains=query)
            | Q(dien_thoai__icontains=query)
            | Q(don_vi__ten_don_vi__icontains=query)
        )
    page_obj = Paginator(qs.order_by("ho_ten"), 15).get_page(request.GET.get("page"))
    return render(request, "quanly/danh_sach_can_bo.html", {"page_obj": page_obj, "query": query})


@admin_required
def them_can_bo(request):
    form = CanBoForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Đã thêm hồ sơ Cán bộ thành công.")
        return redirect("danh_sach_can_bo")
    return render(request, "quanly/them_can_bo.html", {"form": form})


@admin_required
def sua_can_bo(request, id):
    can_bo = get_object_or_404(CanBo, pk=id)
    form = CanBoForm(request.POST or None, instance=can_bo)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Đã cập nhật hồ sơ Cán bộ.")
        return redirect("danh_sach_can_bo")
    return render(request, "quanly/sua_can_bo.html", {"form": form, "can_bo": can_bo})


@admin_required
def xoa_can_bo(request, id):
    if request.method != "POST":
        return redirect("danh_sach_can_bo")
    can_bo = get_object_or_404(CanBo, pk=id)
    try:
        can_bo.delete()
        messages.success(request, "Đã xóa hồ sơ Cán bộ.")
    except Exception as exc:
        messages.error(request, f"Không thể xóa cán bộ: {exc}")
    return redirect("danh_sach_can_bo")


@admin_required
def import_can_bo(request):
    if request.method != "POST" or not request.FILES.get("file_excel"):
        return render(request, "quanly/import_can_bo.html")

    try:
        df = normalized_columns(pd.read_excel(request.FILES["file_excel"]))
    except Exception as exc:
        messages.error(request, f"Không đọc được file Excel: {exc}")
        return render(request, "quanly/import_can_bo.html")

    created = updated = skipped = 0
    errors = []
    for row_no, (_, row) in enumerate(df.iterrows(), start=2):
        try:
            ma_cb = clean_empty_excel_value(get_excel_value(row, "MaCB", "MaCBCT", "Mã CBCT", "Mã CB"))
            ho_ten = clean_empty_excel_value(get_excel_value(row, "TenCB", "Họ tên", "Họ và tên"))
            if not ma_cb or not ho_ten:
                skipped += 1
                continue

            defaults = {
                "ho_ten": ho_ten,
                "gioi_tinh": clean_empty_excel_value(get_excel_value(row, "GioiTinh", "Giới tính")),
                "cccd": clean_empty_excel_value(get_excel_value(row, "CCCD", "Số CCCD", "CMND")),
                "mst": clean_empty_excel_value(get_excel_value(row, "MST", "MSTCN", "Mã số thuế")),
                "dien_thoai": clean_empty_excel_value(get_excel_value(row, "DienThoai", "Điện thoại", "SĐT")),
                "email": clean_empty_excel_value(get_excel_value(row, "Email")),
                "dia_chi": clean_empty_excel_value(get_excel_value(row, "DiaChi", "Địa chỉ")),
                "tai_khoan": clean_empty_excel_value(get_excel_value(row, "TaiKhoanNH", "Số tài khoản", "STK")),
                "ngan_hang": clean_empty_excel_value(get_excel_value(row, "TenNH", "Ngân hàng")),
                "chi_nhanh": clean_empty_excel_value(get_excel_value(row, "ChiNhanhNH", "Chi nhánh")),
                "ngay_cap": parse_date(get_excel_value(row, "NgayCapCCCD", "Ngày cấp CCCD", "Ngày cấp")),
                "noi_cap": clean_empty_excel_value(get_excel_value(row, "NoiCapCCCD", "Nơi cấp CCCD", "Nơi cấp")),
            }
            don_vi_name = clean_empty_excel_value(get_excel_value(row, "DonViCongTac", "Đơn vị công tác", "Đơn vị"))
            if don_vi_name:
                don_vi = DonVi.objects.filter(Q(ma_don_vi=don_vi_name) | Q(ten_don_vi__iexact=don_vi_name)).first()
                if don_vi:
                    defaults["don_vi"] = don_vi
                else:
                    raise ValueError(f"Không tìm thấy Đơn vị '{don_vi_name}'")
            elif not CanBo.objects.filter(ma_can_bo=ma_cb).exists():
                raise ValueError("Thiếu Đơn vị công tác cho cán bộ mới")

            obj, is_created = CanBo.objects.update_or_create(ma_can_bo=ma_cb, defaults=defaults)
            created += int(is_created)
            updated += int(not is_created)
        except Exception as exc:
            skipped += 1
            errors.append(f"Dòng {row_no}: {exc}")

    msg = f"Import cán bộ hoàn tất: thêm {created}, cập nhật {updated}, bỏ qua {skipped}."
    if errors:
        msg += " " + " | ".join(errors[:5])
    messages.success(request, msg)
    return redirect("danh_sach_can_bo")


# =========================================================
# PHÂN CÔNG TRẺ
# =========================================================
@hopdong_required
def danh_sach_phan_cong(request):
    query = request.GET.get("q", "").strip()
    phan_bo_id = request.GET.get("phan_bo_id", "").strip()
    qs = PhanCongTre.objects.select_related("tre", "phan_bo__can_bo", "phan_bo__nhom_hd")

    if phan_bo_id.isdigit():
        qs = qs.filter(phan_bo_id=int(phan_bo_id))

    if query:
        qs = qs.filter(
            Q(tre__ma_tre__icontains=query)
            | Q(tre__ho_ten__icontains=query)
            | Q(phan_bo__can_bo__ma_can_bo__icontains=query)
            | Q(phan_bo__can_bo__ho_ten__icontains=query)
        )

    page_obj = Paginator(qs.order_by("-ngay_phan_cong", "-id"), 20).get_page(request.GET.get("page"))
    phan_bo = None
    if phan_bo_id.isdigit():
        phan_bo = PhanBoChiTieu.objects.select_related("can_bo", "nhom_hd").filter(pk=int(phan_bo_id)).first()

    return render(
        request,
        "quanly/danh_sach_phan_cong.html",
        {
            "page_obj": page_obj,
            "danh_sach": page_obj,
            "query": query,
            "phan_bo": phan_bo,
            "phan_bo_id": phan_bo_id,
        },
    )


@hopdong_required
def them_phan_cong(request):
    phan_bo_id = request.GET.get("phan_bo_id") or request.POST.get("phan_bo")
    phan_bo = None
    if phan_bo_id and str(phan_bo_id).isdigit():
        phan_bo = get_object_or_404(
            PhanBoChiTieu.objects.select_related("can_bo", "nhom_hd"),
            pk=int(phan_bo_id),
        )
        if phan_bo.is_locked:
            messages.error(request, f"Phân bổ #{phan_bo.pk} đã khóa, không thể thêm phân công.")
            return redirect("danh_sach_phan_bo")

    if request.method == "POST":
        form = PhanCongTreForm(request.POST)
    else:
        initial = {"phan_bo": phan_bo} if phan_bo else {}
        form = PhanCongTreForm(initial=initial)

    if request.method == "POST" and form.is_valid():
        obj = form.save()
        messages.success(request, f"Đã thêm phân công trẻ #{obj.pk} cho phân bổ #{obj.phan_bo_id}.")
        if phan_bo:
            return redirect("danh_sach_phan_cong")
        return redirect("danh_sach_phan_cong")

    return render(
        request,
        "quanly/them_phan_cong.html",
        {"form": form, "phan_bo": phan_bo},
    )


@hopdong_required
def sua_phan_cong(request, pk):
    item = get_object_or_404(PhanCongTre, pk=pk)
    form = PhanCongTreForm(request.POST or None, instance=item)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Đã cập nhật phân công trẻ.")
        return redirect("danh_sach_phan_cong")
    return render(request, "quanly/sua_phan_cong.html", {"form": form, "item": item})


@admin_required
def xoa_phan_cong(request, pk):
    item = get_object_or_404(PhanCongTre, pk=pk)
    if request.method == "POST":
        try:
            item.delete()
            messages.success(request, "Đã xóa phân công trẻ.")
        except Exception as exc:
            messages.error(request, f"Không thể xóa phân công: {exc}")
    return redirect("danh_sach_phan_cong")


@hopdong_required
def dieu_chuyen_phan_cong(request, pk):
    item = get_object_or_404(PhanCongTre.objects.select_related("phan_bo__nhom_hd", "tre"), pk=pk)
    queryset = PhanBoChiTieu.objects.filter(nhom_hd=item.phan_bo.nhom_hd).exclude(pk=item.phan_bo_id).select_related("can_bo", "nhom_hd")
    if request.method == "POST":
        form = DieuChuyenPhanCongForm(request.POST)
        form.fields["phan_bo"].queryset = queryset
        if form.is_valid():
            target = form.cleaned_data["phan_bo"]
            old = item.phan_bo
            item.phan_bo = target
            is_cs = PhanCongTre.service_group(item.loai_dich_vu) == "CS"
            item.dinh_muc_di_lai = target.dinh_muc_di_lai_cs if is_cs else target.dinh_muc_di_lai_phcn
            item.full_clean()
            with transaction.atomic():
                item.save(update_fields=["phan_bo", "dinh_muc_di_lai", "updated_at"])
                LichSuDieuChuyenPhanCong.objects.create(phan_cong=item, phan_bo_cu=old, phan_bo_moi=target, nguoi_thuc_hien=request.user.get_username(), ly_do=form.cleaned_data.get("ly_do"))
            messages.success(request, "Đã điều chuyển phân công và ghi nhận lịch sử.")
            return redirect("danh_sach_phan_cong")
    else:
        form = DieuChuyenPhanCongForm()
        form.fields["phan_bo"].queryset = queryset
    return render(request, "quanly/dieu_chuyen_phan_cong.html", {"form": form, "item": item})


@hopdong_required
def lich_su_phan_cong(request, pk):
    item = get_object_or_404(PhanCongTre.objects.select_related("tre", "phan_bo__can_bo"), pk=pk)
    history = item.lich_su_dieu_chuyen.select_related("phan_bo_cu__can_bo", "phan_bo_moi__can_bo")
    return render(request, "quanly/lich_su_phan_cong.html", {"item": item, "history": history})


@admin_required
def import_phan_cong(request):
    if request.method != "POST" or not request.FILES.get("file_excel"):
        return render(request, "quanly/import_phan_cong.html")

    try:
        df = normalized_columns(pd.read_excel(request.FILES["file_excel"]))
    except Exception as exc:
        messages.error(request, f"Không đọc được file Excel: {exc}")
        return render(request, "quanly/import_phan_cong.html")

    created = skipped = 0
    errors = []
    for row_no, (_, row) in enumerate(df.iterrows(), start=2):
        try:
            ma_tre = clean_empty_excel_value(get_excel_value(row, "IDChild", "MaTre", "Mã trẻ"))
            ma_cb = clean_empty_excel_value(get_excel_value(row, "Mã CB", "MaCB", "MaCBCT", "Mã CBCT"))
            if not ma_tre or not ma_cb:
                raise ValueError("Thiếu mã trẻ hoặc mã CBCT")

            tre, _ = Tre.objects.get_or_create(
                ma_tre=ma_tre,
                defaults={
                    "ho_ten": clean_empty_excel_value(get_excel_value(row, "Tên trẻ", "HoTen")) or "Chưa cập nhật",
                    "ngay_sinh": date(2000, 1, 1),
                    "gioi_tinh": "Khác",
                },
            )
            can_bo = CanBo.objects.filter(ma_can_bo=ma_cb).first()
            if not can_bo:
                raise ValueError(f"Không tìm thấy cán bộ '{ma_cb}'")

            nhom_value = clean_empty_excel_value(get_excel_value(row, "Nhóm HĐ", "NhomHD", "Mã nhóm HĐ"))
            nhom = None
            if nhom_value:
                nhom = NhomHD.objects.filter(Q(ma_nhom_hd=nhom_value) | Q(ten_nhom_hd__iexact=nhom_value)).first()
            if not nhom:
                nhom = PhanBoChiTieu.objects.filter(can_bo=can_bo).order_by("-ngay_lap", "-id").values_list("nhom_hd", flat=True).first()
                nhom = NhomHD.objects.filter(pk=nhom).first() if nhom else None
            if not nhom:
                raise ValueError(f"Không tìm thấy Nhóm HĐ cho cán bộ '{ma_cb}'")

            phan_bo = PhanBoChiTieu.objects.filter(can_bo=can_bo, nhom_hd=nhom).order_by("-ngay_lap", "-id").first()
            if not phan_bo:
                raise ValueError("Chưa có Phân bổ chỉ tiêu tương ứng; không tự tạo phân bổ từ file phân công")

            service = clean_empty_excel_value(get_excel_value(row, "Loại dịch vụ", "LoaiDichVu", "Chỉ định CT")) or "CSXH"
            service_upper = service.upper()
            service_map = {"VLTL": "VLTL", "HDTL": "HDTL", "NNTL": "NNTL", "GDDB": "GDDB", "CSXH": "CSXH", "CSYT": "CSYT"}
            service = service_map.get(service_upper, "CSXH" if "CS" in service_upper else "VLTL")

            item = PhanCongTre.objects.create(
                phan_bo=phan_bo,
                tre=tre,
                loai_dich_vu=service,
                so_buoi_du_kien=parse_int(get_excel_value(row, "Số buổi dự kiến", "SoBuoi"), 0),
                dinh_muc_di_lai=parse_decimal(
                    get_excel_value(row, "Định mức đi lại", "DMDL"),
                    phan_bo.dinh_muc_di_lai_cs
                    if PhanCongTre.service_group(service) == "CS"
                    else phan_bo.dinh_muc_di_lai_phcn,
                ),
                dia_diem_ct=clean_empty_excel_value(get_excel_value(row, "Địa điểm CT", "DiaDiemCT")),
                hinh_thuc_ct=clean_empty_excel_value(get_excel_value(row, "Hình thức CT", "HinhThucCT")),
                dot_phan_cong=parse_int(get_excel_value(row, "Đợt phân công", "DotPhanCong"), 1),
                ky_phan_cong=parse_int(get_excel_value(row, "Kỳ phân công", "KyPhanCong"), 1),
                ngay_phan_cong=parse_date(get_excel_value(row, "Ngày phân công", "NgayPhanCong")),
                ghi_chu=clean_empty_excel_value(get_excel_value(row, "Ghi chú", "GhiChu")),
            )
            if item.so_buoi_du_kien <= 0:
                item.delete()
                raise ValueError("Số buổi dự kiến phải lớn hơn 0")
            created += 1
        except Exception as exc:
            skipped += 1
            errors.append(f"Dòng {row_no}: {exc}")

    msg = f"Import phân công hoàn tất: thêm {created}, bỏ qua {skipped}."
    if errors:
        msg += " " + " | ".join(errors[:8])
    messages.success(request, msg)
    return redirect("danh_sach_phan_cong")


@admin_required
def import_nhat_ky_can_thiep(request):
    if request.method != "POST" or not request.FILES.get("file_excel"):
        return render(request, "quanly/import_nhat_ky_can_thiep.html")
    try:
        df = normalized_columns(pd.read_excel(request.FILES["file_excel"]))
    except Exception as exc:
        messages.error(request, f"Không đọc được file Excel: {exc}")
        return render(request, "quanly/import_nhat_ky_can_thiep.html")
    created = updated = skipped = 0
    errors = []
    for row_no, (_, row) in enumerate(df.iterrows(), start=2):
        try:
            ma_cb = clean_empty_excel_value(get_excel_value(row, "MaCBCT", "Mã CBCT"))
            ma_tre = clean_empty_excel_value(get_excel_value(row, "MaTre", "Mã trẻ", "IDChild"))
            ngay = parse_date(get_excel_value(row, "NgayCanThiep", "Ngày can thiệp"))
            if not ma_cb or not ma_tre or not ngay:
                raise ValueError("Thiếu mã CBCT, mã trẻ hoặc ngày can thiệp")
            can_bo = CanBo.objects.get(ma_can_bo=ma_cb)
            tre = Tre.objects.get(ma_tre=ma_tre)
            nhom_value = clean_empty_excel_value(get_excel_value(row, "NhomHD", "Nhóm HĐ"))
            contracts = HopDong.objects.filter(can_bo=can_bo, tu_ngay__lte=ngay, den_ngay__gte=ngay).select_related("nhom_hd", "de_xuat")
            if nhom_value:
                contracts = contracts.filter(Q(nhom_hd__ma_nhom_hd=nhom_value) | Q(nhom_hd__ten_nhom_hd__iexact=nhom_value))
            hop_dong = contracts.order_by("-ngay_ky", "-id").first()
            if not hop_dong:
                raise ValueError("Không tìm thấy hợp đồng đang hiệu lực")
            raw_service = (clean_empty_excel_value(get_excel_value(row, "MaLoaiDichVu", "Loại dịch vụ")) or "PHCN").upper()
            service_codes = {"PHCN": PhanCongTre.PHCN_SERVICE_CODES, "CS": PhanCongTre.CS_SERVICE_CODES}
            if raw_service in PhanCongTre.LOAI_DV_CHOICES:
                assignment_qs = PhanCongTre.objects.filter(phan_bo=hop_dong.de_xuat.phan_bo, tre=tre, loai_dich_vu=raw_service)
            else:
                group = "CS" if raw_service in {"CS", "CSXH", "CSYT"} else "PHCN"
                assignment_qs = PhanCongTre.objects.filter(phan_bo=hop_dong.de_xuat.phan_bo, tre=tre, loai_dich_vu__in=service_codes[group])
            assignment = assignment_qs.order_by("id").first()
            if not assignment:
                raise ValueError("Không tìm thấy phân công tương ứng")
            defaults = {"so_buoi_thuc_hien": parse_int(get_excel_value(row, "SoBuoiThucTe", "Số buổi thực tế"), 0), "so_luot_di_lai": parse_int(get_excel_value(row, "SoLuotDiLaiPH", "Số lượt đi lại PH"), 0), "don_gia_cong": hop_dong.don_gia_cong, "dinh_muc_di_lai": assignment.dinh_muc_di_lai, "ghi_chu": clean_empty_excel_value(get_excel_value(row, "GhiChu", "Ghi chú"))}
            obj, is_created = NhatKyThucHien.objects.update_or_create(hop_dong=hop_dong, phan_cong=assignment, ngay_thuc_hien=ngay, defaults=defaults)
            created += int(is_created); updated += int(not is_created)
        except Exception as exc:
            skipped += 1; errors.append(f"Dòng {row_no}: {exc}")
    msg = f"Import nhật ký hoàn tất: thêm {created}, cập nhật {updated}, bỏ qua {skipped}."
    if errors:
        msg += " Chi tiết: " + " | ".join(errors[:8])
        messages.warning(request, msg)
    elif created or updated:
        messages.success(request, msg + " Dữ liệu đã được lưu vào cơ sở dữ liệu.")
    else:
        messages.warning(request, msg + " Không có dữ liệu nào được lưu.")
    return redirect("nhat_ky_can_thiep")


# =========================================================
# PHÂN BỔ CHỈ TIÊU
# =========================================================
@hopdong_required
def phan_bo_chi_tieu(request):
    form = PhanBoChiTieuForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        obj = form.save()
        messages.success(request, f"Đã lưu Phân bổ chỉ tiêu #{obj.pk}. Bước tiếp theo là phân công trẻ; chưa tạo đề xuất hợp đồng.")
        return redirect("danh_sach_phan_bo")
    return render(request, "quanly/phan_bo_chi_tieu.html", {"form": form})


@hopdong_required
def danh_sach_phan_bo(request):
    query = request.GET.get("q", "").strip()
    qs = PhanBoChiTieu.objects.select_related("can_bo", "nhom_hd").prefetch_related("danh_sach_phan_cong")
    if query:
        qs = qs.filter(Q(can_bo__ho_ten__icontains=query) | Q(can_bo__ma_can_bo__icontains=query) | Q(nhom_hd__ten_nhom_hd__icontains=query))
    page_obj = Paginator(qs.order_by("-ngay_lap", "-id"), 15).get_page(request.GET.get("page"))
    return render(request, "quanly/danh_sach_phan_bo.html", {"danh_sach": page_obj, "page_obj": page_obj, "query": query})


@admin_required
def xoa_phan_bo(request, pk):
    if request.method != "POST":
        return redirect("danh_sach_phan_bo")
    item = get_object_or_404(PhanBoChiTieu, pk=pk)
    if item.is_locked:
        messages.error(request, "Phân bổ đã khóa, không thể xóa.")
        return redirect("danh_sach_phan_bo")
    try:
        item.delete()
        messages.success(request, "Đã xóa Phân bổ chỉ tiêu.")
    except Exception as exc:
        messages.error(request, f"Không thể xóa Phân bổ: {exc}")
    return redirect("danh_sach_phan_bo")


@admin_required
def sua_phan_bo_chi_tieu(request, pk):
    item = get_object_or_404(PhanBoChiTieu, pk=pk)
    if item.is_locked:
        messages.error(request, "Phân bổ đã khóa, không thể sửa.")
        return redirect("danh_sach_phan_bo")
    form = PhanBoChiTieuForm(request.POST or None, instance=item)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Đã cập nhật Phân bổ chỉ tiêu.")
        return redirect("danh_sach_phan_bo")
    return render(request, "quanly/phan_bo_chi_tieu.html", {"form": form, "item": item})


@admin_required
def khoa_phan_bo(request, pk):
    item = get_object_or_404(PhanBoChiTieu, pk=pk)
    item.is_locked = True
    item.save(update_fields=["is_locked", "updated_at"])
    messages.success(request, f"Đã khóa Phân bổ #{item.pk}.")
    return redirect("danh_sach_phan_bo")


@admin_required
def import_phan_bo(request):
    if request.method != "POST" or "excel_file" not in request.FILES:
        return render(request, "quanly/import_phan_bo.html", {"has_preview": False})

    try:
        df = normalized_columns(pd.read_excel(request.FILES["excel_file"]))
    except Exception as exc:
        messages.error(request, f"Lỗi đọc file Excel: {exc}")
        return render(request, "quanly/import_phan_bo.html", {"has_preview": False})

    preview = []
    for row_no, (_, row) in enumerate(df.iterrows(), start=2):
        errors = []
        ma_cb = clean_empty_excel_value(get_excel_value(row, "MaCBCT", "Mã CBCT", "MaCB", "Mã CB"))
        can_bo = CanBo.objects.filter(ma_can_bo=ma_cb).first() if ma_cb else None
        if not can_bo:
            errors.append("Không tìm thấy cán bộ")

        nhom_raw = clean_empty_excel_value(get_excel_value(row, "NhomHD", "Mã nhóm HĐ", "Nhóm HĐ"))
        nhom = NhomHD.objects.filter(Q(ma_nhom_hd=nhom_raw) | Q(ten_nhom_hd__iexact=nhom_raw)).first() if nhom_raw else None
        if not nhom:
            errors.append("Không tìm thấy nhóm hợp đồng")

        so_tre_phcn = parse_int(get_excel_value(row, "SoTrePHCN"))
        so_buoi_phcn = parse_int(get_excel_value(row, "SoBuoiPHCN"))
        so_tre_cs = parse_int(get_excel_value(row, "SoTreCS"))
        so_buoi_cs = parse_int(get_excel_value(row, "SoBuoiCS"))
        dm_phcn_code = clean_empty_excel_value(get_excel_value(row, "DMDL_PHCN")) or "1"
        dm_cs_code = clean_empty_excel_value(get_excel_value(row, "DMDL_CS")) or "1"
        dm_phcn = Decimal(str(FinancialConfig.DON_GIA_DI_LAI_DM1 if dm_phcn_code in {"1", "1.0"} else FinancialConfig.DON_GIA_DI_LAI_DM2))
        dm_cs = Decimal(str(FinancialConfig.DON_GIA_DI_LAI_DM1 if dm_cs_code in {"1", "1.0"} else FinancialConfig.DON_GIA_DI_LAI_DM2))
        if so_tre_phcn and not so_buoi_phcn:
            errors.append("Số buổi PHCN phải > 0")
        if so_tre_cs and not so_buoi_cs:
            errors.append("Số buổi CSXH phải > 0")

        preview.append({
            "row_num": row_no,
            "ma_cb": ma_cb or "",
            "ten_cb": can_bo.ho_ten if can_bo else "",
            "can_bo_id": can_bo.pk if can_bo else None,
            "nhom_hd_id": nhom.pk if nhom else None,
            "nhom_hd": nhom.ten_nhom_hd if nhom else (nhom_raw or ""),
            "tham_gia_ct": clean_empty_excel_value(get_excel_value(row, "ThamGiaCt")) not in {"0", "0.0", "không", "khong", "false"},
            "ngay_lap": parse_date(get_excel_value(row, "NgayLap", "Ngày lập"), timezone.localdate()),
            "so_tre_phcn": so_tre_phcn,
            "so_buoi_phcn": so_buoi_phcn,
            "dmdl_phcn_val": dm_phcn,
            "so_tre_cs": so_tre_cs,
            "so_buoi_cs": so_buoi_cs,
            "dmdl_cs_val": dm_cs,
            "gia_tri_du_kien": calculate_expected_value(so_tre_phcn, so_buoi_phcn, dm_phcn, so_tre_cs, so_buoi_cs, dm_cs),
            "is_valid": not errors,
            "error_msg": "; ".join(errors),
        })

    request.session["import_phan_bo_valid_data"] = [x for x in preview if x["is_valid"]]
    return render(request, "quanly/import_phan_bo.html", {
        "preview_data": preview,
        "valid_count": sum(x["is_valid"] for x in preview),
        "invalid_count": sum(not x["is_valid"] for x in preview),
        "has_preview": True,
    })


@admin_required
def confirm_import_phan_bo(request):
    if request.method != "POST":
        return redirect("import_phan_bo")
    items = request.session.pop("import_phan_bo_valid_data", [])
    if not items:
        messages.error(request, "Không có dữ liệu hợp lệ để lưu.")
        return redirect("import_phan_bo")

    records = []
    for item in items:
        records.append(PhanBoChiTieu(
            can_bo_id=item["can_bo_id"],
            nhom_hd_id=item["nhom_hd_id"],
            tham_gia_ct=item["tham_gia_ct"],
            ngay_lap=item["ngay_lap"],
            so_tre_phcn=item["so_tre_phcn"],
            so_buoi_phcn=item["so_buoi_phcn"],
            dinh_muc_di_lai_phcn=item["dmdl_phcn_val"],
            so_tre_cs=item["so_tre_cs"],
            so_buoi_cs=item["so_buoi_cs"],
            dinh_muc_di_lai_cs=item["dmdl_cs_val"],
        ))
    PhanBoChiTieu.objects.bulk_create(records)
    messages.success(request, f"Đã lưu {len(records)} Phân bổ chỉ tiêu.")
    return redirect("danh_sach_phan_bo")


# =========================================================
# ĐỀ XUẤT HỢP ĐỒNG
# =========================================================
def build_proposal_from_allocation(phan_bo):
    assignments = phan_bo.danh_sach_phan_cong.select_related("tre")
    if not assignments.exists():
        raise ValueError("Phân bổ chưa có phân công trẻ; không đủ điều kiện tạo đề xuất hợp đồng.")

    phcn = assignments.filter(loai_dich_vu__in=PhanCongTre.PHCN_SERVICE_CODES)
    cs = assignments.filter(loai_dich_vu__in=PhanCongTre.CS_SERVICE_CODES)
    so_tre_phcn = phcn.values("tre_id").distinct().count()
    so_tre_cs = cs.values("tre_id").distinct().count()
    so_buoi_phcn = sum(item.so_buoi_du_kien for item in phcn)
    so_buoi_cs = sum(item.so_buoi_du_kien for item in cs)
    gia_tri = sum(
        Decimal(item.so_buoi_du_kien)
        * (Decimal(str(FinancialConfig.DON_GIA_CONG)) + Decimal(item.dinh_muc_di_lai))
        for item in assignments
    )
    lan = (phan_bo.de_xuat_hop_dong.order_by("-lan_de_xuat").values_list("lan_de_xuat", flat=True).first() or 0) + 1
    return DeXuatHopDong.objects.create(
        phan_bo=phan_bo,
        lan_de_xuat=lan,
        ngay_de_xuat=timezone.localdate(),
        so_tre_phcn=so_tre_phcn,
        so_buoi_phcn=so_buoi_phcn,
        so_tre_cs=so_tre_cs,
        so_buoi_cs=so_buoi_cs,
        gia_tri_du_kien=gia_tri,
        trang_thai="CHO_KIEM_TRA",
    )


@hopdong_required
def tao_de_xuat_hop_dong(request, pk):
    phan_bo = get_object_or_404(PhanBoChiTieu.objects.select_related("can_bo", "nhom_hd"), pk=pk)
    if request.method == "POST":
        try:
            with transaction.atomic():
                proposal = build_proposal_from_allocation(phan_bo)
                phan_bo.is_locked = True
                phan_bo.save(update_fields=["is_locked", "updated_at"])
            messages.success(request, f"Đã tạo Đề xuất HĐ #{proposal.pk} cho {phan_bo.can_bo.ho_ten}.")
            return redirect("danh_sach_de_xuat")
        except ValueError as exc:
            messages.error(request, str(exc))
    return render(request, "quanly/xac_nhan_tao_de_xuat.html", {"phan_bo": phan_bo})


@hopdong_required
def danh_sach_de_xuat(request):
    query = request.GET.get("q", "").strip()
    qs = DeXuatHopDong.objects.select_related("phan_bo__can_bo", "phan_bo__nhom_hd").order_by("-ngay_de_xuat", "-id")
    if query:
        qs = qs.filter(Q(phan_bo__can_bo__ho_ten__icontains=query) | Q(phan_bo__can_bo__ma_can_bo__icontains=query))
    page_obj = Paginator(qs, 15).get_page(request.GET.get("page"))
    return render(request, "quanly/danh_sach_de_xuat.html", {"page_obj": page_obj, "query": query})


@hopdong_required
def tao_de_xuat_hop_dong(request, pk):
    phan_bo = get_object_or_404(PhanBoChiTieu.objects.select_related("can_bo", "nhom_hd"), pk=pk)
    if request.method == "POST":
        try:
            with transaction.atomic():
                proposal = build_proposal_from_allocation(phan_bo)
                phan_bo.is_locked = True
                phan_bo.save(update_fields=["is_locked", "updated_at"])
            messages.success(request, f"Đã tạo Đề xuất HĐ #{proposal.pk} cho {phan_bo.can_bo.ho_ten}.")
            return redirect("danh_sach_de_xuat")
        except ValueError as exc:
            messages.error(request, str(exc))
    return render(request, "quanly/xac_nhan_tao_de_xuat.html", {"phan_bo": phan_bo})


@hopdong_required
def danh_sach_de_xuat(request):
    query = request.GET.get("q", "").strip()
    qs = DeXuatHopDong.objects.select_related("phan_bo__can_bo", "phan_bo__nhom_hd").order_by("-ngay_de_xuat", "-id")
    if query:
        qs = qs.filter(Q(phan_bo__can_bo__ho_ten__icontains=query) | Q(phan_bo__can_bo__ma_can_bo__icontains=query))
    page_obj = Paginator(qs, 15).get_page(request.GET.get("page"))
    return render(request, "quanly/danh_sach_de_xuat.html", {"page_obj": page_obj, "query": query})


@hopdong_required
def duyet_de_xuat(request, pk):
    proposal = get_object_or_404(DeXuatHopDong, pk=pk)
    if request.method == "POST":
        if not proposal.phan_bo.danh_sach_phan_cong.exists():
            messages.error(request, "Đề xuất chưa có phân công trẻ nên chưa thể duyệt.")
            return redirect("danh_sach_de_xuat")
        proposal.trang_thai = "DA_DUYET"
        proposal.save(update_fields=["trang_thai", "updated_at"])
        messages.success(request, "Đã duyệt đề xuất hợp đồng.")
    return redirect("danh_sach_de_xuat")


@hopdong_required
def tao_hop_dong_chinh_thuc(request, pk):
    proposal = get_object_or_404(DeXuatHopDong.objects.select_related("phan_bo__can_bo", "phan_bo__nhom_hd"), pk=pk)
    if request.method == "POST":
        form = HopDongForm(request.POST)
        if form.is_valid():
            try:
                hop_dong = create_contract_from_proposal(proposal, form.cleaned_data)
            except ValidationError as exc:
                form.add_error(None, exc)
            else:
                messages.success(request, f"Đã tạo Hợp đồng {hop_dong.so_hop_dong} và Phụ lục Kỳ 1.")
                return redirect("danh_sach_hop_dong")
    else:
        form = HopDongForm(initial={
            "de_xuat": proposal,
            "can_bo": proposal.phan_bo.can_bo,
            "nhom_hd": proposal.phan_bo.nhom_hd,
            "don_gia_cong": FinancialConfig.DON_GIA_CONG,
            "dinh_muc_di_lai_phcn": proposal.phan_bo.dinh_muc_di_lai_phcn,
            "dinh_muc_di_lai_cs": proposal.phan_bo.dinh_muc_di_lai_cs,
            "gia_tri_hop_dong": proposal.gia_tri_du_kien,
            "trang_thai": "DU_THAO",
        })
    return render(request, "quanly/tao_hop_dong_chinh_thuc.html", {"form": form, "proposal": proposal})


@hopdong_required
def danh_sach_hop_dong(request):
    query = request.GET.get("q", "").strip()
    qs = HopDong.objects.select_related("can_bo", "nhom_hd", "de_xuat").order_by("-ngay_ky", "-id")
    if query:
        qs = qs.filter(Q(so_hop_dong__icontains=query) | Q(can_bo__ma_can_bo__icontains=query) | Q(can_bo__ho_ten__icontains=query))
    page_obj = Paginator(qs, 15).get_page(request.GET.get("page"))
    return render(request, "quanly/danh_sach_hop_dong.html", {"hop_dongs": page_obj, "page_obj": page_obj, "query": query})


@admin_required
def import_hop_dong(request):
    if request.method != "POST" or not request.FILES.get("file_excel"):
        return render(request, "quanly/import_hop_dong.html")
    try:
        df = normalized_columns(pd.read_excel(request.FILES["file_excel"]))
    except Exception as exc:
        messages.error(request, f"Không đọc được file Excel: {exc}")
        return render(request, "quanly/import_hop_dong.html")
    created = updated = skipped = 0
    errors = []
    for row_no, (_, row) in enumerate(df.iterrows(), start=2):
        try:
            ma_cb = clean_empty_excel_value(get_excel_value(row, "MaCbct", "MaCBCT", "Mã CBCT"))
            so_hd = clean_empty_excel_value(get_excel_value(row, "SoHopDong", "Số Hợp đồng", "Số HĐ"))
            if not ma_cb or not so_hd:
                skipped += 1
                continue
            can_bo = get_object_or_404(CanBo, ma_can_bo=ma_cb)
            nhom_value = clean_empty_excel_value(get_excel_value(row, "NhomHD", "Nhóm HĐ"))
            nhom_hd = NhomHD.objects.filter(pk=int(float(nhom_value))).first() if nhom_value and str(nhom_value).isdigit() else NhomHD.objects.filter(Q(ma_nhom_hd=nhom_value) | Q(ten_nhom_hd__iexact=nhom_value)).first()
            if not nhom_hd:
                raise ValueError(f"Không tìm thấy Nhóm hợp đồng '{nhom_value}'")
            phan_bo = PhanBoChiTieu.objects.filter(can_bo=can_bo, nhom_hd=nhom_hd).order_by("-ngay_lap", "-id").first()
            if not phan_bo:
                raise ValueError("Không tìm thấy phân bổ tương ứng để liên kết hợp đồng")
            proposal = phan_bo.de_xuat_hop_dong.order_by("-lan_de_xuat", "-id").first()
            if not proposal:
                proposal = DeXuatHopDong.objects.create(phan_bo=phan_bo, so_tre_phcn=phan_bo.so_tre_phcn, so_buoi_phcn=phan_bo.so_buoi_phcn, so_tre_cs=phan_bo.so_tre_cs, so_buoi_cs=phan_bo.so_buoi_cs, gia_tri_du_kien=phan_bo.gia_tri_du_kien, trang_thai="DA_DUYET")
            defaults = {"de_xuat": proposal, "can_bo": can_bo, "nhom_hd": nhom_hd, "ngay_ky": parse_date(get_excel_value(row, "NgayKy", "Ngày ký")), "tu_ngay": parse_date(get_excel_value(row, "TuNgay", "Từ ngày")), "den_ngay": parse_date(get_excel_value(row, "DenNgay", "Đến ngày")), "don_gia_cong": FinancialConfig.DON_GIA_CONG, "dinh_muc_di_lai_phcn": phan_bo.dinh_muc_di_lai_phcn, "dinh_muc_di_lai_cs": phan_bo.dinh_muc_di_lai_cs, "gia_tri_hop_dong": proposal.gia_tri_du_kien, "trang_thai": "DA_KY"}
            _, is_created = HopDong.objects.update_or_create(so_hop_dong=so_hd, defaults=defaults)
            created += int(is_created)
            updated += int(not is_created)
        except Exception as exc:
            skipped += 1
            errors.append(f"Dòng {row_no}: {exc}")
    msg = f"Import hợp đồng hoàn tất: thêm {created}, cập nhật {updated}, bỏ qua {skipped}."
    if errors:
        msg += " " + " | ".join(errors[:5])
    messages.success(request, msg)
    return redirect("danh_sach_hop_dong")


@hopdong_required
def chi_tiet_hop_dong(request, pk):
    hop_dong = get_object_or_404(HopDong.objects.select_related("can_bo", "nhom_hd", "de_xuat"), pk=pk)
    khoi_luong = hop_dong.chi_tiet_khoi_luong.all().order_by("loai_dich_vu")
    phu_luc = hop_dong.phu_luc.all().prefetch_related("chi_tiet_phan_cong").order_by("-ngay_lap", "-id")
    ky_choices = (
        PhanCongTre.objects.filter(phan_bo=hop_dong.de_xuat.phan_bo, ky_phan_cong__gte=2)
        .values_list("ky_phan_cong", flat=True)
        .distinct()
        .order_by("ky_phan_cong")
    )
    nhat_ky = hop_dong.nhat_ky_thuc_hien.select_related("phan_cong__tre").order_by("-ngay_thuc_hien", "-id")
    dot_thanh_toan = hop_dong.dot_thanh_toan.prefetch_related("chi_tiet").order_by("-nam", "-thang", "-id")
    return render(
        request,
        "quanly/chi_tiet_hop_dong.html",
        {
            "hop_dong": hop_dong,
            "khoi_luong": khoi_luong,
            "phu_luc": phu_luc,
            "ky_choices": ky_choices,
            "nhat_ky": nhat_ky,
            "dot_thanh_toan": dot_thanh_toan,
        },
    )


@hopdong_required
def xuat_bo_hop_dong(request, pk):
    hop_dong = get_object_or_404(
        HopDong.objects.select_related("can_bo", "de_xuat__phan_bo"),
        pk=pk,
    )
    try:
        output = export_contract_bundle(hop_dong)
    except ValidationError as exc:
        messages.error(request, str(exc))
        return redirect("chi_tiet_hop_dong", pk=hop_dong.pk)

    response = HttpResponse(
        output.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    safe_number = re.sub(r"[^A-Za-z0-9._-]+", "_", hop_dong.so_hop_dong)
    response["Content-Disposition"] = f'attachment; filename="HopDong_{safe_number}.docx"'
    return response


@hopdong_required
def xuat_phu_luc_phan_cong(request, pk):
    hop_dong = get_object_or_404(
        HopDong.objects.select_related("can_bo", "de_xuat__phan_bo"),
        pk=pk,
    )
    try:
        ky = int(request.GET.get("ky", "0"))
        output = export_assignment_annex(hop_dong, ky)
    except (TypeError, ValueError):
        messages.error(request, "Kỳ phân công không hợp lệ.")
        return redirect("chi_tiet_hop_dong", pk=hop_dong.pk)
    except ValidationError as exc:
        messages.error(request, str(exc))
        return redirect("chi_tiet_hop_dong", pk=hop_dong.pk)

    safe_number = re.sub(r"[^A-Za-z0-9._-]+", "_", hop_dong.so_hop_dong)
    response = HttpResponse(
        output.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    response["Content-Disposition"] = f'attachment; filename="PhuLuc_{safe_number}_Ky{ky}.docx"'
    return response


@hopdong_required
def them_nhat_ky_thuc_hien(request, hop_dong_id):
    hop_dong = get_object_or_404(
        HopDong.objects.select_related("de_xuat__phan_bo"),
        pk=hop_dong_id,
    )
    form = NhatKyThucHienForm(request.POST or None, hop_dong=hop_dong)
    if request.method == "POST" and form.is_valid():
        item = form.save(commit=False)
        item.hop_dong = hop_dong
        item.don_gia_cong = FinancialConfig.DON_GIA_CONG
        is_cs = PhanCongTre.service_group(item.phan_cong.loai_dich_vu) == "CS"
        allocation = hop_dong.de_xuat.phan_bo
        item.dinh_muc_di_lai = allocation.dinh_muc_di_lai_cs if is_cs else allocation.dinh_muc_di_lai_phcn
        item.save()
        messages.success(request, "Đã ghi nhận nhật ký thực hiện.")
        return redirect("chi_tiet_hop_dong", pk=hop_dong.pk)
    return render(request, "quanly/them_nhat_ky_thuc_hien.html", {"form": form, "hop_dong": hop_dong})


@hopdong_required
def them_nhat_ky_can_thiep(request):
    form = NhatKyCanThiepForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        item = form.save(commit=False)
        item.don_gia_cong = FinancialConfig.DON_GIA_CONG
        item.dinh_muc_di_lai = item.hop_dong.dinh_muc_di_lai_cs if PhanCongTre.service_group(item.phan_cong.loai_dich_vu) == "CS" else item.hop_dong.dinh_muc_di_lai_phcn
        item.save()
        messages.success(request, "Đã thêm nhật ký và lưu vào cơ sở dữ liệu.")
        return redirect("nhat_ky_can_thiep")
    return render(request, "quanly/them_nhat_ky_can_thiep.html", {"form": form})


@hopdong_required
def tao_dot_thanh_toan(request, hop_dong_id):
    hop_dong = get_object_or_404(HopDong, pk=hop_dong_id)
    form = DotThanhToanForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        item = form.save(commit=False)
        item.hop_dong = hop_dong
        item.save()
        messages.success(request, "Đã tạo đợt thanh toán.")
        return redirect("chi_tiet_dot_thanh_toan", pk=item.pk)
    return render(request, "quanly/tao_dot_thanh_toan.html", {"form": form, "hop_dong": hop_dong})


@hopdong_required
def chi_tiet_dot_thanh_toan(request, pk):
    dot = get_object_or_404(
        DotThanhToan.objects.select_related("hop_dong").prefetch_related("chi_tiet__nhat_ky__phan_cong__tre"),
        pk=pk,
    )
    return render(request, "quanly/chi_tiet_dot_thanh_toan.html", {"dot": dot})


@hopdong_required
def xuat_de_nghi_thanh_toan(request, pk):
    dot = get_object_or_404(DotThanhToan.objects.select_related("hop_dong"), pk=pk)
    try:
        output = export_intervention_payment_request(dot)
    except ValidationError as exc:
        messages.error(request, str(exc))
        return redirect("chi_tiet_dot_thanh_toan", pk=dot.pk)
    response = HttpResponse(
        output.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    safe_number = re.sub(r"[^A-Za-z0-9._-]+", "_", dot.hop_dong.so_hop_dong)
    response["Content-Disposition"] = f'attachment; filename="DNTT_{safe_number}_{dot.thang}_{dot.nam}.xlsx"'
    return response


@hopdong_required
def xuat_danh_sach_tai_khoan(request, pk):
    dot = get_object_or_404(DotThanhToan.objects.select_related("hop_dong__can_bo"), pk=pk)
    try:
        output = export_intervention_account_list(dot)
    except ValidationError as exc:
        messages.error(request, str(exc))
        return redirect("chi_tiet_dot_thanh_toan", pk=dot.pk)
    response = HttpResponse(
        output.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    safe_number = re.sub(r"[^A-Za-z0-9._-]+", "_", dot.hop_dong.so_hop_dong)
    response["Content-Disposition"] = f'attachment; filename="DSTK_{safe_number}_{dot.thang}_{dot.nam}.xlsx"'
    return response


@hopdong_required
def cap_nhat_nghiem_thu(request, hop_dong_id):
    hop_dong = get_object_or_404(HopDong.objects.select_related("de_xuat__phan_bo"), pk=hop_dong_id)
    record, _ = NghiemThu.objects.get_or_create(hop_dong=hop_dong)
    if request.method == "POST":
        form = NghiemThuForm(request.POST, instance=record)
        if form.is_valid():
            obj = form.save(commit=False)
            paid_total = ChiTietThanhToan.objects.filter(nhat_ky__hop_dong=hop_dong).aggregate(total=Sum("thanh_tien"))["total"]
            obj.gia_tri_nghiem_thu = paid_total or hop_dong.gia_tri_hop_dong
            obj.save()
            messages.success(request, "Đã lưu thông tin nghiệm thu.")
            return redirect("chi_tiet_hop_dong", pk=hop_dong.pk)
    else:
        form = NghiemThuForm(instance=record)
    return render(request, "quanly/cap_nhat_nghiem_thu.html", {"form": form, "hop_dong": hop_dong, "record": record})


@hopdong_required
def cap_nhat_thanh_ly(request, hop_dong_id):
    hop_dong = get_object_or_404(HopDong.objects.select_related("de_xuat__phan_bo"), pk=hop_dong_id)
    if not hasattr(hop_dong, "nghiem_thu"):
        messages.error(request, "Chỉ được thanh lý sau khi đã lập biên bản nghiệm thu.")
        return redirect("chi_tiet_hop_dong", pk=hop_dong.pk)
    record, _ = ThanhLyHopDong.objects.get_or_create(hop_dong=hop_dong, defaults={"gia_tri_thanh_ly": hop_dong.nghiem_thu.gia_tri_nghiem_thu})
    if request.method == "POST":
        form = ThanhLyHopDongForm(request.POST, instance=record)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.gia_tri_thanh_ly = hop_dong.nghiem_thu.gia_tri_nghiem_thu
            obj.save()
            messages.success(request, "Đã lưu thông tin thanh lý hợp đồng.")
            return redirect("chi_tiet_hop_dong", pk=hop_dong.pk)
    else:
        form = ThanhLyHopDongForm(instance=record)
    return render(request, "quanly/cap_nhat_thanh_ly.html", {"form": form, "hop_dong": hop_dong, "record": record})


def _document_response(output, filename):
    response = HttpResponse(output.getvalue(), content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@hopdong_required
def xuat_bien_ban_nghiem_thu(request, pk):
    hop_dong = get_object_or_404(HopDong.objects.select_related("can_bo", "de_xuat__phan_bo"), pk=pk)
    try:
        record = hop_dong.nghiem_thu
        return _document_response(export_acceptance_record(hop_dong, record), f"BBNT_{hop_dong.so_hop_dong}.docx")
    except (NghiemThu.DoesNotExist, ValidationError) as exc:
        messages.error(request, "Chưa có hồ sơ nghiệm thu hợp lệ để xuất.")
        return redirect("chi_tiet_hop_dong", pk=hop_dong.pk)


@hopdong_required
def xuat_bien_ban_thanh_ly(request, pk):
    hop_dong = get_object_or_404(HopDong.objects.select_related("can_bo", "de_xuat__phan_bo"), pk=pk)
    try:
        record = hop_dong.thanh_ly
        return _document_response(export_liquidation_record(hop_dong, record), f"TLHD_{hop_dong.so_hop_dong}.docx")
    except (ThanhLyHopDong.DoesNotExist, ValidationError) as exc:
        messages.error(request, "Chưa có hồ sơ thanh lý hợp lệ để xuất.")
        return redirect("chi_tiet_hop_dong", pk=hop_dong.pk)


@hopdong_required
def tao_dot_thanh_toan_phu_huynh(request, hop_dong_id):
    hop_dong = get_object_or_404(HopDong, pk=hop_dong_id)
    if request.method == "POST":
        form = DotThanhToanDiLaiPhuHuynhForm(request.POST)
        if form.is_valid():
            dot = form.save(commit=False)
            dot.hop_dong = hop_dong
            try:
                dot.save()
            except Exception as exc:
                form.add_error(None, "Đợt thanh toán tháng/năm này đã tồn tại.")
            else:
                messages.success(request, "Đã tạo đợt thanh toán đi lại phụ huynh.")
                return redirect("chi_tiet_dot_thanh_toan_phu_huynh", pk=dot.pk)
    else:
        form = DotThanhToanDiLaiPhuHuynhForm(initial={"nam": timezone.localdate().year, "thang": timezone.localdate().month})
    return render(request, "quanly/tao_dot_thanh_toan_phu_huynh.html", {"form": form, "hop_dong": hop_dong})


@hopdong_required
def chi_tiet_dot_thanh_toan_phu_huynh(request, pk):
    dot = get_object_or_404(DotThanhToanDiLaiPhuHuynh.objects.select_related("hop_dong"), pk=pk)
    chi_tiet = dot.chi_tiet.select_related("nhat_ky__phan_cong__tre")
    return render(request, "quanly/chi_tiet_dot_thanh_toan_phu_huynh.html", {"dot": dot, "chi_tiet": chi_tiet})


@hopdong_required
def them_chi_tiet_thanh_toan_phu_huynh(request, dot_id):
    dot = get_object_or_404(DotThanhToanDiLaiPhuHuynh.objects.select_related("hop_dong"), pk=dot_id)
    if request.method == "POST":
        form = ChiTietThanhToanDiLaiPhuHuynhForm(request.POST, hop_dong=dot.hop_dong)
        if form.is_valid():
            item = form.save(commit=False)
            item.dot_thanh_toan = dot
            item.dinh_muc_di_lai = item.nhat_ky.dinh_muc_di_lai
            try:
                item.save()
            except ValidationError as exc:
                form.add_error(None, str(exc))
            else:
                messages.success(request, "Đã thêm chi tiết thanh toán đi lại phụ huynh.")
                return redirect("chi_tiet_dot_thanh_toan_phu_huynh", pk=dot.pk)
    else:
        form = ChiTietThanhToanDiLaiPhuHuynhForm(hop_dong=dot.hop_dong)
    return render(request, "quanly/them_chi_tiet_thanh_toan_phu_huynh.html", {"form": form, "dot": dot})


def _export_parent_travel(request, pk, category, account_list=False):
    dot = get_object_or_404(DotThanhToanDiLaiPhuHuynh.objects.select_related("hop_dong"), pk=pk)
    try:
        output = (export_parent_travel_account_list if account_list else export_parent_travel_payment_request)(dot, category)
    except ValidationError as exc:
        messages.error(request, str(exc))
        return redirect("chi_tiet_dot_thanh_toan_phu_huynh", pk=dot.pk)
    kind = "DSTK" if account_list else "DNTT"
    response = HttpResponse(output.getvalue(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response["Content-Disposition"] = f'attachment; filename="{kind}_DiLai_PH_{category}_{dot.thang}_{dot.nam}.xlsx"'
    return response


@hopdong_required
def xuat_dntt_di_lai_phu_huynh(request, pk):
    return _export_parent_travel(request, pk, request.GET.get("nhom", "NCS"))


@hopdong_required
def xuat_dstk_di_lai_phu_huynh(request, pk):
    return _export_parent_travel(request, pk, request.GET.get("nhom", "NCS"), account_list=True)


@readonly_required
def nhat_ky_can_thiep(request):
    query = request.GET.get("q", "").strip()
    cb_id = request.GET.get("can_bo", "").strip()
    nhom_id = request.GET.get("nhom_hd", "").strip()
    ky = request.GET.get("ky", "").strip()
    thang = request.GET.get("thang", "").strip()
    nam = request.GET.get("nam", "").strip()
    qs = NhatKyThucHien.objects.select_related("hop_dong__can_bo", "hop_dong__nhom_hd", "phan_cong__tre").order_by("-ngay_thuc_hien", "-id")
    if query:
        qs = qs.filter(Q(phan_cong__tre__ma_tre__icontains=query) | Q(phan_cong__tre__ho_ten__icontains=query) | Q(hop_dong__so_hop_dong__icontains=query) | Q(hop_dong__can_bo__ho_ten__icontains=query))
    if cb_id.isdigit(): qs = qs.filter(hop_dong__can_bo_id=int(cb_id))
    if nhom_id.isdigit(): qs = qs.filter(hop_dong__nhom_hd_id=int(nhom_id))
    if ky.isdigit(): qs = qs.filter(phan_cong__ky_phan_cong=int(ky))
    if thang.isdigit(): qs = qs.filter(ngay_thuc_hien__month=int(thang))
    if nam.isdigit(): qs = qs.filter(ngay_thuc_hien__year=int(nam))
    page_obj = Paginator(qs, 25).get_page(request.GET.get("page"))
    return render(request, "quanly/nhat_ky_can_thiep.html", {"page_obj": page_obj, "danh_sach": page_obj, "query": query, "tong_so": qs.count(), "can_bo_list": CanBo.objects.filter(is_active=True), "nhom_list": NhomHD.objects.filter(is_active=True), "filters": {"can_bo": cb_id, "nhom_hd": nhom_id, "ky": ky, "thang": thang, "nam": nam}})


@readonly_required
def thanh_quyet_toan(request):
    """Tổng hợp và lập hồ sơ thanh toán theo Nhóm HĐ + Kỳ can thiệp."""
    qs, ky, thang, nam = _journal_export_queryset(request)
    query = request.GET.get("q", "").strip()
    if query:
        qs = qs.filter(
            Q(phan_cong__tre__ma_tre__icontains=query)
            | Q(phan_cong__tre__ho_ten__icontains=query)
            | Q(hop_dong__so_hop_dong__icontains=query)
            | Q(hop_dong__can_bo__ho_ten__icontains=query)
        )
    rows = {}
    for journal in qs:
        key = (journal.hop_dong.nhom_hd_id, journal.phan_cong.ky_phan_cong)
        item = rows.setdefault(key, {
            "nhom": journal.hop_dong.nhom_hd,
            "ky": journal.phan_cong.ky_phan_cong,
            "hop_dong_count": set(),
            "can_bo_count": set(),
            "journal_count": 0,
            "so_buoi": Decimal("0"),
            "di_lai": Decimal("0"),
            "tien_cong": Decimal("0"),
            "tien_di_lai": Decimal("0"),
        })
        item["hop_dong_count"].add(journal.hop_dong_id)
        item["can_bo_count"].add(journal.hop_dong.can_bo_id)
        item["journal_count"] += 1
        item["so_buoi"] += Decimal(journal.so_buoi_thuc_hien)
        item["di_lai"] += Decimal(journal.so_luot_di_lai)
        item["tien_cong"] += Decimal(journal.so_buoi_thuc_hien) * Decimal(journal.don_gia_cong)
        item["tien_di_lai"] += Decimal(journal.so_luot_di_lai) * Decimal(journal.dinh_muc_di_lai)
    for item in rows.values():
        breakdown = calculate_payment_breakdown(item["tien_cong"], item["tien_di_lai"])
        item["hop_dong_count"] = len(item["hop_dong_count"])
        item["can_bo_count"] = len(item["can_bo_count"])
        item.update(breakdown)
    danh_sach = sorted(rows.values(), key=lambda item: (item["nhom"].ma_nhom_hd, item["ky"]))
    return render(request, "quanly/thanh_quyet_toan.html", {
        "danh_sach": danh_sach,
        "query": query,
        "can_bo_list": CanBo.objects.filter(is_active=True),
        "nhom_list": NhomHD.objects.filter(is_active=True),
        "filters": {"can_bo": request.GET.get("can_bo", ""), "nhom_hd": request.GET.get("nhom_hd", ""), "ky": ky, "thang": thang, "nam": nam},
    })


def _journal_export_queryset(request):
    qs = NhatKyThucHien.objects.select_related("hop_dong__can_bo__don_vi", "hop_dong__nhom_hd", "phan_cong__tre").order_by("ngay_thuc_hien", "id")
    cb_id, nhom_id, ky, thang, nam = (request.GET.get(key, "").strip() for key in ("can_bo", "nhom_hd", "ky", "thang", "nam"))
    if cb_id.isdigit(): qs = qs.filter(hop_dong__can_bo_id=int(cb_id))
    if nhom_id.isdigit(): qs = qs.filter(hop_dong__nhom_hd_id=int(nhom_id))
    if ky.isdigit(): qs = qs.filter(phan_cong__ky_phan_cong=int(ky))
    if thang.isdigit(): qs = qs.filter(ngay_thuc_hien__month=int(thang))
    if nam.isdigit(): qs = qs.filter(ngay_thuc_hien__year=int(nam))
    return qs, ky, thang, nam


@readonly_required
def xuat_dntt_nhat_ky(request):
    qs, ky, thang, nam = _journal_export_queryset(request)
    try: output = export_journal_payment_request(qs, ky=ky, thang=thang, nam=nam)
    except ValidationError as exc:
        messages.error(request, str(exc)); return redirect("nhat_ky_can_thiep")
    return _document_response(output, f"DNTT_NhatKy_{ky or 'tat-ca'}_{thang or 'tat-ca'}_{nam or 'tat-ca'}.docx")


@readonly_required
def xuat_dntt_excel_nhat_ky(request):
    qs, _, _, _ = _journal_export_queryset(request)
    try:
        output = export_journal_payment_request_excel(qs)
    except ValidationError as exc:
        messages.error(request, str(exc))
        return redirect("nhat_ky_can_thiep")
    response = HttpResponse(output.getvalue(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response["Content-Disposition"] = 'attachment; filename="DNTT_NhatKy.xlsx"'
    return response


@readonly_required
def xuat_dstk_nhat_ky(request):
    qs, _, _, _ = _journal_export_queryset(request)
    try: output = export_journal_account_list(qs)
    except ValidationError as exc:
        messages.error(request, str(exc)); return redirect("nhat_ky_can_thiep")
    response = HttpResponse(output.getvalue(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response["Content-Disposition"] = 'attachment; filename="DSTK_NhatKy.xlsx"'
    return response


@readonly_required
def xuat_dnck_nhat_ky(request):
    qs, _, thang, nam = _journal_export_queryset(request)
    try: output = export_journal_commitment(qs, tu_ngay=f"01/{thang}/{nam}" if thang and nam else "", den_ngay="")
    except ValidationError as exc:
        messages.error(request, str(exc)); return redirect("nhat_ky_can_thiep")
    response = HttpResponse(output.getvalue(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response["Content-Disposition"] = 'attachment; filename="DNCK_NhatKy.xlsx"'
    return response


@hopdong_required
def them_chi_tiet_thanh_toan(request, dot_id):
    dot = get_object_or_404(DotThanhToan.objects.select_related("hop_dong"), pk=dot_id)
    form = ChiTietThanhToanForm(request.POST or None, hop_dong=dot.hop_dong)
    if request.method == "POST" and form.is_valid():
        item = form.save(commit=False)
        item.dot_thanh_toan = dot
        item.save()
        messages.success(request, "Đã thêm chi tiết thanh toán.")
        return redirect("chi_tiet_dot_thanh_toan", pk=dot.pk)
    return render(request, "quanly/them_chi_tiet_thanh_toan.html", {"form": form, "dot": dot})


@hopdong_required
def them_khoi_luong_hop_dong(request, hop_dong_id):
    hop_dong = get_object_or_404(HopDong, pk=hop_dong_id)
    if hop_dong.is_locked:
        messages.error(request, "Hợp đồng đã khóa, không thể sửa khối lượng.")
        return redirect("chi_tiet_hop_dong", pk=hop_dong.pk)
    form = ChiTietKhoiLuongHopDongForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        item = form.save(commit=False)
        item.hop_dong = hop_dong
        item.save()
        messages.success(request, "Đã thêm chi tiết khối lượng hợp đồng.")
        return redirect("chi_tiet_hop_dong", pk=hop_dong.pk)
    return render(request, "quanly/them_khoi_luong_hop_dong.html", {"form": form, "hop_dong": hop_dong})


@hopdong_required
def them_phu_luc_hop_dong(request, hop_dong_id):
    hop_dong = get_object_or_404(HopDong, pk=hop_dong_id)
    if hop_dong.is_locked:
        messages.error(request, "Hợp đồng đã khóa, không thể thêm phụ lục.")
        return redirect("chi_tiet_hop_dong", pk=hop_dong.pk)
    form = PhuLucHopDongForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        item = form.save(commit=False)
        item.hop_dong = hop_dong
        item.save()
        messages.success(request, "Đã thêm phụ lục hợp đồng.")
        return redirect("chi_tiet_hop_dong", pk=hop_dong.pk)
    return render(request, "quanly/them_phu_luc_hop_dong.html", {"form": form, "hop_dong": hop_dong})
