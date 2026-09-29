"""SQL aggregation and bounded HTML pages; no journal model hydration."""
from decimal import Decimal

from django.core.paginator import Paginator
from django.db.models import Count, F, Q, Sum
from django.db.models.functions import Coalesce

from .financial import calculate_payment_breakdown
from .models import ChiTietPhieuThanhToan, HopDong, NhomHD, PhanCongTre
from .reporting import _metrics


PAGE_SIZE = 25


def navigation(request, page, parameter):
    params = request.GET.copy()
    params.pop(parameter, None)
    params.pop("format", None)
    links = []
    for number, label in (
        (1, "Đầu"),
        (page.number - 1, "Trước"),
        (page.number + 1, "Sau"),
        (page.paginator.num_pages, "Cuối"),
    ):
        enabled = 1 <= number <= page.paginator.num_pages and number != page.number
        params[parameter] = str(number)
        links.append({"label": label, "url": "?" + params.urlencode(), "enabled": enabled})
    return {"page": page, "links": links}


def journal_totals():
    return {
        "so_nhat_ky": Count("pk"),
        "so_buoi": Sum("so_buoi_thuc_hien"),
        "di_lai": Sum("so_luot_di_lai_cbct"),
        "tien_cong": Sum(F("so_buoi_thuc_hien") * F("don_gia_cong")),
        "tien_di_lai": Sum(F("so_luot_di_lai_cbct") * F("dinh_muc_di_lai")),
    }


def payment_report_page(queryset, *, request, year_queryset, since_signing_queryset, report_year):
    base = queryset.select_related(None).order_by()
    contract_rows = base.values("hop_dong_id", "ky_can_thiep").annotate(
        **journal_totals()
    ).order_by("hop_dong_id", "ky_can_thiep")
    page = Paginator(contract_rows, PAGE_SIZE).get_page(request.GET.get("page"))
    rows = list(page.object_list)
    contracts = HopDong.objects.select_related("can_bo", "don_vi", "nhom_hd").in_bulk(
        [row["hop_dong_id"] for row in rows]
    )
    pairs = Q(pk__in=[])
    for row in rows:
        pairs |= Q(nhat_ky__hop_dong_id=row["hop_dong_id"], nhat_ky__ky_can_thiep=row["ky_can_thiep"])
    paid = {
        (row["nhat_ky__hop_dong_id"], row["nhat_ky__ky_can_thiep"]): row["amount"]
        for row in ChiTietPhieuThanhToan.objects.filter(
            pairs, hoat_dong=True, nhat_ky_id__in=base.values("pk"),
        ).order_by().values("nhat_ky__hop_dong_id", "nhat_ky__ky_can_thiep")
        .annotate(amount=Sum(F("tien_cong") + F("tien_di_lai")))
    }
    for row in rows:
        contract = contracts[row["hop_dong_id"]]
        staff, unit = contract.can_bo, contract.don_vi
        row.update(
            so_hop_dong=contract.so_hop_dong,
            doi_tac=f"{staff.ma_can_bo} - {staff.ho_ten}" if staff else f"{unit.ma_don_vi} - {unit.ten_don_vi}",
            ngay_ky=contract.ngay_ky,
            nhom=str(contract.nhom_hd),
            ky=row["ky_can_thiep"],
            da_thanh_toan=paid.get((contract.pk, row["ky_can_thiep"]), Decimal("0")),
        )
    page.object_list = rows
    children = base.annotate(
        group_id=Coalesce("nhom_hd_nguon_id", "hop_dong__nhom_hd_id"),
    ).values(
        "hop_dong_id", "hop_dong__so_hop_dong", "group_id", "ky_can_thiep",
        "phan_cong__tre_id", "phan_cong__tre__ma_tre", "phan_cong__tre__ho_ten",
        "phan_cong__loai_dich_vu",
    ).annotate(**journal_totals()).order_by(
        "hop_dong_id", "ky_can_thiep", "phan_cong__tre_id", "phan_cong__loai_dich_vu", "group_id",
    )
    child_page = Paginator(children, PAGE_SIZE).get_page(request.GET.get("child_page"))
    child_rows = list(child_page.object_list)
    groups = NhomHD.objects.in_bulk([row["group_id"] for row in child_rows])
    services = dict(PhanCongTre.LOAI_DV_CHOICES)
    for row in child_rows:
        row.update(
            ma_tre=row["phan_cong__tre__ma_tre"], ho_ten=row["phan_cong__tre__ho_ten"],
            dich_vu=services.get(row["phan_cong__loai_dich_vu"], row["phan_cong__loai_dich_vu"]),
            nhom=str(groups.get(row["group_id"], "")), ky=row["ky_can_thiep"],
            so_hop_dong=row["hop_dong__so_hop_dong"],
        )
    child_page.object_list = child_rows
    return {
        "contracts": rows, "children": child_rows, "summary": _metrics(base),
        "year_cumulative": _metrics(year_queryset), "since_signing": _metrics(since_signing_queryset),
        "report_year": report_year,
        "contract_navigation": navigation(request, page, "page"),
        "child_navigation": navigation(request, child_page, "child_page"),
    }


def settlement_page(queryset, request):
    base = queryset.select_related(None).order_by().annotate(
        group_id=Coalesce("nhom_hd_nguon_id", "hop_dong__nhom_hd_id",
                          "phan_cong__nhom_hd_id", "phan_cong__phan_bo__nhom_hd_id"),
        staff_id=Coalesce("can_bo_nguon_id", "hop_dong__can_bo_id", "phan_cong__phan_bo__can_bo_id"),
    ).filter(group_id__isnull=False, staff_id__isnull=False)
    totals = base.values("group_id", "ky_can_thiep").annotate(
        **journal_totals(), hop_dong_count=Count("hop_dong_id", distinct=True),
        can_bo_count=Count("staff_id", distinct=True),
    ).order_by("group_id", "ky_can_thiep")
    page = Paginator(totals, PAGE_SIZE).get_page(request.GET.get("page"))
    rows = list(page.object_list)
    groups = NhomHD.objects.in_bulk([row["group_id"] for row in rows])
    pairs = Q(pk__in=[])
    indexed = {}
    for row in rows:
        key = (row["group_id"], row["ky_can_thiep"])
        indexed[key] = row
        row.update(nhom=groups[row["group_id"]], ky=row["ky_can_thiep"],
                   journal_count=row["so_nhat_ky"], thue_tncn=Decimal("0"))
        pairs |= Q(group_id=key[0], ky_can_thiep=key[1])
    # Tax is calculated per CBCT, not on the group total.
    for staff in base.filter(pairs).values("group_id", "ky_can_thiep", "staff_id").annotate(
        labor=Sum(F("so_buoi_thuc_hien") * F("don_gia_cong")),
        travel=Sum(F("so_luot_di_lai_cbct") * F("dinh_muc_di_lai")),
    ):
        indexed[(staff["group_id"], staff["ky_can_thiep"])]["thue_tncn"] += calculate_payment_breakdown(
            staff["labor"], staff["travel"],
        )["thue_tncn"]
    for row in rows:
        row["tong_truoc_thue"] = row["tien_cong"] + row["tien_di_lai"]
        row["thuc_linh"] = row["tong_truoc_thue"] - row["thue_tncn"]
    page.object_list = rows
    return page, navigation(request, page, "page")
