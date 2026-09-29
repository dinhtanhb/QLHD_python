from collections import defaultdict
from decimal import Decimal

from django.db.models import Count, DecimalField, ExpressionWrapper, F, OuterRef, Q, Subquery, Sum

from .models import ChiTietPhieuThanhToan, NhatKyThucHien


def _paid_subquery(field):
    return Subquery(
        ChiTietPhieuThanhToan.objects.filter(nhat_ky_id=OuterRef("pk"), hoat_dong=True)
        .values("nhat_ky_id").annotate(total=Sum(field)).values("total")[:1],
        output_field=DecimalField(max_digits=18, decimal_places=0),
    )


def _annotated_journal_queryset():
    labor = ExpressionWrapper(F("so_buoi_thuc_hien") * F("don_gia_cong"), output_field=DecimalField(max_digits=18, decimal_places=0))
    travel = ExpressionWrapper(F("so_luot_di_lai_cbct") * F("dinh_muc_di_lai"), output_field=DecimalField(max_digits=18, decimal_places=0))
    return NhatKyThucHien.objects.filter(hop_dong__isnull=False).select_related(
        "hop_dong__can_bo__don_vi", "hop_dong__don_vi", "hop_dong__nhom_hd", "nhom_hd_nguon",
        "can_bo_nguon__don_vi", "phan_cong__tre", "phan_cong__nhom_hd",
        "phan_cong__phan_bo__can_bo__don_vi", "phan_cong__phan_bo__nhom_hd",
    ).annotate(
        tien_cong_tinh=labor, tien_di_lai_tinh=travel,
        paid_tien_cong=_paid_subquery("tien_cong"), paid_tien_di_lai=_paid_subquery("tien_di_lai"),
    ).order_by("ngay_thuc_hien", "id")


def intervention_report_queryset(*, nhom_hd_id=None, hop_dong_id=None, ky=None, nam=None, tu_ngay=None, den_ngay=None):
    queryset = _annotated_journal_queryset()
    if hop_dong_id:
        queryset = queryset.filter(hop_dong_id=hop_dong_id)
    if nhom_hd_id:
        queryset = queryset.filter(
            Q(nhom_hd_nguon_id=nhom_hd_id)
            | Q(nhom_hd_nguon__isnull=True, hop_dong__nhom_hd_id=nhom_hd_id)
            | Q(nhom_hd_nguon__isnull=True, hop_dong__nhom_hd__isnull=True, phan_cong__nhom_hd_id=nhom_hd_id)
            | Q(nhom_hd_nguon__isnull=True, hop_dong__nhom_hd__isnull=True, phan_cong__nhom_hd__isnull=True, phan_cong__phan_bo__nhom_hd_id=nhom_hd_id)
        )
    if ky:
        queryset = queryset.filter(ky_can_thiep=ky)
    if nam:
        queryset = queryset.filter(ngay_thuc_hien__year=nam)
    if tu_ngay:
        queryset = queryset.filter(ngay_thuc_hien__gte=tu_ngay)
    if den_ngay:
        queryset = queryset.filter(ngay_thuc_hien__lte=den_ngay)
    return queryset


def _group_for(journal):
    if journal.nhom_hd_nguon_id:
        return journal.nhom_hd_nguon
    if journal.hop_dong_id and journal.hop_dong.nhom_hd_id:
        return journal.hop_dong.nhom_hd
    if journal.phan_cong.nhom_hd_id:
        return journal.phan_cong.nhom_hd
    return journal.phan_cong.phan_bo.nhom_hd if journal.phan_cong.phan_bo_id else None


def _group_label(group):
    return f"{group.ma_nhom_hd} - {group.ten_nhom_hd}" if group else "Chưa xác định"


def _amount(value):
    return Decimal(value or 0)


def _metrics(queryset):
    values = queryset.aggregate(
        so_hop_dong=Count("hop_dong_id", distinct=True), so_nhat_ky=Count("pk"), so_buoi=Sum("so_buoi_thuc_hien"), di_lai=Sum("so_luot_di_lai_cbct"),
        tien_cong=Sum("tien_cong_tinh"), tien_di_lai=Sum("tien_di_lai_tinh"),
        # MySQL không cho tham chiếu alias của một Subquery trong SUM bên ngoài;
        # truyền biểu thức trực tiếp để tương thích cả SQLite và MySQL.
        paid_tien_cong=Sum(_paid_subquery("tien_cong")),
        paid_tien_di_lai=Sum(_paid_subquery("tien_di_lai")),
    )
    tien_cong, tien_di_lai = _amount(values["tien_cong"]), _amount(values["tien_di_lai"])
    return {
        "so_hop_dong": values["so_hop_dong"] or 0, "so_nhat_ky": values["so_nhat_ky"] or 0, "so_buoi": values["so_buoi"] or 0,
        "di_lai": values["di_lai"] or 0, "tien_cong": tien_cong, "tien_di_lai": tien_di_lai,
        "tong_gross": tien_cong + tien_di_lai,
        "da_thanh_toan": _amount(values["paid_tien_cong"]) + _amount(values["paid_tien_di_lai"]),
    }


def _new_contract_row(journal, group):
    contract = journal.hop_dong
    partner = contract.can_bo or contract.don_vi
    if getattr(partner, "ma_can_bo", None):
        partner_label = f"{partner.ma_can_bo} - {partner.ho_ten}"
    elif partner:
        partner_label = f"{partner.ma_don_vi} - {partner.ten_don_vi}"
    else:
        partner_label = "Chưa xác định"
    return {
        "hop_dong_id": contract.pk, "so_hop_dong": contract.so_hop_dong, "doi_tac": partner_label,
        "nhom": _group_label(group), "ngay_ky": contract.ngay_ky, "ky": journal.ky_can_thiep,
        "so_nhat_ky": 0, "so_buoi": 0, "di_lai": 0,
        "tien_cong": Decimal("0"), "tien_di_lai": Decimal("0"), "da_thanh_toan": Decimal("0"),
    }


def build_intervention_report(queryset, *, year_queryset=None, since_signing_queryset=None, report_year=None):
    """Tạo báo cáo thanh toán theo số HĐ, đồng thời giữ khóa dữ liệu cũ cho tương thích."""
    journals = list(queryset)
    by_contract, by_group, by_child = defaultdict(lambda: None), defaultdict(lambda: {
        "nhom": "Chưa xác định", "ky": 0, "so_nhat_ky": 0, "so_buoi": 0, "di_lai": 0,
        "tien_cong": Decimal("0"), "tien_di_lai": Decimal("0"), "da_thanh_toan": Decimal("0"),
    }), defaultdict(lambda: {
        "ma_tre": "", "ho_ten": "", "dich_vu": "", "nhom": "Chưa xác định", "ky": 0,
        "so_buoi": 0, "di_lai": 0, "tien_cong": Decimal("0"), "tien_di_lai": Decimal("0"),
    })
    missing_group = conflict_count = 0
    for journal in journals:
        group = _group_for(journal)
        group_code, group_name = (group.ma_nhom_hd if group else "?"), _group_label(group)
        contract_key = (journal.hop_dong_id, journal.ky_can_thiep)
        contract_row = by_contract[contract_key]
        if contract_row is None:
            contract_row = by_contract[contract_key] = _new_contract_row(journal, group)
        group_row = by_group[(group_code, journal.ky_can_thiep)]
        if not group_row["so_nhat_ky"]:
            group_row["nhom"], group_row["ky"] = group_name, journal.ky_can_thiep
        labor, travel = _amount(journal.tien_cong_tinh), _amount(journal.tien_di_lai_tinh)
        paid = _amount(journal.paid_tien_cong) + _amount(journal.paid_tien_di_lai)
        for row in (contract_row, group_row):
            row["so_nhat_ky"] += 1; row["so_buoi"] += journal.so_buoi_thuc_hien or 0; row["di_lai"] += journal.so_luot_di_lai_cbct or 0
            row["tien_cong"] += labor; row["tien_di_lai"] += travel; row["da_thanh_toan"] += paid
        if not group:
            missing_group += 1
        if journal.canh_bao_trung:
            conflict_count += 1
        child = journal.phan_cong.tre
        child_row = by_child[(child.pk, journal.phan_cong.loai_dich_vu, group_code, journal.ky_can_thiep)]
        child_row.update({"ma_tre": child.ma_tre, "ho_ten": child.ho_ten, "dich_vu": journal.phan_cong.get_loai_dich_vu_display(), "nhom": group_name, "ky": journal.ky_can_thiep})
        child_row["so_buoi"] += journal.so_buoi_thuc_hien or 0; child_row["di_lai"] += journal.so_luot_di_lai_cbct or 0
        child_row["tien_cong"] += labor; child_row["tien_di_lai"] += travel
    summary = _metrics(queryset)
    summary.update({"thieu_nhom": missing_group, "trung_lich": conflict_count})
    year_metrics = _metrics(year_queryset) if year_queryset is not None else summary.copy()
    signing_metrics = _metrics(since_signing_queryset) if since_signing_queryset is not None else summary.copy()
    return {
        "contracts": sorted(by_contract.values(), key=lambda row: (row["so_hop_dong"], row["ky"])),
        "groups": sorted(by_group.values(), key=lambda row: (row["nhom"], row["ky"])),
        "children": sorted(by_child.values(), key=lambda row: (row["nhom"], row["ky"], row["ma_tre"], row["dich_vu"])),
        "summary": summary, "year_cumulative": year_metrics, "since_signing": signing_metrics, "report_year": report_year,
    }


def export_intervention_report_xlsx(report):
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill
    except ImportError as exc:
        raise RuntimeError("Thiếu openpyxl để xuất báo cáo Excel.") from exc
    workbook = Workbook(); summary_sheet = workbook.active; summary_sheet.title = "TongHop"
    summary_sheet.append(["BÁO CÁO THANH TOÁN"]); summary_sheet["A1"].font = Font(bold=True, size=14); summary_sheet.append([])
    summary_sheet.append(["Chỉ tiêu", "Kỳ lọc", "Lũy kế năm", "Lũy kế từ ngày ký"])
    for cell in summary_sheet[3]:
        cell.font = Font(bold=True, color="FFFFFF"); cell.fill = PatternFill("solid", fgColor="0D6EFD")
    labels = (("Số hợp đồng", "so_hop_dong"), ("Số nhật ký", "so_nhat_ky"), ("Số buổi", "so_buoi"), ("Lượt đi lại CBCT", "di_lai"), ("Tiền công", "tien_cong"), ("Tiền đi lại", "tien_di_lai"), ("Tổng trước thuế", "tong_gross"), ("Đã thanh toán", "da_thanh_toan"), ("Nhật ký trùng lịch", "trung_lich"))
    summary, year_metrics, signing_metrics = report["summary"], report["year_cumulative"], report["since_signing"]
    for label, key in labels:
        current = summary.get(key, 0)
        summary_sheet.append([label, current, year_metrics.get(key, ""), signing_metrics.get(key, "")])
    contract_sheet = workbook.create_sheet("TheoNhomKy")
    contract_sheet.append(["Số HĐ", "Đối tác", "Nhóm HĐ", "Ngày ký", "Kỳ", "Số nhật ký", "Số buổi", "Lượt đi lại", "Tiền công", "Tiền đi lại", "Đã thanh toán"])
    child_sheet = workbook.create_sheet("TheoTreDichVu")
    child_sheet.append(["Mã trẻ", "Họ tên", "Dịch vụ", "Nhóm HĐ", "Kỳ", "Số buổi", "Lượt đi lại", "Tiền công", "Tiền đi lại"])
    for sheet in (contract_sheet, child_sheet):
        for cell in sheet[1]:
            cell.font = Font(bold=True, color="FFFFFF"); cell.fill = PatternFill("solid", fgColor="198754")
    for row in report["contracts"]:
        contract_sheet.append([row["so_hop_dong"], row["doi_tac"], row["nhom"], row["ngay_ky"], row["ky"], row["so_nhat_ky"], row["so_buoi"], row["di_lai"], row["tien_cong"], row["tien_di_lai"], row["da_thanh_toan"]])
    for row in report["children"]:
        child_sheet.append([row["ma_tre"], row["ho_ten"], row["dich_vu"], row["nhom"], row["ky"], row["so_buoi"], row["di_lai"], row["tien_cong"], row["tien_di_lai"]])
    for sheet in workbook.worksheets:
        sheet.freeze_panes = "A2"; sheet.auto_filter.ref = sheet.dimensions
        for column_cells in sheet.columns:
            width = min(max(len(str(cell.value or "")) for cell in column_cells) + 2, 32); sheet.column_dimensions[column_cells[0].column_letter].width = width
        for row in sheet.iter_rows():
            for cell in row:
                if isinstance(cell.value, Decimal): cell.number_format = "#,##0"
    return workbook
