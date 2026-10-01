from copy import copy
from collections import OrderedDict
from decimal import Decimal
from functools import lru_cache
from io import BytesIO
from pathlib import Path
import re
import unicodedata

from django.conf import settings
from django.core.exceptions import ValidationError

TEMPLATE_ROOT = Path(settings.BASE_DIR) / "quanly" / "document_templates"
INTERVENTION_PAYMENT_TEMPLATE = TEMPLATE_ROOT / "thanh_toan_cong_can_thiep" / "Mau_DNTT.xlsx"
INTERVENTION_ACCOUNT_TEMPLATE = TEMPLATE_ROOT / "thanh_toan_cong_can_thiep" / "Mau_DSTK.xlsx"
INTERVENTION_COMMITMENT_TEMPLATE = TEMPLATE_ROOT / "thanh_toan_cong_can_thiep" / "Mau_DNCK.xlsx"
PARENT_TRAVEL_TEMPLATE_ROOT = TEMPLATE_ROOT / "thanh_toan_di_lai_phu_huynh"
FIRST_DETAIL_ROW = 12
LAST_TEMPLATE_DETAIL_ROW = 50
TOTAL_ROW = 51


def _workbook(path):
    try:
        from openpyxl import load_workbook
    except ImportError as exc:
        raise ValidationError("Thiếu thư viện openpyxl để xuất Excel.") from exc
    # Khong giu external links cua mau Excel. Mau DNCK cu tro toi workbook
    # SharePoint va add-in VND(), lam Excel hien Repair va mat cong thuc.
    workbook = load_workbook(path, keep_links=False)
    for name in list(workbook.defined_names):
        defined_name = workbook.defined_names[name]
        if "[" in (defined_name.attr_text or ""):
            del workbook.defined_names[name]
    # Mẫu DNTT có các bảng kiểu queryTable ở sheet tra cứu ẩn. openpyxl
    # không ghi lại được queryTable/connection tương ứng nhưng vẫn giữ metadata
    # của bảng, khiến Excel phải Repair khi mở file xuất. Các bảng này chỉ phục
    # vụ tra cứu nội bộ nên bỏ metadata, giữ nguyên dữ liệu và sheet.
    for worksheet in workbook.worksheets:
        if worksheet.tables:
            worksheet.tables.clear()
    _normalize_workbook_print_layout(workbook)
    return workbook


def _normalize_workbook_print_layout(workbook):
    """Đặt page setup A4 và lề thống nhất cho workbook xuất ra."""
    from openpyxl.worksheet.page import PageMargins

    for worksheet in workbook.worksheets:
        name = worksheet.title.casefold()
        if name in {"dntt", "dntt_ncs"}:
            orientation = "landscape"
        elif name == "dstk":
            orientation = "landscape"
        elif name.startswith("dnck") or name.startswith("dstk"):
            orientation = "portrait"
        else:
            orientation = "landscape" if worksheet.max_column >= 10 else "portrait"
        worksheet.page_setup.paperSize = worksheet.PAPERSIZE_A4
        worksheet.page_setup.orientation = orientation
        worksheet.page_setup.fitToWidth = 1
        worksheet.page_setup.fitToHeight = 0
        worksheet.page_setup.scale = None
        worksheet.sheet_properties.pageSetUpPr.fitToPage = True
        worksheet.page_margins = PageMargins(
            left=0.5,
            right=0.5,
            top=0.5,
            bottom=0.5,
            header=0.2,
            footer=0.2,
        )


def _set_print_area(worksheet, end_row=None, end_column=None):
    """Giới hạn vùng in đến hết nội dung và phần ký của mẫu."""
    from openpyxl.utils import get_column_letter

    end_row = end_row or worksheet.max_row
    end_column = end_column or worksheet.max_column
    worksheet.print_area = f"A1:{get_column_letter(end_column)}{end_row}"


def _location_bucket(value):
    text = (value or "").strip().lower()
    if "nhà" in text or "nha" in text:
        return "home"
    if "trường" in text or "truong" in text or "cơ sở" in text or "co so" in text:
        return "facility"
    return "other"


def _copy_row_style(ws, source_row, target_row):
    for source, target in zip(ws[source_row], ws[target_row]):
        if source.has_style:
            target._style = copy(source._style)
        target.number_format = source.number_format
        target.alignment = copy(source.alignment)
        target.font = copy(source.font)
        target.fill = copy(source.fill)
        target.border = copy(source.border)
        target.protection = copy(source.protection)
    ws.row_dimensions[target_row].height = ws.row_dimensions[source_row].height


def _clear_detail_rows(ws):
    for row in range(FIRST_DETAIL_ROW, LAST_TEMPLATE_DETAIL_ROW + 1):
        for cell in ws[row]:
            cell.value = None


def _fill_placeholders(workbook, context):
    for ws in workbook.worksheets:
        for row in ws.iter_rows():
            for cell in row:
                if isinstance(cell.value, str):
                    for key, value in context.items():
                        cell.value = cell.value.replace("{{" + key + "}}", str(value or ""))


def _set_requester_name(workbook, requester_name):
    """Ghi ten CBDA vao dong ky 'Nguoi de nghi' neu mau co san vi tri nay."""
    if not requester_name:
        return
    for worksheet in workbook.worksheets:
        # Hai mau can thiep hien hanh khong cung co nhan "Nguoi de nghi":
        # DSTK dung cot J cho Can bo du an, con DNCK de trong cot D khu vuc ky.
        if worksheet.title == "DSTK":
            worksheet["J27"] = requester_name
        elif worksheet.title == "DNCK":
            worksheet["D22"] = "Người đề nghị"
            worksheet["D28"] = requester_name
        for row in worksheet.iter_rows():
            for cell in row:
                if str(cell.value or "").strip().casefold() != "Người đề nghị".casefold():
                    continue
                for offset in range(1, 10):
                    target = worksheet.cell(cell.row + offset, cell.column)
                    if target.value not in (None, ""):
                        target.value = requester_name
                        break


def _blank_zero(value):
    """Giữ kiểu số trong Excel nhưng không hiển thị các giá trị bằng 0."""
    if isinstance(value, (int, float, Decimal)) and value == 0:
        return None
    return value


def _payment_note(value):
    """Loại ghi chú kỹ thuật khi import; chỉ giữ ghi chú nghiệp vụ do người dùng nhập."""
    lines = [line.strip() for line in str(value or "").splitlines() if line.strip()]
    return "\n".join(
        line for line in lines
        if not line.casefold().startswith("dữ liệu lịch sử:")
    )


@lru_cache(maxsize=64)
def _location_for_group(group_code):
    workbook = _workbook(INTERVENTION_PAYMENT_TEMPLATE)
    try:
        if "Dia diem thuc hien" not in workbook.sheetnames:
            return "Theo nhật ký thực hiện"
        ws = workbook["Dia diem thuc hien"]
        for code, location in ws.iter_rows(min_row=2, max_col=2, values_only=True):
            if str(code or "").strip().replace(".0", "") == str(group_code or "").strip():
                return location or "Theo nhật ký thực hiện"
    finally:
        workbook.close()
    return "Theo nhật ký thực hiện"


def export_intervention_payment_request(dot, nguoi_de_nghi=None):
    """Xuất đề nghị thanh toán công cán bộ theo một đợt thanh toán."""
    if not INTERVENTION_PAYMENT_TEMPLATE.exists():
        raise ValidationError("Chưa có template đề nghị thanh toán công cán bộ.")
    rows = list(dot.chi_tiet.select_related("nhat_ky__phan_cong__tre", "nhat_ky__hop_dong").order_by("id"))
    if not rows:
        raise ValidationError("Đợt thanh toán chưa có chi tiết để xuất.")

    workbook = _workbook(INTERVENTION_PAYMENT_TEMPLATE)
    ws = workbook["DNTT"]
    _clear_detail_rows(ws)
    context = {
        "KyThanhToan": f"{dot.thang}/{dot.nam}",
        "TuNgay": dot.hop_dong.tu_ngay.strftime("%d/%m/%Y"),
        "DenNgay": dot.hop_dong.den_ngay.strftime("%d/%m/%Y"),
        "DiaDiemThucHien": "Theo nhật ký thực hiện",
    }

    for index, item in enumerate(rows):
        row_number = FIRST_DETAIL_ROW + index
        if row_number > LAST_TEMPLATE_DETAIL_ROW:
            ws.insert_rows(row_number)
            _copy_row_style(ws, FIRST_DETAIL_ROW, row_number)
        journal = item.nhat_ky
        assignment = journal.phan_cong
        bucket = _location_bucket(assignment.dia_diem_ct)
        planned = assignment.so_buoi_du_kien
        actual = item.so_buoi_thanh_toan
        travel = item.so_luot_di_lai
        values = {
            "A": index + 1,
            "B": f"{journal.hop_dong.can_bo.ho_ten} - {assignment.tre.ho_ten}",
            "C": journal.hop_dong.so_hop_dong,
            "D": assignment.nhom_dich_vu,
            "E": planned if bucket == "facility" else 0,
            "F": planned if bucket == "home" else 0,
            "G": planned if bucket == "other" else 0,
            "H": travel if bucket == "home" else 0,
            "I": journal.don_gia_cong,
            "J": journal.dinh_muc_di_lai,
            "K": f"=E{row_number}*I{row_number}+H{row_number}*J{row_number}",
            "L": actual if bucket == "facility" else 0,
            "M": actual if bucket == "home" else 0,
            "N": actual if bucket == "other" else 0,
            "O": travel,
            "P": f"=(L{row_number}+M{row_number}+N{row_number})*I{row_number}",
            "Q": f"=O{row_number}*J{row_number}",
            "R": f"=P{row_number}+Q{row_number}",
            "S": f"=IF(P{row_number}>=5000000,P{row_number}*10%,0)",
            "T": f"=R{row_number}-S{row_number}",
            "U": item.ghi_chu or "",
        }
        for column, value in values.items():
            ws[f"{column}{row_number}"] = value

    end_row = FIRST_DETAIL_ROW + len(rows) - 1
    for column in ("K", "P", "Q", "R", "S", "T"):
        ws[f"{column}{TOTAL_ROW}"] = f"=SUM({column}{FIRST_DETAIL_ROW}:{column}{end_row})"
    _fill_placeholders(workbook, context)
    _set_requester_name(workbook, getattr(nguoi_de_nghi, "ho_ten", nguoi_de_nghi))
    _set_print_area(ws, max(ws.max_row, TOTAL_ROW), 21)
    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    return output


def export_intervention_account_list(dot, nguoi_de_nghi=None):
    """Xuất danh sách tài khoản và số tiền thực lĩnh của một đợt thanh toán."""
    if not INTERVENTION_ACCOUNT_TEMPLATE.exists():
        raise ValidationError("Chưa có template danh sách tài khoản thanh toán.")
    rows = list(dot.chi_tiet.select_related("nhat_ky__hop_dong__can_bo").order_by("id"))
    if not rows:
        raise ValidationError("Đợt thanh toán chưa có chi tiết để xuất danh sách tài khoản.")

    workbook = _workbook(INTERVENTION_ACCOUNT_TEMPLATE)
    ws = workbook["DSTK"]
    for row in range(5, 20):
        for cell in ws[row]:
            cell.value = None

    staff = dot.hop_dong.can_bo
    gross = sum(item.thanh_tien for item in rows)
    net = sum(item.thuc_linh for item in rows)
    values = {
        "A5": 1,
        "B5": staff.ho_ten,
        "C5": staff.dien_thoai or "",
        "D5": staff.email or "",
        "E5": staff.dia_chi or "",
        "F5": staff.tai_khoan or "",
        "G5": staff.ngan_hang or "",
        "H5": staff.chi_nhanh or "",
        "I5": gross,
        "J5": net,
        "K5": staff.mst or "",
        "L5": staff.cccd or "",
        "I20": "=SUM(I5:I19)",
        "J20": "=SUM(J5:J19)",
    }
    for coordinate, value in values.items():
        ws[coordinate] = value
    _fill_placeholders(workbook, {"DiaDiemThucHien": "Theo hồ sơ thanh toán"})
    _set_requester_name(workbook, getattr(nguoi_de_nghi, "ho_ten", nguoi_de_nghi))
    _set_print_area(ws, 27, 12)
    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    return output


PARENT_TRAVEL_CATEGORIES = {"CG", "NCS", "CBDA"}


def _parent_template(category, prefix):
    category = (category or "NCS").upper()
    if category not in PARENT_TRAVEL_CATEGORIES:
        raise ValidationError("Nhóm mẫu phải là CG, NCS hoặc CBDA.")
    path = PARENT_TRAVEL_TEMPLATE_ROOT / f"Mau_{prefix}_DiLai_{category}.xlsx"
    if not path.exists():
        raise ValidationError(f"Chưa có template {path.name}.")
    return path


def _plain_text(value):
    """Chuẩn hóa chuỗi nghiệp vụ để nhận diện không phụ thuộc dấu tiếng Việt."""
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(char for char in text if not unicodedata.combining(char))
    return " ".join(text.casefold().replace("_", " ").split())


def normalize_parent_travel_category(value):
    """Chuẩn hóa mã nhóm hồ sơ chi phí đi lại của phụ huynh."""
    category = str(value or "NCS").strip().upper()
    if category not in PARENT_TRAVEL_CATEGORIES:
        raise ValidationError("Nhóm hồ sơ phải là CG, NCS hoặc CBDA.")
    return category


def parent_travel_category(journal_or_assignment):
    """Xác định bộ hồ sơ theo dữ liệu gốc, không nhân bản vào nhật ký.

    CBDA được ưu tiên khi ghi chú của trẻ có mã CBDA. Các phân công có hình thức
    ``Chuyên gia`` (hoặc mã CG) dùng bộ CG; phần còn lại dùng bộ NCS.
    """
    assignment = getattr(journal_or_assignment, "phan_cong", journal_or_assignment)
    child = getattr(assignment, "tre", None)
    note = _plain_text(getattr(child, "ghi_chu", ""))
    if re.search(r"(?<!\w)cbda(?!\w)", note) and not re.search(r"\bkhong(?: phai)?\s+cbda\b", note):
        return "CBDA"
    method = _plain_text(getattr(assignment, "hinh_thuc_ct", ""))
    if method in {"cg", "chuyen gia"}:
        return "CG"
    return "NCS"


def _parent_travel_rows(dot, category):
    category = normalize_parent_travel_category(category)
    rows = list(dot.chi_tiet.select_related(
        "nhat_ky__can_bo_nguon",
        "nhat_ky__hop_dong__can_bo",
        "nhat_ky__hop_dong__don_vi",
        "nhat_ky__phan_cong__tre",
        "nhat_ky__phan_cong__phan_bo__can_bo",
    ).order_by("id"))
    rows = [item for item in rows if parent_travel_category(item.nhat_ky) == category]
    if not rows:
        raise ValidationError(f"Đợt thanh toán không có dữ liệu thuộc nhóm hồ sơ {category}.")
    return category, rows


def _parent_travel_date_range(dot, rows):
    """Lấy thời hạn người dùng chọn, rồi mới fallback về thời hạn hợp đồng."""
    if getattr(dot, "tu_ngay", None) and getattr(dot, "den_ngay", None):
        return dot.tu_ngay, dot.den_ngay
    contract = getattr(dot, "hop_dong", None)
    if getattr(dot, "hop_dong_id", None) or contract:
        return contract.tu_ngay, contract.den_ngay
    contracts = []
    for item in rows:
        contract = getattr(item.nhat_ky, "hop_dong_hieu_luc", None) or getattr(item.nhat_ky, "hop_dong", None)
        if contract:
            contracts.append(contract)
    if not contracts:
        return None, None
    return min(contract.tu_ngay for contract in contracts), max(contract.den_ngay for contract in contracts)


def _parent_travel_location(rows):
    """Lấy danh sách xã/phường của các trẻ thực sự phát sinh lượt đi lại."""
    locations = OrderedDict()
    for item in rows:
        child = item.nhat_ky.phan_cong.tre
        xa = getattr(child, "xa", None)
        name = str(getattr(xa, "ten_xa", "") or "").strip()
        if name:
            locations[name] = None
    if not locations:
        return "Chưa cập nhật xã/phường của trẻ có phát sinh đi lại"
    return "Xã/phường " + ", ".join(locations)


def _find_template_sheet(workbook, prefix):
    """Lấy sheet nghiệp vụ theo tiền tố, vì các mẫu hiện tại dùng tên sheet cũ."""
    prefix = prefix.casefold()
    for worksheet in workbook.worksheets:
        if worksheet.title.casefold().startswith(prefix):
            return worksheet
    raise ValidationError(f"Template không có sheet {prefix.upper()}.")


def _clear_template_row(worksheet, row):
    for cell in worksheet[row]:
        if cell.__class__.__name__ == "MergedCell":
            continue
        cell.value = None


def _group_parent_travel_rows(rows):
    grouped = OrderedDict()
    for item in rows:
        child = item.nhat_ky.phan_cong.tre
        key = (
            child.ten_phu_huynh or "",
            child.ten_tai_khoan or "",
            child.tai_khoan or "",
            child.ngan_hang or "",
            child.chi_nhanh or "",
        )
        grouped[key] = grouped.get(key, Decimal("0")) + item.thanh_tien
    return grouped


def _validate_parent_account_rows(rows, category):
    if category == "CBDA":
        raise ValidationError("Nhóm CBDA ký nhận thủ công, không xuất danh sách tài khoản.")
    missing = []
    seen = set()
    for item in rows:
        child = item.nhat_ky.phan_cong.tre
        key = child.pk
        if key in seen:
            continue
        seen.add(key)
        if not (child.tai_khoan and child.ngan_hang):
            missing.append(f"{child.ma_tre} - {child.ho_ten}")
    if missing:
        names = ", ".join(missing[:5])
        suffix = "..." if len(missing) > 5 else ""
        raise ValidationError(
            f"Nhóm {category} yêu cầu phụ huynh có số tài khoản và ngân hàng. "
            f"Chưa đủ thông tin: {names}{suffix}."
        )


def _parent_travel_payment_groups(rows):
    """Gom nhật ký thành dòng tổng theo CBCT/hợp đồng và dòng chi tiết theo trẻ/dịch vụ."""
    grouped = OrderedDict()
    for item in rows:
        journal = item.nhat_ky
        assignment = journal.phan_cong
        child = assignment.tre
        contract = getattr(journal, "hop_dong_hieu_luc", None) or getattr(journal, "hop_dong", None)
        provider = journal.can_bo_hieu_luc or getattr(contract, "doi_tac", None) or getattr(contract, "can_bo", None)
        provider_name = (
            getattr(provider, "ho_ten", None)
            or getattr(provider, "ten_don_vi", None)
            or getattr(contract, "so_hop_dong", None)
            or "Chưa xác định CBCT/đơn vị"
        )
        group_key = (getattr(contract, "pk", None), provider_name, getattr(contract, "so_hop_dong", ""))
        group = grouped.setdefault(group_key, {
            "provider_name": provider_name,
            "contract_name": getattr(contract, "so_hop_dong", "") or "",
            "details": OrderedDict(),
                "journals": [],
            "planned": 0,
            "actual_sessions": 0,
            "travel": 0,
            "amount": Decimal("0"),
            "rates": OrderedDict(),
        })
        service = getattr(assignment, "nhom_dich_vu", None) or getattr(assignment, "loai_dich_vu", None) or ""
        child_key = getattr(child, "pk", None) or getattr(child, "ma_tre", None) or id(child)
        detail_key = (
            child_key,
            service,
            assignment.so_buoi_du_kien or 0,
            item.dinh_muc_di_lai or Decimal("0"),
        )
        detail = group["details"].setdefault(detail_key, {
            "child_name": child.ho_ten,
            "parent_name": child.ten_phu_huynh or "",
            "service": service,
            "planned": assignment.so_buoi_du_kien or 0,
            "rate": item.dinh_muc_di_lai or Decimal("0"),
            "actual_sessions": 0,
            "travel": 0,
            "amount": Decimal("0"),
            "notes": [],
        })
        detail["actual_sessions"] += journal.so_buoi_thuc_hien or 0
        detail["travel"] += item.so_luot_di_lai or 0
        detail["amount"] += item.thanh_tien or Decimal("0")
        note = _payment_note(item.ghi_chu)
        if note and note not in detail["notes"]:
            detail["notes"].append(note)
        group["actual_sessions"] += journal.so_buoi_thuc_hien or 0
        group["travel"] += item.so_luot_di_lai or 0
        group["amount"] += item.thanh_tien or Decimal("0")
        group["rates"][str(item.dinh_muc_di_lai or 0)] = item.dinh_muc_di_lai or Decimal("0")
    return list(grouped.values())


def _parent_travel_total_row(ws):
    for row in range(1, ws.max_row + 1):
        if str(ws.cell(row, 2).value or "").strip().casefold() == "tổng cộng":
            return row
    raise ValidationError("Template ĐNTT đi lại không có dòng Tổng cộng.")


def export_parent_travel_payment_request(dot, category="NCS", nguoi_de_nghi=None):
    category, rows = _parent_travel_rows(dot, category)
    workbook = _workbook(_parent_template(category, "DNTT"))
    ws = _find_template_sheet(workbook, "DNTT")
    first_row = 11
    total_row = _parent_travel_total_row(ws)
    rendered_groups = _parent_travel_payment_groups(rows)
    rendered_rows = sum(1 + len(group["details"]) for group in rendered_groups)
    capacity = total_row - first_row
    if rendered_rows > capacity:
        extra = rendered_rows - capacity
        for offset in range(extra):
            insert_at = total_row + offset
            ws.insert_rows(insert_at, 1)
            _copy_row_style(ws, total_row - 1, insert_at)
        total_row += extra
    for row in range(first_row, total_row):
        _clear_template_row(ws, row)
    output_row = first_row
    summary_rows = []
    for index, group in enumerate(rendered_groups, start=1):
        group_rate = next(iter(group["rates"].values())) if len(group["rates"]) == 1 else None
        group_planned = sum(detail["planned"] for detail in group["details"].values())
        group_budget = sum(detail["planned"] * detail["rate"] for detail in group["details"].values())
        single_parent = ""
        if len(group["details"]) == 1:
            single_parent = next(iter(group["details"].values()))["parent_name"]
        summary = {
            1: index,
            2: group["provider_name"],
            3: single_parent,
            4: group["contract_name"],
            5: "",
            6: _blank_zero(group_planned),
            7: _blank_zero(group_rate),
            8: _blank_zero(group_budget),
            9: _blank_zero(group["actual_sessions"]),
            10: _blank_zero(group["travel"]),
            11: _blank_zero(group["amount"]),
            12: "",
        }
        for column, value in summary.items():
            ws.cell(output_row, column).value = value
        summary_rows.append(output_row)
        output_row += 1
        for detail in group["details"].values():
            values = {
                1: "",
                2: detail["child_name"],
                3: detail["parent_name"],
                4: "",
                5: detail["service"],
                6: _blank_zero(detail["planned"]),
                7: _blank_zero(detail["rate"]),
                8: _blank_zero(detail["planned"] * detail["rate"]),
                9: _blank_zero(detail["actual_sessions"]),
                10: _blank_zero(detail["travel"]),
                11: _blank_zero(detail["amount"]),
                12: "\n".join(detail["notes"]),
            }
            for column, value in values.items():
                ws.cell(output_row, column).value = value
            output_row += 1
    if len(summary_rows) == 1:
        summary_refs_h = f"H{summary_rows[0]}:H{summary_rows[0]}"
        summary_refs_k = f"K{summary_rows[0]}:K{summary_rows[0]}"
    else:
        summary_refs_h = ",".join(f"H{row}" for row in summary_rows)
        summary_refs_k = ",".join(f"K{row}" for row in summary_rows)
    ws.cell(total_row, 8).value = f"=SUM({summary_refs_h})"
    ws.cell(total_row, 11).value = f"=SUM({summary_refs_k})"
    tu_ngay, den_ngay = _parent_travel_date_range(dot, rows)
    ws["K5"] = _parent_travel_location(rows)
    _fill_placeholders(workbook, {
        "KyThanhToan": f"{dot.thang}/{dot.nam}",
        "TuNgay": tu_ngay.strftime("%d/%m/%Y") if tu_ngay else "",
        "DenNgay": den_ngay.strftime("%d/%m/%Y") if den_ngay else "",
    })
    _set_requester_name(workbook, getattr(nguoi_de_nghi, "ho_ten", nguoi_de_nghi))
    _set_print_area(ws, max(ws.max_row, total_row), 12)
    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    return output


def export_parent_travel_account_list(dot, category="NCS", nguoi_de_nghi=None):
    category, rows = _parent_travel_rows(dot, category)
    _validate_parent_account_rows(rows, category)
    workbook = _workbook(_parent_template(category, "DSTK"))
    ws = _find_template_sheet(workbook, "DSTK")
    first_row, last_row = 5, 120
    for row in range(first_row, last_row + 1):
        _clear_template_row(ws, row)
    grouped = _group_parent_travel_rows(rows)
    for index, (key, amount) in enumerate(grouped.items(), start=1):
        row = first_row + index - 1
        if row > last_row:
            raise ValidationError("Số người nhận vượt giới hạn template.")
        parent, account_name, account, bank, branch = key
        for column, value in enumerate((index, parent, account, bank, branch, amount), start=1):
            ws.cell(row, column).value = value
    ws["A2"] = _parent_travel_location(rows)
    _fill_placeholders(workbook, {"DiaDiemThucHien": _parent_travel_location(rows)})
    _set_requester_name(workbook, getattr(nguoi_de_nghi, "ho_ten", nguoi_de_nghi))
    _set_print_area(ws, 128, 6)
    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    return output


def export_parent_travel_commitment(dot, category="NCS", nguoi_de_nghi=None):
    """Xuất DNCK theo từng phụ huynh, dùng cho nhóm NCS hoặc CG."""
    category, rows = _parent_travel_rows(dot, category)
    _validate_parent_account_rows(rows, category)
    workbook = _workbook(_parent_template(category, "DNCK"))
    ws = _find_template_sheet(workbook, "DNCK")
    first_row, last_row = 4, 119
    for row in range(first_row, last_row + 1):
        _clear_template_row(ws, row)
    grouped = _group_parent_travel_rows(rows)
    for index, (key, amount) in enumerate(grouped.items(), start=1):
        row = first_row + index - 1
        if row > last_row:
            raise ValidationError("Số người nhận vượt giới hạn template DNCK.")
        parent, _account_name, account, bank, branch = key
        for column, value in enumerate((index, parent, account, bank, branch, amount), start=1):
            ws.cell(row, column).value = value
    tu_ngay, den_ngay = _parent_travel_date_range(dot, rows)
    _fill_placeholders(workbook, {
        "KyThanhToan": f"{dot.thang}/{dot.nam}",
        "TuNgay": tu_ngay.strftime("%d/%m/%Y") if tu_ngay else "",
        "DenNgay": den_ngay.strftime("%d/%m/%Y") if den_ngay else "",
    })
    _set_requester_name(workbook, getattr(nguoi_de_nghi, "ho_ten", nguoi_de_nghi))
    _set_print_area(ws, 128, 6)
    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    return output


def _journal_totals(journals):
    labor = sum((Decimal(row.so_buoi_thuc_hien) * Decimal(row.don_gia_cong) for row in journals), Decimal("0"))
    travel = sum((Decimal(row.so_luot_di_lai_cbct) * Decimal(row.dinh_muc_di_lai) for row in journals), Decimal("0"))
    return labor, travel


def _group_journal_payment_rows(journals):
    """Gom nhật ký theo CBCT, sau đó theo đúng dòng phân công của trẻ.

    Một dòng nhật ký là một phiên can thiệp. ĐNTT chỉ hiển thị một dòng cho
    mỗi phân công (trẻ + dịch vụ + đợt phân công), và một dòng tổng cho CBCT.
    """
    grouped = OrderedDict()
    for journal in journals:
        staff = getattr(journal, "can_bo_hieu_luc", None) or getattr(getattr(journal, "hop_dong", None), "can_bo", None)
        if not staff:
            continue
        staff_key = staff.pk
        if staff_key not in grouped:
            grouped[staff_key] = {
                "staff": staff,
                "contracts": OrderedDict(),
                "details": OrderedDict(),
                "journals": [],
            }
        staff_group = grouped[staff_key]
        staff_group["journals"].append(journal)
        contract = getattr(journal, "hop_dong_hieu_luc", None) or getattr(journal, "hop_dong", None)
        if contract:
            staff_group["contracts"][contract.pk] = contract
        detail_key = journal.phan_cong_id
        if detail_key not in staff_group["details"]:
            assignment = journal.phan_cong
            bucket = _location_bucket(assignment.dia_diem_ct or journal.dia_diem_ct)
            planned = int(assignment.so_buoi_du_kien or 0)
            staff_group["details"][detail_key] = {
                "assignment": assignment,
                "child": assignment.tre,
                "service": assignment.loai_dich_vu,
                "planned_facility": planned if bucket == "facility" else 0,
                "planned_home": planned if bucket == "home" else 0,
                "planned_other": planned if bucket == "other" else 0,
                "planned_travel": planned if bucket in {"home", "other"} else 0,
                "actual_facility": 0,
                "actual_home": 0,
                "actual_other": 0,
                "actual_travel": 0,
                "labor": Decimal("0"),
                "travel": Decimal("0"),
                "labor_rate": Decimal(journal.don_gia_cong),
                "travel_rate": Decimal(journal.dinh_muc_di_lai),
                "notes": [],
            }
        detail = staff_group["details"][detail_key]
        bucket = _location_bucket(journal.dia_diem_ct or journal.phan_cong.dia_diem_ct)
        detail[f"actual_{bucket}"] += int(journal.so_buoi_thuc_hien or 0)
        detail["actual_travel"] += int(journal.so_luot_di_lai_cbct or 0)
        detail["labor"] += Decimal(journal.so_buoi_thuc_hien or 0) * Decimal(journal.don_gia_cong)
        detail["travel"] += Decimal(journal.so_luot_di_lai_cbct or 0) * Decimal(journal.dinh_muc_di_lai)
        note = _payment_note(journal.ghi_chu)
        if note and note not in detail["notes"]:
            detail["notes"].append(note)

    for staff_group in grouped.values():
        details = list(staff_group["details"].values())
        staff_group["details"] = details
        staff_group["planned_facility"] = sum(x["planned_facility"] for x in details)
        staff_group["planned_home"] = sum(x["planned_home"] for x in details)
        staff_group["planned_other"] = sum(x["planned_other"] for x in details)
        staff_group["planned_travel"] = sum(x["planned_travel"] for x in details)
        staff_group["actual_facility"] = sum(x["actual_facility"] for x in details)
        staff_group["actual_home"] = sum(x["actual_home"] for x in details)
        staff_group["actual_other"] = sum(x["actual_other"] for x in details)
        staff_group["actual_travel"] = sum(x["actual_travel"] for x in details)
        staff_group["labor"] = sum((x["labor"] for x in details), Decimal("0"))
        staff_group["travel"] = sum((x["travel"] for x in details), Decimal("0"))
    return list(grouped.values())


def _selection_context(journals, ky="", thang="", nam="", tu_ngay="", den_ngay=""):
    first = journals[0]
    group = first.nhom_hd_hieu_luc
    location = _location_for_group(group.ma_nhom_hd)
    return {
        "KyThanhToan": ky or first.ky_can_thiep,
        "TuNgay": tu_ngay,
        "DenNgay": den_ngay,
        "DiaDiemThucHien": location,
        "NhomHD": group.ma_nhom_hd,
        "Thang": thang,
        "Nam": nam,
    }


def export_journal_account_list(journals, nguoi_de_nghi=None):
    journals = list(journals)
    if not journals:
        raise ValidationError("Không có nhật ký phù hợp để xuất DSTK.")
    workbook = _workbook(INTERVENTION_ACCOUNT_TEMPLATE)
    ws = workbook["DSTK"]
    for row in range(5, 20):
        for cell in ws[row]:
            cell.value = None
    grouped = {}
    for journal in journals:
        staff = getattr(journal, "can_bo_hieu_luc", None) or getattr(getattr(journal, "hop_dong", None), "can_bo", None)
        if staff:
            grouped.setdefault(staff.pk, (staff, []))[1].append(journal)
    if len(grouped) > 15:
        raise ValidationError("DSTK hiện hỗ trợ tối đa 15 CBCT trong một Nhóm HĐ/kỳ.")
    total_net = Decimal("0")
    for index, (staff, items) in enumerate(grouped.values(), start=1):
        row = 4 + index
        labor, travel = _journal_totals(items)
        from .services.payment_ledger import journal_payment_breakdown
        net = journal_payment_breakdown(items)["thuc_linh"]
        total_net += net
        for column, value in enumerate((index, staff.ho_ten, staff.dien_thoai or "", staff.email or "", staff.dia_chi or "", staff.tai_khoan or "", staff.ngan_hang or "", staff.chi_nhanh or "", labor + travel, net, staff.mst or "", staff.cccd or ""), start=1):
            ws.cell(row, column).value = value
    ws["J20"] = total_net
    _fill_placeholders(workbook, _selection_context(journals))
    _set_requester_name(workbook, getattr(nguoi_de_nghi, "ho_ten", nguoi_de_nghi))
    if "DataStaff" in workbook.sheetnames:
        workbook["DataStaff"].sheet_state = "hidden"
    _set_print_area(ws, 27, 12)
    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    return output


def export_journal_payment_request_excel(
    journals, ky="", thang="", nam="", tu_ngay="", den_ngay="", nguoi_de_nghi=None
):
    journals = list(journals)
    if not journals:
        raise ValidationError("Không có nhật ký phù hợp để xuất ĐNTT Excel.")
    workbook = _workbook(INTERVENTION_PAYMENT_TEMPLATE)
    ws = workbook["DNTT"]
    for cells in ws.iter_rows(max_row=FIRST_DETAIL_ROW - 1):
        for cell in cells:
            if isinstance(cell.value, str) and "10%" in cell.value:
                cell.value = "Theo phiếu"
    _clear_detail_rows(ws)
    staff_groups = _group_journal_payment_rows(journals)
    output_rows = sum(1 + len(group["details"]) for group in staff_groups)
    total_row = TOTAL_ROW
    extra_rows = max(0, output_rows - (LAST_TEMPLATE_DETAIL_ROW - FIRST_DETAIL_ROW + 1))
    for _ in range(extra_rows):
        ws.insert_rows(total_row)
        _copy_row_style(ws, LAST_TEMPLATE_DETAIL_ROW, total_row)
        total_row += 1
    from openpyxl.styles import PatternFill
    from .services.payment_ledger import journal_payment_breakdown

    summary_fill = PatternFill(fill_type="solid", fgColor="FFF200")
    row = FIRST_DETAIL_ROW
    for index, group in enumerate(staff_groups, start=1):
        contracts = list(group["contracts"].values())
        labor_rate = group["details"][0]["labor_rate"] if group["details"] else Decimal("0")
        travel_rate = group["details"][0]["travel_rate"] if group["details"] else Decimal("0")
        planned_total = sum(
            (
                Decimal(detail["planned_facility"] + detail["planned_home"] + detail["planned_other"]) * detail["labor_rate"]
                + Decimal(detail["planned_travel"]) * detail["travel_rate"]
                for detail in group["details"]
            ),
            Decimal("0"),
        )
        breakdown = journal_payment_breakdown(group["journals"])
        summary_values = (
            index,
            group["staff"].ho_ten,
            ", ".join(item.so_hop_dong for item in contracts),
            "",
            group["planned_facility"], group["planned_home"], group["planned_other"], group["planned_travel"],
            labor_rate, travel_rate, planned_total,
            group["actual_facility"], group["actual_home"], group["actual_other"], group["actual_travel"],
            group["labor"], group["travel"], breakdown["tong_truoc_thue"], breakdown["thue_tncn"], breakdown["thuc_linh"], "",
        )
        for column, value in enumerate(summary_values, start=1):
            ws.cell(row, column).value = _blank_zero(value)
            ws.cell(row, column).fill = copy(summary_fill)
            font = copy(ws.cell(row, column).font)
            font.bold = True
            ws.cell(row, column).font = font
        row += 1
        for detail in group["details"]:
            planned_total = (
                Decimal(detail["planned_facility"] + detail["planned_home"] + detail["planned_other"]) * detail["labor_rate"]
                + Decimal(detail["planned_travel"]) * detail["travel_rate"]
            )
            gross = detail["labor"] + detail["travel"]
            detail_values = (
                "", detail["child"].ho_ten, "", detail["service"],
                detail["planned_facility"], detail["planned_home"], detail["planned_other"], detail["planned_travel"],
                detail["labor_rate"], detail["travel_rate"], planned_total,
                detail["actual_facility"], detail["actual_home"], detail["actual_other"], detail["actual_travel"],
                detail["labor"], detail["travel"], gross, "", gross, "; ".join(detail["notes"]),
            )
            for column, value in enumerate(detail_values, start=1):
                ws.cell(row, column).value = _blank_zero(value)
            row += 1

    totals = {
        "K": sum((
            Decimal(detail["planned_facility"] + detail["planned_home"] + detail["planned_other"]) * detail["labor_rate"]
            + Decimal(detail["planned_travel"]) * detail["travel_rate"]
            for group in staff_groups for detail in group["details"]
        ), Decimal("0")),
        "P": sum((group["labor"] for group in staff_groups), Decimal("0")),
        "Q": sum((group["travel"] for group in staff_groups), Decimal("0")),
    }
    totals["R"] = totals["P"] + totals["Q"]
    totals["S"] = sum((journal_payment_breakdown(group["journals"])["thue_tncn"] for group in staff_groups), Decimal("0"))
    totals["T"] = totals["R"] - totals["S"]
    for column, value in totals.items():
        ws[f"{column}{total_row}"] = _blank_zero(value)
    context = _selection_context(
        journals,
        ky=ky,
        thang=thang,
        nam=nam,
        tu_ngay=tu_ngay,
        den_ngay=den_ngay,
    )
    _fill_placeholders(workbook, context)
    _set_requester_name(workbook, getattr(nguoi_de_nghi, "ho_ten", nguoi_de_nghi))
    ws.print_title_rows = "8:11"
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    _set_print_area(ws, max(ws.max_row, total_row), 21)
    for helper_name in ("Dia diem thuc hien", "DataStaff"):
        if helper_name in workbook.sheetnames:
            workbook[helper_name].sheet_state = "hidden"
    output = BytesIO(); workbook.save(output); output.seek(0); return output


def export_journal_commitment(journals, tu_ngay="", den_ngay="", nguoi_de_nghi=None):
    journals = list(journals)
    if not journals:
        raise ValidationError("Không có nhật ký phù hợp để xuất ĐNCK.")
    workbook = _workbook(INTERVENTION_COMMITMENT_TEMPLATE)
    ws = workbook["DNCK"]
    for row in range(5, 26):
        for cell in ws[row]:
            try:
                cell.value = None
            except AttributeError:
                # Một số template gộp ô ở khu vực cuối bảng.
                pass
    grouped = {}
    for journal in journals:
        staff = getattr(journal, "can_bo_hieu_luc", None) or getattr(getattr(journal, "hop_dong", None), "can_bo", None)
        if staff:
            grouped.setdefault(staff.pk, (staff, []))[1].append(journal)
    if len(grouped) > 14:
        raise ValidationError("ĐNCK hiện hỗ trợ tối đa 14 CBCT trong một Nhóm HĐ/kỳ.")
    total_net = Decimal("0")
    for index, (staff, items) in enumerate(grouped.values(), start=1):
        row = 4 + index
        labor, travel = _journal_totals(items)
        from .services.payment_ledger import journal_payment_breakdown
        net = journal_payment_breakdown(items)["thuc_linh"]
        total_net += net
        for column, value in enumerate((index, staff.ho_ten, staff.dia_chi or "", staff.tai_khoan or "", staff.ngan_hang or "", staff.chi_nhanh or "", net), start=1):
            ws.cell(row, column).value = value
    ws["G19"] = total_net
    _fill_placeholders(workbook, {"TuNgay": tu_ngay, "DenNgay": den_ngay})
    # A20 cua mau cu dung add-in VND() tu file ngoai. Ghi truc tiep de file
    # tu chu, mo duoc tren may khong cai add-in va khong bi Excel Repair.
    from .document_export import _number_to_words
    ws["A20"] = f"Tổng cộng số tiền bằng chữ: {_number_to_words(total_net)}"
    _set_requester_name(workbook, getattr(nguoi_de_nghi, "ho_ten", nguoi_de_nghi))
    _set_print_area(ws, 30, 7)
    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    return output
