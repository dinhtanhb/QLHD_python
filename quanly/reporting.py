from decimal import Decimal

from django.core.paginator import Paginator
from django.db.models import Case, Count, DecimalField, ExpressionWrapper, F, IntegerField, Min, OuterRef, Q, Subquery, Sum, Value, When

from .models import ChiTietPhieuThanhToan, HopDong, NhatKyThucHien, NhomHD, PhanCongTre, Tre

UNKNOWN_GROUP_LABEL = "Chưa xác định"
_MONEY = DecimalField(max_digits=18, decimal_places=0)


def _paid_subquery(field):
    return Subquery(
        ChiTietPhieuThanhToan.objects.filter(
            nhat_ky_id=OuterRef("pk"),
            hoat_dong=True,
            phieu__trang_thai="DA_CHI",
        )
        .values("nhat_ky_id").annotate(total=Sum(field)).values("total")[:1],
        output_field=_MONEY,
    )


def effective_group_id_expression(prefix=""):
    """Nhóm HĐ hiệu lực của nhật ký, đúng thứ tự ưu tiên của ``NhatKyThucHien.nhom_hd_hieu_luc``.

    Nhóm nguồn (lịch sử) -> nhóm của hợp đồng -> nhóm của phân công -> nhóm của phân bổ.
    Nhật ký có hợp đồng luôn lấy nhóm của hợp đồng (``HopDong.nhom_hd`` là bắt buộc).
    """
    return Case(
        When(**{f"{prefix}nhom_hd_nguon_id__isnull": False}, then=F(f"{prefix}nhom_hd_nguon_id")),
        When(**{f"{prefix}hop_dong_id__isnull": False}, then=F(f"{prefix}hop_dong__nhom_hd_id")),
        When(**{f"{prefix}phan_cong__nhom_hd_id__isnull": False}, then=F(f"{prefix}phan_cong__nhom_hd_id")),
        default=F(f"{prefix}phan_cong__phan_bo__nhom_hd_id"),
        output_field=IntegerField(),
    )


def effective_staff_id_expression(prefix=""):
    """CBCT hiệu lực, đúng thứ tự của ``NhatKyThucHien.can_bo_hieu_luc``."""
    return Case(
        When(**{f"{prefix}can_bo_nguon_id__isnull": False}, then=F(f"{prefix}can_bo_nguon_id")),
        When(**{f"{prefix}hop_dong__can_bo_id__isnull": False}, then=F(f"{prefix}hop_dong__can_bo_id")),
        default=F(f"{prefix}phan_cong__phan_bo__can_bo_id"),
        output_field=IntegerField(),
    )


def labor_expression():
    return ExpressionWrapper(F("so_buoi_thuc_hien") * F("don_gia_cong"), output_field=_MONEY)


def travel_expression():
    return ExpressionWrapper(F("so_luot_di_lai_cbct") * F("dinh_muc_di_lai"), output_field=_MONEY)


def _annotated_journal_queryset():
    # Không select_related: báo cáo gom bằng GROUP BY ở CSDL, không dựng đối tượng Python.
    return NhatKyThucHien.objects.filter(hop_dong__isnull=False).annotate(
        nhom_hieu_luc_id=effective_group_id_expression(),
        tien_cong_tinh=labor_expression(),
        tien_di_lai_tinh=travel_expression(),
    )


def intervention_report_queryset(*, nhom_hd_id=None, hop_dong_id=None, ky=None, nam=None, tu_ngay=None, den_ngay=None):
    queryset = _annotated_journal_queryset()
    if hop_dong_id:
        queryset = queryset.filter(hop_dong_id=hop_dong_id)
    if nhom_hd_id:
        queryset = queryset.filter(nhom_hieu_luc_id=nhom_hd_id)
    if ky:
        queryset = queryset.filter(ky_can_thiep=ky)
    if nam:
        queryset = queryset.filter(ngay_thuc_hien__year=nam)
    if tu_ngay:
        queryset = queryset.filter(ngay_thuc_hien__gte=tu_ngay)
    if den_ngay:
        queryset = queryset.filter(ngay_thuc_hien__lte=den_ngay)
    return queryset


def _group_label(group):
    return f"{group.ma_nhom_hd} - {group.ten_nhom_hd}" if group else UNKNOWN_GROUP_LABEL


def _amount(value):
    return Decimal(value or 0)


def _metrics(queryset):
    values = queryset.order_by().aggregate(
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


def _sum_measures(with_paid=False, with_conflict=False):
    measures = {
        "so_nhat_ky": Count("pk"),
        "so_buoi": Sum("so_buoi_thuc_hien"),
        "di_lai": Sum("so_luot_di_lai_cbct"),
        "tien_cong": Sum("tien_cong_tinh"),
        "tien_di_lai": Sum("tien_di_lai_tinh"),
    }
    if with_paid:
        measures["paid_cong"] = Sum(_paid_subquery("tien_cong"))
        measures["paid_di_lai"] = Sum(_paid_subquery("tien_di_lai"))
    if with_conflict:
        measures["trung_lich"] = Count("pk", filter=Q(canh_bao_trung=True))
    return measures


def _base_row(values):
    return {
        "so_nhat_ky": values["so_nhat_ky"] or 0, "so_buoi": values["so_buoi"] or 0, "di_lai": values["di_lai"] or 0,
        "tien_cong": _amount(values["tien_cong"]), "tien_di_lai": _amount(values["tien_di_lai"]),
    }


def _partner_label(contract):
    partner = contract.can_bo or contract.don_vi
    if getattr(partner, "ma_can_bo", None):
        return f"{partner.ma_can_bo} - {partner.ho_ten}"
    if partner:
        return f"{partner.ma_don_vi} - {partner.ten_don_vi}"
    return UNKNOWN_GROUP_LABEL


def _contract_rows(queryset, groups):
    rows = queryset.order_by().values("hop_dong_id", "ky_can_thiep", "nhom_hieu_luc_id").annotate(
        first_date=Min("ngay_thuc_hien"), first_id=Min("pk"), **_sum_measures(with_paid=True),
    )
    # Exports need every grouped row, but evaluate the grouped SQL only once.
    rows = list(rows)
    contracts = {c.pk: c for c in HopDong.objects.filter(pk__in={r["hop_dong_id"] for r in rows}).select_related("can_bo", "don_vi")}
    merged = {}
    for values in rows:
        key = (values["hop_dong_id"], values["ky_can_thiep"])
        first_key = (values["first_date"] is not None, values["first_date"], values["first_id"])
        entry = merged.get(key)
        if entry is None:
            contract = contracts[values["hop_dong_id"]]
            entry = merged[key] = {
                "hop_dong_id": contract.pk, "nhom_hd_id": contract.nhom_hd_id,
                "so_hop_dong": contract.so_hop_dong, "doi_tac": _partner_label(contract),
                "ngay_ky": contract.ngay_ky, "ky": values["ky_can_thiep"], "nhom": None, "nhom_ma": None,
                "co_the_lap_tt": bool(contract.can_bo_id) and contract.trang_thai not in {"DU_THAO", "HUY", "THANH_LY"},
                "_first": None,
                "so_nhat_ky": 0, "so_buoi": 0, "di_lai": 0,
                "tien_cong": Decimal("0"), "tien_di_lai": Decimal("0"), "da_thanh_toan": Decimal("0"),
            }
        # Nhóm hiển thị của dòng hợp đồng × kỳ = nhóm của nhật ký sớm nhất (ngày, id).
        if entry["_first"] is None or first_key < entry["_first"]:
            group = groups.get(values["nhom_hieu_luc_id"])
            entry["_first"], entry["nhom"] = first_key, _group_label(group)
            entry["nhom_ma"] = group.ma_nhom_hd if group else UNKNOWN_GROUP_LABEL
        base = _base_row(values)
        for name in ("so_nhat_ky", "so_buoi", "di_lai", "tien_cong", "tien_di_lai"):
            entry[name] += base[name]
        entry["da_thanh_toan"] += _amount(values["paid_cong"]) + _amount(values["paid_di_lai"])
    for entry in merged.values():
        entry.pop("_first")
    return sorted(merged.values(), key=lambda row: (row["so_hop_dong"], row["ky"]))


def _group_rows(queryset, groups):
    rows = queryset.order_by().values("nhom_hieu_luc_id", "ky_can_thiep").annotate(**_sum_measures(with_paid=True, with_conflict=True))
    result, missing_group, conflict_count = [], 0, 0
    for values in rows:
        group = groups.get(values["nhom_hieu_luc_id"])
        row = {"nhom": _group_label(group), "ky": values["ky_can_thiep"], **_base_row(values)}
        row["da_thanh_toan"] = _amount(values["paid_cong"]) + _amount(values["paid_di_lai"])
        result.append(row)
        conflict_count += values["trung_lich"] or 0
        if group is None:
            missing_group += values["so_nhat_ky"] or 0
    return sorted(result, key=lambda row: (row["nhom"], row["ky"])), missing_group, conflict_count


def _child_rows(queryset, groups):
    rows = list(queryset.order_by().values("phan_cong__tre_id", "phan_cong__loai_dich_vu", "nhom_hieu_luc_id", "ky_can_thiep").annotate(
        so_buoi=Sum("so_buoi_thuc_hien"), di_lai=Sum("so_luot_di_lai_cbct"),
        tien_cong=Sum("tien_cong_tinh"), tien_di_lai=Sum("tien_di_lai_tinh"),
    ))
    children = {c.pk: c for c in Tre.objects.filter(pk__in={r["phan_cong__tre_id"] for r in rows})}
    service_names = dict(PhanCongTre._meta.get_field("loai_dich_vu").flatchoices)
    result = []
    for values in rows:
        child = children[values["phan_cong__tre_id"]]
        service = values["phan_cong__loai_dich_vu"]
        result.append({
            "ma_tre": child.ma_tre, "ho_ten": child.ho_ten, "dich_vu": service_names.get(service, service),
            "nhom": _group_label(groups.get(values["nhom_hieu_luc_id"])),
            "nhom_ma": groups[values["nhom_hieu_luc_id"]].ma_nhom_hd if values["nhom_hieu_luc_id"] in groups else UNKNOWN_GROUP_LABEL,
            "ky": values["ky_can_thiep"],
            "so_buoi": values["so_buoi"] or 0, "di_lai": values["di_lai"] or 0,
            "tien_cong": _amount(values["tien_cong"]), "tien_di_lai": _amount(values["tien_di_lai"]),
        })
    return sorted(result, key=lambda row: (row["nhom"], row["ky"], row["ma_tre"], row["dich_vu"]))


def build_intervention_report(queryset, *, year_queryset=None, since_signing_queryset=None, report_year=None):
    """Tạo báo cáo thanh toán theo số HĐ; toàn bộ phép gom chạy bằng GROUP BY ở CSDL."""
    group_ids = set(queryset.order_by().values_list("nhom_hieu_luc_id", flat=True).distinct())
    groups = {g.pk: g for g in NhomHD.objects.filter(pk__in={g for g in group_ids if g})}
    group_rows, missing_group, conflict_count = _group_rows(queryset, groups)
    summary = _metrics(queryset)
    summary.update({"thieu_nhom": missing_group, "trung_lich": conflict_count})
    year_metrics = _metrics(year_queryset) if year_queryset is not None else summary.copy()
    signing_metrics = _metrics(since_signing_queryset) if since_signing_queryset is not None else summary.copy()
    return {
        "contracts": _contract_rows(queryset, groups),
        "groups": group_rows,
        "children": _child_rows(queryset, groups),
        "summary": summary, "year_cumulative": year_metrics, "since_signing": signing_metrics, "report_year": report_year,
    }


def build_intervention_report_page(
    queryset, *, contract_page=1, child_page=1, year_queryset=None,
    since_signing_queryset=None, report_year=None, per_page=15,
):
    """Build an HTML report without loading every grouped contract/child row.

    Financial totals and the compact group/period summary cover the full filter.
    The two potentially large detail tables are counted and sliced by SQL.
    Excel export continues to use ``build_intervention_report`` for full detail.
    """
    queryset = queryset.order_by()
    group_ids = set(queryset.values_list("nhom_hieu_luc_id", flat=True).distinct())
    groups = {group.pk: group for group in NhomHD.objects.filter(pk__in={value for value in group_ids if value})}
    group_rows, missing_group, conflict_count = _group_rows(queryset, groups)
    summary = _metrics(queryset)
    summary.update({"thieu_nhom": missing_group, "trung_lich": conflict_count})
    year_metrics = _metrics(year_queryset) if year_queryset is not None else summary.copy()
    signing_metrics = _metrics(since_signing_queryset) if since_signing_queryset is not None else summary.copy()

    first_group_id = Subquery(
        queryset.filter(
            hop_dong_id=OuterRef("hop_dong_id"),
            ky_can_thiep=OuterRef("ky_can_thiep"),
        ).order_by("ngay_thuc_hien", "pk").values("nhom_hieu_luc_id")[:1],
        output_field=IntegerField(),
    )
    contract_groups = queryset.values("hop_dong_id", "ky_can_thiep").annotate(
        nhom_hieu_luc_id=first_group_id,
        **_sum_measures(with_paid=True),
    ).order_by("hop_dong__so_hop_dong", "ky_can_thiep")
    contracts_page = Paginator(contract_groups, per_page).get_page(contract_page)
    contract_values = list(contracts_page.object_list)
    contract_ids = {row["hop_dong_id"] for row in contract_values}
    contracts = {
        contract.pk: contract
        for contract in HopDong.objects.filter(pk__in=contract_ids).select_related("can_bo", "don_vi")
    }
    contract_rows = []
    for values in contract_values:
        contract = contracts[values["hop_dong_id"]]
        group = groups.get(values["nhom_hieu_luc_id"])
        row = {
            "hop_dong_id": contract.pk,
            "nhom_hd_id": contract.nhom_hd_id,
            "so_hop_dong": contract.so_hop_dong,
            "doi_tac": _partner_label(contract),
            "ngay_ky": contract.ngay_ky,
            "ky": values["ky_can_thiep"],
            "nhom": _group_label(group),
            "nhom_ma": group.ma_nhom_hd if group else UNKNOWN_GROUP_LABEL,
            "co_the_lap_tt": bool(contract.can_bo_id) and contract.trang_thai not in {"DU_THAO", "HUY", "THANH_LY"},
            **_base_row(values),
            "da_thanh_toan": _amount(values["paid_cong"]) + _amount(values["paid_di_lai"]),
        }
        contract_rows.append(row)
    contracts_page.object_list = contract_rows

    child_groups = queryset.values(
        "phan_cong__tre_id", "phan_cong__loai_dich_vu", "nhom_hieu_luc_id", "ky_can_thiep",
    ).annotate(
        so_buoi=Sum("so_buoi_thuc_hien"),
        di_lai=Sum("so_luot_di_lai_cbct"),
        tien_cong=Sum("tien_cong_tinh"),
        tien_di_lai=Sum("tien_di_lai_tinh"),
    ).order_by(
        "nhom_hieu_luc_id", "ky_can_thiep", "phan_cong__tre__ma_tre", "phan_cong__loai_dich_vu",
    )
    children_page = Paginator(child_groups, per_page).get_page(child_page)
    child_values = list(children_page.object_list)
    tre_ids = {row["phan_cong__tre_id"] for row in child_values}
    children = {child.pk: child for child in Tre.objects.filter(pk__in=tre_ids)}
    service_names = dict(PhanCongTre._meta.get_field("loai_dich_vu").flatchoices)
    child_rows = []
    for values in child_values:
        child = children[values["phan_cong__tre_id"]]
        group = groups.get(values["nhom_hieu_luc_id"])
        service = values["phan_cong__loai_dich_vu"]
        child_rows.append({
            "ma_tre": child.ma_tre,
            "ho_ten": child.ho_ten,
            "dich_vu": service_names.get(service, service),
            "nhom": _group_label(group),
            "nhom_ma": group.ma_nhom_hd if group else UNKNOWN_GROUP_LABEL,
            "ky": values["ky_can_thiep"],
            "so_buoi": values["so_buoi"] or 0,
            "di_lai": values["di_lai"] or 0,
            "tien_cong": _amount(values["tien_cong"]),
            "tien_di_lai": _amount(values["tien_di_lai"]),
        })
    children_page.object_list = child_rows
    return {
        "contracts": contract_rows,
        "groups": group_rows,
        "children": child_rows,
        "summary": summary,
        "year_cumulative": year_metrics,
        "since_signing": signing_metrics,
        "report_year": report_year,
        "contracts_page": contracts_page,
        "children_page": children_page,
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
