"""Validated, atomic import for the child-assignment workbook."""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
import logging
from pathlib import Path

import pandas as pd
from django.db import transaction
from django.db.models import Q

from .models import CanBo, NhomHD, PhanBoChiTieu, PhanCongTre, Tre

logger = logging.getLogger(__name__)
MAX_FILE_SIZE = 10 * 1024 * 1024
MAX_ROWS = 20_000


@dataclass
class AssignmentImportResult:
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    phan_bo_tao_moi: int = 0
    dry_run: bool = False
    system_error: bool = False


class _DryRunRollback(Exception):
    pass


def _read_workbook(uploaded_file):
    filename = str(getattr(uploaded_file, "name", ""))
    if Path(filename).suffix.lower() != ".xlsx":
        raise ValueError("Chỉ chấp nhận file Excel .xlsx.")
    if getattr(uploaded_file, "size", 0) > MAX_FILE_SIZE:
        raise ValueError("File Excel không được vượt quá 10 MB.")
    frame = pd.read_excel(uploaded_file)
    frame.columns = [str(col).replace("\xa0", " ").strip() for col in frame.columns]
    if len(frame.index) > MAX_ROWS:
        raise ValueError("File Excel không được vượt quá 20.000 dòng dữ liệu.")
    return frame


def import_assignment_workbook(uploaded_file, *, validate_only=False):
    """Validate every row first, then write the complete workbook atomically."""
    from .views import clean_empty_excel_value, get_excel_value, normalize_service_code, parse_date, parse_int, parse_decimal, take_import_occurrence

    result = AssignmentImportResult(dry_run=validate_only)
    try:
        frame = _read_workbook(uploaded_file)
    except ValueError:
        raise
    except Exception as exc:
        logger.exception("Unable to read assignment workbook")
        result.system_error = True
        result.errors.append("Không đọc được file Excel. Vui lòng kiểm tra đúng mẫu .xlsx.")
        return result

    rows = []
    errors = []
    cb_codes = set()
    child_codes = set()
    group_values = set()
    for row_no, (_, row) in enumerate(frame.iterrows(), start=2):
        cb_codes.add(clean_empty_excel_value(get_excel_value(row, "Mã CB", "MaCB", "MaCBCT", "Mã CBCT")))
        child_codes.add(clean_empty_excel_value(get_excel_value(row, "IDChild", "MaTre", "Mã trẻ")))
        group_values.add(clean_empty_excel_value(get_excel_value(row, "Nhóm HĐ", "NhomHD", "Mã nhóm HĐ")))
        rows.append((row_no, row))

    cb_codes.discard(None)
    child_codes.discard(None)
    group_values.discard(None)
    can_bo_by_code = {item.ma_can_bo: item for item in CanBo.objects.filter(ma_can_bo__in=cb_codes)}
    tre_by_code = {item.ma_tre: item for item in Tre.objects.filter(ma_tre__in=child_codes)}
    groups = list(NhomHD.objects.all())
    group_by_key = {}
    for group in groups:
        group_by_key.setdefault(group.ma_nhom_hd.casefold(), group)
        group_by_key.setdefault(group.ten_nhom_hd.casefold(), group)

    allocations = list(PhanBoChiTieu.objects.select_related("can_bo", "nhom_hd").order_by("-ngay_lap", "-id"))
    allocation_by_key = {}
    inferred_group_by_cb = {}
    for allocation in allocations:
        allocation_by_key.setdefault((allocation.can_bo_id, allocation.nhom_hd_id), allocation)
        if allocation.can_bo_id:
            inferred_group_by_cb.setdefault(allocation.can_bo_id, allocation.nhom_hd)

    prepared = []
    identity_cache = {}
    identity_occurrences = {}
    new_children = {}
    new_allocation_specs = {}
    pending_identity_seen = set()

    for row_no, row in rows:
        try:
            ma_tre = clean_empty_excel_value(get_excel_value(row, "IDChild", "MaTre", "Mã trẻ"))
            if not ma_tre:
                raise ValueError("Thiếu mã trẻ")
            ma_cb = clean_empty_excel_value(get_excel_value(row, "Mã CB", "MaCB", "MaCBCT", "Mã CBCT"))
            can_bo = can_bo_by_code.get(ma_cb) if ma_cb else None
            if ma_cb and not can_bo:
                raise ValueError(f"Không tìm thấy cán bộ '{ma_cb}'")

            tre = tre_by_code.get(ma_tre)
            if not tre:
                child_name = clean_empty_excel_value(get_excel_value(row, "Tên trẻ", "HoTen"))
                child_birth = parse_date(get_excel_value(row, "Ngày sinh", "NgaySinh"))
                child_gender = clean_empty_excel_value(get_excel_value(row, "Giới tính", "GioiTinh"))
                if not child_name or not child_birth or not child_gender:
                    raise ValueError("Trẻ chưa có trong danh mục; cần đủ Tên trẻ, Ngày sinh và Giới tính để tạo mới")
                valid_genders = {value for value, _ in Tre.GIOI_TINH_CHOICES}
                if child_gender not in valid_genders:
                    raise ValueError("Giới tính của trẻ không hợp lệ")
                tre = new_children.setdefault(ma_tre, {"ma_tre": ma_tre, "ho_ten": child_name, "ngay_sinh": child_birth, "gioi_tinh": child_gender})

            nhom_value = clean_empty_excel_value(get_excel_value(row, "Nhóm HĐ", "NhomHD", "Mã nhóm HĐ"))
            nhom = None
            if nhom_value:
                nhom = group_by_key.get(str(nhom_value).casefold())
                if not nhom and str(nhom_value).replace(".0", "", 1).isdigit():
                    nhom = NhomHD.objects.filter(pk=int(float(nhom_value))).first()
            if not nhom and can_bo:
                nhom = inferred_group_by_cb.get(can_bo.pk)
                if nhom:
                    result.warnings.append(f"Dòng {row_no}: suy Nhóm HĐ {nhom.ma_nhom_hd} từ phân bổ gần nhất của {ma_cb}.")
            if not nhom:
                raise ValueError("Thiếu hoặc không tìm thấy Nhóm HĐ")

            cbda = clean_empty_excel_value(get_excel_value(row, "CBDA", "Mã CBDA", "CanBoDuAn"))
            allocation = allocation_by_key.get((can_bo.pk if can_bo else None, nhom.pk))
            if not allocation and not can_bo:
                allocation_key = (None, nhom.pk, cbda or "")
                allocation = new_allocation_specs.setdefault(
                    allocation_key,
                    {"nhom_hd": nhom, "cbda_quan_ly": cbda, "ngay_lap": parse_date(get_excel_value(row, "Ngày phân công", "NgayPhanCong"), date.today())},
                )
                result.warnings.append(f"Dòng {row_no}: sẽ tạo Phân bổ mới cho Nhóm HĐ {nhom.ma_nhom_hd}.")

            raw_service = clean_empty_excel_value(get_excel_value(row, "Loại dịch vụ", "LoaiDichVu", "MaLoaiDichVu", "Chỉ định CT"))
            service = normalize_service_code(raw_service)
            if not service or service not in {value for value, _ in PhanCongTre.LOAI_DV_CHOICES}:
                raise ValueError(f"Dịch vụ '{raw_service or 'trống'}' không hợp lệ")
            so_buoi = parse_int(get_excel_value(row, "Số buổi dự kiến", "SoBuoi"), 0)
            if so_buoi <= 0:
                raise ValueError("Số buổi dự kiến phải lớn hơn 0")
            dot_value = parse_int(get_excel_value(row, "Đợt phân công", "DotPhanCong"), 1)
            ky_value = parse_int(get_excel_value(row, "Kỳ phân công", "KyPhanCong"), 1)
            if dot_value <= 0 or not 1 <= ky_value <= 30:
                raise ValueError("Đợt phải lớn hơn 0 và kỳ phân công phải từ 1 đến 30")
            ngay_phan_cong = parse_date(get_excel_value(row, "Ngày phân công", "NgayPhanCong"))
            dia_diem_ct = clean_empty_excel_value(get_excel_value(row, "Địa điểm CT", "DiaDiemCT"))
            hinh_thuc_ct = clean_empty_excel_value(get_excel_value(row, "Hình thức CT", "HinhThucCT"))
            ghi_chu = clean_empty_excel_value(get_excel_value(row, "Ghi chú", "GhiChu"))
            default_dm = Decimal("0")
            if allocation and PhanCongTre.service_group(service) == "CS":
                default_dm = allocation.dinh_muc_di_lai_cs
            elif allocation:
                default_dm = allocation.dinh_muc_di_lai_phcn
            raw_dinh_muc = clean_empty_excel_value(get_excel_value(row, "Định mức đi lại", "DMDL"))
            if raw_dinh_muc is None:
                dinh_muc = default_dm
            else:
                normalized_dm = str(raw_dinh_muc).replace("\xa0", "").replace(" ", "")
                if "," in normalized_dm and "." in normalized_dm:
                    if normalized_dm.rfind(",") > normalized_dm.rfind("."):
                        normalized_dm = normalized_dm.replace(".", "").replace(",", ".")
                    else:
                        normalized_dm = normalized_dm.replace(",", "")
                elif "," in normalized_dm:
                    left, right = normalized_dm.rsplit(",", 1)
                    normalized_dm = left + right if len(right) == 3 else left + "." + right
                elif "." in normalized_dm:
                    left, right = normalized_dm.rsplit(".", 1)
                    normalized_dm = left + right if len(right) == 3 else normalized_dm
                try:
                    dinh_muc = Decimal(normalized_dm)
                except (InvalidOperation, ValueError):
                    raise ValueError("Định mức đi lại không phải số hợp lệ")

            tre_id = tre.pk if hasattr(tre, "pk") else None
            cb_id = can_bo.pk if can_bo else None
            identity_base = PhanCongTre.objects.filter(
                tu_dong_tu_nhat_ky=False,
                tre_id=tre_id,
                nhom_hd=nhom,
                dot_phan_cong=dot_value,
                ky_phan_cong=ky_value,
            )
            if cb_id:
                # Old rows may keep CBCT only through PhanBoChiTieu.
                identity_base = identity_base.filter(
                    Q(can_bo_nguon_id=cb_id) | Q(can_bo_nguon__isnull=True, phan_bo__can_bo_id=cb_id)
                )
            else:
                identity_base = identity_base.filter(can_bo_nguon__isnull=True, phan_bo__can_bo__isnull=True)
            identity_qs = identity_base.filter(loai_dich_vu=service)
            identity_key = (tre_id or ma_tre, cb_id, service, nhom.pk, dot_value, ky_value)

            def load_existing_assignments():
                return list(identity_qs.order_by("id")) if tre_id else []

            identity, _ = take_import_occurrence(identity_cache, identity_occurrences, identity_key, load_existing_assignments)
            skip_duplicate = False
            if tre_id is None and identity is None:
                if identity_key in pending_identity_seen:
                    skip_duplicate = True
                    result.warnings.append(f"Dòng {row_no}: trùng mã trẻ mới với cùng CBCT/dịch vụ/nhóm/đợt/kỳ; bỏ qua bản sao trong cùng file.")
                else:
                    pending_identity_seen.add(identity_key)
            prepared.append({
                "row_no": row_no, "tre": tre, "can_bo": can_bo, "allocation": allocation, "nhom": nhom,
                "cbda": cbda, "service": service, "so_buoi": so_buoi, "dot": dot_value, "ky": ky_value,
                "ngay": ngay_phan_cong, "dia_diem": dia_diem_ct, "hinh_thuc": hinh_thuc_ct, "ghi_chu": ghi_chu,
                "dinh_muc": dinh_muc, "identity": identity, "skip_duplicate": skip_duplicate,
            })
        except Exception as exc:
            errors.append(f"Dòng {row_no}: {exc}")

    if errors:
        result.errors = errors
        return result

    try:
        with transaction.atomic():
            child_objects = {}
            for ma_tre, data in new_children.items():
                child_objects[ma_tre] = Tre.objects.create(**data)
            created_allocations = {}
            for key, data in new_allocation_specs.items():
                allocation = PhanBoChiTieu.objects.create(**data)
                created_allocations[key] = allocation
                result.phan_bo_tao_moi += 1

            for item in prepared:
                if item["skip_duplicate"]:
                    result.unchanged += 1
                    continue
                tre = child_objects.get(item["tre"].get("ma_tre")) if isinstance(item["tre"], dict) else item["tre"]
                allocation = item["allocation"]
                if isinstance(allocation, dict):
                    allocation = created_allocations[(None, item["nhom"].pk, item["cbda"] or "")]
                obj = item["identity"] or PhanCongTre(tre=tre, loai_dich_vu=item["service"])
                old_values = (obj.phan_bo_id, obj.can_bo_nguon_id, obj.nhom_hd_id, obj.so_buoi_du_kien, obj.dinh_muc_di_lai, obj.dia_diem_ct, obj.hinh_thuc_ct, obj.dot_phan_cong, obj.ky_phan_cong, obj.ngay_phan_cong, obj.ghi_chu, obj.cbda_quan_ly) if obj.pk else None
                obj.phan_bo = allocation
                obj.can_bo_nguon = item["can_bo"]
                obj.nhom_hd = item["nhom"]
                obj.tre = tre
                obj.loai_dich_vu = item["service"]
                obj.so_buoi_du_kien = item["so_buoi"]
                obj.dinh_muc_di_lai = item["dinh_muc"]
                obj.dia_diem_ct = item["dia_diem"]
                obj.hinh_thuc_ct = item["hinh_thuc"]
                obj.dot_phan_cong = item["dot"]
                obj.ky_phan_cong = item["ky"]
                obj.ngay_phan_cong = item["ngay"]
                obj.ghi_chu = item["ghi_chu"]
                obj.cbda_quan_ly = item["cbda"]
                obj.full_clean()
                obj.save()
                if old_values is None:
                    result.created += 1
                elif old_values == (obj.phan_bo_id, obj.can_bo_nguon_id, obj.nhom_hd_id, obj.so_buoi_du_kien, obj.dinh_muc_di_lai, obj.dia_diem_ct, obj.hinh_thuc_ct, obj.dot_phan_cong, obj.ky_phan_cong, obj.ngay_phan_cong, obj.ghi_chu, obj.cbda_quan_ly):
                    result.unchanged += 1
                else:
                    result.updated += 1
            if validate_only:
                raise _DryRunRollback
    except _DryRunRollback:
        return result
    except Exception:
        logger.exception("Assignment import failed; transaction rolled back")
        result.system_error = True
        result.errors = ["Không thể lưu file phân công; toàn bộ thay đổi đã được hoàn tác."]
    return result
