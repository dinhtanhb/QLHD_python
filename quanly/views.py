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
from .document_export import create_contract_from_proposal, export_assignment_annex, export_contract_bundle
from .financial import FinancialConfig
from .forms import (
    CanBoForm,
    ChiTietKhoiLuongHopDongForm,
    DeXuatHopDongForm,
    DonViForm,
    HopDongForm,
    NhomHDForm,
    PhanBoChiTieuForm,
    PhanCongTreForm,
    PhuLucHopDongForm,
    TreForm,
)
from .models import (
    CanBo,
    ChiTietKhoiLuongHopDong,
    ChiTietPhuLucPhanCong,
    DeXuatHopDong,
    DonVi,
    HopDong,
    NhomHD,
    PhanBoChiTieu,
    PhanCongTre,
    PhuLucHopDong,
    Tre,
    Tinh,
    Xa,
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
                return redirect("chi_tiet_hop_dong", pk=hop_dong.pk)
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
    qs = HopDong.objects.select_related("can_bo", "nhom_hd", "de_xuat").order_by("-ngay_ky", "-id")
    return render(request, "quanly/danh_sach_hop_dong.html", {"danh_sach": qs})


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
    return render(
        request,
        "quanly/chi_tiet_hop_dong.html",
        {"hop_dong": hop_dong, "khoi_luong": khoi_luong, "phu_luc": phu_luc, "ky_choices": ky_choices},
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
