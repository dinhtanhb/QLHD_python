from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from io import BytesIO
import re
import unicodedata
import zipfile
from urllib.parse import quote

import pandas as pd
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.db.models import Count, Exists, F, IntegerField, Max, Min, OuterRef, Q, Sum
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from .decorators import accountant_required, admin_required, dashboard_required, hopdong_required, readonly_required
from .permissions import is_admin_user
from .document_export import (
    create_contract_from_proposal,
    export_acceptance_record,
    export_assignment_annex,
    export_contract_bundle,
    export_extension_annex,
    export_journal_payment_request,
    export_liquidation_record,
)
from .payment_export import (
    export_intervention_account_list,
    export_intervention_payment_request,
    export_journal_account_list,
    export_journal_commitment,
    export_journal_payment_request_excel,
    export_parent_travel_account_list,
    export_parent_travel_commitment,
    export_parent_travel_payment_request,
    normalize_parent_travel_category,
    parent_travel_category,
)
from .financial import FinancialConfig, calculate_payment_breakdown, normalize_travel_location
from .parsing import parse_decimal as parse_decimal_legacy
from .services.contract_status import sync_trang_thai_hop_dong, validate_status_transition
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
    DotThanhToanDiLaiPhuHuynhDateForm,
    DotThanhToanDiLaiPhuHuynhTheoNhomForm,
    ChiTietThanhToanDiLaiPhuHuynhForm,
    GiaHanKhoiLuongForm,
    GiaHanThoiGianForm,
    _current_contract_end,
)
from .models import (
    CanBo,
    ChiTietThanhToan,
    ChiTietKhoiLuongHopDong,
    ChiTietPhuLucPhanCong,
    ChiTietGiaHanKhoiLuong,
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
    DotThanhToan,
    ThanhLyHopDong,
    DotThanhToanDiLaiPhuHuynh,
    ChiTietThanhToanDiLaiPhuHuynh,
    ChiTietPhieuThanhToan,
    PhieuThanhToan,
)
from .services.payment_ledger import huy_phieu as huy_phieu_thanh_toan, tao_phieu_thanh_toan as tao_phieu_thanh_toan_service, xac_nhan_chi


def _is_operationally_locked(hop_dong):
    """Hợp đồng đã khóa hoặc đã thanh lý thì không cho tài khoản thường phát sinh dữ liệu."""
    return bool(hop_dong and (hop_dong.is_locked or hop_dong.trang_thai == "THANH_LY"))


def _hop_dong_has_financial_records(hop_dong):
    return any(
        (
            NghiemThu.objects.filter(hop_dong=hop_dong).exists(),
            ThanhLyHopDong.objects.filter(hop_dong=hop_dong).exists(),
            DotThanhToan.objects.filter(hop_dong=hop_dong).exists(),
            DotThanhToanDiLaiPhuHuynh.objects.filter(hop_dong=hop_dong).exists(),
            ChiTietThanhToanDiLaiPhuHuynh.objects.filter(nhat_ky__hop_dong=hop_dong).exists(),
        )
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
    return parse_decimal_legacy(value, default)


def parse_date(value, default=None):
    value = clean_empty_excel_value(value)
    if value is None:
        return default
    try:
        return pd.to_datetime(value, errors="raise").date()
    except (ValueError, TypeError):
        return default


def parse_time(value, default=None):
    value = clean_empty_excel_value(value)
    if value is None:
        return default
    try:
        parsed = pd.to_datetime(value, errors="raise")
        return parsed.time()
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


def resolve_contract_group(value):
    """Ưu tiên mã nhóm nghiệp vụ; chỉ dùng khóa chính để tương thích dữ liệu cũ."""
    normalized = clean_empty_excel_value(value)
    if not normalized:
        return None
    group = NhomHD.objects.filter(
        Q(ma_nhom_hd__iexact=normalized) | Q(ten_nhom_hd__iexact=normalized)
    ).first()
    if group:
        return group
    if normalized.isdigit():
        return NhomHD.objects.filter(pk=int(normalized)).first()
    return None


def safe_download_component(value):
    """Giữ tên dễ đọc nhưng loại ký tự không hợp lệ trong tên file Windows."""
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", str(value or ""))
    value = re.sub(r"\s+", " ", value).strip(" .")
    return value or "Khong_ro"


def content_disposition_filename(filename):
    """Trả cả tên ASCII dự phòng và tên UTF-8 để trình duyệt giữ đúng tiếng Việt."""
    ascii_name = unicodedata.normalize("NFKD", filename.replace("Đ", "D").replace("đ", "d"))
    ascii_name = "".join(char for char in ascii_name if not unicodedata.combining(char))
    ascii_name = ascii_name.encode("ascii", "ignore").decode("ascii") or "download"
    return f'attachment; filename="{ascii_name}"; filename*=UTF-8\'\'{quote(filename)}'


def normalized_reference_keys(value, prefixes=()):
    """Sinh các khóa tra cứu không phân biệt hoa/thường, dấu và tiền tố hành chính."""
    value = clean_empty_excel_value(value)
    if value is None:
        return set()

    text = unicodedata.normalize("NFKD", value.casefold().replace("đ", "d"))
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = re.sub(r"[^a-z0-9]+", " ", text).strip()
    keys = {text} if text else set()
    for prefix in prefixes:
        normalized_prefix = unicodedata.normalize("NFKD", prefix.casefold().replace("đ", "d"))
        normalized_prefix = "".join(char for char in normalized_prefix if not unicodedata.combining(char))
        normalized_prefix = re.sub(r"[^a-z0-9]+", " ", normalized_prefix).strip()
        if text.startswith(normalized_prefix + " "):
            keys.add(text[len(normalized_prefix):].strip())
    return {key for key in keys if key}


def add_unique_reference(lookup, key, obj):
    """Chỉ giữ khóa duy nhất; khóa trùng được đánh dấu để không chọn nhầm danh mục."""
    if key not in lookup:
        lookup[key] = obj
    elif lookup[key] is None or lookup[key].pk != obj.pk:
        lookup[key] = None


def resolve_reference(value, lookup, label, prefixes=()):
    for key in normalized_reference_keys(value, prefixes):
        obj = lookup.get(key)
        if obj is not None:
            return obj
    raise ValueError(f"Không tìm thấy {label} '{clean_empty_excel_value(value)}' trong danh mục")


def take_import_occurrence(identity_cache, occurrence_counts, key, loader):
    """Ghép dòng Excel thứ N với bản ghi thứ N của cùng khóa nghiệp vụ."""
    if key not in identity_cache:
        identity_cache[key] = list(loader())
    occurrence = occurrence_counts.get(key, 0)
    occurrence_counts[key] = occurrence + 1
    existing_items = identity_cache[key]
    identity = existing_items[occurrence] if occurrence < len(existing_items) else None
    return identity, existing_items


def journal_import_identity_key(can_bo_id, tre_id, service, group_id, period, intervention_date, start, end, location):
    """Khóa đầy đủ của một dòng nhật ký; kỳ và dịch vụ không được phép ghi đè lẫn nhau."""
    return (
        can_bo_id,
        tre_id,
        service,
        group_id,
        period,
        intervention_date,
        start,
        end,
        normalize_travel_location(location),
    )


def normalize_service_code(value):
    """Chuẩn hóa mã/tên dịch vụ, gồm cả biến thể GDĐB và GDDB."""
    aliases = {
        "vltl": "VLTL",
        "vat ly tri lieu": "VLTL",
        "hdtl": "HDTL",
        "hoat dong tri lieu": "HDTL",
        "nntl": "NNTL",
        "ngon ngu tri lieu": "NNTL",
        "gddb": "GDDB",
        "giao duc dac biet": "GDDB",
        "csxh": "CSXH",
        "cham soc xa hoi": "CSXH",
        "csyt": "CSYT",
        "cham soc y te": "CSYT",
    }
    for key in normalized_reference_keys(value):
        if key in aliases:
            return aliases[key]
    return None


def normalize_intervention_method(value):
    keys = normalized_reference_keys(value)
    if not keys:
        return ""
    if keys & {"cg", "chuyen gia"}:
        return "CG"
    return sorted(keys)[0]


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
    assignments = PhanCongTre.objects.filter(tu_dong_tu_nhat_ky=False)
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


def next_payment_round(can_bo, ky_can_thiep=None):
    """Tự tính lần TT theo số kỳ can thiệp trước đó có nhật ký của CBCT."""
    qs = NhatKyThucHien.objects.filter(
        Q(can_bo_nguon=can_bo) | Q(can_bo_nguon__isnull=True, hop_dong__can_bo=can_bo)
    )
    if ky_can_thiep:
        qs = qs.filter(ky_can_thiep__lt=ky_can_thiep)
    return qs.values("ky_can_thiep").distinct().count() + 1


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
    nhom_metrics = NhomHD.objects.annotate(
        so_hop_dong=Count("hop_dong", distinct=True),
        so_phan_bo=Count("phan_bo_chi_tieu", distinct=True),
    )
    kpi = {
        "total": nhom_metrics.count(),
        "active": nhom_metrics.filter(is_active=True).count(),
        "with_allocation": nhom_metrics.filter(so_phan_bo__gt=0).count(),
        "with_contract": nhom_metrics.filter(so_hop_dong__gt=0).count(),
        "without_contract": nhom_metrics.filter(so_hop_dong=0).count(),
    }
    return render(request, "quanly/danh_sach_nhom_hd.html", {"ds_nhom": ds_nhom, "kpi": kpi})


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
    page_obj = Paginator(qs.order_by("-ma_don_vi", "-id"), 15).get_page(request.GET.get("page"))
    contract_unit_ids = HopDong.objects.filter(don_vi__isnull=False).values("don_vi_id").distinct()
    kpi = {
        "total": DonVi.objects.count(),
        "active": DonVi.objects.filter(is_active=True).count(),
        "with_staff": DonVi.objects.filter(pk__in=CanBo.objects.values("don_vi_id").distinct()).count(),
        "with_contract": DonVi.objects.filter(pk__in=contract_unit_ids).count(),
        "without_contract": DonVi.objects.exclude(pk__in=contract_unit_ids).count(),
    }
    return render(request, "quanly/danh_sach_don_vi.html", {"page_obj": page_obj, "query": query, "kpi": kpi})


@admin_required
def import_don_vi(request):
    if request.method != "POST" or not request.FILES.get("file_excel"):
        return render(request, "quanly/import_don_vi.html")

    try:
        df = normalized_columns(pd.read_excel(request.FILES["file_excel"]))
    except Exception as exc:
        messages.error(request, f"Không đọc được file Excel: {exc}")
        return render(request, "quanly/import_don_vi.html")

    created = updated = skipped = 0
    errors = []
    for row_no, (_, row) in enumerate(df.iterrows(), start=2):
        try:
            ma_don_vi = clean_empty_excel_value(
                get_excel_value(row, "MaDonVi", "Mã đơn vị", "Mã Đơn Vị", "Mã")
            )
            ten_don_vi = clean_empty_excel_value(
                get_excel_value(row, "TenDonVi", "Tên đơn vị", "Tên Đơn Vị")
            )
            if not ma_don_vi or not ten_don_vi:
                raise ValueError("Thiếu Mã đơn vị hoặc Tên đơn vị")

            mstdv = clean_empty_excel_value(
                get_excel_value(row, "MST", "MSTDV", "MaSoThue", "Mã số thuế")
            )
            existing = DonVi.objects.filter(ma_don_vi=ma_don_vi).first()
            if not existing:
                existing = DonVi.objects.filter(ten_don_vi__iexact=ten_don_vi).first()
            duplicate_tax_qs = DonVi.objects.filter(mstdv=mstdv) if mstdv else DonVi.objects.none()
            if existing:
                duplicate_tax_qs = duplicate_tax_qs.exclude(pk=existing.pk)
            duplicate_tax = duplicate_tax_qs.first()
            if duplicate_tax:
                raise ValueError(
                    f"Mã số thuế {mstdv} đang thuộc đơn vị {duplicate_tax.ma_don_vi}; vui lòng kiểm tra lại"
                )

            defaults = {
                "ten_don_vi": ten_don_vi,
                "mstdv": mstdv,
                "nguoi_dai_dien": clean_empty_excel_value(
                    get_excel_value(row, "NguoiDaiDien", "Người đại diện")
                ) or "",
                "dia_chi": clean_empty_excel_value(get_excel_value(row, "DiaChi", "Địa chỉ")),
                "dien_thoai": clean_empty_excel_value(get_excel_value(row, "DienThoai", "Điện thoại", "SĐT")),
                "email": clean_empty_excel_value(get_excel_value(row, "Email")),
                "is_active": True,
            }
            if existing:
                existing.ma_don_vi = ma_don_vi
                for field, value in defaults.items():
                    setattr(existing, field, value)
                existing.save()
                updated += 1
            else:
                DonVi.objects.create(ma_don_vi=ma_don_vi, **defaults)
                created += 1
        except Exception as exc:
            skipped += 1
            errors.append(f"Dòng {row_no}: {exc}")

    summary = f"Import đơn vị hoàn tất: thêm {created}, cập nhật {updated}, bỏ qua {skipped}."
    if errors:
        messages.warning(request, summary)
        for error in errors:
            messages.warning(request, error)
    else:
        messages.success(request, summary + " Dữ liệu đã được lưu vào cơ sở dữ liệu.")
    return redirect("danh_sach_don_vi")


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
    all_tre = Tre.objects.all()
    known_child_location = Q(ma_tre__istartswith="CBP") | Q(ma_tre__istartswith="CDN")
    kpi = {
        "total": all_tre.count(),
        # Dữ liệu hiện hữu dùng tiền tố mã trẻ; Tỉnh là fallback cho mã mới/khác quy ước.
        "dong_nai": all_tre.filter(
            Q(ma_tre__istartswith="CDN")
            | (~known_child_location & Q(tinh__ten_tinh__icontains="Đồng Nai"))
        ).count(),
        "binh_phuoc": all_tre.filter(
            Q(ma_tre__istartswith="CBP")
            | (~known_child_location & Q(tinh__ten_tinh__icontains="Bình Phước"))
        ).count(),
        "nam": all_tre.filter(gioi_tinh="Nam").count(),
        "nu": all_tre.filter(gioi_tinh="Nữ").count(),
        "other_gender": all_tre.exclude(gioi_tinh__in=["Nam", "Nữ"]).count(),
    }
    return render(request, "quanly/danh_sach_tre.html", {"page_obj": page_obj, "query": query, "kpi": kpi})


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
        messages.warning(request, msg)
        for error in errors:
            messages.warning(request, error)
    else:
        messages.success(request, msg + " Dữ liệu đã được lưu vào cơ sở dữ liệu.")
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
    all_can_bo = CanBo.objects.all()
    known_staff_location = Q(ma_can_bo__istartswith="ABP") | Q(ma_can_bo__istartswith="ADN")
    kpi = {
        "total": all_can_bo.count(),
        "active": all_can_bo.filter(is_active=True).count(),
        # Mã ABP/ADN là quy ước địa bàn đang dùng; Tỉnh là fallback cho mã khác.
        "dong_nai": all_can_bo.filter(
            Q(ma_can_bo__istartswith="ADN")
            | (~known_staff_location & Q(tinh__ten_tinh__icontains="Đồng Nai"))
        ).count(),
        "binh_phuoc": all_can_bo.filter(
            Q(ma_can_bo__istartswith="ABP")
            | (~known_staff_location & Q(tinh__ten_tinh__icontains="Bình Phước"))
        ).count(),
        "nam": all_can_bo.filter(gioi_tinh="Nam").count(),
        "nu": all_can_bo.filter(gioi_tinh="Nữ").count(),
        "other_gender": all_can_bo.exclude(gioi_tinh__in=["Nam", "Nữ"]).count(),
    }
    return render(request, "quanly/danh_sach_can_bo.html", {"page_obj": page_obj, "query": query, "kpi": kpi})


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

    tinh_lookup = {}
    for tinh in Tinh.objects.filter(is_active=True):
        for raw_value in (tinh.pk, tinh.ma_tinh, tinh.ten_tinh):
            for key in normalized_reference_keys(raw_value, ("tỉnh", "thành phố", "tp")):
                add_unique_reference(tinh_lookup, key, tinh)

    xa_lookup_by_tinh = {}
    for xa in Xa.objects.filter(is_active=True).select_related("tinh"):
        xa_lookup = xa_lookup_by_tinh.setdefault(xa.tinh_id, {})
        for raw_value in (xa.pk, xa.ma_xa, xa.ten_xa):
            for key in normalized_reference_keys(raw_value, ("xã", "phường", "thị trấn")):
                add_unique_reference(xa_lookup, key, xa)

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
            tinh_value = clean_empty_excel_value(
                get_excel_value(row, "Tinh", "Tỉnh", "TenTinh", "Tên tỉnh", "MaTinh", "Mã tỉnh", "TinhID", "tinh_id")
            )
            xa_value = clean_empty_excel_value(
                get_excel_value(row, "Xa", "Xã", "TenXa", "Tên xã", "MaXa", "Mã xã", "XaID", "xa_id")
            )
            if tinh_value:
                tinh = resolve_reference(tinh_value, tinh_lookup, "Tỉnh/Thành phố", ("tỉnh", "thành phố", "tp"))
                defaults["tinh"] = tinh
                if xa_value:
                    defaults["xa"] = resolve_reference(
                        xa_value,
                        xa_lookup_by_tinh.get(tinh.pk, {}),
                        f"Xã/Phường thuộc {tinh.ten_tinh}",
                        ("xã", "phường", "thị trấn"),
                    )
                else:
                    defaults["xa"] = None
            elif xa_value:
                raise ValueError(f"Có Xã/Phường '{xa_value}' nhưng thiếu cột Tỉnh")

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
        messages.warning(request, msg)
        for error in errors:
            messages.warning(request, error)
    else:
        messages.success(request, msg + " Dữ liệu đã được lưu vào cơ sở dữ liệu.")
    return redirect("danh_sach_can_bo")


# =========================================================
# PHÂN CÔNG TRẺ
# =========================================================
@hopdong_required
def danh_sach_phan_cong(request):
    query = request.GET.get("q", "").strip()
    phan_bo_id = request.GET.get("phan_bo_id", "").strip()
    nhom_hd_id = request.GET.get("nhom_hd", "").strip()
    dot_phan_cong = request.GET.get("dot_phan_cong", "").strip()
    qs = PhanCongTre.objects.filter(tu_dong_tu_nhat_ky=False).select_related(
        "tre", "can_bo_nguon", "phan_bo__can_bo", "phan_bo__nhom_hd", "nhom_hd"
    )

    if phan_bo_id.isdigit():
        qs = qs.filter(phan_bo_id=int(phan_bo_id))

    if nhom_hd_id.isdigit():
        qs = qs.filter(Q(nhom_hd_id=int(nhom_hd_id)) | Q(nhom_hd__isnull=True, phan_bo__nhom_hd_id=int(nhom_hd_id)))

    if dot_phan_cong.isdigit():
        qs = qs.filter(dot_phan_cong=int(dot_phan_cong))

    if query:
        qs = qs.filter(
            Q(tre__ma_tre__icontains=query)
            | Q(tre__ho_ten__icontains=query)
            | Q(phan_bo__can_bo__ma_can_bo__icontains=query)
            | Q(phan_bo__can_bo__ho_ten__icontains=query)
            | Q(can_bo_nguon__ma_can_bo__icontains=query)
            | Q(can_bo_nguon__ho_ten__icontains=query)
            | Q(cbda_quan_ly__icontains=query)
            | Q(phan_bo__cbda_quan_ly__icontains=query)
        )

    page_obj = Paginator(qs.order_by("-ngay_phan_cong", "-id"), 20).get_page(request.GET.get("page"))
    total_count = qs.count()
    phcn_count = qs.filter(loai_dich_vu__in=PhanCongTre.PHCN_SERVICE_CODES).count()
    cs_count = qs.filter(loai_dich_vu__in=PhanCongTre.CS_SERVICE_CODES).count()
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
            "total_count": total_count,
            "phcn_count": phcn_count,
            "cs_count": cs_count,
            "nhom_list": NhomHD.objects.filter(is_active=True).order_by("ma_nhom_hd"),
            "dot_choices": PhanCongTre.objects.filter(tu_dong_tu_nhat_ky=False).order_by("dot_phan_cong").values_list("dot_phan_cong", flat=True).distinct(),
            "filters": {"nhom_hd": nhom_hd_id, "dot_phan_cong": dot_phan_cong},
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
        if phan_bo.is_locked and not is_admin_user(request.user):
            messages.error(request, f"Phân bổ #{phan_bo.pk} đã khóa, không thể thêm phân công.")
            return redirect("danh_sach_phan_bo")

    if request.method == "POST":
        form = PhanCongTreForm(request.POST, allow_locked=is_admin_user(request.user))
    else:
        initial = {"phan_bo": phan_bo} if phan_bo else {}
        form = PhanCongTreForm(initial=initial, allow_locked=is_admin_user(request.user))

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
    if item.phan_bo_id and item.phan_bo.is_locked and not is_admin_user(request.user):
        messages.error(request, "Phân bổ đã khóa, chỉ Admin mới được sửa phân công.")
        return redirect("danh_sach_phan_cong")
    form = PhanCongTreForm(request.POST or None, instance=item)
    if request.method == "POST" and form.is_valid():
        affected_dates = set(
            NhatKyThucHien.objects.filter(phan_cong=item).values_list("ngay_thuc_hien", flat=True)
        )
        form.save()
        for date_value in sorted(value for value in affected_dates if value):
            NhatKyThucHien.recalculate_day(date_value)
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
    if not item.phan_bo_id:
        messages.error(request, "Phân công chưa thuộc Phân bổ; chưa thể điều chuyển CBCT.")
        return redirect("danh_sach_phan_cong")
    queryset = PhanBoChiTieu.objects.filter(nhom_hd=item.phan_bo.nhom_hd).exclude(pk=item.phan_bo_id).select_related("can_bo", "nhom_hd")
    if not is_admin_user(request.user):
        if item.phan_bo.is_locked:
            messages.error(request, "Phân bổ đã khóa, chỉ Admin mới được điều chuyển phân công.")
            return redirect("danh_sach_phan_cong")
        queryset = queryset.filter(is_locked=False)
    if request.method == "POST":
        form = DieuChuyenPhanCongForm(request.POST)
        form.fields["phan_bo"].queryset = queryset
        if form.is_valid():
            target = form.cleaned_data["phan_bo"]
            old = item.phan_bo
            affected_dates = set(
                NhatKyThucHien.objects.filter(phan_cong=item).values_list("ngay_thuc_hien", flat=True)
            )
            item.phan_bo = target
            is_cs = PhanCongTre.service_group(item.loai_dich_vu) == "CS"
            item.dinh_muc_di_lai = target.dinh_muc_di_lai_cs if is_cs else target.dinh_muc_di_lai_phcn
            item.full_clean()
            with transaction.atomic():
                item.save(update_fields=["phan_bo", "dinh_muc_di_lai", "updated_at"])
                LichSuDieuChuyenPhanCong.objects.create(phan_cong=item, phan_bo_cu=old, phan_bo_moi=target, nguoi_thuc_hien=request.user.get_username(), ly_do=form.cleaned_data.get("ly_do"))
            for date_value in sorted(value for value in affected_dates if value):
                NhatKyThucHien.recalculate_day(date_value)
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
def import_nhat_ky_can_thiep(request):
    """Import nhật ký mới hoặc dữ liệu lịch sử có hồ sơ hợp đồng không đầy đủ."""
    if request.method != "POST" or not request.FILES.get("file_excel"):
        return render(request, "quanly/import_nhat_ky_can_thiep.html")

    historical_mode = request.POST.get("historical_mode") == "1"
    try:
        df = normalized_columns(pd.read_excel(request.FILES["file_excel"]))
    except Exception as exc:
        messages.error(request, f"Không đọc được file Excel: {exc}")
        return render(request, "quanly/import_nhat_ky_can_thiep.html")

    created = updated = skipped = 0
    errors, warnings = [], []
    service_codes = {"PHCN": PhanCongTre.PHCN_SERVICE_CODES, "CS": PhanCongTre.CS_SERVICE_CODES}
    identity_cache, identity_occurrences = {}, {}
    affected_dates = set()

    for row_no, (_, row) in enumerate(df.iterrows(), start=2):
        row_warnings = []
        try:
            ma_cb = clean_empty_excel_value(get_excel_value(row, "MaCBCT", "Mã CBCT"))
            ma_tre = clean_empty_excel_value(get_excel_value(row, "MaTre", "Mã trẻ", "IDChild"))
            ngay = parse_date(get_excel_value(row, "NgayCanThiep", "Ngày can thiệp"))
            if not ma_cb or not ma_tre:
                raise ValueError("Thiếu mã CBCT hoặc mã trẻ")
            if not ngay:
                if historical_mode:
                    row_warnings.append("thiếu ngày can thiệp; bản ghi vẫn được lưu để bảo toàn dữ liệu nguồn")
                else:
                    raise ValueError("Thiếu ngày can thiệp")
            can_bo = CanBo.objects.filter(ma_can_bo=ma_cb).first()
            tre = Tre.objects.filter(ma_tre=ma_tre).first()
            if not can_bo:
                raise ValueError(f"Không tìm thấy CBCT {ma_cb}")
            if not tre:
                raise ValueError(f"Không tìm thấy trẻ {ma_tre}")

            nhom_value = clean_empty_excel_value(get_excel_value(row, "NhomHD", "Nhóm HĐ"))
            source_group = None
            if nhom_value:
                source_filter = Q(ma_nhom_hd=nhom_value) | Q(ten_nhom_hd__iexact=nhom_value)
                if str(nhom_value).replace(".0", "", 1).isdigit():
                    source_filter |= Q(pk=int(float(nhom_value)))
                source_group = NhomHD.objects.filter(source_filter).first()
                if not source_group and not historical_mode:
                    raise ValueError(f"Không tìm thấy Nhóm HĐ {nhom_value}")
                if not source_group:
                    row_warnings.append(f"không tìm thấy danh mục Nhóm HĐ {nhom_value}")

            contracts = HopDong.objects.none()
            if ngay:
                contracts = HopDong.objects.filter(
                    can_bo=can_bo, tu_ngay__lte=ngay, den_ngay__gte=ngay
                ).select_related("nhom_hd", "de_xuat__phan_bo", "don_vi")
            if source_group:
                contracts = contracts.filter(nhom_hd=source_group)
            hop_dong = contracts.order_by("-ngay_ky", "-id").first()

            # Nếu CBCT làm việc trong nhóm ký HĐ với đơn vị, liên kết nhật ký với HĐ đơn vị
            # để tiếp tục thanh toán đi lại PH; tiền công CBCT của HĐ này được giữ bằng 0.
            if not hop_dong and source_group:
                unit_contracts = HopDong.objects.filter(
                    can_bo__isnull=True,
                    don_vi__isnull=False,
                    nhom_hd=source_group,
                ).select_related("nhom_hd", "don_vi")
                if ngay:
                    unit_contracts = unit_contracts.filter(tu_ngay__lte=ngay, den_ngay__gte=ngay)
                hop_dong = unit_contracts.order_by("-ngay_ky", "-id").first()

            if not hop_dong and historical_mode:
                fallback = HopDong.objects.filter(can_bo=can_bo).select_related("nhom_hd", "de_xuat__phan_bo")
                if source_group:
                    hop_dong = fallback.filter(nhom_hd=source_group).order_by("-ngay_ky", "-id").first()
                if not hop_dong:
                    hop_dong = fallback.order_by("-ngay_ky", "-id").first()
                if hop_dong:
                    row_warnings.append(
                        f"dùng HĐ {hop_dong.so_hop_dong} làm liên kết kỹ thuật vì không có HĐ bao phủ ngày/nhóm nguồn"
                    )
            if not hop_dong and historical_mode and source_group:
                hop_dong = HopDong.objects.filter(
                    can_bo__isnull=True,
                    don_vi__isnull=False,
                    nhom_hd=source_group,
                ).select_related("nhom_hd", "don_vi").order_by("-ngay_ky", "-id").first()
                if hop_dong:
                    row_warnings.append(
                        f"dùng HĐ đơn vị {hop_dong.so_hop_dong} làm liên kết kỹ thuật theo Nhóm HĐ"
                    )
            if not hop_dong and not historical_mode:
                raise ValueError(
                    f"Không có hợp đồng bao phủ ngày {ngay:%d/%m/%Y} cho CBCT {ma_cb}, Nhóm HĐ {nhom_value or 'chưa có'}"
                )
            if not hop_dong:
                row_warnings.append("chưa có hợp đồng; nhật ký được lưu độc lập theo phân công")

            raw_service = (clean_empty_excel_value(get_excel_value(row, "MaLoaiDichVu", "Loại dịch vụ")) or "PHCN").upper()
            exact_service = normalize_service_code(raw_service)
            service_group = "CS" if raw_service in {"CS", "CSXH", "CSYT"} or exact_service in PhanCongTre.CS_SERVICE_CODES else "PHCN"
            service_filter = Q(loai_dich_vu=exact_service) if exact_service else Q(loai_dich_vu__in=service_codes[service_group])
            ky_can_thiep = parse_int(get_excel_value(row, "KyCanThiep", "Kỳ can thiệp"), 0)
            if not 1 <= ky_can_thiep <= 30:
                raise ValueError("Kỳ can thiệp phải từ 1 đến 30")
            sessions = parse_int(get_excel_value(row, "SoBuoiThucTe", "Số buổi thực tế"), 0)
            if sessions <= 0:
                raise ValueError("Số buổi thực tế phải lớn hơn 0")
            source_location = clean_empty_excel_value(get_excel_value(row, "DiaDiem", "Địa điểm"))
            source_hinh_thuc_ct = clean_empty_excel_value(get_excel_value(row, "Hình thức CT", "HinhThucCT"))

            def choose_assignment(queryset):
                candidates = queryset.order_by("id")
                if not source_hinh_thuc_ct:
                    return candidates.first()
                source_method = normalize_intervention_method(source_hinh_thuc_ct)
                return next(
                    (
                        candidate for candidate in candidates
                        if normalize_intervention_method(candidate.hinh_thuc_ct) == source_method
                    ),
                    None,
                )

            assignment = None
            if hop_dong and hop_dong.de_xuat_id:
                assignment = choose_assignment(PhanCongTre.objects.filter(
                    Q(phan_bo=hop_dong.de_xuat.phan_bo), Q(tre=tre), service_filter
                ))
            if not assignment and historical_mode:
                fallback_assignments = PhanCongTre.objects.filter(Q(tre=tre), service_filter)
                same_cb = fallback_assignments.filter(Q(phan_bo__can_bo=can_bo) | Q(can_bo_nguon=can_bo))
                if source_group:
                    assignment = choose_assignment(same_cb.filter(Q(nhom_hd=source_group) | Q(phan_bo__nhom_hd=source_group)))
                if not assignment:
                    assignment = choose_assignment(same_cb)
                if not assignment and source_group:
                    assignment = choose_assignment(fallback_assignments.filter(phan_bo__isnull=True, nhom_hd=source_group))
                if assignment:
                    row_warnings.append("phân công không cùng phân bổ với HĐ liên kết")
            if not assignment and historical_mode and exact_service:
                template_assignments = PhanCongTre.objects.filter(
                    Q(tre=tre), Q(phan_bo__can_bo=can_bo) | Q(can_bo_nguon=can_bo)
                )
                if source_group:
                    grouped_templates = template_assignments.filter(
                        Q(nhom_hd=source_group) | Q(phan_bo__nhom_hd=source_group)
                    )
                    if grouped_templates.exists():
                        template_assignments = grouped_templates
                same_service_group = [
                    item for item in template_assignments.select_related("phan_bo", "nhom_hd")
                    if PhanCongTre.service_group(item.loai_dich_vu) == service_group
                ]
                template_candidates = same_service_group or list(template_assignments)
                if source_hinh_thuc_ct:
                    source_method = normalize_intervention_method(source_hinh_thuc_ct)
                    template_assignment = next(
                        (
                            candidate for candidate in template_candidates
                            if normalize_intervention_method(candidate.hinh_thuc_ct) == source_method
                        ),
                        None,
                    )
                else:
                    template_assignment = template_candidates[0] if template_candidates else None
                if template_assignment:
                    assignment = PhanCongTre.objects.create(
                        phan_bo=template_assignment.phan_bo,
                        can_bo_nguon=can_bo,
                        cbda_quan_ly=template_assignment.cbda_quan_ly,
                        nhom_hd=source_group or template_assignment.nhom_hd,
                        tre=tre,
                        loai_dich_vu=exact_service,
                        so_buoi_du_kien=max(sessions, 1),
                        dinh_muc_di_lai=Decimal(str(FinancialConfig.DON_GIA_DI_LAI_DM1)),
                        dia_diem_ct=source_location or template_assignment.dia_diem_ct,
                        hinh_thuc_ct=source_hinh_thuc_ct or template_assignment.hinh_thuc_ct,
                        dot_phan_cong=template_assignment.dot_phan_cong,
                        ky_phan_cong=template_assignment.ky_phan_cong,
                        ngay_phan_cong=template_assignment.ngay_phan_cong,
                        trang_thai=template_assignment.trang_thai,
                        ghi_chu="Tự tạo từ import nhật ký lịch sử do thiếu phân công đúng dịch vụ.",
                        tu_dong_tu_nhat_ky=True,
                    )
                    row_warnings.append(f"đã tạo phân công lịch sử cho dịch vụ {exact_service}")
            if not assignment and historical_mode and exact_service:
                assignment = PhanCongTre.objects.create(
                    phan_bo=None,
                    can_bo_nguon=can_bo,
                    nhom_hd=source_group,
                    tre=tre,
                    loai_dich_vu=exact_service,
                    so_buoi_du_kien=max(sessions, 1),
                    dinh_muc_di_lai=Decimal(str(FinancialConfig.DON_GIA_DI_LAI_DM1)),
                    dia_diem_ct=source_location,
                    hinh_thuc_ct=source_hinh_thuc_ct,
                    dot_phan_cong=1,
                    ky_phan_cong=ky_can_thiep if 1 <= ky_can_thiep <= 30 else 1,
                    ngay_phan_cong=ngay,
                    trang_thai="DA_HOAN_THANH",
                    ghi_chu="Tự tạo từ import nhật ký lịch sử do chưa có dữ liệu phân công nguồn.",
                    tu_dong_tu_nhat_ky=True,
                )
                row_warnings.append(f"đã tạo phân công kỹ thuật độc lập cho dịch vụ {exact_service}")
            if not assignment:
                raise ValueError(f"Không tìm thấy phân công của trẻ {ma_tre} cho CBCT {ma_cb} và dịch vụ {raw_service}")
            if source_hinh_thuc_ct and not assignment.hinh_thuc_ct:
                assignment.hinh_thuc_ct = source_hinh_thuc_ct
                assignment.save(update_fields=["hinh_thuc_ct", "updated_at"])

            gio_bat_dau = parse_time(get_excel_value(row, "GioBatDau", "Giờ bắt đầu"))
            gio_ket_thuc = parse_time(get_excel_value(row, "GioKetThuc", "Giờ kết thúc"))
            if (gio_bat_dau is None) != (gio_ket_thuc is None) or (
                gio_bat_dau and gio_ket_thuc and gio_ket_thuc <= gio_bat_dau
            ):
                if historical_mode:
                    gio_bat_dau = gio_ket_thuc = None
                    row_warnings.append("giờ không đủ/không hợp lệ nên lưu trống")
                else:
                    raise ValueError("Giờ bắt đầu/kết thúc phải đủ cặp và giờ kết thúc phải lớn hơn giờ bắt đầu")
            elif historical_mode and not gio_bat_dau:
                row_warnings.append("thiếu giờ bắt đầu/kết thúc")

            dia_diem_ct = source_location or assignment.dia_diem_ct
            cbct_travel_raw = get_excel_value(row, "SoLuotDiLaiCBCT", "Số lượt đi lại CBCT")
            cbct_travel = parse_int(cbct_travel_raw, -1)
            if cbct_travel < 0:
                location = (dia_diem_ct or "").strip().lower()
                cbct_travel = sessions if location in {"nhà", "nha", "khác", "khac"} else 0
                if historical_mode and not gio_bat_dau:
                    row_warnings.append("lượt đi lại CBCT được suy ra theo địa điểm và số buổi")

            is_cs = PhanCongTre.service_group(assignment.loai_dich_vu) == "CS"
            note = clean_empty_excel_value(get_excel_value(row, "GhiChu", "Ghi chú")) or ""
            if row_warnings:
                history_note = "Dữ liệu lịch sử: " + "; ".join(row_warnings)
                note = f"{note}\n{history_note}".strip()
            if ngay:
                affected_dates.add(ngay)
            defaults = {
                "nhom_hd_nguon": source_group,
                "can_bo_nguon": can_bo,
                "du_lieu_lich_su": historical_mode,
                "so_buoi_thuc_hien": sessions,
                "so_luot_di_lai": parse_int(get_excel_value(row, "SoLuotDiLaiPH", "Số lượt đi lại PH"), 0),
                "so_luot_di_lai_cbct": cbct_travel,
                "ky_can_thiep": ky_can_thiep,
                "lan_thanh_toan": next_payment_round(can_bo, ky_can_thiep),
                "dia_diem_ct": dia_diem_ct,
                "don_gia_cong": (
                    Decimal("0") if hop_dong and hop_dong.la_hop_dong_don_vi
                    else hop_dong.don_gia_cong if hop_dong
                    else Decimal(str(FinancialConfig.DON_GIA_CONG))
                ),
                "dinh_muc_di_lai": (
                    Decimal("0") if hop_dong and hop_dong.la_hop_dong_don_vi
                    else (hop_dong.dinh_muc_di_lai_cs if is_cs else hop_dong.dinh_muc_di_lai_phcn)
                    if hop_dong else Decimal(str(FinancialConfig.DON_GIA_DI_LAI_DM1))
                ),
                "ghi_chu": note,
            }
            identity_key = journal_import_identity_key(
                can_bo.pk,
                tre.pk,
                exact_service,
                source_group.pk if source_group else None,
                ky_can_thiep,
                ngay,
                gio_bat_dau,
                gio_ket_thuc,
                dia_diem_ct,
            )

            def load_existing_journals():
                candidates = NhatKyThucHien.objects.filter(
                    can_bo_nguon=can_bo,
                    phan_cong__tre=tre,
                    phan_cong__loai_dich_vu=exact_service,
                    ky_can_thiep=ky_can_thiep,
                    ngay_thuc_hien=ngay,
                    gio_bat_dau=gio_bat_dau,
                    gio_ket_thuc=gio_ket_thuc,
                )
                if source_group:
                    candidates = candidates.filter(nhom_hd_nguon=source_group)
                else:
                    candidates = candidates.filter(nhom_hd_nguon__isnull=True)
                normalized_location = normalize_travel_location(dia_diem_ct)
                return [
                    item for item in candidates.order_by("id")
                    if normalize_travel_location(item.dia_diem_ct) == normalized_location
                ]

            identity, _ = take_import_occurrence(
                identity_cache,
                identity_occurrences,
                identity_key,
                load_existing_journals,
            )

            if identity:
                identity.hop_dong = hop_dong
                identity.phan_cong = assignment
                identity.ngay_thuc_hien = ngay
                identity.gio_bat_dau = gio_bat_dau
                identity.gio_ket_thuc = gio_ket_thuc
                for field, value in defaults.items():
                    setattr(identity, field, value)
                identity.save(recalculate_travel=False)
                is_created = False
            else:
                journal = NhatKyThucHien(
                    hop_dong=hop_dong, phan_cong=assignment, ngay_thuc_hien=ngay,
                    gio_bat_dau=gio_bat_dau, gio_ket_thuc=gio_ket_thuc, **defaults,
                )
                journal.save(recalculate_travel=False)
                is_created = True
            created += int(is_created)
            updated += int(not is_created)
            if row_warnings:
                warnings.append(f"Dòng {row_no}: " + "; ".join(row_warnings))
        except Exception as exc:
            skipped += 1
            errors.append(f"Dòng {row_no}: {exc}")

    for date_value in sorted(affected_dates):
        NhatKyThucHien.recalculate_day(date_value)

    summary = (
        f"Import nhật ký hoàn tất: thêm {created}, cập nhật {updated}, "
        f"bỏ qua {skipped} (không lưu/không tính KPI), "
        f"đã lưu kèm cảnh báo {len(warnings)} (vẫn tính KPI)."
    )
    if errors or warnings:
        messages.warning(request, summary)
        for detail in errors[:200]:
            messages.error(request, detail)
        remaining_slots = max(200 - len(errors), 0)
        for detail in warnings[:remaining_slots]:
            messages.warning(request, detail)
        hidden_count = len(errors) + len(warnings) - min(len(errors), 200) - min(len(warnings), remaining_slots)
        if hidden_count > 0:
            messages.warning(request, f"Còn {hidden_count} cảnh báo/lỗi khác; hãy chia file nhỏ hơn để xem chi tiết theo dòng.")
    else:
        messages.success(request, summary + " Dữ liệu đã được lưu vào cơ sở dữ liệu.")
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
    nhom_id = request.GET.get("nhom_hd", "").strip()
    trang_thai = request.GET.get("trang_thai", "").strip()
    tien_do = request.GET.get("tien_do", "").strip()
    qs = (
        PhanBoChiTieu.objects.select_related("can_bo", "nhom_hd")
        .annotate(
            official_assignment_count=Count(
                "danh_sach_phan_cong",
                filter=Q(danh_sach_phan_cong__tu_dong_tu_nhat_ky=False),
                distinct=True,
            )
        )
    )
    if query:
        qs = qs.filter(
            Q(can_bo__ho_ten__icontains=query)
            | Q(can_bo__ma_can_bo__icontains=query)
            | Q(cbda_quan_ly__icontains=query)
            | Q(nhom_hd__ma_nhom_hd__icontains=query)
            | Q(nhom_hd__ten_nhom_hd__icontains=query)
        )
    if nhom_id.isdigit():
        qs = qs.filter(nhom_hd_id=int(nhom_id))
    if trang_thai == "mo":
        qs = qs.filter(is_locked=False)
    elif trang_thai == "khoa":
        qs = qs.filter(is_locked=True)
    if tien_do == "chua_phan_cong":
        qs = qs.filter(official_assignment_count=0)
    elif tien_do == "da_phan_cong":
        qs = qs.filter(official_assignment_count__gt=0)

    filtered_allocations = PhanBoChiTieu.objects.filter(pk__in=qs.values("pk"))
    kpi = filtered_allocations.aggregate(
        total_allocations=Count("id"),
        assigned_staff=Count("can_bo", distinct=True),
        allocations_without_staff=Count("id", filter=Q(can_bo__isnull=True)),
        open_allocations=Count("id", filter=Q(is_locked=False)),
        locked_allocations=Count("id", filter=Q(is_locked=True)),
        phcn_children=Sum("so_tre_phcn"),
        cs_children=Sum("so_tre_cs"),
        phcn_sessions=Sum(F("so_tre_phcn") * F("so_buoi_phcn"), output_field=IntegerField()),
        cs_sessions=Sum(F("so_tre_cs") * F("so_buoi_cs"), output_field=IntegerField()),
    )
    for key in (
        "total_allocations", "assigned_staff", "allocations_without_staff", "open_allocations",
        "locked_allocations", "phcn_children", "cs_children", "phcn_sessions", "cs_sessions",
    ):
        kpi[key] = kpi[key] or 0
    kpi["target_children"] = kpi["phcn_children"] + kpi["cs_children"]
    kpi["target_sessions"] = kpi["phcn_sessions"] + kpi["cs_sessions"]
    official_assignments = PhanCongTre.objects.filter(
        phan_bo_id__in=qs.values("pk"),
        tu_dong_tu_nhat_ky=False,
    )
    kpi["official_assignments"] = official_assignments.count()
    kpi["allocations_without_assignments"] = max(
        kpi["total_allocations"] - official_assignments.values("phan_bo_id").distinct().count(),
        0,
    )
    kpi["assignment_percent"] = round(
        kpi["official_assignments"] * 100 / kpi["target_children"]
    ) if kpi["target_children"] else 0
    page_obj = Paginator(qs.order_by("-ngay_lap", "-id"), 15).get_page(request.GET.get("page"))
    pagination_params = request.GET.copy()
    pagination_params.pop("page", None)
    return render(request, "quanly/danh_sach_phan_bo.html", {
        "danh_sach": page_obj,
        "page_obj": page_obj,
        "query": query,
        "kpi": kpi,
        "nhom_list": NhomHD.objects.filter(is_active=True),
        "filters": {"nhom_hd": nhom_id, "trang_thai": trang_thai, "tien_do": tien_do},
        "pagination_query": pagination_params.urlencode(),
    })


@admin_required
def xoa_phan_bo(request, pk):
    if request.method != "POST":
        return redirect("danh_sach_phan_bo")
    item = get_object_or_404(PhanBoChiTieu, pk=pk)
    try:
        item.delete()
        messages.success(request, "Đã xóa Phân bổ chỉ tiêu.")
    except Exception as exc:
        messages.error(request, f"Không thể xóa Phân bổ: {exc}")
    return redirect("danh_sach_phan_bo")


@admin_required
def sua_phan_bo_chi_tieu(request, pk):
    item = get_object_or_404(PhanBoChiTieu, pk=pk)
    form = PhanBoChiTieuForm(request.POST or None, instance=item)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Đã cập nhật Phân bổ chỉ tiêu.")
        return redirect("danh_sach_phan_bo")
    return render(request, "quanly/phan_bo_chi_tieu.html", {"form": form, "item": item})


@admin_required
def khoa_phan_bo(request, pk):
    item = get_object_or_404(PhanBoChiTieu, pk=pk)
    if request.method != "POST":
        messages.warning(request, "Khóa Phân bổ phải được xác nhận bằng biểu mẫu POST.")
        return redirect("danh_sach_phan_bo")
    if item.is_locked:
        messages.error(request, f"Phân bổ #{item.pk} đã được khóa trước đó.")
        return redirect("danh_sach_phan_bo")
    item.is_locked = True
    item.save(update_fields=["is_locked", "updated_at"])
    messages.success(request, f"Đã khóa Phân bổ #{item.pk}.")
    return redirect("danh_sach_phan_bo")


@admin_required
def mo_khoa_phan_bo(request, pk):
    item = get_object_or_404(PhanBoChiTieu, pk=pk)
    if request.method != "POST":
        return redirect("danh_sach_phan_bo")
    if not item.is_locked:
        messages.info(request, f"Phân bổ #{item.pk} đang ở trạng thái mở.")
        return redirect("danh_sach_phan_bo")
    item.is_locked = False
    item.save(update_fields=["is_locked", "updated_at"])
    messages.success(request, f"Đã mở khóa Phân bổ #{item.pk} để tiếp tục kiểm thử/chỉnh sửa.")
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
    if not phan_bo.can_bo_id:
        raise ValueError("Phân bổ chưa có CBCT; chưa thể tạo đề xuất hợp đồng.")
    assignments = phan_bo.danh_sach_phan_cong.filter(tu_dong_tu_nhat_ky=False).select_related("tre")
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
    nhom_id = request.GET.get("nhom_hd", "").strip()
    trang_thai = request.GET.get("trang_thai", "").strip()
    hop_dong_status = request.GET.get("hop_dong", "").strip()
    qs = DeXuatHopDong.objects.select_related(
        "phan_bo__can_bo", "phan_bo__nhom_hd"
    ).prefetch_related("hop_dong")
    if query:
        qs = qs.filter(
            Q(phan_bo__can_bo__ho_ten__icontains=query)
            | Q(phan_bo__can_bo__ma_can_bo__icontains=query)
            | Q(phan_bo__nhom_hd__ma_nhom_hd__icontains=query)
            | Q(phan_bo__nhom_hd__ten_nhom_hd__icontains=query)
        )
    if nhom_id.isdigit():
        qs = qs.filter(phan_bo__nhom_hd_id=int(nhom_id))
    valid_proposal_statuses = {value for value, _ in DeXuatHopDong.TRANG_THAI_CHOICES}
    if trang_thai in valid_proposal_statuses:
        qs = qs.filter(trang_thai=trang_thai)
    if hop_dong_status == "chua_tao":
        qs = qs.filter(hop_dong__isnull=True)
    elif hop_dong_status == "da_tao":
        qs = qs.filter(hop_dong__isnull=False)
    qs = qs.distinct()

    filtered_proposals = DeXuatHopDong.objects.filter(pk__in=qs.values("pk"))
    proposal_totals = filtered_proposals.aggregate(
        total=Count("id"),
        expected_value=Sum("gia_tri_du_kien"),
        phcn_children=Sum("so_tre_phcn"),
        cs_children=Sum("so_tre_cs"),
    )
    kpi = {key: value or 0 for key, value in proposal_totals.items()}
    kpi["target_children"] = kpi["phcn_children"] + kpi["cs_children"]
    kpi["pending_review"] = filtered_proposals.filter(
        trang_thai__in={"CHO_KIEM_TRA", "DU_DIEU_KIEN"}
    ).count()
    kpi["approved_without_contract"] = filtered_proposals.filter(
        trang_thai="DA_DUYET", hop_dong__isnull=True
    ).count()
    kpi["contracts_created"] = filtered_proposals.filter(hop_dong__isnull=False).distinct().count()
    kpi["rejected_or_cancelled"] = filtered_proposals.filter(trang_thai__in={"TU_CHOI", "HUY"}).count()

    page_obj = Paginator(qs.order_by("-ngay_de_xuat", "-id"), 15).get_page(request.GET.get("page"))
    pagination_params = request.GET.copy()
    pagination_params.pop("page", None)
    return render(request, "quanly/danh_sach_de_xuat.html", {
        "page_obj": page_obj,
        "query": query,
        "kpi": kpi,
        "nhom_list": NhomHD.objects.filter(is_active=True),
        "status_choices": DeXuatHopDong.TRANG_THAI_CHOICES,
        "filters": {"nhom_hd": nhom_id, "trang_thai": trang_thai, "hop_dong": hop_dong_status},
        "pagination_query": pagination_params.urlencode(),
    })


@admin_required
def sua_de_xuat(request, pk):
    proposal = get_object_or_404(DeXuatHopDong, pk=pk)
    if proposal.hop_dong.exists():
        messages.error(request, "Đề xuất đã tạo hợp đồng, không thể sửa trực tiếp; hãy sửa hợp đồng hoặc tạo đề xuất lần mới.")
        return redirect("danh_sach_de_xuat")
    form = DeXuatHopDongForm(request.POST or None, instance=proposal)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"Đã cập nhật đề xuất HĐ #{proposal.pk}.")
        return redirect("danh_sach_de_xuat")
    return render(request, "quanly/sua_de_xuat.html", {"form": form, "proposal": proposal})


@admin_required
def xoa_de_xuat(request, pk):
    if request.method != "POST":
        return redirect("danh_sach_de_xuat")
    proposal = get_object_or_404(DeXuatHopDong, pk=pk)
    if proposal.hop_dong.exists():
        messages.error(request, "Đề xuất đã tạo hợp đồng, không thể xóa.")
        return redirect("danh_sach_de_xuat")
    try:
        with transaction.atomic():
            allocation = proposal.phan_bo
            proposal.delete()
            if not allocation.de_xuat_hop_dong.exists():
                allocation.is_locked = False
                allocation.save(update_fields=["is_locked", "updated_at"])
        messages.success(request, f"Đã xóa đề xuất HĐ #{pk} và mở khóa phân bổ nếu không còn đề xuất khác.")
    except ProtectedError:
        messages.error(request, "Không thể xóa đề xuất vì còn dữ liệu liên kết.")
    return redirect("danh_sach_de_xuat")


@hopdong_required
def duyet_de_xuat(request, pk):
    proposal = get_object_or_404(DeXuatHopDong, pk=pk)
    if request.method == "POST":
        if not proposal.phan_bo.danh_sach_phan_cong.filter(tu_dong_tu_nhat_ky=False).exists():
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
    nhom_id = request.GET.get("nhom_hd", "").strip()
    trang_thai = request.GET.get("trang_thai", "").strip()
    thoi_han = request.GET.get("thoi_han", "").strip()
    today = timezone.localdate()
    next_30_days = today + timedelta(days=30)
    qs = HopDong.objects.select_related("can_bo", "don_vi", "nhom_hd", "de_xuat").order_by("-ngay_ky", "-id")
    if query:
        qs = qs.filter(
            Q(so_hop_dong__icontains=query)
            | Q(can_bo__ma_can_bo__icontains=query)
            | Q(can_bo__ho_ten__icontains=query)
            | Q(don_vi__ma_don_vi__icontains=query)
            | Q(don_vi__ten_don_vi__icontains=query)
            | Q(nhom_hd__ma_nhom_hd__icontains=query)
            | Q(nhom_hd__ten_nhom_hd__icontains=query)
        )
    if nhom_id.isdigit():
        qs = qs.filter(nhom_hd_id=int(nhom_id))
    valid_contract_statuses = {value for value, _ in HopDong.TRANG_THAI_CHOICES}
    if trang_thai in valid_contract_statuses:
        qs = qs.filter(trang_thai=trang_thai)
    if thoi_han == "hieu_luc":
        qs = qs.filter(tu_ngay__lte=today, den_ngay__gte=today).exclude(trang_thai__in={"HUY", "THANH_LY"})
    elif thoi_han == "sap_het_han":
        qs = qs.filter(den_ngay__gte=today, den_ngay__lte=next_30_days).exclude(trang_thai__in={"HUY", "THANH_LY"})
    elif thoi_han == "qua_han":
        qs = qs.filter(den_ngay__lt=today)

    contract_totals = qs.aggregate(
        total=Count("id"),
        total_value=Sum("gia_tri_hop_dong"),
        staff_count=Count("can_bo", distinct=True),
        unit_count=Count("don_vi", distinct=True),
        missing_signed_date=Count("id", filter=Q(ngay_ky__isnull=True)),
    )
    kpi = {key: value or 0 for key, value in contract_totals.items()}
    kpi["active"] = qs.filter(tu_ngay__lte=today, den_ngay__gte=today).exclude(
        trang_thai__in={"HUY", "THANH_LY"}
    ).count()
    kpi["expiring"] = qs.filter(den_ngay__gte=today, den_ngay__lte=next_30_days).exclude(
        trang_thai__in={"HUY", "THANH_LY"}
    ).count()
    kpi["expired"] = qs.filter(den_ngay__lt=today).count()
    page_obj = Paginator(qs, 15).get_page(request.GET.get("page"))
    pagination_params = request.GET.copy()
    pagination_params.pop("page", None)
    return render(request, "quanly/danh_sach_hop_dong.html", {
        "hop_dongs": page_obj,
        "page_obj": page_obj,
        "query": query,
        "kpi": kpi,
        "today": today,
        "next_30_days": next_30_days,
        "nhom_list": NhomHD.objects.filter(is_active=True),
        "status_choices": HopDong.TRANG_THAI_CHOICES,
        "filters": {"nhom_hd": nhom_id, "trang_thai": trang_thai, "thoi_han": thoi_han},
        "pagination_query": pagination_params.urlencode(),
    })


@admin_required
def sua_hop_dong(request, pk):
    hop_dong = get_object_or_404(HopDong, pk=pk)
    current_status = hop_dong.trang_thai
    form = HopDongForm(request.POST or None, instance=hop_dong)
    if request.method == "POST" and form.is_valid():
        target_status = form.cleaned_data.get("trang_thai")
        try:
            # ModelForm mutates its instance during _post_clean; compare with
            # the status captured before validation, not the mutated instance.
            hop_dong.trang_thai = current_status
            if target_status != current_status:
                validate_status_transition(hop_dong, target_status)
                if target_status in {"NGHIEM_THU", "THANH_LY"}:
                    acceptance = NghiemThu.objects.filter(hop_dong=hop_dong).first()
                    if not acceptance or not acceptance.ngay_nghiem_thu or acceptance.ket_qua != "DAT":
                        raise ValidationError("Chỉ được chuyển sang nghiệm thu/thanh lý sau khi có hồ sơ nghiệm thu Đạt.")
            with transaction.atomic():
                form.save()
                _sync_hop_dong_from_signed_extensions(hop_dong)
            messages.success(request, f"Đã cập nhật hợp đồng {hop_dong.so_hop_dong}.")
            return redirect("danh_sach_hop_dong")
        except ValidationError as exc:
            form.add_error("trang_thai", str(exc))
    return render(request, "quanly/sua_hop_dong.html", {"form": form, "hop_dong": hop_dong})


@admin_required
def xoa_hop_dong(request, pk):
    if request.method != "POST":
        return redirect("danh_sach_hop_dong")
    hop_dong = get_object_or_404(HopDong, pk=pk)
    try:
        hop_dong.delete()
        messages.success(request, "Đã xóa hợp đồng.")
    except Exception as exc:
        messages.error(request, f"Không thể xóa hợp đồng vì còn dữ liệu liên quan: {exc}")
    return redirect("danh_sach_hop_dong")


@admin_required
def mo_khoa_hop_dong(request, pk):
    hop_dong = get_object_or_404(HopDong, pk=pk)
    if request.method != "POST":
        return redirect("danh_sach_hop_dong")
    if not hop_dong.is_locked:
        messages.info(request, f"Hợp đồng {hop_dong.so_hop_dong} đang ở trạng thái mở.")
        return redirect("danh_sach_hop_dong")
    hop_dong.is_locked = False
    hop_dong.save(update_fields=["is_locked", "updated_at"])
    messages.success(request, f"Đã mở khóa hợp đồng {hop_dong.so_hop_dong} để tiếp tục kiểm thử/chỉnh sửa.")
    return redirect("danh_sach_hop_dong")


@admin_required
def import_hop_dong(request):
    if request.method != "POST" or not request.FILES.get("file_excel"):
        return render(request, "quanly/import_hop_dong.html")
    try:
        df = normalized_columns(pd.read_excel(request.FILES["file_excel"]))
    except Exception as exc:
        messages.error(request, f"Không đọc được file Excel: {exc}")
        return render(request, "quanly/import_hop_dong.html")
    created = updated = skipped = linked_journals = 0
    errors = []
    for row_no, (_, row) in enumerate(df.iterrows(), start=2):
        try:
            ma_doi_tac = clean_empty_excel_value(
                get_excel_value(row, "MaCbct", "MaCBCT", "Mã CBCT", "MaDoiTac", "Mã đối tác")
            )
            so_hd = clean_empty_excel_value(get_excel_value(row, "SoHopDong", "Số Hợp đồng", "Số HĐ"))
            if not ma_doi_tac or not so_hd:
                raise ValueError("Thiếu Mã CBCT/Đơn vị hoặc Số hợp đồng")

            ma_doi_tac = ma_doi_tac.upper()
            can_bo = None
            don_vi = None
            if ma_doi_tac.startswith("DV"):
                don_vi = DonVi.objects.filter(ma_don_vi__iexact=ma_doi_tac).first()
                if not don_vi:
                    raise ValueError(f"Không tìm thấy Đơn vị {ma_doi_tac}")
            else:
                can_bo = CanBo.objects.filter(ma_can_bo__iexact=ma_doi_tac).first()
                if not can_bo:
                    raise ValueError(f"Không tìm thấy CBCT {ma_doi_tac}")

            nhom_value = clean_empty_excel_value(get_excel_value(row, "NhomHD", "Nhóm HĐ"))
            nhom_hd = resolve_contract_group(nhom_value)
            if not nhom_hd:
                raise ValueError(f"Không tìm thấy Nhóm hợp đồng '{nhom_value}'")

            phan_bo = None
            if can_bo:
                phan_bo = PhanBoChiTieu.objects.filter(
                    can_bo=can_bo,
                    nhom_hd=nhom_hd,
                ).order_by("-ngay_lap", "-id").first()
                if not phan_bo:
                    raise ValueError(
                        f"Không tìm thấy phân bổ của CBCT {ma_doi_tac} cho Nhóm HĐ {nhom_hd.ma_nhom_hd}"
                    )

            ngay_ky = parse_date(get_excel_value(row, "NgayKy", "Ngày ký"))
            tu_ngay = parse_date(get_excel_value(row, "TuNgay", "Từ ngày"))
            den_ngay = parse_date(get_excel_value(row, "DenNgay", "Đến ngày"))
            if not tu_ngay or not den_ngay:
                raise ValueError("Thiếu Từ ngày hoặc Đến ngày")
            if den_ngay < tu_ngay:
                raise ValueError("Đến ngày không được trước Từ ngày")
            with transaction.atomic():
                proposal = None
                if phan_bo:
                    proposal = phan_bo.de_xuat_hop_dong.order_by("-lan_de_xuat", "-id").first()
                    if not proposal:
                        gia_tri_du_kien = calculate_expected_value(
                            phan_bo.so_tre_phcn,
                            phan_bo.so_buoi_phcn,
                            phan_bo.dinh_muc_di_lai_phcn,
                            phan_bo.so_tre_cs,
                            phan_bo.so_buoi_cs,
                            phan_bo.dinh_muc_di_lai_cs,
                        )
                        proposal = DeXuatHopDong.objects.create(
                            phan_bo=phan_bo,
                            so_tre_phcn=phan_bo.so_tre_phcn,
                            so_buoi_phcn=phan_bo.so_buoi_phcn,
                            so_tre_cs=phan_bo.so_tre_cs,
                            so_buoi_cs=phan_bo.so_buoi_cs,
                            gia_tri_du_kien=gia_tri_du_kien,
                            trang_thai="DA_DUYET",
                        )

                defaults = {
                    "de_xuat": proposal,
                    "can_bo": can_bo,
                    "don_vi": don_vi,
                    "nhom_hd": nhom_hd,
                    "ngay_ky": ngay_ky,
                    "tu_ngay": tu_ngay,
                    "den_ngay": den_ngay,
                    # Đơn vị thanh toán công can thiệp theo cơ chế riêng.
                    "don_gia_cong": FinancialConfig.DON_GIA_CONG if can_bo else Decimal("0"),
                    "dinh_muc_di_lai_phcn": phan_bo.dinh_muc_di_lai_phcn if phan_bo else Decimal("0"),
                    "dinh_muc_di_lai_cs": phan_bo.dinh_muc_di_lai_cs if phan_bo else Decimal("0"),
                    "gia_tri_hop_dong": proposal.gia_tri_du_kien if proposal else Decimal("0"),
                    "trang_thai": "DA_KY",
                    "ghi_chu": "Hợp đồng đơn vị; thanh toán công can thiệp theo cơ chế riêng."
                    if don_vi else None,
                }
                contract, is_created = HopDong.objects.update_or_create(
                    so_hop_dong=so_hd,
                    defaults=defaults,
                )
                journal_group_filter = (
                    Q(nhom_hd_nguon=nhom_hd)
                    | Q(phan_cong__nhom_hd=nhom_hd)
                    | Q(phan_cong__phan_bo__nhom_hd=nhom_hd)
                )
                journal_candidates = NhatKyThucHien.objects.filter(
                    journal_group_filter,
                    ngay_thuc_hien__gte=tu_ngay,
                    ngay_thuc_hien__lte=den_ngay,
                ).filter(Q(hop_dong__isnull=True) | Q(hop_dong=contract))
                if can_bo:
                    journal_candidates = journal_candidates.filter(
                        Q(can_bo_nguon=can_bo)
                        | Q(phan_cong__can_bo_nguon=can_bo)
                        | Q(phan_cong__phan_bo__can_bo=can_bo)
                    )
                    linked_journals += journal_candidates.filter(hop_dong__isnull=True).count()
                    journal_candidates.update(hop_dong=contract)
                else:
                    linked_journals += journal_candidates.filter(hop_dong__isnull=True).count()
                    journal_candidates.update(
                        hop_dong=contract,
                        don_gia_cong=Decimal("0"),
                        dinh_muc_di_lai=Decimal("0"),
                        thanh_tien=Decimal("0"),
                    )
                if proposal and proposal.trang_thai != "DA_TAO_HOP_DONG":
                    proposal.trang_thai = "DA_TAO_HOP_DONG"
                    proposal.save(update_fields=["trang_thai", "updated_at"])
            created += int(is_created)
            updated += int(not is_created)
        except Exception as exc:
            skipped += 1
            errors.append(f"Dòng {row_no}: {exc}")
    msg = (
        f"Import hợp đồng hoàn tất: thêm {created}, cập nhật {updated}, bỏ qua {skipped}; "
        f"liên kết thêm {linked_journals} nhật ký."
    )
    if errors:
        messages.warning(request, msg)
        for error in errors:
            messages.warning(request, error)
    else:
        messages.success(request, msg + " Dữ liệu đã được lưu vào cơ sở dữ liệu.")
    return redirect("danh_sach_hop_dong")


@hopdong_required
def chi_tiet_hop_dong(request, pk):
    hop_dong = get_object_or_404(
        HopDong.objects.select_related("can_bo", "don_vi", "nhom_hd", "de_xuat__phan_bo"),
        pk=pk,
    )
    khoi_luong = hop_dong.chi_tiet_khoi_luong.all().order_by("loai_dich_vu")
    phu_luc = hop_dong.phu_luc.all().prefetch_related("chi_tiet_phan_cong").order_by("-ngay_lap", "-id")
    ky_choices = []
    if hop_dong.de_xuat_id:
        ky_choices = (
            PhanCongTre.objects.filter(
                phan_bo=hop_dong.de_xuat.phan_bo,
                ky_phan_cong__gte=2,
                tu_dong_tu_nhat_ky=False,
            )
            .values_list("ky_phan_cong", flat=True)
            .distinct()
            .order_by("ky_phan_cong")
        )

    journals = hop_dong.nhat_ky_thuc_hien.all()
    if hop_dong.de_xuat_id:
        snapshots = list(
            ChiTietPhuLucPhanCong.objects.filter(
                phu_luc__hop_dong=hop_dong,
                phu_luc__loai_phu_luc="KY_1",
            ).order_by("id")
        )
        if snapshots:
            summary_sources = [
                {
                    "ma_tre": item.ma_tre,
                    "ten_tre": item.ten_tre,
                    "loai_dich_vu": item.loai_dich_vu,
                    "loai_dich_vu_display": item.get_loai_dich_vu_display(),
                    "planned_sessions": item.so_buoi_du_kien,
                }
                for item in snapshots
            ]
        else:
            assignments = (
                PhanCongTre.objects.filter(
                    phan_bo=hop_dong.de_xuat.phan_bo,
                    ky_phan_cong=1,
                    tu_dong_tu_nhat_ky=False,
                )
                .select_related("tre")
                .order_by("id")
            )
            summary_sources = [
                {
                    "ma_tre": item.tre.ma_tre,
                    "ten_tre": item.tre.ho_ten,
                    "loai_dich_vu": item.loai_dich_vu,
                    "loai_dich_vu_display": item.get_loai_dich_vu_display(),
                    "planned_sessions": item.so_buoi_du_kien,
                }
                for item in assignments
            ]
    else:
        assignments = (
            PhanCongTre.objects.filter(nhat_ky_thuc_hien__hop_dong=hop_dong)
            .select_related("tre")
            .distinct()
            .order_by("tre__ho_ten", "loai_dich_vu", "id")
        )
        summary_sources = [
            {
                "ma_tre": item.tre.ma_tre,
                "ten_tre": item.tre.ho_ten,
                "loai_dich_vu": item.loai_dich_vu,
                "loai_dich_vu_display": item.get_loai_dich_vu_display(),
                "planned_sessions": item.so_buoi_du_kien,
            }
            for item in assignments
        ]

    actual_by_child_service = {
        (row["phan_cong__tre__ma_tre"], row["phan_cong__loai_dich_vu"]): row
        for row in journals.values(
            "phan_cong__tre__ma_tre",
            "phan_cong__loai_dich_vu",
        ).annotate(
            actual_sessions=Sum("so_buoi_thuc_hien"),
            parent_travel=Sum("so_luot_di_lai"),
        )
    }
    journal_summary = []
    for source in summary_sources:
        actual = actual_by_child_service.get(
            (source["ma_tre"], source["loai_dich_vu"]),
            {},
        )
        actual_sessions = actual.get("actual_sessions") or 0
        planned_sessions = source["planned_sessions"] or 0
        if actual_sessions <= 0:
            status = "Chưa can thiệp"
            status_class = "bg-secondary"
        elif planned_sessions > 0 and actual_sessions >= planned_sessions:
            status = "Hoàn thành"
            status_class = "bg-success"
        else:
            status = "Đang can thiệp"
            status_class = "bg-warning text-dark"
        journal_summary.append({
            **source,
            "planned_sessions": planned_sessions,
            "actual_sessions": actual_sessions,
            "parent_travel": actual.get("parent_travel") or 0,
            "status": status,
            "status_class": status_class,
        })
    dot_thanh_toan = hop_dong.dot_thanh_toan.prefetch_related("chi_tiet").order_by("-nam", "-thang", "-id")
    dot_thanh_toan_ph = hop_dong.dot_thanh_toan_phu_huynh.prefetch_related("chi_tiet").order_by("-nam", "-thang", "-id")
    return render(
        request,
        "quanly/chi_tiet_hop_dong.html",
        {
            "hop_dong": hop_dong,
            "khoi_luong": khoi_luong,
            "phu_luc": phu_luc,
            "ky_choices": ky_choices,
            "journal_summary": journal_summary,
            "dot_thanh_toan": dot_thanh_toan,
            "dot_thanh_toan_ph": dot_thanh_toan_ph,
        },
    )


@hopdong_required
def xuat_bo_hop_dong(request, pk):
    hop_dong = get_object_or_404(
        HopDong.objects.select_related("can_bo", "don_vi", "de_xuat__phan_bo"),
        pk=pk,
    )
    if hop_dong.la_hop_dong_don_vi:
        messages.error(request, "Hợp đồng đơn vị sử dụng cơ chế hồ sơ riêng, không xuất theo mẫu HĐ cá nhân.")
        return redirect("chi_tiet_hop_dong", pk=hop_dong.pk)
    try:
        output = export_contract_bundle(hop_dong)
    except ValidationError as exc:
        messages.error(request, str(exc))
        return redirect("chi_tiet_hop_dong", pk=hop_dong.pk)

    response = HttpResponse(
        output.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    filename = (
        f"HDDV - {safe_download_component(hop_dong.so_hop_dong)} - "
        f"{safe_download_component(hop_dong.can_bo.ma_can_bo)}_"
        f"{safe_download_component(hop_dong.can_bo.ho_ten)}.docx"
    )
    response["Content-Disposition"] = content_disposition_filename(filename)
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
    if _is_operationally_locked(hop_dong) and not is_admin_user(request.user):
        messages.error(request, "Hợp đồng đã khóa, chỉ Admin mới được thêm nhật ký.")
        return redirect("chi_tiet_hop_dong", pk=hop_dong.pk)
    form = NhatKyThucHienForm(request.POST or None, hop_dong=hop_dong)
    if request.method == "POST" and form.is_valid():
        item = form.save(commit=False)
        item.hop_dong = hop_dong
        effective_staff = item.can_bo_hieu_luc
        if not item.pk and effective_staff:
            item.lan_thanh_toan = next_payment_round(effective_staff, item.ky_can_thiep)
        item.dia_diem_ct = item.dia_diem_ct or item.phan_cong.dia_diem_ct
        is_cs = PhanCongTre.service_group(item.phan_cong.loai_dich_vu) == "CS"
        if hop_dong.la_hop_dong_don_vi:
            item.don_gia_cong = Decimal("0")
            item.dinh_muc_di_lai = Decimal("0")
        else:
            item.don_gia_cong = FinancialConfig.DON_GIA_CONG
            allocation = hop_dong.de_xuat.phan_bo
            item.dinh_muc_di_lai = allocation.dinh_muc_di_lai_cs if is_cs else allocation.dinh_muc_di_lai_phcn
        item.save()
        if item.canh_bao_trung:
            messages.warning(request, f"Đã lưu nhưng phát hiện trùng lịch: {item.chi_tiet_trung}. Bản ghi đã chuyển vào Danh sách trùng.")
        messages.success(request, "Đã ghi nhận nhật ký thực hiện.")
        return redirect("chi_tiet_hop_dong", pk=hop_dong.pk)
    return render(request, "quanly/them_nhat_ky_thuc_hien.html", {"form": form, "hop_dong": hop_dong})


@hopdong_required
def them_nhat_ky_can_thiep(request):
    form = NhatKyCanThiepForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        item = form.save(commit=False)
        if item.hop_dong_id and _is_operationally_locked(item.hop_dong) and not is_admin_user(request.user):
            messages.error(request, "Hợp đồng đã khóa, chỉ Admin mới được thêm nhật ký.")
            return redirect("nhat_ky_can_thiep")
        effective_staff = item.can_bo_hieu_luc
        if not item.pk and effective_staff:
            item.lan_thanh_toan = next_payment_round(effective_staff, item.ky_can_thiep)
        item.dia_diem_ct = item.dia_diem_ct or item.phan_cong.dia_diem_ct
        if item.hop_dong.la_hop_dong_don_vi:
            item.don_gia_cong = Decimal("0")
            item.dinh_muc_di_lai = Decimal("0")
        else:
            item.don_gia_cong = FinancialConfig.DON_GIA_CONG
            item.dinh_muc_di_lai = item.hop_dong.dinh_muc_di_lai_cs if PhanCongTre.service_group(item.phan_cong.loai_dich_vu) == "CS" else item.hop_dong.dinh_muc_di_lai_phcn
        item.save()
        if item.canh_bao_trung:
            messages.warning(request, f"Đã lưu nhưng phát hiện trùng lịch: {item.chi_tiet_trung}. Bản ghi đã chuyển vào Danh sách trùng.")
        messages.success(request, "Đã thêm nhật ký và lưu vào cơ sở dữ liệu.")
        return redirect("nhat_ky_can_thiep")
    return render(request, "quanly/them_nhat_ky_can_thiep.html", {"form": form})


@hopdong_required
def sua_nhat_ky_can_thiep(request, pk):
    item = get_object_or_404(
        NhatKyThucHien.objects.select_related("hop_dong", "phan_cong"),
        pk=pk,
    )
    if item.hop_dong_id and _is_operationally_locked(item.hop_dong) and not is_admin_user(request.user):
        messages.error(request, "Hợp đồng đã khóa, chỉ Admin mới được sửa nhật ký.")
        return redirect("nhat_ky_can_thiep")
    form = NhatKyCanThiepForm(
        request.POST or None,
        instance=item,
        require_contract=False,
    )
    if request.method == "POST" and form.is_valid():
        updated = form.save(commit=False)
        updated.dia_diem_ct = updated.dia_diem_ct or updated.phan_cong.dia_diem_ct
        if updated.hop_dong_id:
            if updated.hop_dong.la_hop_dong_don_vi:
                updated.don_gia_cong = Decimal("0")
                updated.dinh_muc_di_lai = Decimal("0")
            else:
                updated.don_gia_cong = updated.hop_dong.don_gia_cong
                updated.dinh_muc_di_lai = (
                    updated.hop_dong.dinh_muc_di_lai_cs
                    if PhanCongTre.service_group(updated.phan_cong.loai_dich_vu) == "CS"
                    else updated.hop_dong.dinh_muc_di_lai_phcn
                )
        updated.save()
        if updated.canh_bao_trung:
            messages.warning(request, f"Đã lưu nhưng phát hiện trùng lịch: {updated.chi_tiet_trung}. Bản ghi đã chuyển vào Danh sách trùng.")
        messages.success(request, "Đã cập nhật nhật ký can thiệp.")
        return redirect("nhat_ky_can_thiep")
    return render(request, "quanly/them_nhat_ky_can_thiep.html", {
        "form": form,
        "page_title": "Sửa nhật ký can thiệp",
        "submit_label": "Lưu thay đổi",
    })


@hopdong_required
def xoa_nhat_ky_can_thiep(request, pk):
    if request.method != "POST":
        return redirect("nhat_ky_can_thiep")
    item = get_object_or_404(NhatKyThucHien, pk=pk)
    if item.hop_dong_id and _is_operationally_locked(item.hop_dong) and not is_admin_user(request.user):
        messages.error(request, "Hợp đồng đã khóa, chỉ Admin mới được xóa nhật ký.")
        return redirect("nhat_ky_can_thiep")
    try:
        item.delete()
        messages.success(request, "Đã xóa nhật ký can thiệp.")
    except ProtectedError:
        messages.error(request, "Không thể xóa nhật ký đã được sử dụng trong hồ sơ thanh toán.")
    return redirect("nhat_ky_can_thiep")


@hopdong_required
def tao_dot_thanh_toan(request, hop_dong_id):
    hop_dong = get_object_or_404(HopDong, pk=hop_dong_id)
    if _is_operationally_locked(hop_dong) and not is_admin_user(request.user):
        messages.error(request, "Hợp đồng đã khóa, chỉ Admin mới được tạo đợt thanh toán.")
        return redirect("chi_tiet_hop_dong", pk=hop_dong.pk)
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


@admin_required
def sua_dot_thanh_toan(request, pk):
    dot = get_object_or_404(DotThanhToan.objects.select_related("hop_dong"), pk=pk)
    form = DotThanhToanForm(request.POST or None, instance=dot)
    if request.method == "POST" and form.is_valid():
        try:
            form.save()
        except IntegrityError:
            form.add_error(None, "Đợt thanh toán tháng/năm này đã tồn tại cho hợp đồng.")
        else:
            messages.success(request, "Đã cập nhật đợt thanh toán.")
            return redirect("chi_tiet_dot_thanh_toan", pk=dot.pk)
    return render(request, "quanly/sua_dot_thanh_toan.html", {"form": form, "dot": dot})


@admin_required
def xoa_dot_thanh_toan(request, pk):
    if request.method != "POST":
        return redirect("chi_tiet_dot_thanh_toan", pk=pk)
    dot = get_object_or_404(DotThanhToan, pk=pk)
    try:
        dot.delete()
        messages.success(request, "Đã xóa đợt thanh toán.")
        return redirect("chi_tiet_hop_dong", pk=dot.hop_dong_id)
    except ProtectedError:
        messages.error(request, "Không thể xóa đợt thanh toán vì đã có chi tiết thanh toán liên kết.")
        return redirect("chi_tiet_dot_thanh_toan", pk=dot.pk)


@admin_required
def sua_chi_tiet_thanh_toan(request, pk):
    item = get_object_or_404(
        ChiTietThanhToan.objects.select_related("dot_thanh_toan__hop_dong", "nhat_ky"),
        pk=pk,
    )
    dot = item.dot_thanh_toan
    form = ChiTietThanhToanForm(request.POST or None, instance=item, hop_dong=dot.hop_dong)
    if request.method == "POST" and form.is_valid():
        updated = form.save(commit=False)
        updated.dot_thanh_toan = dot
        try:
            updated.save()
        except ValidationError as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, "Đã cập nhật chi tiết thanh toán.")
            return redirect("chi_tiet_dot_thanh_toan", pk=dot.pk)
    return render(request, "quanly/sua_chi_tiet_thanh_toan.html", {"form": form, "dot": dot, "item": item})


@admin_required
def xoa_chi_tiet_thanh_toan(request, pk):
    if request.method != "POST":
        return redirect("chi_tiet_dot_thanh_toan", pk=get_object_or_404(ChiTietThanhToan, pk=pk).dot_thanh_toan_id)
    item = get_object_or_404(ChiTietThanhToan, pk=pk)
    dot_id = item.dot_thanh_toan_id
    try:
        item.delete()
        messages.success(request, "Đã xóa chi tiết thanh toán.")
    except ProtectedError:
        messages.error(request, "Không thể xóa chi tiết thanh toán đang được dữ liệu khác sử dụng.")
    return redirect("chi_tiet_dot_thanh_toan", pk=dot_id)


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
    if _is_operationally_locked(hop_dong) and not is_admin_user(request.user):
        messages.error(request, "Hợp đồng đã khóa/thanh lý, chỉ Admin mới được sửa nghiệm thu.")
        return redirect("chi_tiet_hop_dong", pk=hop_dong.pk)
    record = NghiemThu.objects.filter(hop_dong=hop_dong).first()
    journal_total = NhatKyThucHien.objects.filter(hop_dong=hop_dong).aggregate(total=Sum("thanh_tien"))["total"] or Decimal("0")
    if request.method == "POST":
        form = NghiemThuForm(request.POST, instance=record, hop_dong=hop_dong)
        if form.is_valid():
            try:
                with transaction.atomic():
                    obj = form.save(commit=False)
                    obj.hop_dong = hop_dong
                    obj.save()
                    sync_trang_thai_hop_dong(hop_dong)
                messages.success(request, "Đã lưu thông tin nghiệm thu.")
                return redirect("chi_tiet_hop_dong", pk=hop_dong.pk)
            except ValidationError as exc:
                form.add_error(None, str(exc))
    else:
        instance = record or NghiemThu(gia_tri_nghiem_thu=journal_total)
        form = NghiemThuForm(instance=instance, hop_dong=hop_dong)
    return render(request, "quanly/cap_nhat_nghiem_thu.html", {"form": form, "hop_dong": hop_dong, "record": record, "journal_total": journal_total})


@hopdong_required
def cap_nhat_thanh_ly(request, hop_dong_id):
    hop_dong = get_object_or_404(HopDong.objects.select_related("de_xuat__phan_bo"), pk=hop_dong_id)
    if _is_operationally_locked(hop_dong) and not is_admin_user(request.user):
        messages.error(request, "Hợp đồng đã khóa/thanh lý, chỉ Admin mới được sửa thanh lý.")
        return redirect("chi_tiet_hop_dong", pk=hop_dong.pk)
    acceptance = NghiemThu.objects.filter(hop_dong=hop_dong).first()
    if not acceptance or not acceptance.ngay_nghiem_thu or acceptance.ket_qua != "DAT":
        messages.error(request, "Chỉ được thanh lý sau khi đã lập biên bản nghiệm thu.")
        return redirect("chi_tiet_hop_dong", pk=hop_dong.pk)
    record = ThanhLyHopDong.objects.filter(hop_dong=hop_dong).first()
    if request.method == "POST":
        form = ThanhLyHopDongForm(request.POST, instance=record)
        if form.is_valid():
            try:
                with transaction.atomic():
                    obj = form.save(commit=False)
                    obj.hop_dong = hop_dong
                    obj.gia_tri_thanh_ly = acceptance.gia_tri_nghiem_thu
                    obj.save()
                    sync_trang_thai_hop_dong(hop_dong)
                messages.success(request, "Đã lưu thông tin thanh lý hợp đồng.")
                return redirect("chi_tiet_hop_dong", pk=hop_dong.pk)
            except ValidationError as exc:
                form.add_error(None, str(exc))
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
        if not record.ngay_nghiem_thu or record.ket_qua != "DAT":
            raise ValidationError("Hồ sơ nghiệm thu chưa có ngày và kết quả Đạt.")
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
    if _is_operationally_locked(hop_dong) and not is_admin_user(request.user):
        messages.error(request, "Hợp đồng đã khóa, chỉ Admin mới được tạo đợt thanh toán đi lại phụ huynh.")
        return redirect("chi_tiet_hop_dong", pk=hop_dong.pk)
    form_instance = DotThanhToanDiLaiPhuHuynh(hop_dong=hop_dong)
    if request.method == "POST":
        form = DotThanhToanDiLaiPhuHuynhForm(request.POST, instance=form_instance)
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
        form = DotThanhToanDiLaiPhuHuynhForm(instance=form_instance, initial={
            "nam": timezone.localdate().year,
            "thang": timezone.localdate().month,
            "tu_ngay": hop_dong.tu_ngay,
            "den_ngay": hop_dong.den_ngay,
        })
    return render(request, "quanly/tao_dot_thanh_toan_phu_huynh.html", {"form": form, "hop_dong": hop_dong})


def _parent_travel_group_journals(nhom_hd, ky_can_thiep, nam, thang, include_locked=True):
    group_filter = (
        Q(nhom_hd_nguon=nhom_hd)
        | Q(nhom_hd_nguon__isnull=True, phan_cong__nhom_hd=nhom_hd)
        | Q(nhom_hd_nguon__isnull=True, phan_cong__nhom_hd__isnull=True, phan_cong__phan_bo__nhom_hd=nhom_hd)
    )
    queryset = NhatKyThucHien.objects.filter(
        group_filter,
        ky_can_thiep=ky_can_thiep,
        ngay_thuc_hien__year=nam,
        ngay_thuc_hien__month=thang,
        so_luot_di_lai__gt=0,
    ).select_related(
        "nhom_hd_nguon",
        "hop_dong",
        "phan_cong__nhom_hd",
        "phan_cong__phan_bo__nhom_hd",
    )
    if not include_locked:
        queryset = queryset.exclude(hop_dong__is_locked=True).exclude(hop_dong__trang_thai="THANH_LY")
    return queryset.order_by("ngay_thuc_hien", "id")


def _sync_parent_travel_group_dot(dot, journals):
    """Bổ sung nhật ký còn thiếu vào đợt theo Nhóm HĐ + Kỳ, không ghi trùng lượt."""
    paid_by_journal = dict(
        ChiTietThanhToanDiLaiPhuHuynh.objects.filter(nhat_ky_id__in=[journal.pk for journal in journals])
        .values("nhat_ky_id")
        .annotate(total=Sum("so_luot_di_lai"))
        .values_list("nhat_ky_id", "total")
    )
    added = 0
    for journal in journals:
        already_paid = paid_by_journal.get(journal.pk, 0)
        remaining = journal.so_luot_di_lai - already_paid
        if remaining <= 0:
            continue
        ChiTietThanhToanDiLaiPhuHuynh.objects.create(
            dot_thanh_toan=dot,
            nhat_ky=journal,
            so_luot_di_lai=remaining,
            dinh_muc_di_lai=journal.dinh_muc_di_lai,
        )
        added += 1
    return added


def _parent_travel_dot_is_locked(dot):
    if dot.hop_dong_id:
        return _is_operationally_locked(dot.hop_dong)
    return dot.chi_tiet.filter(
        Q(nhat_ky__hop_dong__is_locked=True) | Q(nhat_ky__hop_dong__trang_thai="THANH_LY")
    ).exists()


@hopdong_required
def tao_dot_thanh_toan_di_lai_phu_huynh_theo_nhom(request):
    initial = {
        "nam": timezone.localdate().year,
        "thang": timezone.localdate().month,
    }
    if request.method == "GET":
        if request.GET.get("nhom_hd", "").isdigit():
            initial["nhom_hd"] = int(request.GET["nhom_hd"])
        if request.GET.get("ky", "").isdigit():
            initial["ky_can_thiep"] = int(request.GET["ky"])
        if request.GET.get("nam", "").isdigit():
            initial["nam"] = int(request.GET["nam"])
        if request.GET.get("thang", "").isdigit():
            initial["thang"] = int(request.GET["thang"])
    existing_dot = None
    if request.method == "POST":
        raw_scope = [request.POST.get(name, "").strip() for name in ("nhom_hd", "ky_can_thiep", "nam", "thang")]
        if raw_scope[0].isdigit() and raw_scope[1].isdigit() and raw_scope[2].isdigit() and raw_scope[3].isdigit():
            existing_dot = DotThanhToanDiLaiPhuHuynh.objects.filter(
                nhom_hd_id=int(raw_scope[0]),
                ky_can_thiep=int(raw_scope[1]),
                nam=int(raw_scope[2]),
                thang=int(raw_scope[3]),
            ).first()
    form = DotThanhToanDiLaiPhuHuynhTheoNhomForm(
        request.POST or None,
        instance=existing_dot,
        initial=initial if request.method == "GET" else None,
    )
    journal_count = 0
    journal_units = 0
    if request.method == "POST" and form.is_valid():
        nhom_hd = form.cleaned_data["nhom_hd"]
        ky_can_thiep = form.cleaned_data["ky_can_thiep"]
        nam = form.cleaned_data["nam"]
        thang = form.cleaned_data["thang"]
        if existing_dot and _parent_travel_dot_is_locked(existing_dot) and not is_admin_user(request.user):
            form.add_error(None, "Đợt thanh toán đã có nhật ký thuộc hợp đồng khóa/thanh lý, chỉ Admin mới được cập nhật.")
            journals = []
        else:
            journals = list(_parent_travel_group_journals(
                nhom_hd,
                ky_can_thiep,
                nam,
                thang,
                include_locked=is_admin_user(request.user),
            ))
        if not journals and not form.errors:
            form.add_error(None, "Không có nhật ký có lượt đi lại phù hợp với Nhóm HĐ và Kỳ đã chọn.")
        elif journals:
            dot = None
            added_count = 0
            try:
                with transaction.atomic():
                    dot = form.save()
                    added_count = _sync_parent_travel_group_dot(dot, journals)
            except IntegrityError:
                dot = DotThanhToanDiLaiPhuHuynh.objects.filter(
                    nhom_hd=nhom_hd,
                    ky_can_thiep=ky_can_thiep,
                    nam=nam,
                    thang=thang,
                ).first()
                if dot:
                    with transaction.atomic():
                        added_count = _sync_parent_travel_group_dot(dot, journals)
                else:
                    form.add_error(None, "Đợt thanh toán theo Nhóm HĐ, Kỳ, tháng và năm này đã tồn tại.")
            if dot and not form.errors:
                messages.success(request, f"Đã gom đủ {len(journals)} nhật ký; bổ sung {added_count} dòng còn thiếu.")
                return redirect("chi_tiet_dot_thanh_toan_phu_huynh", pk=dot.pk)
        journal_count = len(journals)
        journal_units = sum(journal.so_luot_di_lai for journal in journals)
    elif request.method == "GET":
        group_id = initial.get("nhom_hd")
        ky = initial.get("ky_can_thiep")
        nam = initial.get("nam")
        thang = initial.get("thang")
        if group_id and ky:
            nhom = NhomHD.objects.filter(pk=group_id).first()
            if nhom:
                preview = _parent_travel_group_journals(
                    nhom,
                    ky,
                    nam,
                    thang,
                    include_locked=is_admin_user(request.user),
                )
                journal_count = preview.count()
                journal_units = preview.aggregate(total=Sum("so_luot_di_lai"))["total"] or 0
                contracts = [journal.hop_dong for journal in preview if journal.hop_dong and journal.hop_dong.tu_ngay and journal.hop_dong.den_ngay]
                if contracts:
                    form.initial.setdefault("tu_ngay", min(contract.tu_ngay for contract in contracts))
                    form.initial.setdefault("den_ngay", max(contract.den_ngay for contract in contracts))
    return render(request, "quanly/tao_dot_thanh_toan_di_lai_phu_huynh_theo_nhom.html", {
        "form": form,
        "journal_count": journal_count,
        "journal_units": journal_units,
    })


@hopdong_required
def danh_sach_gia_han_hop_dong(request):
    query = request.GET.get("q", "").strip()
    loai = request.GET.get("loai", "").strip()
    qs = (
        PhuLucHopDong.objects.filter(loai_phu_luc__in={"GIA_HAN_THOI_GIAN", "GIA_HAN_KHOI_LUONG"})
        .select_related("hop_dong__can_bo", "hop_dong__don_vi", "hop_dong__nhom_hd")
        .prefetch_related("chi_tiet_gia_han_khoi_luong")
        .order_by("-ngay_lap", "-id")
    )
    if query:
        qs = qs.filter(
            Q(so_phu_luc__icontains=query)
            | Q(hop_dong__so_hop_dong__icontains=query)
            | Q(hop_dong__can_bo__ma_can_bo__icontains=query)
            | Q(hop_dong__can_bo__ho_ten__icontains=query)
        )
    if loai in {"GIA_HAN_THOI_GIAN", "GIA_HAN_KHOI_LUONG"}:
        qs = qs.filter(loai_phu_luc=loai)
    kpi = {
        "total": qs.count(),
        "time": qs.filter(loai_phu_luc="GIA_HAN_THOI_GIAN").count(),
        "volume": qs.filter(loai_phu_luc="GIA_HAN_KHOI_LUONG").count(),
        "unsigned": qs.filter(is_signed=False).count(),
    }
    return render(request, "quanly/danh_sach_gia_han_hop_dong.html", {
        "extensions": qs,
        "kpi": kpi,
        "query": query,
        "loai": loai,
        "loai_choices": [
            ("GIA_HAN_THOI_GIAN", "Gia hạn thời gian"),
            ("GIA_HAN_KHOI_LUONG", "Gia hạn khối lượng"),
        ],
    })


def _sync_hop_dong_from_signed_extensions(hop_dong, fallback_end=None, fallback_total=None, fallback_volume=None):
    """Đồng bộ HĐ theo các phụ lục đã ký, kể cả khi Admin bỏ ký một phụ lục."""
    time_extensions = hop_dong.phu_luc.filter(
        loai_phu_luc="GIA_HAN_THOI_GIAN",
        den_ngay_moi__isnull=False,
    ).order_by("ngay_lap", "id")
    signed_time = time_extensions.filter(is_signed=True).order_by("-ngay_lap", "-id").first()
    first_time = time_extensions.first()
    effective_end = (
        signed_time.den_ngay_moi
        if signed_time
        else (first_time.den_ngay_cu if first_time else fallback_end if fallback_end is not None else hop_dong.den_ngay)
    )

    volume_extensions = hop_dong.phu_luc.filter(
        loai_phu_luc="GIA_HAN_KHOI_LUONG",
    ).prefetch_related("chi_tiet_gia_han_khoi_luong").order_by("ngay_lap", "id")
    signed_volume = volume_extensions.filter(is_signed=True).order_by("-ngay_lap", "-id").first()
    first_volume = volume_extensions.first()
    effective_volume = signed_volume or first_volume
    if signed_volume:
        effective_total = signed_volume.tong_tien_moi
    elif first_volume:
        effective_total = first_volume.tong_tien_moi - first_volume.tong_tien_tang_them
    else:
        if fallback_total is not None:
            effective_total = fallback_total
        else:
            detail_total = ChiTietKhoiLuongHopDong.objects.filter(hop_dong=hop_dong).aggregate(
                total=Sum("thanh_tien")
            )["total"]
            effective_total = detail_total if detail_total is not None else hop_dong.gia_tri_hop_dong

    update_fields = []
    if hop_dong.den_ngay != effective_end:
        hop_dong.den_ngay = effective_end
        update_fields.append("den_ngay")
    if hop_dong.gia_tri_hop_dong != effective_total:
        hop_dong.gia_tri_hop_dong = effective_total
        update_fields.append("gia_tri_hop_dong")
    if update_fields:
        update_fields.append("updated_at")
        hop_dong.save(update_fields=update_fields)

    effective_services = set()
    if effective_volume:
        is_signed = bool(signed_volume)
        for detail in effective_volume.chi_tiet_gia_han_khoi_luong.all():
            effective_services.add(detail.loai_dich_vu)
            ChiTietKhoiLuongHopDong.objects.update_or_create(
                hop_dong=hop_dong,
                loai_dich_vu=detail.loai_dich_vu,
                defaults={
                    "so_tre": detail.so_tre_moi if is_signed else detail.so_tre_cu,
                    "so_buoi": detail.so_buoi_moi if is_signed else detail.so_buoi_cu,
                    "don_gia_cong": detail.don_gia_cong,
                    "dinh_muc_di_lai": detail.dinh_muc_di_lai,
                },
            )
    elif fallback_volume is not None:
        for detail in fallback_volume:
            effective_services.add(detail["loai_dich_vu"])
            ChiTietKhoiLuongHopDong.objects.update_or_create(
                hop_dong=hop_dong,
                loai_dich_vu=detail["loai_dich_vu"],
                defaults={
                    "so_tre": detail["so_tre"],
                    "so_buoi": detail["so_buoi"],
                    "don_gia_cong": detail["don_gia_cong"],
                    "dinh_muc_di_lai": detail["dinh_muc_di_lai"],
                },
            )
    if effective_services:
        ChiTietKhoiLuongHopDong.objects.filter(hop_dong=hop_dong).exclude(
            loai_dich_vu__in=effective_services
        ).delete()

    contract_details = list(ChiTietKhoiLuongHopDong.objects.filter(hop_dong=hop_dong))
    if contract_details:
        rate_fields = {
            "don_gia_cong": contract_details[0].don_gia_cong,
        }
        service_rates = {detail.loai_dich_vu: detail.dinh_muc_di_lai for detail in contract_details}
        if "VLTL" in service_rates:
            rate_fields["dinh_muc_di_lai_phcn"] = service_rates["VLTL"]
        if "CSXH" in service_rates:
            rate_fields["dinh_muc_di_lai_cs"] = service_rates["CSXH"]
        rate_update_fields = []
        for field, value in rate_fields.items():
            if getattr(hop_dong, field) != value:
                setattr(hop_dong, field, value)
                rate_update_fields.append(field)
        if rate_update_fields:
            hop_dong.save(update_fields=[*rate_update_fields, "updated_at"])


@hopdong_required
def them_gia_han_thoi_gian(request, hop_dong_id=None):
    selected = get_object_or_404(HopDong, pk=hop_dong_id) if hop_dong_id else None
    if selected and _is_operationally_locked(selected) and not is_admin_user(request.user):
        messages.error(request, "Hợp đồng đã khóa, chỉ Admin mới được thêm phụ lục gia hạn.")
        return redirect("danh_sach_gia_han_hop_dong")
    initial = {"hop_dong": selected} if selected else {}
    form = GiaHanThoiGianForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        hop_dong = form.cleaned_data["hop_dong"]
        if _is_operationally_locked(hop_dong) and not is_admin_user(request.user):
            messages.error(request, "Hợp đồng đã khóa, chỉ Admin mới được thêm phụ lục gia hạn.")
            return redirect("danh_sach_gia_han_hop_dong")
        with transaction.atomic():
            current_end = (
                PhuLucHopDong.objects.filter(hop_dong=hop_dong, loai_phu_luc="GIA_HAN_THOI_GIAN", den_ngay_moi__isnull=False)
                .order_by("-ngay_lap", "-id")
                .values_list("den_ngay_moi", flat=True)
                .first()
                or hop_dong.den_ngay
            )
            new_end = form.cleaned_data["den_ngay_moi"]
            if new_end <= current_end:
                form.add_error("den_ngay_moi", "Ngày kết thúc mới phải sau thời hạn gia hạn gần nhất.")
            else:
                extension = PhuLucHopDong.objects.create(
                    hop_dong=hop_dong,
                    loai_phu_luc="GIA_HAN_THOI_GIAN",
                    so_phu_luc=f"GH-TG-{hop_dong.so_hop_dong}",
                    ngay_lap=form.cleaned_data["ngay_lap"],
                    is_signed=form.cleaned_data["is_signed"],
                    den_ngay_cu=current_end,
                    den_ngay_moi=new_end,
                    tong_tien_moi=hop_dong.gia_tri_hop_dong,
                    ghi_chu=form.cleaned_data["ghi_chu"],
                )
                if extension.is_signed:
                    hop_dong.den_ngay = new_end
                    hop_dong.save(update_fields=["den_ngay", "updated_at"])
                messages.success(request, f"Đã lưu phụ lục gia hạn thời gian {extension.so_phu_luc}.")
                return redirect("danh_sach_gia_han_hop_dong")
    return render(request, "quanly/them_gia_han_thoi_gian.html", {
        "form": form,
        "hop_dong": selected,
        "contract_end_dates": form.contract_end_dates,
    })


@hopdong_required
def them_gia_han_khoi_luong(request, hop_dong_id=None):
    selected = get_object_or_404(HopDong, pk=hop_dong_id) if hop_dong_id else None
    if selected and _is_operationally_locked(selected) and not is_admin_user(request.user):
        messages.error(request, "Hợp đồng đã khóa, chỉ Admin mới được thêm phụ lục gia hạn.")
        return redirect("danh_sach_gia_han_hop_dong")
    form = GiaHanKhoiLuongForm(request.POST or None)
    if selected and request.method != "POST":
        form.initial["hop_dong"] = selected
        form.set_contract_initial(selected)
    if request.method == "POST" and form.is_valid():
        hop_dong = form.cleaned_data["hop_dong"]
        if _is_operationally_locked(hop_dong) and not is_admin_user(request.user):
            messages.error(request, "Hợp đồng đã khóa, chỉ Admin mới được thêm phụ lục gia hạn.")
            return redirect("danh_sach_gia_han_hop_dong")
        baseline = form.baseline(hop_dong)
        current_end = _current_contract_end(hop_dong)
        new_end = form.cleaned_data["den_ngay_moi"]
        rates = {
            "PHCN": (hop_dong.dinh_muc_di_lai_phcn, form.cleaned_data["so_tre_phcn_moi"], form.cleaned_data["so_buoi_phcn_moi"]),
            "CS": (hop_dong.dinh_muc_di_lai_cs, form.cleaned_data["so_tre_cs_moi"], form.cleaned_data["so_buoi_cs_moi"]),
        }
        amounts = form.calculate_amounts(
            hop_dong,
            {
                "phcn": (form.cleaned_data["so_tre_phcn_moi"], form.cleaned_data["so_buoi_phcn_moi"]),
                "cs": (form.cleaned_data["so_tre_cs_moi"], form.cleaned_data["so_buoi_cs_moi"]),
            },
        )
        with transaction.atomic():
            extension = PhuLucHopDong.objects.create(
                hop_dong=hop_dong,
                loai_phu_luc="GIA_HAN_KHOI_LUONG",
                so_phu_luc=f"GH-KL-{hop_dong.so_hop_dong}",
                ngay_lap=form.cleaned_data["ngay_lap"],
                is_signed=form.cleaned_data["is_signed"],
                den_ngay_cu=current_end,
                den_ngay_moi=new_end,
                tong_tien_tang_them=amounts["gia_tri_tang_them"],
                tong_tien_moi=amounts["tong_gia_tri_moi"],
                ghi_chu=form.cleaned_data["ghi_chu"],
            )
            for service, group in (("VLTL", "PHCN"), ("CSXH", "CS")):
                old_count, old_sessions = baseline[group.lower()]
                travel, new_count, new_sessions = rates[group]
                ChiTietGiaHanKhoiLuong.objects.create(
                    phu_luc=extension,
                    loai_dich_vu=service,
                    so_tre_cu=old_count,
                    so_tre_moi=new_count,
                    so_buoi_cu=old_sessions,
                    so_buoi_moi=new_sessions,
                    don_gia_cong=hop_dong.don_gia_cong,
                    dinh_muc_di_lai=travel,
                )
            if extension.is_signed:
                hop_dong.gia_tri_hop_dong = amounts["tong_gia_tri_moi"]
                hop_dong.save(update_fields=["gia_tri_hop_dong", "updated_at"])
                for service, group in (("VLTL", "PHCN"), ("CSXH", "CS")):
                    travel, new_count, new_sessions = rates[group]
                    ChiTietKhoiLuongHopDong.objects.update_or_create(
                        hop_dong=hop_dong,
                        loai_dich_vu=service,
                        defaults={
                            "so_tre": new_count,
                            "so_buoi": new_sessions,
                            "don_gia_cong": hop_dong.don_gia_cong,
                            "dinh_muc_di_lai": travel,
                        },
                    )
        messages.success(request, f"Đã lưu phụ lục gia hạn khối lượng {extension.so_phu_luc}.")
        return redirect("danh_sach_gia_han_hop_dong")
    return render(request, "quanly/them_gia_han_khoi_luong.html", {
        "form": form,
        "hop_dong": selected,
        "contract_metrics": form.contract_metrics(),
    })


@admin_required
def sua_gia_han_hop_dong(request, pk):
    extension = get_object_or_404(
        PhuLucHopDong.objects.select_related("hop_dong").prefetch_related("chi_tiet_gia_han_khoi_luong"),
        pk=pk,
        loai_phu_luc__in={"GIA_HAN_THOI_GIAN", "GIA_HAN_KHOI_LUONG"},
    )
    is_volume = extension.loai_phu_luc == "GIA_HAN_KHOI_LUONG"
    form_class = GiaHanKhoiLuongForm if is_volume else GiaHanThoiGianForm
    form = form_class(request.POST or None, instance=extension)
    if request.method == "GET":
        form.initial["hop_dong"] = extension.hop_dong
        if is_volume:
            form.set_contract_initial(extension.hop_dong)
            details = {detail.loai_dich_vu: detail for detail in extension.chi_tiet_gia_han_khoi_luong.all()}
            phcn = details.get("VLTL")
            cs = details.get("CSXH")
            if phcn:
                form.initial.update({"so_tre_phcn_moi": phcn.so_tre_moi, "so_buoi_phcn_moi": phcn.so_buoi_moi})
            if cs:
                form.initial.update({"so_tre_cs_moi": cs.so_tre_moi, "so_buoi_cs_moi": cs.so_buoi_moi})
            form.initial["den_ngay_moi"] = extension.den_ngay_moi or form.initial.get("den_ngay_cu")

    if request.method == "POST" and form.is_valid():
        hop_dong = form.cleaned_data["hop_dong"]
        if extension.is_signed and _hop_dong_has_financial_records(hop_dong):
            messages.error(request, "Không thể sửa phụ lục đã ký sau khi hợp đồng đã phát sinh nghiệm thu, thanh lý hoặc thanh toán.")
            return redirect("danh_sach_gia_han_hop_dong")
        try:
            with transaction.atomic():
                if is_volume:
                    baseline = form.baseline(hop_dong, extension.pk)
                    values = {
                        "phcn": (form.cleaned_data["so_tre_phcn_moi"], form.cleaned_data["so_buoi_phcn_moi"]),
                        "cs": (form.cleaned_data["so_tre_cs_moi"], form.cleaned_data["so_buoi_cs_moi"]),
                    }
                    amounts = form.calculate_amounts(hop_dong, values, exclude_id=extension.pk)
                    current_end = _current_contract_end(hop_dong, extension.pk)
                    extension.den_ngay_cu = current_end
                    extension.den_ngay_moi = form.cleaned_data["den_ngay_moi"]
                    extension.tong_tien_tang_them = amounts["gia_tri_tang_them"]
                    extension.tong_tien_moi = amounts["tong_gia_tri_moi"]
                    extension.ngay_lap = form.cleaned_data["ngay_lap"]
                    extension.is_signed = form.cleaned_data["is_signed"]
                    extension.ghi_chu = form.cleaned_data["ghi_chu"]
                    extension.save()
                    rates = {"PHCN": hop_dong.dinh_muc_di_lai_phcn, "CS": hop_dong.dinh_muc_di_lai_cs}
                    for service, group in (("VLTL", "PHCN"), ("CSXH", "CS")):
                        old_count, old_sessions = baseline[group.lower()]
                        new_count, new_sessions = values[group.lower()]
                        ChiTietGiaHanKhoiLuong.objects.update_or_create(
                            phu_luc=extension,
                            loai_dich_vu=service,
                            defaults={
                                "so_tre_cu": old_count,
                                "so_tre_moi": new_count,
                                "so_buoi_cu": old_sessions,
                                "so_buoi_moi": new_sessions,
                                "don_gia_cong": hop_dong.don_gia_cong,
                                "dinh_muc_di_lai": rates[group],
                            },
                        )
                else:
                    extension.den_ngay_cu = _current_contract_end(hop_dong, extension.pk)
                    extension.den_ngay_moi = form.cleaned_data["den_ngay_moi"]
                    extension.ngay_lap = form.cleaned_data["ngay_lap"]
                    extension.is_signed = form.cleaned_data["is_signed"]
                    extension.tong_tien_moi = hop_dong.gia_tri_hop_dong
                    extension.ghi_chu = form.cleaned_data["ghi_chu"]
                    extension.save()
                _sync_hop_dong_from_signed_extensions(hop_dong)
        except (IntegrityError, ValidationError) as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, "Đã cập nhật phụ lục và đồng bộ lại giá trị hiện hành của hợp đồng.")
            return redirect("danh_sach_gia_han_hop_dong")

    context = {"form": form, "hop_dong": extension.hop_dong, "extension": extension, "is_edit": True}
    if is_volume:
        context["contract_metrics"] = form.contract_metrics()
        return render(request, "quanly/them_gia_han_khoi_luong.html", context)
    context["contract_end_dates"] = form.contract_end_dates
    return render(request, "quanly/them_gia_han_thoi_gian.html", context)


@admin_required
def xoa_gia_han_hop_dong(request, pk):
    extension = get_object_or_404(
        PhuLucHopDong.objects.prefetch_related("chi_tiet_gia_han_khoi_luong"),
        pk=pk,
        loai_phu_luc__in={"GIA_HAN_THOI_GIAN", "GIA_HAN_KHOI_LUONG"},
    )
    if request.method != "POST":
        return redirect("danh_sach_gia_han_hop_dong")

    hop_dong = extension.hop_dong
    if extension.is_signed and _hop_dong_has_financial_records(hop_dong):
        messages.error(
            request,
            "Không thể xóa phụ lục đã ký vì hợp đồng đã phát sinh nghiệm thu, thanh lý hoặc thanh toán.",
        )
        return redirect("danh_sach_gia_han_hop_dong")
    fallback_end = extension.den_ngay_cu if extension.loai_phu_luc == "GIA_HAN_THOI_GIAN" and extension.is_signed else None
    fallback_total = None
    fallback_volume = None
    if extension.loai_phu_luc == "GIA_HAN_KHOI_LUONG" and extension.is_signed:
        fallback_total = extension.tong_tien_moi - extension.tong_tien_tang_them
        fallback_volume = [
            {
                "loai_dich_vu": detail.loai_dich_vu,
                "so_tre": detail.so_tre_cu,
                "so_buoi": detail.so_buoi_cu,
                "don_gia_cong": detail.don_gia_cong,
                "dinh_muc_di_lai": detail.dinh_muc_di_lai,
            }
            for detail in extension.chi_tiet_gia_han_khoi_luong.all()
        ]
    try:
        with transaction.atomic():
            extension.delete()
            _sync_hop_dong_from_signed_extensions(
                hop_dong,
                fallback_end=fallback_end,
                fallback_total=fallback_total,
                fallback_volume=fallback_volume,
            )
        messages.success(request, "Đã xóa phụ lục gia hạn và đồng bộ lại hợp đồng.")
    except ProtectedError:
        messages.error(request, "Không thể xóa phụ lục vì còn hồ sơ phụ thuộc đang được bảo vệ.")
    return redirect("danh_sach_gia_han_hop_dong")


@hopdong_required
def xuat_gia_han_hop_dong(request, pk):
    extension = get_object_or_404(
        PhuLucHopDong.objects.select_related("hop_dong__can_bo").prefetch_related("chi_tiet_gia_han_khoi_luong"),
        pk=pk,
        loai_phu_luc__in={"GIA_HAN_THOI_GIAN", "GIA_HAN_KHOI_LUONG"},
    )
    try:
        output = export_extension_annex(extension)
    except ValidationError as exc:
        messages.error(request, str(exc))
        return redirect("danh_sach_gia_han_hop_dong")
    suffix = "ThoiGian" if extension.loai_phu_luc == "GIA_HAN_THOI_GIAN" else "KhoiLuong"
    staff = extension.hop_dong.can_bo
    filename = (
        f"GHHD_{suffix} - {safe_download_component(extension.hop_dong.so_hop_dong)} - "
        f"{safe_download_component(staff.ma_can_bo)}_{safe_download_component(staff.ho_ten)}.docx"
    )
    response = HttpResponse(
        output.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    response["Content-Disposition"] = content_disposition_filename(filename)
    return response


@hopdong_required
def danh_sach_thanh_toan_di_lai_phu_huynh(request):
    query = request.GET.get("q", "").strip()
    nhom_hd = request.GET.get("nhom_hd", "").strip()
    trang_thai = request.GET.get("trang_thai", "").strip()
    qs = DotThanhToanDiLaiPhuHuynh.objects.select_related(
        "hop_dong__can_bo", "hop_dong__don_vi", "hop_dong__nhom_hd", "nhom_hd"
    ).annotate(
        chi_tiet_count=Count("chi_tiet", distinct=True),
        tong_tien=Sum("chi_tiet__thanh_tien"),
    ).order_by("-nam", "-thang", "-id")
    if query:
        qs = qs.filter(
            Q(hop_dong__so_hop_dong__icontains=query)
            | Q(hop_dong__can_bo__ma_can_bo__icontains=query)
            | Q(hop_dong__can_bo__ho_ten__icontains=query)
            | Q(hop_dong__don_vi__ma_don_vi__icontains=query)
            | Q(hop_dong__don_vi__ten_don_vi__icontains=query)
            | Q(nhom_hd__ma_nhom_hd__icontains=query)
            | Q(nhom_hd__ten_nhom_hd__icontains=query)
        )
    if nhom_hd.isdigit():
        qs = qs.filter(Q(nhom_hd_id=int(nhom_hd)) | Q(hop_dong__nhom_hd_id=int(nhom_hd)))
    if trang_thai:
        qs = qs.filter(trang_thai=trang_thai)
    page_obj = Paginator(qs, 25).get_page(request.GET.get("page"))
    kpi = {
        "dot_count": qs.count(),
        "detail_count": sum((item.chi_tiet_count or 0) for item in page_obj.object_list),
        "amount": sum((item.tong_tien or 0) for item in page_obj.object_list),
    }
    return render(request, "quanly/danh_sach_thanh_toan_di_lai_phu_huynh.html", {
        "page_obj": page_obj,
        "danh_sach": page_obj.object_list,
        "query": query,
        "filters": {"nhom_hd": nhom_hd, "trang_thai": trang_thai},
        "nhom_list": NhomHD.objects.filter(is_active=True).order_by("ma_nhom_hd"),
        "status_choices": [("CHO_THANH_TOAN", "Chờ thanh toán"), ("DA_THANH_TOAN", "Đã thanh toán")],
        "kpi": kpi,
    })


@hopdong_required
def chi_tiet_dot_thanh_toan_phu_huynh(request, pk):
    dot = get_object_or_404(
        DotThanhToanDiLaiPhuHuynh.objects.select_related("hop_dong", "nhom_hd"),
        pk=pk,
    )
    chi_tiet = list(dot.chi_tiet.select_related("nhat_ky__phan_cong__tre"))
    category_counts = {category: 0 for category in ("NCS", "CG", "CBDA")}
    for item in chi_tiet:
        item.parent_travel_category = parent_travel_category(item.nhat_ky)
        category_counts[item.parent_travel_category] += 1
    cbda_list = CanBo.objects.filter(ma_can_bo__istartswith="AVH").order_by("ho_ten")
    return render(request, "quanly/chi_tiet_dot_thanh_toan_phu_huynh.html", {
        "dot": dot,
        "chi_tiet": chi_tiet,
        "category_counts": category_counts,
        "cbda_list": cbda_list,
        "selected_cbda": cbda_list.first(),
    })


@admin_required
def sua_dot_thanh_toan_phu_huynh(request, pk):
    dot = get_object_or_404(
        DotThanhToanDiLaiPhuHuynh.objects.select_related("hop_dong", "nhom_hd"),
        pk=pk,
    )
    form = DotThanhToanDiLaiPhuHuynhForm(request.POST or None, instance=dot)
    if request.method == "POST" and form.is_valid():
        try:
            form.save()
        except IntegrityError:
            form.add_error(None, "Đợt thanh toán tháng/năm này đã tồn tại trong cùng phạm vi.")
        else:
            messages.success(request, "Đã cập nhật đợt thanh toán đi lại phụ huynh.")
            return redirect("chi_tiet_dot_thanh_toan_phu_huynh", pk=dot.pk)
    return render(request, "quanly/sua_dot_thanh_toan_phu_huynh.html", {"form": form, "dot": dot})


@admin_required
def xoa_dot_thanh_toan_phu_huynh(request, pk):
    if request.method != "POST":
        return redirect("chi_tiet_dot_thanh_toan_phu_huynh", pk=pk)
    dot = get_object_or_404(DotThanhToanDiLaiPhuHuynh, pk=pk)
    try:
        dot.delete()
        messages.success(request, "Đã xóa đợt thanh toán đi lại phụ huynh.")
        return redirect("danh_sach_thanh_toan_di_lai_phu_huynh")
    except ProtectedError:
        messages.error(request, "Không thể xóa đợt vì đã có chi tiết thanh toán liên kết.")
        return redirect("chi_tiet_dot_thanh_toan_phu_huynh", pk=dot.pk)


@admin_required
def sua_chi_tiet_thanh_toan_phu_huynh(request, pk):
    item = get_object_or_404(
        ChiTietThanhToanDiLaiPhuHuynh.objects.select_related(
            "dot_thanh_toan__hop_dong", "dot_thanh_toan__nhom_hd", "nhat_ky"
        ),
        pk=pk,
    )
    dot = item.dot_thanh_toan
    form_kwargs = {
        "hop_dong": dot.hop_dong,
        "nhom_hd": dot.nhom_hd,
        "ky_can_thiep": dot.ky_can_thiep,
        "dot": dot,
        "instance": item,
    }
    form = ChiTietThanhToanDiLaiPhuHuynhForm(request.POST or None, **form_kwargs)
    if request.method == "POST" and form.is_valid():
        updated = form.save(commit=False)
        updated.dot_thanh_toan = dot
        updated.dinh_muc_di_lai = updated.nhat_ky.dinh_muc_di_lai
        try:
            updated.save()
        except (IntegrityError, ValidationError) as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, "Đã cập nhật chi tiết thanh toán đi lại phụ huynh.")
            return redirect("chi_tiet_dot_thanh_toan_phu_huynh", pk=dot.pk)
    return render(request, "quanly/sua_chi_tiet_thanh_toan_phu_huynh.html", {"form": form, "dot": dot, "item": item})


@admin_required
def xoa_chi_tiet_thanh_toan_phu_huynh(request, pk):
    if request.method != "POST":
        item = get_object_or_404(ChiTietThanhToanDiLaiPhuHuynh, pk=pk)
        return redirect("chi_tiet_dot_thanh_toan_phu_huynh", pk=item.dot_thanh_toan_id)
    item = get_object_or_404(ChiTietThanhToanDiLaiPhuHuynh, pk=pk)
    dot_id = item.dot_thanh_toan_id
    try:
        item.delete()
        messages.success(request, "Đã xóa chi tiết thanh toán đi lại phụ huynh.")
    except ProtectedError:
        messages.error(request, "Không thể xóa chi tiết đang được dữ liệu khác sử dụng.")
    return redirect("chi_tiet_dot_thanh_toan_phu_huynh", pk=dot_id)


@hopdong_required
def cap_nhat_thoi_gian_thanh_toan_di_lai_phu_huynh(request, pk):
    dot = get_object_or_404(DotThanhToanDiLaiPhuHuynh, pk=pk)
    if request.method != "POST":
        return redirect("chi_tiet_dot_thanh_toan_phu_huynh", pk=dot.pk)
    if _parent_travel_dot_is_locked(dot) and not is_admin_user(request.user):
        messages.error(request, "Đợt thanh toán có dữ liệu thuộc hợp đồng khóa/thanh lý, chỉ Admin mới được sửa thời gian.")
        return redirect("chi_tiet_dot_thanh_toan_phu_huynh", pk=dot.pk)
    form = DotThanhToanDiLaiPhuHuynhDateForm(request.POST, instance=dot)
    if form.is_valid():
        form.save()
        messages.success(request, "Đã cập nhật Từ ngày - Đến ngày trên hồ sơ.")
    else:
        messages.error(request, "Không thể cập nhật thời gian hồ sơ: " + " ".join(
            error for errors in form.errors.values() for error in errors
        ))
    return redirect("chi_tiet_dot_thanh_toan_phu_huynh", pk=dot.pk)


@hopdong_required
def them_chi_tiet_thanh_toan_phu_huynh(request, dot_id):
    dot = get_object_or_404(
        DotThanhToanDiLaiPhuHuynh.objects.select_related("hop_dong", "nhom_hd"),
        pk=dot_id,
    )
    if _parent_travel_dot_is_locked(dot) and not is_admin_user(request.user):
        messages.error(request, "Đợt thanh toán có dữ liệu thuộc hợp đồng khóa/thanh lý, chỉ Admin mới được thêm chi tiết.")
        return redirect("chi_tiet_dot_thanh_toan_phu_huynh", pk=dot.pk)
    form_kwargs = {
        "hop_dong": dot.hop_dong,
        "nhom_hd": dot.nhom_hd,
        "ky_can_thiep": dot.ky_can_thiep,
        "dot": dot,
    }
    if request.method == "POST":
        form = ChiTietThanhToanDiLaiPhuHuynhForm(request.POST, **form_kwargs)
        if form.is_valid():
            item = form.save(commit=False)
            item.dot_thanh_toan = dot
            try:
                with transaction.atomic():
                    item.nhat_ky = NhatKyThucHien.objects.select_for_update().get(pk=item.nhat_ky_id)
                    if item.nhat_ky.hop_dong_id and _is_operationally_locked(item.nhat_ky.hop_dong) and not is_admin_user(request.user):
                        raise ValidationError("Nhật ký thuộc hợp đồng khóa/thanh lý, chỉ Admin mới được thêm vào đợt.")
                    item.dinh_muc_di_lai = item.nhat_ky.dinh_muc_di_lai
                    item.save()
            except ValidationError as exc:
                form.add_error(None, str(exc))
            else:
                messages.success(request, "Đã thêm chi tiết thanh toán đi lại phụ huynh.")
                return redirect("chi_tiet_dot_thanh_toan_phu_huynh", pk=dot.pk)
    else:
        form = ChiTietThanhToanDiLaiPhuHuynhForm(**form_kwargs)
    return render(request, "quanly/them_chi_tiet_thanh_toan_phu_huynh.html", {"form": form, "dot": dot})


def _export_parent_travel(request, pk, category, export_kind="DNTT"):
    dot = get_object_or_404(DotThanhToanDiLaiPhuHuynh.objects.select_related("hop_dong"), pk=pk)
    try:
        category = normalize_parent_travel_category(category)
    except ValidationError as exc:
        messages.error(request, str(exc))
        return redirect("chi_tiet_dot_thanh_toan_phu_huynh", pk=dot.pk)
    try:
        requester = None
        cbda_id = request.GET.get("cbda", "").strip()
        if cbda_id.isdigit():
            requester = CanBo.objects.filter(pk=int(cbda_id), ma_can_bo__istartswith="AVH").first()
        exporters = {
            "DNTT": export_parent_travel_payment_request,
            "DSTK": export_parent_travel_account_list,
            "DNCK": export_parent_travel_commitment,
        }
        output = exporters[export_kind](dot, category, nguoi_de_nghi=requester)
    except ValidationError as exc:
        messages.error(request, str(exc))
        return redirect("chi_tiet_dot_thanh_toan_phu_huynh", pk=dot.pk)
    response = HttpResponse(output.getvalue(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response["Content-Disposition"] = f'attachment; filename="{export_kind}_DiLai_PH_{category}_{dot.thang}_{dot.nam}.xlsx"'
    return response


@hopdong_required
def xuat_dntt_di_lai_phu_huynh(request, pk):
    return _export_parent_travel(request, pk, request.GET.get("nhom", "NCS"))


@hopdong_required
def xuat_dstk_di_lai_phu_huynh(request, pk):
    return _export_parent_travel(request, pk, request.GET.get("nhom", "NCS"), export_kind="DSTK")


@hopdong_required
def xuat_dnck_di_lai_phu_huynh(request, pk):
    return _export_parent_travel(request, pk, request.GET.get("nhom", "NCS"), export_kind="DNCK")


@readonly_required
def nhat_ky_can_thiep(request):
    query = request.GET.get("q", "").strip()
    cb_id = request.GET.get("can_bo", "").strip()
    nhom_id = request.GET.get("nhom_hd", "").strip()
    ky = request.GET.get("ky", "").strip()
    thang = request.GET.get("thang", "").strip()
    nam = request.GET.get("nam", "").strip()
    only_conflicts = request.GET.get("trung") == "1"
    qs = NhatKyThucHien.objects.select_related(
        "can_bo_nguon", "nhom_hd_nguon", "phan_cong__tre",
        "phan_cong__nhom_hd", "phan_cong__phan_bo__can_bo", "phan_cong__phan_bo__nhom_hd",
    ).prefetch_related("hop_dong__can_bo", "hop_dong__nhom_hd").order_by("-ngay_thuc_hien", "-id")
    if query:
        qs = qs.filter(Q(phan_cong__tre__ma_tre__icontains=query) | Q(phan_cong__tre__ho_ten__icontains=query) | Q(hop_dong__so_hop_dong__icontains=query) | Q(can_bo_nguon__ho_ten__icontains=query) | Q(phan_cong__phan_bo__can_bo__ho_ten__icontains=query))
    if cb_id.isdigit():
        qs = qs.filter(Q(can_bo_nguon_id=int(cb_id)) | Q(can_bo_nguon__isnull=True, phan_cong__phan_bo__can_bo_id=int(cb_id)))
    if nhom_id.isdigit():
        qs = qs.filter(Q(nhom_hd_nguon_id=int(nhom_id)) | Q(nhom_hd_nguon__isnull=True, phan_cong__nhom_hd_id=int(nhom_id)) | Q(nhom_hd_nguon__isnull=True, phan_cong__nhom_hd__isnull=True, phan_cong__phan_bo__nhom_hd_id=int(nhom_id)))
    if ky.isdigit(): qs = qs.filter(ky_can_thiep=int(ky))
    if thang.isdigit(): qs = qs.filter(ngay_thuc_hien__month=int(thang))
    if nam.isdigit(): qs = qs.filter(ngay_thuc_hien__year=int(nam))
    if only_conflicts:
        qs = qs.filter(canh_bao_trung=True)
    page_obj = Paginator(qs, 25).get_page(request.GET.get("page"))
    total_records = qs.count()
    phcn_records = qs.filter(phan_cong__loai_dich_vu__in=PhanCongTre.PHCN_SERVICE_CODES).count()
    cs_records = qs.filter(phan_cong__loai_dich_vu__in=PhanCongTre.CS_SERVICE_CODES).count()
    period_summary = list(
        NhatKyThucHien.objects.values("ky_can_thiep")
        .annotate(
            journal_count=Count("id"),
            session_count=Sum("so_buoi_thuc_hien"),
            first_date=Min("ngay_thuc_hien"),
            last_date=Max("ngay_thuc_hien"),
        )
        .order_by("ky_can_thiep")
    )
    return render(request, "quanly/nhat_ky_can_thiep.html", {
        "page_obj": page_obj,
        "danh_sach": page_obj,
        "query": query,
        "tong_so": total_records,
        "phcn_records": phcn_records,
        "cs_records": cs_records,
        "period_count": len(period_summary),
        "period_summary": period_summary,
        "conflict_count": NhatKyThucHien.objects.filter(canh_bao_trung=True).count(),
        "only_conflicts": only_conflicts,
        "can_bo_list": CanBo.objects.filter(is_active=True),
        "nhom_list": NhomHD.objects.filter(is_active=True),
        "ky_choices": FinancialConfig.KY_CAN_THIEP_CHOICES,
        "month_choices": range(1, 13),
        "year_choices": FinancialConfig.NAM_CAN_THIEP_CHOICES,
        "filters": {"can_bo": cb_id, "nhom_hd": nhom_id, "ky": ky, "thang": thang, "nam": nam},
    })


@readonly_required
def xuat_nhat_ky_trung(request):
    """Xuất danh sách nhật ký đang có cảnh báo trùng để CBDA xử lý."""
    from openpyxl import Workbook

    qs = NhatKyThucHien.objects.filter(canh_bao_trung=True).select_related(
        "can_bo_nguon", "hop_dong__can_bo", "hop_dong__nhom_hd", "nhom_hd_nguon",
        "phan_cong__tre", "phan_cong__nhom_hd", "phan_cong__phan_bo__can_bo", "phan_cong__phan_bo__nhom_hd",
    ).order_by("ngay_thuc_hien", "gio_bat_dau", "id")
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Nhat ky trung"
    worksheet.append([
        "ID nhật ký", "Ngày", "Giờ bắt đầu", "Giờ kết thúc", "Mã CBCT", "Tên CBCT",
        "Mã trẻ", "Tên trẻ", "Hợp đồng", "Nhóm HĐ", "Địa điểm", "Dịch vụ", "Kỳ",
        "Buổi", "Lượt đi lại CBCT", "Lượt đi lại PH", "Dữ liệu lịch sử", "Cảnh báo",
    ])
    for item in qs:
        staff = item.can_bo_hieu_luc
        group = item.nhom_hd_hieu_luc
        worksheet.append([
            item.pk,
            item.ngay_thuc_hien,
            item.gio_bat_dau,
            item.gio_ket_thuc,
            staff.ma_can_bo if staff else "",
            staff.ho_ten if staff else "",
            item.phan_cong.tre.ma_tre,
            item.phan_cong.tre.ho_ten,
            item.so_hop_dong_hieu_luc,
            group.ma_nhom_hd if group else "",
            item.dia_diem_ct or item.phan_cong.dia_diem_ct or "",
            item.phan_cong.loai_dich_vu,
            item.ky_can_thiep,
            item.so_buoi_thuc_hien,
            item.so_luot_di_lai_cbct,
            item.so_luot_di_lai,
            "Có" if item.du_lieu_lich_su else "Không",
            item.chi_tiet_trung,
        ])
    worksheet.freeze_panes = "A2"
    worksheet.auto_filter.ref = worksheet.dimensions
    for column_cells in worksheet.columns:
        width = min(max(len(str(cell.value or "")) for cell in column_cells) + 2, 32)
        worksheet.column_dimensions[column_cells[0].column_letter].width = width
    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    response = HttpResponse(
        output.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = 'attachment; filename="Nhat_ky_trung_CBCT.xlsx"'
    return response


@readonly_required
@readonly_required
def danh_sach_phieu_thanh_toan(request):
    query = request.GET.get("q", "").strip()
    qs = PhieuThanhToan.objects.select_related("can_bo", "hop_dong", "hop_dong__nhom_hd").all()
    if query:
        qs = qs.filter(
            Q(can_bo__ma_can_bo__icontains=query)
            | Q(can_bo__ho_ten__icontains=query)
            | Q(hop_dong__so_hop_dong__icontains=query)
        )
    trang_thai = request.GET.get("trang_thai", "").strip()
    if trang_thai:
        qs = qs.filter(trang_thai=trang_thai)
    page_obj = Paginator(qs, 25).get_page(request.GET.get("page"))
    return render(request, "quanly/danh_sach_phieu_thanh_toan.html", {
        "page_obj": page_obj,
        "query": query,
        "trang_thai": trang_thai,
        "choices": PhieuThanhToan.TRANG_THAI_CHOICES,
    })


@accountant_required
def tao_phieu_thanh_toan(request):
    nhom_id = request.POST.get("nhom_hd") or request.GET.get("nhom_hd", "")
    ky = request.POST.get("ky") or request.GET.get("ky", "")
    if request.method == "POST":
        if not str(nhom_id).isdigit() or not str(ky).isdigit():
            messages.error(request, "Cần chọn Nhóm HĐ và Kỳ can thiệp.")
        else:
            contracts = HopDong.objects.filter(nhom_hd_id=int(nhom_id), can_bo__isnull=False).exclude(
                trang_thai__in={"DU_THAO", "HUY", "THANH_LY"}
            ).select_related("can_bo")
            created = 0
            errors = []
            for contract in contracts:
                try:
                    tao_phieu_thanh_toan_service(contract.can_bo, contract, int(ky), request.user)
                    created += 1
                except ValidationError as exc:
                    errors.append(f"{contract.so_hop_dong}: {exc.messages[0] if exc.messages else exc}")
            if created:
                messages.success(request, f"Đã tạo {created} phiếu thanh toán.")
            for error in errors:
                messages.warning(request, error)
            return redirect("danh_sach_phieu_thanh_toan")
    return render(request, "quanly/tao_phieu_thanh_toan.html", {
        "nhom_list": NhomHD.objects.filter(is_active=True),
        "ky_choices": range(1, 31),
        "nhom_id": str(nhom_id),
        "ky": str(ky),
    })


@accountant_required
def huy_phieu_thanh_toan_view(request, pk):
    if request.method != "POST":
        return redirect("danh_sach_phieu_thanh_toan")
    phieu = get_object_or_404(PhieuThanhToan, pk=pk)
    try:
        huy_phieu_thanh_toan(phieu, request.POST.get("ly_do_huy", ""), request.user)
        messages.success(request, "Đã hủy phiếu thanh toán.")
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
    return redirect("danh_sach_phieu_thanh_toan")


@accountant_required
def xac_nhan_chi_phieu_thanh_toan(request, pk):
    if request.method != "POST":
        return redirect("danh_sach_phieu_thanh_toan")
    phieu = get_object_or_404(PhieuThanhToan, pk=pk)
    try:
        xac_nhan_chi(phieu, parse_date(request.POST.get("ngay_chi")), request.user)
        messages.success(request, "Đã xác nhận phiếu đã chi.")
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
    return redirect("danh_sach_phieu_thanh_toan")


def thanh_quyet_toan(request):
    """Tổng hợp và lập hồ sơ thanh toán theo Nhóm HĐ + Kỳ can thiệp."""
    qs, ky, thang, nam = _journal_export_queryset(request)
    query = request.GET.get("q", "").strip()
    if query:
        qs = qs.filter(
            Q(phan_cong__tre__ma_tre__icontains=query)
            | Q(phan_cong__tre__ho_ten__icontains=query)
            | Q(hop_dong__so_hop_dong__icontains=query)
            | Q(can_bo_nguon__ho_ten__icontains=query)
            | Q(phan_cong__phan_bo__can_bo__ho_ten__icontains=query)
        )
    rows = {}
    for journal in qs:
        effective_group = journal.nhom_hd_hieu_luc
        effective_staff = journal.can_bo_hieu_luc
        if not effective_group or not effective_staff:
            continue
        key = (effective_group.pk, journal.ky_can_thiep)
        item = rows.setdefault(key, {
            "nhom": effective_group,
            "ky": journal.ky_can_thiep,
            "hop_dong_count": set(),
            "can_bo_count": set(),
            "journal_count": 0,
            "so_buoi": Decimal("0"),
            "di_lai": Decimal("0"),
            "tien_cong": Decimal("0"),
            "tien_di_lai": Decimal("0"),
            "staff_amounts": {},
        })
        if journal.hop_dong_hieu_luc:
            item["hop_dong_count"].add(journal.hop_dong_id)
        item["can_bo_count"].add(effective_staff.pk)
        item["journal_count"] += 1
        item["so_buoi"] += Decimal(journal.so_buoi_thuc_hien)
        item["di_lai"] += Decimal(journal.so_luot_di_lai_cbct)
        item["tien_cong"] += Decimal(journal.so_buoi_thuc_hien) * Decimal(journal.don_gia_cong)
        item["tien_di_lai"] += Decimal(journal.so_luot_di_lai_cbct) * Decimal(journal.dinh_muc_di_lai)
        staff_amount = item["staff_amounts"].setdefault(
            effective_staff.pk,
            {"labor": Decimal("0"), "travel": Decimal("0")},
        )
        staff_amount["labor"] += Decimal(journal.so_buoi_thuc_hien) * Decimal(journal.don_gia_cong)
        staff_amount["travel"] += Decimal(journal.so_luot_di_lai_cbct) * Decimal(journal.dinh_muc_di_lai)
    for item in rows.values():
        staff_breakdowns = [
            calculate_payment_breakdown(amount["labor"], amount["travel"])
            for amount in item.pop("staff_amounts").values()
        ]
        breakdown = {
            key: sum((value[key] for value in staff_breakdowns), Decimal("0"))
            for key in ("tien_cong", "tien_di_lai", "tong_truoc_thue", "thue_tncn", "thuc_linh")
        }
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
        "ky_choices": FinancialConfig.KY_CAN_THIEP_CHOICES,
        "month_choices": range(1, 13),
        "year_choices": FinancialConfig.NAM_CAN_THIEP_CHOICES,
    })


@readonly_required
def de_nghi_thanh_toan(request):
    """Trang xuất hồ sơ cho một Nhóm HĐ + Kỳ can thiệp đã chọn."""
    qs, ky, thang, nam = _journal_export_queryset(request)
    nhom_id = request.GET.get("nhom_hd", "").strip()
    nhom = get_object_or_404(NhomHD, pk=int(nhom_id)) if nhom_id.isdigit() else None
    tu_ngay = request.GET.get("tu_ngay", "").strip()
    den_ngay = request.GET.get("den_ngay", "").strip()
    date_error = ""
    if tu_ngay or den_ngay:
        start_date = parse_date(tu_ngay)
        end_date = parse_date(den_ngay)
        if not start_date or not end_date:
            date_error = "Vui lòng chọn đủ Từ ngày và Đến ngày."
        elif start_date > end_date:
            date_error = "Từ ngày không được sau Đến ngày."
    cbda_list = list(CanBo.objects.filter(is_active=True, ma_can_bo__istartswith="AVH").order_by("ma_can_bo"))
    cbda_id = request.GET.get("cbda", "").strip()
    selected_cbda = next((item for item in cbda_list if str(item.pk) == cbda_id), None)
    if selected_cbda is None and cbda_list:
        selected_cbda = cbda_list[0]
    export_params = request.GET.copy()
    if selected_cbda:
        export_params["cbda"] = str(selected_cbda.pk)
    return render(request, "quanly/de_nghi_thanh_toan.html", {
        "nhom": nhom,
        "ky": ky,
        "thang": thang,
        "nam": nam,
        "journal_count": qs.count(),
        "so_buoi": qs.aggregate(total=Sum("so_buoi_thuc_hien"))["total"] or 0,
        "can_bo_count": len({item.can_bo_hieu_luc_id for item in qs if item.can_bo_hieu_luc_id}),
        "tu_ngay": tu_ngay,
        "den_ngay": den_ngay,
        "date_error": date_error,
        "dates_ready": bool(tu_ngay and den_ngay and not date_error),
        "cbda_list": cbda_list,
        "selected_cbda": selected_cbda,
        "query_string": export_params.urlencode(),
    })


def _selected_payment_date_range(request):
    tu_ngay = parse_date(request.GET.get("tu_ngay", ""))
    den_ngay = parse_date(request.GET.get("den_ngay", ""))
    if not tu_ngay or not den_ngay:
        raise ValidationError("Vui lòng chọn đủ Từ ngày và Đến ngày trước khi xuất file.")
    if tu_ngay > den_ngay:
        raise ValidationError("Từ ngày không được sau Đến ngày.")
    return tu_ngay.strftime("%d/%m/%Y"), den_ngay.strftime("%d/%m/%Y")


def _selected_cbda(request):
    cbda_id = request.GET.get("cbda", "").strip()
    cbda = CanBo.objects.filter(
        pk=int(cbda_id) if cbda_id.isdigit() else 0,
        is_active=True,
        ma_can_bo__istartswith="AVH",
    ).first()
    if not cbda:
        raise ValidationError("Vui lòng chọn CBDA là người đề nghị trước khi xuất file.")
    return cbda


def _journal_export_queryset(request):
    qs = NhatKyThucHien.objects.select_related(
        "can_bo_nguon__don_vi", "nhom_hd_nguon", "phan_cong__tre",
        "phan_cong__nhom_hd", "phan_cong__phan_bo__can_bo__don_vi", "phan_cong__phan_bo__nhom_hd",
    ).prefetch_related("hop_dong__can_bo__don_vi", "hop_dong__nhom_hd").order_by("ngay_thuc_hien", "id")
    cb_id, nhom_id, ky, thang, nam = (request.GET.get(key, "").strip() for key in ("can_bo", "nhom_hd", "ky", "thang", "nam"))
    if cb_id.isdigit():
        qs = qs.filter(Q(can_bo_nguon_id=int(cb_id)) | Q(can_bo_nguon__isnull=True, phan_cong__phan_bo__can_bo_id=int(cb_id)))
    if nhom_id.isdigit():
        qs = qs.filter(Q(nhom_hd_nguon_id=int(nhom_id)) | Q(nhom_hd_nguon__isnull=True, phan_cong__nhom_hd_id=int(nhom_id)) | Q(nhom_hd_nguon__isnull=True, phan_cong__nhom_hd__isnull=True, phan_cong__phan_bo__nhom_hd_id=int(nhom_id)))
    if ky.isdigit(): qs = qs.filter(ky_can_thiep=int(ky))
    if thang.isdigit(): qs = qs.filter(ngay_thuc_hien__month=int(thang))
    if nam.isdigit(): qs = qs.filter(ngay_thuc_hien__year=int(nam))
    return qs, ky, thang, nam


def _paid_voucher_journal_queryset(queryset):
    active_voucher = ChiTietPhieuThanhToan.objects.filter(nhat_ky_id=OuterRef("pk"), hoat_dong=True)
    return queryset.filter(hop_dong__isnull=False).filter(Exists(active_voucher))


def _journal_export_file_stem(qs, ky):
    first = qs.first()
    if not first:
        return "NTatCaK" + (ky or "TatCa")
    group_codes = list({item.nhom_hd_hieu_luc.ma_nhom_hd for item in qs[:1000]})
    group_code = group_codes[0] if len(group_codes) == 1 else "TatCa"
    period = ky or (str(first.ky_can_thiep) if qs.values("ky_can_thiep").distinct().count() == 1 else "TatCa")
    return f"N{group_code}K{period}"


@readonly_required
def xuat_dntt_nhat_ky(request):
    qs, ky, thang, nam = _journal_export_queryset(request)
    qs = _paid_voucher_journal_queryset(qs)
    if not qs.exists():
        messages.error(request, "Chưa có phiếu thanh toán hiệu lực; hãy tạo phiếu trước khi xuất ĐNTT.")
        return redirect(f"{reverse('tao_phieu_thanh_toan')}?{request.GET.urlencode()}")
    archive = BytesIO()
    try:
        cbda = _selected_cbda(request)
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
            grouped = {}
            for journal in qs:
                staff = journal.can_bo_hieu_luc
                if staff:
                    grouped.setdefault(staff.pk, []).append(journal)
            for journals in grouped.values():
                staff = journals[0].can_bo_hieu_luc
                period = int(ky) if ky.isdigit() else journals[0].ky_can_thiep
                payment_round = next_payment_round(staff, period)
                output = export_journal_payment_request(journals, ky=ky, thang=thang, nam=nam, lan_tt=payment_round, nguoi_de_nghi=cbda)
                safe_name = re.sub(r'[\\/:*?"<>|]+', "_", f"{staff.ma_can_bo} {staff.ho_ten}").strip()
                bundle.writestr(f"L{payment_round}_DNTT - {safe_name}.docx", output.getvalue())
    except ValidationError as exc:
        messages.error(request, str(exc)); return redirect(f"{reverse('de_nghi_thanh_toan')}?{request.GET.urlencode()}")
    response = HttpResponse(archive.getvalue(), content_type="application/zip")
    response["Content-Disposition"] = f'attachment; filename="DNTT_Word_{_journal_export_file_stem(qs, ky)}.zip"'
    return response


@readonly_required
def xuat_dntt_excel_nhat_ky(request):
    qs, ky, thang, nam = _journal_export_queryset(request)
    qs = _paid_voucher_journal_queryset(qs)
    try:
        cbda = _selected_cbda(request)
        tu_ngay, den_ngay = _selected_payment_date_range(request)
        output = export_journal_payment_request_excel(
            qs,
            ky=ky,
            thang=thang,
            nam=nam,
            tu_ngay=tu_ngay,
            den_ngay=den_ngay,
            nguoi_de_nghi=cbda,
        )
    except ValidationError as exc:
        messages.error(request, str(exc)); return redirect(f"{reverse('de_nghi_thanh_toan')}?{request.GET.urlencode()}")
    response = HttpResponse(output.getvalue(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response["Content-Disposition"] = f'attachment; filename="DNTT_{_journal_export_file_stem(qs, ky)}.xlsx"'
    return response


@readonly_required
def xuat_dstk_nhat_ky(request):
    qs, ky, _, _ = _journal_export_queryset(request)
    qs = _paid_voucher_journal_queryset(qs)
    try:
        cbda = _selected_cbda(request)
        output = export_journal_account_list(qs, nguoi_de_nghi=cbda)
    except ValidationError as exc:
        messages.error(request, str(exc)); return redirect("nhat_ky_can_thiep")
    response = HttpResponse(output.getvalue(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response["Content-Disposition"] = f'attachment; filename="DSTK_{_journal_export_file_stem(qs, ky)}.xlsx"'
    return response


@readonly_required
def xuat_dnck_nhat_ky(request):
    qs, ky, _, _ = _journal_export_queryset(request)
    qs = _paid_voucher_journal_queryset(qs)
    try:
        cbda = _selected_cbda(request)
        tu_ngay, den_ngay = _selected_payment_date_range(request)
        output = export_journal_commitment(
            qs,
            tu_ngay=tu_ngay,
            den_ngay=den_ngay,
            nguoi_de_nghi=cbda,
        )
    except ValidationError as exc:
        messages.error(request, str(exc)); return redirect(f"{reverse('de_nghi_thanh_toan')}?{request.GET.urlencode()}")
    response = HttpResponse(output.getvalue(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response["Content-Disposition"] = f'attachment; filename="DNCK_{_journal_export_file_stem(qs, ky)}.xlsx"'
    return response


@hopdong_required
def them_chi_tiet_thanh_toan(request, dot_id):
    dot = get_object_or_404(DotThanhToan.objects.select_related("hop_dong"), pk=dot_id)
    if _is_operationally_locked(dot.hop_dong) and not is_admin_user(request.user):
        messages.error(request, "Hợp đồng đã khóa/thanh lý, chỉ Admin mới được thêm chi tiết thanh toán.")
        return redirect("chi_tiet_dot_thanh_toan", pk=dot.pk)
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
    return redirect("them_gia_han_khoi_luong", hop_dong_id=hop_dong_id)


@hopdong_required
def them_phu_luc_hop_dong(request, hop_dong_id):
    hop_dong = get_object_or_404(HopDong, pk=hop_dong_id)
    if _is_operationally_locked(hop_dong) and not is_admin_user(request.user):
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


@admin_required
def import_phan_cong(request):
    if request.method != "POST" or not request.FILES.get("file_excel"):
        return render(request, "quanly/import_phan_cong.html")
    from .assignment_import import import_assignment_workbook

    validate_only = request.POST.get("validate_only") == "1"
    try:
        result = import_assignment_workbook(request.FILES["file_excel"], validate_only=validate_only)
    except ValueError as exc:
        messages.error(request, str(exc))
        return render(request, "quanly/import_phan_cong.html")
    summary = (
        f"Import phân công {'kiểm tra' if validate_only else 'hoàn tất'}: "
        f"thêm {result.created}, cập nhật {result.updated}, không đổi {result.unchanged}, "
        f"lỗi {len(result.errors)}, cảnh báo {len(result.warnings)}, phân bổ tạo mới {result.phan_bo_tao_moi}."
    )
    if result.errors:
        messages.error(request, summary + " Không có dữ liệu nào được lưu.")
        for error in result.errors[:100]:
            messages.error(request, error)
    elif result.system_error:
        messages.error(request, summary)
    elif validate_only:
        messages.success(request, summary + " Chế độ kiểm tra đã rollback, không ghi cơ sở dữ liệu.")
    else:
        messages.success(request, summary + " Dữ liệu đã được lưu nguyên tử.")
    for warning in result.warnings[:100]:
        messages.warning(request, warning)
    return redirect("danh_sach_phan_cong")
