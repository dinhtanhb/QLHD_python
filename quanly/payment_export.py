from copy import copy
from io import BytesIO
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError

from .financial import calculate_payment_breakdown


TEMPLATE_ROOT = Path(settings.BASE_DIR) / "quanly" / "document_templates"
INTERVENTION_PAYMENT_TEMPLATE = TEMPLATE_ROOT / "thanh_toan_cong_can_thiep" / "Mau_DNTT.xlsx"
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
        breakdown = calculate_payment_breakdown(item.tien_cong, item.tien_di_lai)
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
