from copy import copy
from io import BytesIO
from pathlib import Path

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
    return load_workbook(path)


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


def export_intervention_payment_request(dot):
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
    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    return output


def export_intervention_account_list(dot):
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


def export_parent_travel_payment_request(dot, category="NCS"):
    rows = list(dot.chi_tiet.select_related("nhat_ky__hop_dong__can_bo", "nhat_ky__phan_cong__tre").order_by("id"))
    if not rows:
        raise ValidationError("Đợt thanh toán chưa có chi tiết để xuất.")
    workbook = _workbook(_parent_template(category, "DNTT"))
    ws = workbook["DNTT_NCS"]
    first_row, last_row = 11, ws.max_row - 8
    for row in range(first_row, last_row + 1):
        for cell in ws[row]:
            cell.value = None
    for index, item in enumerate(rows, start=1):
        row = first_row + index - 1
        if row > last_row:
            raise ValidationError("Số dòng thanh toán vượt giới hạn template.")
        journal = item.nhat_ky
        assignment = journal.phan_cong
        child = assignment.tre
        ws.cell(row, 1).value = index
        ws.cell(row, 2).value = f"{journal.hop_dong.can_bo.ho_ten} - {child.ho_ten}"
        ws.cell(row, 3).value = child.ten_phu_huynh or ""
        ws.cell(row, 4).value = journal.hop_dong.so_hop_dong
        ws.cell(row, 5).value = assignment.nhom_dich_vu
        ws.cell(row, 6).value = assignment.so_buoi_du_kien
        ws.cell(row, 7).value = item.dinh_muc_di_lai
        ws.cell(row, 8).value = f"=F{row}*G{row}"
        ws.cell(row, 9).value = item.so_luot_di_lai
        ws.cell(row, 10).value = item.so_luot_di_lai
        ws.cell(row, 11).value = f"=J{row}*G{row}"
        ws.cell(row, 12).value = item.ghi_chu or ""
    _fill_placeholders(workbook, {"KyThanhToan": f"{dot.thang}/{dot.nam}", "TuNgay": dot.hop_dong.tu_ngay.strftime("%d/%m/%Y"), "DenNgay": dot.hop_dong.den_ngay.strftime("%d/%m/%Y")})
    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    return output


def export_parent_travel_account_list(dot, category="NCS"):
    rows = list(dot.chi_tiet.select_related("nhat_ky__phan_cong__tre").order_by("id"))
    if not rows:
        raise ValidationError("Đợt thanh toán chưa có chi tiết để xuất danh sách tài khoản.")
    workbook = _workbook(_parent_template(category, "DSTK"))
    ws = workbook["DSTK_NCS"]
    first_row, last_row = 5, ws.max_row - 5
    for row in range(first_row, last_row + 1):
        for cell in ws[row]:
            cell.value = None
    grouped = {}
    for item in rows:
        child = item.nhat_ky.phan_cong.tre
        key = (child.ten_phu_huynh or "", child.ten_tai_khoan or "", child.tai_khoan or "", child.ngan_hang or "", child.chi_nhanh or "")
        grouped[key] = grouped.get(key, 0) + item.thanh_tien
    for index, (key, amount) in enumerate(grouped.items(), start=1):
        row = first_row + index - 1
        if row > last_row:
            raise ValidationError("Số người nhận vượt giới hạn template.")
        parent, account_name, account, bank, branch = key
        for column, value in enumerate((index, parent, account, bank, branch, amount), start=1):
            ws.cell(row, column).value = value
    _fill_placeholders(workbook, {"DiaDiemThucHien": "Theo hồ sơ thanh toán"})
    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    return output


def _journal_totals(journals):
    from decimal import Decimal
    labor = sum((Decimal(row.so_buoi_thuc_hien) * Decimal(row.don_gia_cong) for row in journals), Decimal("0"))
    travel = sum((Decimal(row.so_luot_di_lai) * Decimal(row.dinh_muc_di_lai) for row in journals), Decimal("0"))
    return labor, travel


def export_journal_account_list(journals):
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
        staff = journal.hop_dong.can_bo
        grouped.setdefault(staff.pk, (staff, []))[1].append(journal)
    for index, (staff, items) in enumerate(grouped.values(), start=1):
        row = 4 + index
        labor, travel = _journal_totals(items)
        from .financial import calculate_payment_breakdown
        net = calculate_payment_breakdown(labor, travel)["thuc_linh"]
        for column, value in enumerate((index, staff.ho_ten, staff.dien_thoai or "", staff.email or "", staff.dia_chi or "", staff.tai_khoan or "", staff.ngan_hang or "", staff.chi_nhanh or "", labor + travel, net, staff.mst or "", staff.cccd or ""), start=1):
            ws.cell(row, column).value = value
    ws["I20"] = "=SUM(I5:I19)"
    ws["J20"] = "=SUM(J5:J19)"
    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    return output


def export_journal_commitment(journals, tu_ngay="", den_ngay=""):
    journals = list(journals)
    if not journals:
        raise ValidationError("Không có nhật ký phù hợp để xuất ĐNCK.")
    workbook = _workbook(INTERVENTION_COMMITMENT_TEMPLATE)
    ws = workbook["DNCK"]
    for row in range(5, 26):
        for cell in ws[row]:
            cell.value = None
    grouped = {}
    for journal in journals:
        staff = journal.hop_dong.can_bo
        grouped.setdefault(staff.pk, (staff, []))[1].append(journal)
    for index, (staff, items) in enumerate(grouped.values(), start=1):
        row = 4 + index
        labor, travel = _journal_totals(items)
        from .financial import calculate_payment_breakdown
        net = calculate_payment_breakdown(labor, travel)["thuc_linh"]
        for column, value in enumerate((index, staff.ho_ten, staff.dia_chi or "", staff.tai_khoan or "", staff.ngan_hang or "", staff.chi_nhanh or "", net), start=1):
            ws.cell(row, column).value = value
    _fill_placeholders(workbook, {"TuNgay": tu_ngay, "DenNgay": den_ngay})
    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    return output
