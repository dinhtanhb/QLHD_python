diff --git a/docs/PROJECT_PROGRESS.md b/docs/PROJECT_PROGRESS.md
index dd7691c..00c05f7 100644
--- a/docs/PROJECT_PROGRESS.md
+++ b/docs/PROJECT_PROGRESS.md
@@ -309,3 +309,29 @@ Rủi ro còn lại: phân loại CBDA vẫn phụ thuộc nội dung Ghi chú h
 - `_journal_export_queryset` của Thanh quyết toán bỏ `prefetch_related` cho FK đơn trị, nạp quan hệ bằng `select_related` và duyệt theo batch để hạn chế N+1 và bộ nhớ.
 - Đã bổ sung test lọc theo Số HĐ, tổng lũy kế và route mới; SQLite đạt 63/63 và MySQL UAT sạch `qlhd_codex_uat_20260929_c` đạt 63/63. Lần chạy MySQL đầu phát hiện lỗi alias Subquery không tương thích, đã sửa bằng biểu thức subquery trực tiếp và chạy lại đạt.
 - Rủi ro còn lại: màn hình vẫn hiển thị toàn bộ dòng chi tiết trẻ/dịch vụ của phạm vi lọc; nếu dữ liệu tăng rất lớn cần bổ sung phân trang hoặc endpoint tải chi tiết riêng.
+
+
+## Rà soát hiệu năng/số liệu Báo cáo – Thanh quyết toán – Phiếu (29/09/2026)
+
+Nguồn: bản review `Review_QLHD_Claude.md`. Các bản vá ghi trong review chưa nằm trong mã nguồn bàn giao nên được áp dụng lại và bổ sung kiểm thử trong đợt này.
+
+**Đã sửa**
+- `quanly/reporting.py`: viết lại bằng `GROUP BY` ở CSDL (hợp đồng×kỳ, nhóm×kỳ, trẻ×dịch vụ, tổng hợp); không còn `list(queryset)`. Nhóm HĐ hiệu lực tính bằng biểu thức `Case/When` đúng thứ tự của `NhatKyThucHien.nhom_hd_hieu_luc` (nguồn → hợp đồng → phân công → phân bổ); bỏ các nhánh `hop_dong__nhom_hd__isnull` là mã chết vì `HopDong.nhom_hd` bắt buộc.
+- `views.thanh_quyet_toan`: gom bằng `GROUP BY`; thuế TNCN đọc từ `CauHinhThue` hiệu lực (`lay_cau_hinh_thue`) thay cho hằng số 5.000.000/10%; bộ lọc Nhóm HĐ dùng nhóm hiệu lực nên khớp Báo cáo.
+- `views._journal_export_queryset` và danh sách nhật ký: bộ lọc Nhóm HĐ và CBCT dùng nhóm/CBCT hiệu lực (trước đây bỏ qua tầng hợp đồng).
+- `services/payment_ledger.huy_phieu`: chỉ tính phiếu còn hiệu lực khi xác định "lần thanh toán mới nhất".
+- `import_phan_bo`/`confirm_import_phan_bo`: chuyển `date`/`Decimal` sang chuỗi trước khi lưu session (session dùng `JSONSerializer`), đọc lại khi xác nhận.
+- Tham số GET xấu (`nam=0`, `nam=99999`, `²`, số quá lớn): thêm `parsing.parse_get_int` và `views._is_id`, giá trị không hợp lệ bị bỏ qua thay vì lỗi 500.
+- N+1 khi xuất DSTK/ĐNTT: `snapshot_journals` nạp trước các quan hệ; `_eligible_journals` bỏ `.exists()` lặp và `kiem_tra_dieu_kien` không còn truy vấn ngầm qua đối số mặc định của `getattr`.
+
+**Kiểm thử**
+- `manage.py check` và `makemigrations --check --dry-run` đạt; SQLite `manage.py test quanly.tests`: **89/89** (63 test cũ + 26 test mới).
+- Test mới chạy trên mã cũ thất bại ở các lỗi đã sửa (TQT lọc nhóm/CBCT, thuế theo cấu hình, hủy phiếu, import phân bổ, tham số GET, N+1), còn hai test đối chiếu số liệu báo cáo đạt trên cả mã cũ lẫn mã mới.
+- Đo trên SQLite với 8.000 nhật ký: Báo cáo 2,21 s → 0,50 s; Thanh quyết toán 1,38 s → 0,07 s.
+
+**Rủi ro/việc còn lại**
+- Chưa chạy trên MySQL UAT; cần chạy lại bộ test và so sánh Báo cáo/TQT trước khi triển khai.
+- Chưa xử lý: phiếu bổ sung khi phát sinh nhật ký mới (ràng buộc `uq_phieu_cb_hd_ky_active`, cần quyết định nghiệp vụ); khóa `select_for_update` cho `xac_nhan_chi`/`huy_phieu` khi hai kế toán thao tác đồng thời; cách tính thuế "vượt ngưỡng thì tính trên toàn bộ tiền công" cần người có chuyên môn xác nhận.
+- TQT tính thuế theo CBCT gộp nhiều hợp đồng trong cùng Nhóm×Kỳ, còn phiếu tính theo từng hợp đồng nên hai nơi có thể lệch khi một CBCT có nhiều hợp đồng; cần chốt quy tắc.
+- `resolve_contract_group` và `assignment_import` còn dùng `str.isdigit()` cho ô Excel (không phải tham số GET).
+- Chưa commit/push.
diff --git a/quanly/parsing.py b/quanly/parsing.py
index c2d69e3..50f5b28 100644
--- a/quanly/parsing.py
+++ b/quanly/parsing.py
@@ -85,3 +85,19 @@ def parse_decimal(value, default=Decimal("0")):
             return Decimal(text)
         except (InvalidOperation, ValueError, TypeError):
             return default
+
+
+def parse_get_int(value, *, min_value=1, max_value=2_147_483_647):
+    """Đọc tham số GET nguyên dương một cách an toàn; giá trị xấu -> None.
+
+    ``str.isdigit()`` chấp nhận cả chữ số Unicode như ``²`` (int() sẽ lỗi), còn
+    ``nam=0``/``nam=99999`` làm ``date()`` hoặc truy vấn năm bị lỗi 500. Hàm này
+    chỉ nhận chữ số ASCII và ép vào khoảng [min_value, max_value].
+    """
+    text = str(value if value is not None else "").strip()
+    if not text or not (text.isascii() and text.isdigit()):
+        return None
+    number = int(text)
+    if number < min_value or number > max_value:
+        return None
+    return number
diff --git a/quanly/reporting.py b/quanly/reporting.py
index 52ba0dd..2e78862 100644
--- a/quanly/reporting.py
+++ b/quanly/reporting.py
@@ -1,30 +1,61 @@
-from collections import defaultdict
 from decimal import Decimal
 
-from django.db.models import Count, DecimalField, ExpressionWrapper, F, OuterRef, Q, Subquery, Sum
+from django.db.models import Case, Count, DecimalField, ExpressionWrapper, F, IntegerField, Min, OuterRef, Q, Subquery, Sum, Value, When
 
-from .models import ChiTietPhieuThanhToan, NhatKyThucHien
+from .models import ChiTietPhieuThanhToan, HopDong, NhatKyThucHien, NhomHD, PhanCongTre, Tre
+
+UNKNOWN_GROUP_LABEL = "Chưa xác định"
+_MONEY = DecimalField(max_digits=18, decimal_places=0)
 
 
 def _paid_subquery(field):
     return Subquery(
         ChiTietPhieuThanhToan.objects.filter(nhat_ky_id=OuterRef("pk"), hoat_dong=True)
         .values("nhat_ky_id").annotate(total=Sum(field)).values("total")[:1],
-        output_field=DecimalField(max_digits=18, decimal_places=0),
+        output_field=_MONEY,
+    )
+
+
+def effective_group_id_expression(prefix=""):
+    """Nhóm HĐ hiệu lực của nhật ký, đúng thứ tự ưu tiên của ``NhatKyThucHien.nhom_hd_hieu_luc``.
+
+    Nhóm nguồn (lịch sử) -> nhóm của hợp đồng -> nhóm của phân công -> nhóm của phân bổ.
+    Nhật ký có hợp đồng luôn lấy nhóm của hợp đồng (``HopDong.nhom_hd`` là bắt buộc).
+    """
+    return Case(
+        When(**{f"{prefix}nhom_hd_nguon_id__isnull": False}, then=F(f"{prefix}nhom_hd_nguon_id")),
+        When(**{f"{prefix}hop_dong_id__isnull": False}, then=F(f"{prefix}hop_dong__nhom_hd_id")),
+        When(**{f"{prefix}phan_cong__nhom_hd_id__isnull": False}, then=F(f"{prefix}phan_cong__nhom_hd_id")),
+        default=F(f"{prefix}phan_cong__phan_bo__nhom_hd_id"),
+        output_field=IntegerField(),
+    )
+
+
+def effective_staff_id_expression(prefix=""):
+    """CBCT hiệu lực, đúng thứ tự của ``NhatKyThucHien.can_bo_hieu_luc``."""
+    return Case(
+        When(**{f"{prefix}can_bo_nguon_id__isnull": False}, then=F(f"{prefix}can_bo_nguon_id")),
+        When(**{f"{prefix}hop_dong__can_bo_id__isnull": False}, then=F(f"{prefix}hop_dong__can_bo_id")),
+        default=F(f"{prefix}phan_cong__phan_bo__can_bo_id"),
+        output_field=IntegerField(),
     )
 
 
+def labor_expression():
+    return ExpressionWrapper(F("so_buoi_thuc_hien") * F("don_gia_cong"), output_field=_MONEY)
+
+
+def travel_expression():
+    return ExpressionWrapper(F("so_luot_di_lai_cbct") * F("dinh_muc_di_lai"), output_field=_MONEY)
+
+
 def _annotated_journal_queryset():
-    labor = ExpressionWrapper(F("so_buoi_thuc_hien") * F("don_gia_cong"), output_field=DecimalField(max_digits=18, decimal_places=0))
-    travel = ExpressionWrapper(F("so_luot_di_lai_cbct") * F("dinh_muc_di_lai"), output_field=DecimalField(max_digits=18, decimal_places=0))
-    return NhatKyThucHien.objects.filter(hop_dong__isnull=False).select_related(
-        "hop_dong__can_bo__don_vi", "hop_dong__don_vi", "hop_dong__nhom_hd", "nhom_hd_nguon",
-        "can_bo_nguon__don_vi", "phan_cong__tre", "phan_cong__nhom_hd",
-        "phan_cong__phan_bo__can_bo__don_vi", "phan_cong__phan_bo__nhom_hd",
-    ).annotate(
-        tien_cong_tinh=labor, tien_di_lai_tinh=travel,
-        paid_tien_cong=_paid_subquery("tien_cong"), paid_tien_di_lai=_paid_subquery("tien_di_lai"),
-    ).order_by("ngay_thuc_hien", "id")
+    # Không select_related: báo cáo gom bằng GROUP BY ở CSDL, không dựng đối tượng Python.
+    return NhatKyThucHien.objects.filter(hop_dong__isnull=False).annotate(
+        nhom_hieu_luc_id=effective_group_id_expression(),
+        tien_cong_tinh=labor_expression(),
+        tien_di_lai_tinh=travel_expression(),
+    )
 
 
 def intervention_report_queryset(*, nhom_hd_id=None, hop_dong_id=None, ky=None, nam=None, tu_ngay=None, den_ngay=None):
@@ -32,12 +63,7 @@ def intervention_report_queryset(*, nhom_hd_id=None, hop_dong_id=None, ky=None,
     if hop_dong_id:
         queryset = queryset.filter(hop_dong_id=hop_dong_id)
     if nhom_hd_id:
-        queryset = queryset.filter(
-            Q(nhom_hd_nguon_id=nhom_hd_id)
-            | Q(nhom_hd_nguon__isnull=True, hop_dong__nhom_hd_id=nhom_hd_id)
-            | Q(nhom_hd_nguon__isnull=True, hop_dong__nhom_hd__isnull=True, phan_cong__nhom_hd_id=nhom_hd_id)
-            | Q(nhom_hd_nguon__isnull=True, hop_dong__nhom_hd__isnull=True, phan_cong__nhom_hd__isnull=True, phan_cong__phan_bo__nhom_hd_id=nhom_hd_id)
-        )
+        queryset = queryset.filter(nhom_hieu_luc_id=nhom_hd_id)
     if ky:
         queryset = queryset.filter(ky_can_thiep=ky)
     if nam:
@@ -49,18 +75,8 @@ def intervention_report_queryset(*, nhom_hd_id=None, hop_dong_id=None, ky=None,
     return queryset
 
 
-def _group_for(journal):
-    if journal.nhom_hd_nguon_id:
-        return journal.nhom_hd_nguon
-    if journal.hop_dong_id and journal.hop_dong.nhom_hd_id:
-        return journal.hop_dong.nhom_hd
-    if journal.phan_cong.nhom_hd_id:
-        return journal.phan_cong.nhom_hd
-    return journal.phan_cong.phan_bo.nhom_hd if journal.phan_cong.phan_bo_id else None
-
-
 def _group_label(group):
-    return f"{group.ma_nhom_hd} - {group.ten_nhom_hd}" if group else "Chưa xác định"
+    return f"{group.ma_nhom_hd} - {group.ten_nhom_hd}" if group else UNKNOWN_GROUP_LABEL
 
 
 def _amount(value):
@@ -68,7 +84,7 @@ def _amount(value):
 
 
 def _metrics(queryset):
-    values = queryset.aggregate(
+    values = queryset.order_by().aggregate(
         so_hop_dong=Count("hop_dong_id", distinct=True), so_nhat_ky=Count("pk"), so_buoi=Sum("so_buoi_thuc_hien"), di_lai=Sum("so_luot_di_lai_cbct"),
         tien_cong=Sum("tien_cong_tinh"), tien_di_lai=Sum("tien_di_lai_tinh"),
         # MySQL không cho tham chiếu alias của một Subquery trong SUM bên ngoài;
@@ -85,66 +101,115 @@ def _metrics(queryset):
     }
 
 
-def _new_contract_row(journal, group):
-    contract = journal.hop_dong
-    partner = contract.can_bo or contract.don_vi
-    if getattr(partner, "ma_can_bo", None):
-        partner_label = f"{partner.ma_can_bo} - {partner.ho_ten}"
-    elif partner:
-        partner_label = f"{partner.ma_don_vi} - {partner.ten_don_vi}"
-    else:
-        partner_label = "Chưa xác định"
+def _sum_measures(with_paid=False, with_conflict=False):
+    measures = {
+        "so_nhat_ky": Count("pk"),
+        "so_buoi": Sum("so_buoi_thuc_hien"),
+        "di_lai": Sum("so_luot_di_lai_cbct"),
+        "tien_cong": Sum("tien_cong_tinh"),
+        "tien_di_lai": Sum("tien_di_lai_tinh"),
+    }
+    if with_paid:
+        measures["paid_cong"] = Sum(_paid_subquery("tien_cong"))
+        measures["paid_di_lai"] = Sum(_paid_subquery("tien_di_lai"))
+    if with_conflict:
+        measures["trung_lich"] = Count("pk", filter=Q(canh_bao_trung=True))
+    return measures
+
+
+def _base_row(values):
     return {
-        "hop_dong_id": contract.pk, "so_hop_dong": contract.so_hop_dong, "doi_tac": partner_label,
-        "nhom": _group_label(group), "ngay_ky": contract.ngay_ky, "ky": journal.ky_can_thiep,
-        "so_nhat_ky": 0, "so_buoi": 0, "di_lai": 0,
-        "tien_cong": Decimal("0"), "tien_di_lai": Decimal("0"), "da_thanh_toan": Decimal("0"),
+        "so_nhat_ky": values["so_nhat_ky"] or 0, "so_buoi": values["so_buoi"] or 0, "di_lai": values["di_lai"] or 0,
+        "tien_cong": _amount(values["tien_cong"]), "tien_di_lai": _amount(values["tien_di_lai"]),
     }
 
 
+def _partner_label(contract):
+    partner = contract.can_bo or contract.don_vi
+    if getattr(partner, "ma_can_bo", None):
+        return f"{partner.ma_can_bo} - {partner.ho_ten}"
+    if partner:
+        return f"{partner.ma_don_vi} - {partner.ten_don_vi}"
+    return UNKNOWN_GROUP_LABEL
+
+
+def _contract_rows(queryset, groups):
+    rows = queryset.order_by().values("hop_dong_id", "ky_can_thiep", "nhom_hieu_luc_id").annotate(
+        first_date=Min("ngay_thuc_hien"), first_id=Min("pk"), **_sum_measures(with_paid=True),
+    )
+    contracts = {c.pk: c for c in HopDong.objects.filter(pk__in={r["hop_dong_id"] for r in rows}).select_related("can_bo", "don_vi")}
+    merged = {}
+    for values in rows:
+        key = (values["hop_dong_id"], values["ky_can_thiep"])
+        first_key = (values["first_date"] is not None, values["first_date"], values["first_id"])
+        entry = merged.get(key)
+        if entry is None:
+            contract = contracts[values["hop_dong_id"]]
+            entry = merged[key] = {
+                "hop_dong_id": contract.pk, "so_hop_dong": contract.so_hop_dong, "doi_tac": _partner_label(contract),
+                "ngay_ky": contract.ngay_ky, "ky": values["ky_can_thiep"], "nhom": None, "_first": None,
+                "so_nhat_ky": 0, "so_buoi": 0, "di_lai": 0,
+                "tien_cong": Decimal("0"), "tien_di_lai": Decimal("0"), "da_thanh_toan": Decimal("0"),
+            }
+        # Nhóm hiển thị của dòng hợp đồng × kỳ = nhóm của nhật ký sớm nhất (ngày, id).
+        if entry["_first"] is None or first_key < entry["_first"]:
+            entry["_first"], entry["nhom"] = first_key, _group_label(groups.get(values["nhom_hieu_luc_id"]))
+        base = _base_row(values)
+        for name in ("so_nhat_ky", "so_buoi", "di_lai", "tien_cong", "tien_di_lai"):
+            entry[name] += base[name]
+        entry["da_thanh_toan"] += _amount(values["paid_cong"]) + _amount(values["paid_di_lai"])
+    for entry in merged.values():
+        entry.pop("_first")
+    return sorted(merged.values(), key=lambda row: (row["so_hop_dong"], row["ky"]))
+
+
+def _group_rows(queryset, groups):
+    rows = queryset.order_by().values("nhom_hieu_luc_id", "ky_can_thiep").annotate(**_sum_measures(with_paid=True, with_conflict=True))
+    result, missing_group, conflict_count = [], 0, 0
+    for values in rows:
+        group = groups.get(values["nhom_hieu_luc_id"])
+        row = {"nhom": _group_label(group), "ky": values["ky_can_thiep"], **_base_row(values)}
+        row["da_thanh_toan"] = _amount(values["paid_cong"]) + _amount(values["paid_di_lai"])
+        result.append(row)
+        conflict_count += values["trung_lich"] or 0
+        if group is None:
+            missing_group += values["so_nhat_ky"] or 0
+    return sorted(result, key=lambda row: (row["nhom"], row["ky"])), missing_group, conflict_count
+
+
+def _child_rows(queryset, groups):
+    rows = list(queryset.order_by().values("phan_cong__tre_id", "phan_cong__loai_dich_vu", "nhom_hieu_luc_id", "ky_can_thiep").annotate(
+        so_buoi=Sum("so_buoi_thuc_hien"), di_lai=Sum("so_luot_di_lai_cbct"),
+        tien_cong=Sum("tien_cong_tinh"), tien_di_lai=Sum("tien_di_lai_tinh"),
+    ))
+    children = {c.pk: c for c in Tre.objects.filter(pk__in={r["phan_cong__tre_id"] for r in rows})}
+    service_names = dict(PhanCongTre._meta.get_field("loai_dich_vu").flatchoices)
+    result = []
+    for values in rows:
+        child = children[values["phan_cong__tre_id"]]
+        service = values["phan_cong__loai_dich_vu"]
+        result.append({
+            "ma_tre": child.ma_tre, "ho_ten": child.ho_ten, "dich_vu": service_names.get(service, service),
+            "nhom": _group_label(groups.get(values["nhom_hieu_luc_id"])), "ky": values["ky_can_thiep"],
+            "so_buoi": values["so_buoi"] or 0, "di_lai": values["di_lai"] or 0,
+            "tien_cong": _amount(values["tien_cong"]), "tien_di_lai": _amount(values["tien_di_lai"]),
+        })
+    return sorted(result, key=lambda row: (row["nhom"], row["ky"], row["ma_tre"], row["dich_vu"]))
+
+
 def build_intervention_report(queryset, *, year_queryset=None, since_signing_queryset=None, report_year=None):
-    """Tạo báo cáo thanh toán theo số HĐ, đồng thời giữ khóa dữ liệu cũ cho tương thích."""
-    journals = list(queryset)
-    by_contract, by_group, by_child = defaultdict(lambda: None), defaultdict(lambda: {
-        "nhom": "Chưa xác định", "ky": 0, "so_nhat_ky": 0, "so_buoi": 0, "di_lai": 0,
-        "tien_cong": Decimal("0"), "tien_di_lai": Decimal("0"), "da_thanh_toan": Decimal("0"),
-    }), defaultdict(lambda: {
-        "ma_tre": "", "ho_ten": "", "dich_vu": "", "nhom": "Chưa xác định", "ky": 0,
-        "so_buoi": 0, "di_lai": 0, "tien_cong": Decimal("0"), "tien_di_lai": Decimal("0"),
-    })
-    missing_group = conflict_count = 0
-    for journal in journals:
-        group = _group_for(journal)
-        group_code, group_name = (group.ma_nhom_hd if group else "?"), _group_label(group)
-        contract_key = (journal.hop_dong_id, journal.ky_can_thiep)
-        contract_row = by_contract[contract_key]
-        if contract_row is None:
-            contract_row = by_contract[contract_key] = _new_contract_row(journal, group)
-        group_row = by_group[(group_code, journal.ky_can_thiep)]
-        if not group_row["so_nhat_ky"]:
-            group_row["nhom"], group_row["ky"] = group_name, journal.ky_can_thiep
-        labor, travel = _amount(journal.tien_cong_tinh), _amount(journal.tien_di_lai_tinh)
-        paid = _amount(journal.paid_tien_cong) + _amount(journal.paid_tien_di_lai)
-        for row in (contract_row, group_row):
-            row["so_nhat_ky"] += 1; row["so_buoi"] += journal.so_buoi_thuc_hien or 0; row["di_lai"] += journal.so_luot_di_lai_cbct or 0
-            row["tien_cong"] += labor; row["tien_di_lai"] += travel; row["da_thanh_toan"] += paid
-        if not group:
-            missing_group += 1
-        if journal.canh_bao_trung:
-            conflict_count += 1
-        child = journal.phan_cong.tre
-        child_row = by_child[(child.pk, journal.phan_cong.loai_dich_vu, group_code, journal.ky_can_thiep)]
-        child_row.update({"ma_tre": child.ma_tre, "ho_ten": child.ho_ten, "dich_vu": journal.phan_cong.get_loai_dich_vu_display(), "nhom": group_name, "ky": journal.ky_can_thiep})
-        child_row["so_buoi"] += journal.so_buoi_thuc_hien or 0; child_row["di_lai"] += journal.so_luot_di_lai_cbct or 0
-        child_row["tien_cong"] += labor; child_row["tien_di_lai"] += travel
+    """Tạo báo cáo thanh toán theo số HĐ; toàn bộ phép gom chạy bằng GROUP BY ở CSDL."""
+    group_ids = set(queryset.order_by().values_list("nhom_hieu_luc_id", flat=True).distinct())
+    groups = {g.pk: g for g in NhomHD.objects.filter(pk__in={g for g in group_ids if g})}
+    group_rows, missing_group, conflict_count = _group_rows(queryset, groups)
     summary = _metrics(queryset)
     summary.update({"thieu_nhom": missing_group, "trung_lich": conflict_count})
     year_metrics = _metrics(year_queryset) if year_queryset is not None else summary.copy()
     signing_metrics = _metrics(since_signing_queryset) if since_signing_queryset is not None else summary.copy()
     return {
-        "contracts": sorted(by_contract.values(), key=lambda row: (row["so_hop_dong"], row["ky"])),
-        "groups": sorted(by_group.values(), key=lambda row: (row["nhom"], row["ky"])),
-        "children": sorted(by_child.values(), key=lambda row: (row["nhom"], row["ky"], row["ma_tre"], row["dich_vu"])),
+        "contracts": _contract_rows(queryset, groups),
+        "groups": group_rows,
+        "children": _child_rows(queryset, groups),
         "summary": summary, "year_cumulative": year_metrics, "since_signing": signing_metrics, "report_year": report_year,
     }
 
diff --git a/quanly/services/payment_ledger.py b/quanly/services/payment_ledger.py
index 901fbd2..8344c97 100644
--- a/quanly/services/payment_ledger.py
+++ b/quanly/services/payment_ledger.py
@@ -62,7 +62,18 @@ def snapshot_journals(journals):
     details = ChiTietPhieuThanhToan.objects.filter(
         nhat_ky_id__in=[journal.pk for journal in journals],
         hoat_dong=True,
-    ).select_related("phieu", "nhat_ky__phan_cong__tre", "nhat_ky__hop_dong")
+    ).select_related(
+        "phieu",
+        "nhat_ky__can_bo_nguon__don_vi",
+        "nhat_ky__nhom_hd_nguon",
+        "nhat_ky__hop_dong__can_bo__don_vi",
+        "nhat_ky__hop_dong__don_vi",
+        "nhat_ky__hop_dong__nhom_hd",
+        "nhat_ky__phan_cong__tre",
+        "nhat_ky__phan_cong__nhom_hd",
+        "nhat_ky__phan_cong__phan_bo__can_bo__don_vi",
+        "nhat_ky__phan_cong__phan_bo__nhom_hd",
+    )
     by_journal = {detail.nhat_ky_id: detail for detail in details}
     missing = [journal.pk for journal in journals if journal.pk not in by_journal]
     if missing:
@@ -112,19 +123,23 @@ def lay_cau_hinh_thue(ngay):
     )()
 
 
-def kiem_tra_dieu_kien(nhat_ky):
+def kiem_tra_dieu_kien(nhat_ky, kiem_tra_da_thanh_toan=True):
     errors = []
     hop_dong = nhat_ky.hop_dong_hieu_luc
     if not hop_dong:
         errors.append("Nhật ký chưa có hợp đồng")
     elif hop_dong.trang_thai in {"DU_THAO", "HUY", "THANH_LY"}:
         errors.append(f"Hợp đồng {hop_dong.so_hop_dong} đang ở trạng thái không được thanh toán: {hop_dong.trang_thai}")
-    effective_staff_id = getattr(nhat_ky, "_effective_staff_id", nhat_ky.can_bo_hieu_luc_id)
+    # Không dùng getattr(..., default) vì đối số mặc định luôn được tính (thêm truy vấn cho từng nhật ký).
+    if hasattr(nhat_ky, "_effective_staff_id"):
+        effective_staff_id = nhat_ky._effective_staff_id
+    else:
+        effective_staff_id = nhat_ky.can_bo_hieu_luc_id
     if not effective_staff_id:
         errors.append("Không xác định được CBCT hiệu lực")
     if nhat_ky.so_buoi_thuc_hien <= 0:
         errors.append("Nhật ký không có số buổi thực hiện hợp lệ")
-    if ChiTietPhieuThanhToan.objects.filter(nhat_ky_id=nhat_ky.pk, hoat_dong=True).exists():
+    if kiem_tra_da_thanh_toan and ChiTietPhieuThanhToan.objects.filter(nhat_ky_id=nhat_ky.pk, hoat_dong=True).exists():
         errors.append("Nhật ký đã nằm trong phiếu thanh toán hiệu lực")
     return errors
 
@@ -139,7 +154,9 @@ def _eligible_journals(can_bo, hop_dong, ky_can_thiep):
         "hop_dong", "can_bo_nguon", "phan_cong__tre", "phan_cong__phan_bo__can_bo"
     )
     queryset = NhatKyQuerySet.chua_thanh_toan(queryset).filter(_effective_staff_id=can_bo.pk)
-    return [item for item in queryset if not kiem_tra_dieu_kien(item)]
+    # queryset đã loại các nhật ký có chi tiết phiếu hiệu lực (Exists ở trên) nên không cần
+    # truy vấn .exists() lần nữa cho từng nhật ký.
+    return [item for item in queryset if not kiem_tra_dieu_kien(item, kiem_tra_da_thanh_toan=False)]
 
 
 def tao_phieu_thanh_toan(can_bo, hop_dong, ky_can_thiep, user=None):
@@ -213,7 +230,7 @@ def huy_phieu(phieu, ly_do, user=None):
         raise ValidationError("Chỉ phiếu chờ chi mới được hủy.")
     if not ly_do or not str(ly_do).strip():
         raise ValidationError("Bắt buộc nhập lý do hủy phiếu.")
-    latest = PhieuThanhToan.objects.filter(can_bo=phieu.can_bo, hop_dong=phieu.hop_dong).aggregate(value=Max("lan_thanh_toan"))["value"]
+    latest = PhieuThanhToan.objects.filter(can_bo=phieu.can_bo, hop_dong=phieu.hop_dong, hoat_dong=True).aggregate(value=Max("lan_thanh_toan"))["value"]
     if latest != phieu.lan_thanh_toan:
         raise ValidationError("Chỉ được hủy phiếu có lần thanh toán mới nhất.")
     with transaction.atomic():
diff --git a/quanly/tests.py b/quanly/tests.py
index d870d3d..9fc4edd 100644
--- a/quanly/tests.py
+++ b/quanly/tests.py
@@ -1181,3 +1181,505 @@ class DatabaseRegressionTests(TestCase):
         )
         journal.save(recalculate_travel=False)
         self.assertEqual(journal.thanh_tien, Decimal("450"))
+
+
+
+# =============================================================================
+# Hồi quy cho đợt rà soát 29/09/2026: báo cáo GROUP BY, Thanh quyết toán,
+# hủy phiếu, import phân bổ (session JSON) và tham số GET xấu.
+# =============================================================================
+from django.db import connection
+from django.db.models import F
+from django.test.utils import CaptureQueriesContext
+
+from .parsing import parse_get_int
+from .reporting import build_intervention_report, intervention_report_queryset
+from .services.payment_ledger import lay_cau_hinh_thue
+
+
+class ParseGetIntTests(SimpleTestCase):
+    def test_accepts_plain_ascii_digits_only(self):
+        self.assertEqual(parse_get_int("12"), 12)
+        self.assertEqual(parse_get_int(" 7 "), 7)
+        for bad in ("", None, "abc", "1.5", "-3", "²", "١٢", "0", "１２"):
+            with self.subTest(value=bad):
+                self.assertIsNone(parse_get_int(bad))
+
+    def test_bounds_are_enforced(self):
+        self.assertIsNone(parse_get_int("0", min_value=1900, max_value=2100))
+        self.assertIsNone(parse_get_int("99999", min_value=1900, max_value=2100))
+        self.assertEqual(parse_get_int("2026", min_value=1900, max_value=2100), 2026)
+        self.assertIsNone(parse_get_int("9" * 40))
+
+
+class SettlementReportingTestBase(TestCase):
+    """Bộ dữ liệu có đủ các tầng nhóm/CBCT để đối chiếu GROUP BY với thuộc tính của model."""
+
+    def setUp(self):
+        self.admin_group = Group.objects.create(name="Admin")
+        self.admin = User.objects.create_user(username="rpt-admin", password="secret")
+        self.admin.groups.add(self.admin_group)
+        self.don_vi = DonVi.objects.create(ma_don_vi="DV-RPT", ten_don_vi="Đơn vị báo cáo", nguoi_dai_dien="Người test")
+        self.cb1 = CanBo.objects.create(ma_can_bo="RPT0001", ho_ten="CB Một", don_vi=self.don_vi)
+        self.cb2 = CanBo.objects.create(ma_can_bo="RPT0002", ho_ten="CB Hai", don_vi=self.don_vi)
+        self.g1 = NhomHD.objects.create(ma_nhom_hd="1", ten_nhom_hd="Nhóm 1")
+        self.g12 = NhomHD.objects.create(ma_nhom_hd="12", ten_nhom_hd="Nhóm 12")
+        self.child1 = Tre.objects.create(ma_tre="RPT-T1", ho_ten="Trẻ 1", ngay_sinh=date(2015, 1, 1), gioi_tinh="Nam")
+        self.child2 = Tre.objects.create(ma_tre="RPT-T2", ho_ten="Trẻ 2", ngay_sinh=date(2016, 2, 2), gioi_tinh="Nữ")
+        self.alloc1 = PhanBoChiTieu.objects.create(can_bo=self.cb1, nhom_hd=self.g1, so_tre_phcn=2, so_buoi_phcn=50)
+        self.alloc2 = PhanBoChiTieu.objects.create(can_bo=self.cb2, nhom_hd=self.g12, so_tre_phcn=2, so_buoi_phcn=50)
+
+    # -- helpers ---------------------------------------------------------
+    def _assignment(self, alloc, child, service="VLTL", nhom=None):
+        return PhanCongTre.objects.create(
+            phan_bo=alloc, can_bo_nguon=alloc.can_bo, nhom_hd=nhom, tre=child, loai_dich_vu=service,
+            so_buoi_du_kien=500, dinh_muc_di_lai=Decimal("50000"),
+        )
+
+    def _contract(self, so, can_bo, nhom, value="1000000000", status="DA_KY"):
+        return HopDong.objects.create(
+            can_bo=can_bo, nhom_hd=nhom, so_hop_dong=so, ngay_ky=date(2026, 8, 1),
+            tu_ngay=date(2026, 8, 1), den_ngay=date(2026, 12, 31),
+            gia_tri_hop_dong=Decimal(value), trang_thai=status,
+        )
+
+    def _journal(self, contract, assignment, day, ky=1, buoi=1, di_lai=0, cong="200000", dm="50000", **extra):
+        journal = NhatKyThucHien(
+            hop_dong=contract, phan_cong=assignment, ngay_thuc_hien=day, ky_can_thiep=ky,
+            so_buoi_thuc_hien=buoi, so_luot_di_lai_cbct=di_lai,
+            don_gia_cong=Decimal(cong), dinh_muc_di_lai=Decimal(dm), du_lieu_lich_su=True, **extra,
+        )
+        journal.save(recalculate_travel=False)
+        return journal
+
+    def _scenario(self):
+        """Hợp đồng nhóm 12 nhưng phân công nhóm 1 (ca gây lỗi #2), nhóm nguồn lịch sử và nhật ký không hợp đồng."""
+        self.a1 = self._assignment(self.alloc1, self.child1, "VLTL", nhom=self.g1)
+        self.a3 = self._assignment(self.alloc1, self.child1, "HDTL", nhom=self.g1)
+        self.a2 = self._assignment(self.alloc2, self.child2, "CSXH")
+        self.cA = self._contract("HD-A", self.cb1, self.g12)
+        self.cB = self._contract("HD-B", self.cb2, self.g1)
+        self.j1 = self._journal(self.cA, self.a1, date(2026, 9, 10), ky=1, buoi=2, di_lai=1)
+        self.j2 = self._journal(self.cA, self.a1, date(2026, 9, 11), ky=1, buoi=3)
+        self.j3 = self._journal(self.cA, self.a3, date(2026, 9, 12), ky=2, buoi=1, di_lai=1)
+        self.j4 = self._journal(self.cB, self.a2, date(2026, 9, 10), ky=1, buoi=4, di_lai=2)
+        self.j5 = self._journal(self.cB, self.a2, date(2026, 9, 9), ky=1, buoi=1, nhom_hd_nguon=self.g12)
+        self.j6 = self._journal(None, self.a2, date(2026, 9, 13), ky=1, buoi=5)
+        NhatKyThucHien.objects.filter(pk=self.j4.pk).update(canh_bao_trung=True)
+
+    def _all_journals(self):
+        return list(NhatKyThucHien.objects.select_related(
+            "hop_dong__can_bo", "hop_dong__nhom_hd", "nhom_hd_nguon", "can_bo_nguon", "phan_cong__tre",
+            "phan_cong__nhom_hd", "phan_cong__phan_bo__can_bo", "phan_cong__phan_bo__nhom_hd",
+        ).order_by("ngay_thuc_hien", "id"))
+
+    @staticmethod
+    def _label(group):
+        return f"{group.ma_nhom_hd} - {group.ten_nhom_hd}" if group else "Chưa xác định"
+
+    @staticmethod
+    def _paid(journal):
+        total = Decimal("0")
+        for detail in journal.chi_tiet_phieu_thanh_toan.filter(hoat_dong=True):
+            total += detail.tien_cong + detail.tien_di_lai
+        return total
+
+
+class InterventionReportEquivalenceTests(SettlementReportingTestBase):
+    """Báo cáo GROUP BY phải khớp tuyệt đối với cách tính từng nhật ký qua thuộc tính model."""
+
+    def _reference(self):
+        contracts, groups, children = {}, {}, {}
+        summary = {"contracts": set(), "so_nhat_ky": 0, "so_buoi": 0, "di_lai": 0, "tien_cong": Decimal("0"),
+                   "tien_di_lai": Decimal("0"), "da_thanh_toan": Decimal("0"), "thieu_nhom": 0, "trung_lich": 0}
+
+        def bucket(store, key, **initial):
+            return store.setdefault(key, {"so_nhat_ky": 0, "so_buoi": 0, "di_lai": 0, "tien_cong": Decimal("0"),
+                                          "tien_di_lai": Decimal("0"), "da_thanh_toan": Decimal("0"), **initial})
+
+        for j in self._all_journals():
+            if not j.hop_dong_id:
+                continue
+            group = j.nhom_hd_hieu_luc
+            labor = Decimal(j.so_buoi_thuc_hien) * j.don_gia_cong
+            travel = Decimal(j.so_luot_di_lai_cbct) * j.dinh_muc_di_lai
+            paid = self._paid(j)
+            service = j.phan_cong.get_loai_dich_vu_display()
+            rows = (
+                bucket(contracts, (j.hop_dong.so_hop_dong, j.ky_can_thiep), nhom=self._label(group)),
+                bucket(groups, (self._label(group), j.ky_can_thiep)),
+                bucket(children, (j.phan_cong.tre.ma_tre, service, self._label(group), j.ky_can_thiep)),
+            )
+            for index, row in enumerate(rows):
+                row["so_nhat_ky"] += 1
+                row["so_buoi"] += j.so_buoi_thuc_hien
+                row["di_lai"] += j.so_luot_di_lai_cbct
+                row["tien_cong"] += labor
+                row["tien_di_lai"] += travel
+                if index < 2:
+                    row["da_thanh_toan"] += paid
+            summary["contracts"].add(j.hop_dong_id)
+            summary["so_nhat_ky"] += 1
+            summary["so_buoi"] += j.so_buoi_thuc_hien
+            summary["di_lai"] += j.so_luot_di_lai_cbct
+            summary["tien_cong"] += labor
+            summary["tien_di_lai"] += travel
+            summary["da_thanh_toan"] += paid
+            summary["thieu_nhom"] += 0 if group else 1
+            summary["trung_lich"] += 1 if j.canh_bao_trung else 0
+        return contracts, groups, children, summary
+
+    def test_report_matches_model_based_reference_at_every_level(self):
+        self._scenario()
+        # Lập phiếu cho HD-A kỳ 1 để có số "đã thanh toán".
+        tao_phieu_thanh_toan(self.cb1, self.cA, 1)
+        contracts, groups, children, summary = self._reference()
+
+        report = build_intervention_report(intervention_report_queryset())
+
+        got_contracts = {(r["so_hop_dong"], r["ky"]): r for r in report["contracts"]}
+        self.assertEqual(set(got_contracts), set(contracts))
+        for key, expected in contracts.items():
+            row = got_contracts[key]
+            for field in ("nhom", "so_nhat_ky", "so_buoi", "di_lai", "tien_cong", "tien_di_lai", "da_thanh_toan"):
+                self.assertEqual(row[field], expected[field], f"contract {key} field {field}")
+
+        got_groups = {(r["nhom"], r["ky"]): r for r in report["groups"]}
+        self.assertEqual(set(got_groups), set(groups))
+        for key, expected in groups.items():
+            for field in ("so_nhat_ky", "so_buoi", "di_lai", "tien_cong", "tien_di_lai", "da_thanh_toan"):
+                self.assertEqual(got_groups[key][field], expected[field], f"group {key} field {field}")
+
+        got_children = {(r["ma_tre"], r["dich_vu"], r["nhom"], r["ky"]): r for r in report["children"]}
+        self.assertEqual(set(got_children), set(children))
+        for key, expected in children.items():
+            for field in ("so_buoi", "di_lai", "tien_cong", "tien_di_lai"):
+                self.assertEqual(got_children[key][field], expected[field], f"child {key} field {field}")
+
+        s = report["summary"]
+        self.assertEqual(s["so_hop_dong"], len(summary["contracts"]))
+        for field in ("so_nhat_ky", "so_buoi", "di_lai", "tien_cong", "tien_di_lai", "da_thanh_toan", "thieu_nhom", "trung_lich"):
+            self.assertEqual(s[field], summary[field], field)
+        self.assertEqual(s["tong_gross"], summary["tien_cong"] + summary["tien_di_lai"])
+        self.assertGreater(s["da_thanh_toan"], 0)
+
+    def test_contract_row_uses_group_of_earliest_journal(self):
+        self._scenario()
+        row = next(r for r in build_intervention_report(intervention_report_queryset())["contracts"]
+                   if r["so_hop_dong"] == "HD-B" and r["ky"] == 1)
+        # j5 (09-09, nhóm nguồn 12) sớm hơn j4 (09-10, nhóm hợp đồng 1).
+        self.assertEqual(row["nhom"], "12 - Nhóm 12")
+        self.assertEqual(row["so_nhat_ky"], 2)
+
+    def test_group_filter_follows_effective_group_priority(self):
+        self._scenario()
+        in_g12 = intervention_report_queryset(nhom_hd_id=self.g12.pk)
+        in_g1 = intervention_report_queryset(nhom_hd_id=self.g1.pk)
+        # j1-j3: hợp đồng nhóm 12 dù phân công nhóm 1; j5: nhóm nguồn 12; j4: hợp đồng nhóm 1.
+        self.assertEqual(set(in_g12.values_list("pk", flat=True)), {self.j1.pk, self.j2.pk, self.j3.pk, self.j5.pk})
+        self.assertEqual(set(in_g1.values_list("pk", flat=True)), {self.j4.pk})
+
+    def test_year_and_signing_cumulatives_are_computed(self):
+        self._scenario()
+        report = build_intervention_report(
+            intervention_report_queryset(nam=2026),
+            year_queryset=intervention_report_queryset(tu_ngay=date(2026, 1, 1), den_ngay=date(2026, 12, 31)),
+            since_signing_queryset=intervention_report_queryset().filter(ngay_thuc_hien__gte=F("hop_dong__ngay_ky")),
+            report_year=2026,
+        )
+        self.assertEqual(report["summary"]["so_nhat_ky"], 5)
+        self.assertEqual(report["year_cumulative"]["so_nhat_ky"], 5)
+        self.assertEqual(report["since_signing"]["so_nhat_ky"], 5)
+
+    def test_empty_report_is_well_formed(self):
+        report = build_intervention_report(intervention_report_queryset())
+        self.assertEqual(report["contracts"], [])
+        self.assertEqual(report["groups"], [])
+        self.assertEqual(report["children"], [])
+        self.assertEqual(report["summary"]["so_nhat_ky"], 0)
+        self.assertEqual(report["summary"]["tong_gross"], Decimal("0"))
+
+
+class ReportQueryCountTests(SettlementReportingTestBase):
+    """Số truy vấn không được tăng theo số nhật ký (không còn nạp từng nhật ký vào Python)."""
+
+    def _count(self, callable_):
+        with CaptureQueriesContext(connection) as ctx:
+            callable_()
+        return len(ctx)
+
+    def _add_many_journals(self, n=30):
+        for i in range(n):
+            contract = self._contract(f"HD-BULK-{i}", self.cb1 if i % 2 else self.cb2, self.g1 if i % 3 else self.g12)
+            assignment = self._assignment(self.alloc1 if i % 2 else self.alloc2, self.child1 if i % 2 else self.child2)
+            for day in range(1, 4):
+                self._journal(contract, assignment, date(2026, 9, day), ky=1 + i % 3, buoi=1 + day)
+
+    def test_report_builder_query_count_is_constant(self):
+        self._scenario()
+        build = lambda: build_intervention_report(
+            intervention_report_queryset(), year_queryset=intervention_report_queryset(),
+            since_signing_queryset=intervention_report_queryset(),
+        )
+        small = self._count(build)
+        self._add_many_journals()
+        large = self._count(build)
+        self.assertEqual(small, large)
+        self.assertLessEqual(large, 20)
+
+    def test_report_page_query_count_is_constant(self):
+        self._scenario()
+        self.client.force_login(self.admin)
+        url = reverse("bao_cao_tong_hop")
+        self.client.get(url)  # làm nóng cache nội bộ (content types, session...)
+        small = self._count(lambda: self.client.get(url))
+        self._add_many_journals()
+        large = self._count(lambda: self.client.get(url))
+        self.assertEqual(small, large)
+
+    def test_thanh_quyet_toan_query_count_is_constant(self):
+        self._scenario()
+        self.client.force_login(self.admin)
+        url = reverse("thanh_quyet_toan")
+        self.client.get(url)
+        small = self._count(lambda: self.client.get(url))
+        self._add_many_journals()
+        large = self._count(lambda: self.client.get(url))
+        self.assertEqual(small, large)
+
+
+class ThanhQuyetToanTests(SettlementReportingTestBase):
+    def _rows(self, **params):
+        self.client.force_login(self.admin)
+        response = self.client.get(reverse("thanh_quyet_toan"), params)
+        self.assertEqual(response.status_code, 200)
+        return response.context["danh_sach"]
+
+    def test_group_filter_matches_report_page(self):
+        """Ca của review: hợp đồng nhóm 12, phân công nhóm 1 → TQT và Báo cáo phải cùng kết luận."""
+        self.a1 = self._assignment(self.alloc1, self.child1, "VLTL", nhom=self.g1)
+        contract = self._contract("HD-X", self.cb1, self.g12)
+        self._journal(contract, self.a1, date(2026, 9, 10), ky=1, buoi=2)
+        self.client.force_login(self.admin)
+        for group, expected in ((self.g1, 0), (self.g12, 1)):
+            with self.subTest(group=group.ma_nhom_hd):
+                tqt = self.client.get(reverse("thanh_quyet_toan"), {"nhom_hd": group.pk}).context["danh_sach"]
+                report = self.client.get(reverse("bao_cao_tong_hop"), {"nhom_hd": group.pk}).context["report"]
+                self.assertEqual(sum(r["journal_count"] for r in tqt), expected)
+                self.assertEqual(report["summary"]["so_nhat_ky"], expected)
+
+    def test_totals_match_model_based_reference(self):
+        self._scenario()
+        config = lay_cau_hinh_thue(timezone_localdate())
+        expected = {}
+        for j in self._all_journals():
+            group, staff = j.nhom_hd_hieu_luc, j.can_bo_hieu_luc
+            if not group or not staff:
+                continue
+            item = expected.setdefault((group.pk, j.ky_can_thiep), {"journals": 0, "hd": set(), "staff": {}, "so_buoi": 0, "di_lai": 0})
+            item["journals"] += 1
+            if j.hop_dong_id:
+                item["hd"].add(j.hop_dong_id)
+            item["so_buoi"] += j.so_buoi_thuc_hien
+            item["di_lai"] += j.so_luot_di_lai_cbct
+            amounts = item["staff"].setdefault(staff.pk, [Decimal("0"), Decimal("0")])
+            amounts[0] += Decimal(j.so_buoi_thuc_hien) * j.don_gia_cong
+            amounts[1] += Decimal(j.so_luot_di_lai_cbct) * j.dinh_muc_di_lai
+        rows = {(r["nhom"].pk, r["ky"]): r for r in self._rows()}
+        self.assertEqual(set(rows), set(expected))
+        for key, item in expected.items():
+            breakdowns = [calculate_payment_breakdown(c, t, config) for c, t in item["staff"].values()]
+            row = rows[key]
+            self.assertEqual(row["journal_count"], item["journals"])
+            self.assertEqual(row["hop_dong_count"], len(item["hd"]))
+            self.assertEqual(row["can_bo_count"], len(item["staff"]))
+            self.assertEqual(row["so_buoi"], item["so_buoi"])
+            self.assertEqual(row["di_lai"], item["di_lai"])
+            for field in ("tien_cong", "tien_di_lai", "tong_truoc_thue", "thue_tncn", "thuc_linh"):
+                self.assertEqual(row[field], sum((b[field] for b in breakdowns), Decimal("0")), f"{key} {field}")
+
+    def test_tax_follows_cau_hinh_thue_in_database(self):
+        self.a1 = self._assignment(self.alloc1, self.child1, "VLTL", nhom=self.g1)
+        contract = self._contract("HD-TAX", self.cb1, self.g1)
+        self._journal(contract, self.a1, date(2026, 9, 10), ky=1, buoi=130)  # 26.000.000 tiền công
+        # Không có cấu hình: dùng mặc định 5 triệu / 10%.
+        self.assertEqual(self._rows()[0]["thue_tncn"], Decimal("2600000"))
+        CauHinhThue.objects.create(tu_ngay=date(2020, 1, 1), nguong_thue=Decimal("20000000"), ty_le=Decimal("0.05"), can_cu_phap_ly="Test")
+        self.assertEqual(self._rows()[0]["thue_tncn"], Decimal("1300000"))
+        CauHinhThue.objects.create(tu_ngay=date(2021, 1, 1), nguong_thue=Decimal("30000000"), ty_le=Decimal("0.05"), can_cu_phap_ly="Test 2")
+        row = self._rows()[0]
+        self.assertEqual(row["thue_tncn"], Decimal("0"))
+        self.assertEqual(row["thuc_linh"], row["tong_truoc_thue"])
+
+    def test_single_contract_tax_matches_voucher(self):
+        self.a1 = self._assignment(self.alloc1, self.child1, "VLTL", nhom=self.g1)
+        contract = self._contract("HD-VOUCHER", self.cb1, self.g1)
+        self._journal(contract, self.a1, date(2026, 9, 10), ky=1, buoi=40, di_lai=3)
+        CauHinhThue.objects.create(tu_ngay=date(2020, 1, 1), nguong_thue=Decimal("1000000"), ty_le=Decimal("0.07"), can_cu_phap_ly="Test")
+        voucher = tao_phieu_thanh_toan(self.cb1, contract, 1)
+        row = self._rows()[0]
+        self.assertEqual(row["thue_tncn"], voucher.thue_tncn)
+        self.assertEqual(row["thuc_linh"], voucher.thuc_nhan)
+
+    def test_can_bo_filter_uses_contract_staff(self):
+        """CBCT hiệu lực = nguồn → hợp đồng → phân bổ; bộ lọc không được bỏ qua tầng hợp đồng."""
+        self.a1 = self._assignment(self.alloc1, self.child1, "VLTL", nhom=self.g1)
+        self.a1.can_bo_nguon = None
+        self.a1.save()
+        contract = self._contract("HD-STAFF", self.cb2, self.g1)  # hợp đồng của cb2, phân bổ của cb1
+        journal = self._journal(contract, self.a1, date(2026, 9, 10), ky=1, buoi=1)
+        self.assertEqual(journal.can_bo_hieu_luc, self.cb2)
+        self.assertEqual(sum(r["journal_count"] for r in self._rows(can_bo=self.cb2.pk)), 1)
+        self.assertEqual(sum(r["journal_count"] for r in self._rows(can_bo=self.cb1.pk)), 0)
+
+
+def timezone_localdate():
+    from django.utils import timezone
+    return timezone.localdate()
+
+
+class HuyPhieuTests(SettlementReportingTestBase):
+    def _two_vouchers(self):
+        self.a1 = self._assignment(self.alloc1, self.child1, "VLTL", nhom=self.g1)
+        contract = self._contract("HD-HUY", self.cb1, self.g1)
+        self._journal(contract, self.a1, date(2026, 9, 10), ky=1, buoi=2)
+        self._journal(contract, self.a1, date(2026, 9, 20), ky=2, buoi=3)
+        first = tao_phieu_thanh_toan(self.cb1, contract, 1)
+        second = tao_phieu_thanh_toan(self.cb1, contract, 2)
+        self.assertEqual((first.lan_thanh_toan, second.lan_thanh_toan), (1, 2))
+        return first, second
+
+    def test_cannot_cancel_older_voucher_while_newer_is_active(self):
+        first, second = self._two_vouchers()
+        with self.assertRaisesMessage(ValidationError, "mới nhất"):
+            huy_phieu(first, "Sai kỳ")
+        first.refresh_from_db()
+        self.assertEqual(first.trang_thai, "CHO_CHI")
+
+    def test_can_cancel_previous_voucher_after_newest_was_cancelled(self):
+        """Lỗi #5: phiếu đã hủy không được tính là 'lần mới nhất'."""
+        first, second = self._two_vouchers()
+        huy_phieu(second, "Hủy lần 2")
+        first.refresh_from_db()
+        huy_phieu(first, "Hủy lần 1")
+        first.refresh_from_db()
+        self.assertEqual(first.trang_thai, "HUY")
+        self.assertIsNone(first.hoat_dong)
+        self.assertFalse(first.chi_tiet.filter(hoat_dong=True).exists())
+
+    def test_cancel_requires_reason_and_pending_state(self):
+        first, second = self._two_vouchers()
+        with self.assertRaises(ValidationError):
+            huy_phieu(second, "   ")
+        xac_nhan_chi(second)
+        with self.assertRaises(ValidationError):
+            huy_phieu(second, "Đã chi rồi")
+
+
+class BadQueryParameterTests(SettlementReportingTestBase):
+    BAD_VALUES = ({"nam": "0"}, {"nam": "99999"}, {"nam": "²"}, {"ky": "²"}, {"ky": "0"}, {"thang": "²"}, {"thang": "13"},
+                  {"nhom_hd": "²"}, {"hop_dong": "²"}, {"can_bo": "²"}, {"nam": "9" * 40}, {"tu_ngay": "not-a-date"})
+
+    def test_pages_do_not_crash_on_malformed_filters(self):
+        self._scenario()
+        self.client.force_login(self.admin)
+        for name in ("bao_cao_tong_hop", "thanh_quyet_toan", "de_nghi_thanh_toan"):
+            for params in self.BAD_VALUES:
+                with self.subTest(view=name, params=params):
+                    self.assertEqual(self.client.get(reverse(name), params).status_code, 200)
+
+    def test_excel_export_survives_malformed_filters(self):
+        self._scenario()
+        self.client.force_login(self.admin)
+        response = self.client.get(reverse("bao_cao_tong_hop"), {"format": "xlsx", "nam": "²", "ky": "²"})
+        self.assertEqual(response.status_code, 200)
+
+    def test_malformed_filter_is_ignored_not_applied(self):
+        self._scenario()
+        self.client.force_login(self.admin)
+        baseline = self.client.get(reverse("bao_cao_tong_hop")).context["report"]["summary"]["so_nhat_ky"]
+        got = self.client.get(reverse("bao_cao_tong_hop"), {"nam": "99999", "ky": "²"}).context["report"]["summary"]["so_nhat_ky"]
+        self.assertEqual(got, baseline)
+
+    def test_valid_filters_still_apply(self):
+        self._scenario()
+        self.client.force_login(self.admin)
+        response = self.client.get(reverse("bao_cao_tong_hop"), {"ky": "2", "nam": "2026"})
+        self.assertEqual(response.context["report"]["summary"]["so_nhat_ky"], 1)
+
+
+class ImportPhanBoSessionTests(SettlementReportingTestBase):
+    """Lỗi #7: preview lưu date/Decimal vào session JSON làm TypeError."""
+
+    def _upload(self, **overrides):
+        row = {"MaCBCT": "RPT0001", "NhomHD": "1", "SoTrePHCN": 2, "SoBuoiPHCN": 10, "SoTreCS": 1, "SoBuoiCS": 5,
+               "DMDL_PHCN": "2", "DMDL_CS": "1", "NgayLap": "2026-09-01"}
+        row.update(overrides)
+        stream = BytesIO()
+        pd.DataFrame([row]).to_excel(stream, index=False)
+        return SimpleUploadedFile("pb.xlsx", stream.getvalue(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
+
+    def test_preview_then_confirm_creates_allocation(self):
+        self.client.force_login(self.admin)
+        before = PhanBoChiTieu.objects.count()
+        preview = self.client.post(reverse("import_phan_bo"), {"excel_file": self._upload()})
+        self.assertEqual(preview.status_code, 200)
+        self.assertEqual(preview.context["valid_count"], 1)
+        stored = self.client.session["import_phan_bo_valid_data"]
+        self.assertEqual(stored[0]["ngay_lap"], "2026-09-01")
+        confirm = self.client.post(reverse("confirm_import_phan_bo"))
+        self.assertEqual(confirm.status_code, 302)
+        self.assertEqual(PhanBoChiTieu.objects.count(), before + 1)
+        created = PhanBoChiTieu.objects.order_by("-pk").first()
+        self.assertEqual((created.can_bo_id, created.nhom_hd_id), (self.cb1.pk, self.g1.pk))
+        self.assertEqual(created.ngay_lap, date(2026, 9, 1))
+        self.assertEqual(created.dinh_muc_di_lai_phcn, Decimal(str(FinancialConfig.DON_GIA_DI_LAI_DM2)))
+        self.assertEqual(created.dinh_muc_di_lai_cs, Decimal(str(FinancialConfig.DON_GIA_DI_LAI_DM1)))
+
+    def test_invalid_rows_are_not_stored_for_confirmation(self):
+        self.client.force_login(self.admin)
+        response = self.client.post(reverse("import_phan_bo"), {"excel_file": self._upload(MaCBCT="KHONG-CO")})
+        self.assertEqual(response.context["invalid_count"], 1)
+        self.assertEqual(self.client.session["import_phan_bo_valid_data"], [])
+        before = PhanBoChiTieu.objects.count()
+        self.client.post(reverse("confirm_import_phan_bo"))
+        self.assertEqual(PhanBoChiTieu.objects.count(), before)
+
+
+class PaymentExportQueryCountTests(SettlementReportingTestBase):
+    """Lỗi N+1 khi xuất DSTK/ĐNTT: số truy vấn không được tăng theo số nhật ký."""
+
+    def _vouchered_journals(self, n):
+        assignment = self._assignment(self.alloc1, self.child1, "VLTL", nhom=self.g1)
+        contract = self._contract(f"HD-N1-{n}-{NhatKyThucHien.objects.count()}", self.cb1, self.g1)
+        for day in range(1, n + 1):
+            self._journal(contract, assignment, date(2026, 9, day), ky=1, buoi=1)
+        tao_phieu_thanh_toan(self.cb1, contract, 1)
+        return list(NhatKyThucHien.objects.filter(hop_dong=contract).order_by("id"))
+
+    def _snapshot_queries(self, journals):
+        with CaptureQueriesContext(connection) as ctx:
+            rows = snapshot_journals(journals)
+            for row in rows:  # các thuộc tính mà exporter đọc
+                row.can_bo_hieu_luc, row.nhom_hd_hieu_luc, row.hop_dong_hieu_luc, row.phan_cong.tre
+        return len(ctx)
+
+    def test_snapshot_journals_query_count_is_constant(self):
+        few = self._vouchered_journals(3)
+        small = self._snapshot_queries(few)
+        many = self._vouchered_journals(25)
+        large = self._snapshot_queries(many)
+        self.assertEqual(small, large)
+        self.assertLessEqual(large, 3)
+
+    def test_creating_voucher_does_not_query_per_journal(self):
+        assignment = self._assignment(self.alloc1, self.child1, "VLTL", nhom=self.g1)
+        counts = []
+        for size in (2, 20):
+            contract = self._contract(f"HD-EX-{size}", self.cb1, self.g1)
+            for day in range(1, size + 1):
+                self._journal(contract, assignment, date(2026, 9, day), ky=1, buoi=1)
+            with CaptureQueriesContext(connection) as ctx:
+                tao_phieu_thanh_toan(self.cb1, contract, 1)
+            counts.append(len(ctx))
+        self.assertEqual(counts[0], counts[1])
diff --git a/quanly/views.py b/quanly/views.py
index 4dbcde8..f691e04 100644
--- a/quanly/views.py
+++ b/quanly/views.py
@@ -42,8 +42,11 @@ from .payment_export import (
     parent_travel_category,
 )
 from .financial import FinancialConfig, calculate_payment_breakdown, normalize_travel_location
-from .parsing import parse_decimal as parse_decimal_legacy
-from .reporting import build_intervention_report, export_intervention_report_xlsx, intervention_report_queryset
+from .parsing import parse_decimal as parse_decimal_legacy, parse_get_int
+from .reporting import (
+    build_intervention_report, effective_group_id_expression, effective_staff_id_expression,
+    export_intervention_report_xlsx, intervention_report_queryset, labor_expression, travel_expression,
+)
 from .services.contract_status import is_het_han, sync_trang_thai_hop_dong, validate_status_transition
 from .forms import (
     CanBoForm,
@@ -99,6 +102,7 @@ from .models import (
 )
 from .services.payment_ledger import (
     huy_phieu as huy_phieu_thanh_toan,
+    lay_cau_hinh_thue,
     NoEligiblePaymentJournals,
     snapshot_journals,
     tao_phieu_thanh_toan as tao_phieu_thanh_toan_service,
@@ -106,6 +110,11 @@ from .services.payment_ledger import (
 )
 
 
+def _is_id(value, min_value=1, max_value=2_147_483_647):
+    """True nếu tham số request là số nguyên ASCII hợp lệ; thay cho str.isdigit() (nhận cả "²")."""
+    return parse_get_int(value, min_value=min_value, max_value=max_value) is not None
+
+
 def _is_operationally_locked(hop_dong):
     """Hợp đồng đã khóa hoặc đã thanh lý thì không cho tài khoản thường phát sinh dữ liệu."""
     return bool(hop_dong and (hop_dong.is_locked or hop_dong.trang_thai == "THANH_LY"))
@@ -337,7 +346,12 @@ def bao_cao_tong_hop(request):
     nam_value = request.GET.get("nam", "").strip()
     tu_ngay_value = request.GET.get("tu_ngay", "").strip()
     den_ngay_value = request.GET.get("den_ngay", "").strip()
-    report_year = int(nam_value) if nam_value.isdigit() else timezone.localdate().year
+    # Tham số xấu (nam=0, nam=99999, chữ số Unicode như "²"...) bị bỏ qua thay vì gây lỗi 500.
+    nhom_filter = parse_get_int(nhom_id)
+    hop_dong_filter = parse_get_int(hop_dong_id)
+    ky_filter = parse_get_int(ky_value, max_value=1000)
+    nam_filter = parse_get_int(nam_value, min_value=1900, max_value=2100)
+    report_year = nam_filter or timezone.localdate().year
     tu_ngay = parse_date(tu_ngay_value)
     den_ngay = parse_date(den_ngay_value)
     date_error = ""
@@ -346,25 +360,25 @@ def bao_cao_tong_hop(request):
     elif tu_ngay and den_ngay and tu_ngay > den_ngay:
         date_error = "Từ ngày không được sau Đến ngày."
     queryset = intervention_report_queryset(
-        nhom_hd_id=int(nhom_id) if nhom_id.isdigit() else None,
-        hop_dong_id=int(hop_dong_id) if hop_dong_id.isdigit() else None,
-        ky=int(ky_value) if ky_value.isdigit() else None,
-        nam=int(nam_value) if nam_value.isdigit() else None,
+        nhom_hd_id=nhom_filter,
+        hop_dong_id=hop_dong_filter,
+        ky=ky_filter,
+        nam=nam_filter,
         tu_ngay=tu_ngay if not date_error else None,
         den_ngay=den_ngay if not date_error else None,
     )
     annual_end = den_ngay or (date(report_year, 12, 31) if report_year != timezone.localdate().year else timezone.localdate())
     annual_queryset = intervention_report_queryset(
-        nhom_hd_id=int(nhom_id) if nhom_id.isdigit() else None,
-        hop_dong_id=int(hop_dong_id) if hop_dong_id.isdigit() else None,
-        ky=int(ky_value) if ky_value.isdigit() else None,
+        nhom_hd_id=nhom_filter,
+        hop_dong_id=hop_dong_filter,
+        ky=ky_filter,
         tu_ngay=date(report_year, 1, 1),
         den_ngay=annual_end if not date_error else None,
     )
     signing_queryset = intervention_report_queryset(
-        nhom_hd_id=int(nhom_id) if nhom_id.isdigit() else None,
-        hop_dong_id=int(hop_dong_id) if hop_dong_id.isdigit() else None,
-        ky=int(ky_value) if ky_value.isdigit() else None,
+        nhom_hd_id=nhom_filter,
+        hop_dong_id=hop_dong_filter,
+        ky=ky_filter,
         den_ngay=den_ngay or timezone.localdate(),
     ).filter(ngay_thuc_hien__gte=F("hop_dong__ngay_ky"))
     report = build_intervention_report(
@@ -935,13 +949,13 @@ def danh_sach_phan_cong(request):
         "tre", "can_bo_nguon", "phan_bo__can_bo", "phan_bo__nhom_hd", "nhom_hd"
     )
 
-    if phan_bo_id.isdigit():
+    if _is_id(phan_bo_id):
         qs = qs.filter(phan_bo_id=int(phan_bo_id))
 
-    if nhom_hd_id.isdigit():
+    if _is_id(nhom_hd_id):
         qs = qs.filter(Q(nhom_hd_id=int(nhom_hd_id)) | Q(nhom_hd__isnull=True, phan_bo__nhom_hd_id=int(nhom_hd_id)))
 
-    if dot_phan_cong.isdigit():
+    if _is_id(dot_phan_cong):
         qs = qs.filter(dot_phan_cong=int(dot_phan_cong))
 
     if query:
@@ -961,7 +975,7 @@ def danh_sach_phan_cong(request):
     phcn_count = qs.filter(loai_dich_vu__in=PhanCongTre.PHCN_SERVICE_CODES).count()
     cs_count = qs.filter(loai_dich_vu__in=PhanCongTre.CS_SERVICE_CODES).count()
     phan_bo = None
-    if phan_bo_id.isdigit():
+    if _is_id(phan_bo_id):
         phan_bo = PhanBoChiTieu.objects.select_related("can_bo", "nhom_hd").filter(pk=int(phan_bo_id)).first()
 
     return render(
@@ -987,7 +1001,7 @@ def danh_sach_phan_cong(request):
 def them_phan_cong(request):
     phan_bo_id = request.GET.get("phan_bo_id") or request.POST.get("phan_bo")
     phan_bo = None
-    if phan_bo_id and str(phan_bo_id).isdigit():
+    if phan_bo_id and _is_id(phan_bo_id):
         phan_bo = get_object_or_404(
             PhanBoChiTieu.objects.select_related("can_bo", "nhom_hd"),
             pk=int(phan_bo_id),
@@ -1479,7 +1493,7 @@ def danh_sach_phan_bo(request):
             | Q(nhom_hd__ma_nhom_hd__icontains=query)
             | Q(nhom_hd__ten_nhom_hd__icontains=query)
         )
-    if nhom_id.isdigit():
+    if _is_id(nhom_id):
         qs = qs.filter(nhom_hd_id=int(nhom_id))
     if trang_thai == "mo":
         qs = qs.filter(is_locked=False)
@@ -1588,6 +1602,14 @@ def mo_khoa_phan_bo(request, pk):
     return redirect("danh_sach_phan_bo")
 
 
+def _session_safe_allocation(item):
+    """Session dùng JSONSerializer: đổi date/Decimal sang chuỗi để lưu được."""
+    return {
+        key: (value.isoformat() if isinstance(value, date) else str(value) if isinstance(value, Decimal) else value)
+        for key, value in item.items()
+    }
+
+
 @admin_required
 def import_phan_bo(request):
     if request.method != "POST" or "excel_file" not in request.FILES:
@@ -1645,7 +1667,7 @@ def import_phan_bo(request):
             "error_msg": "; ".join(errors),
         })
 
-    request.session["import_phan_bo_valid_data"] = [x for x in preview if x["is_valid"]]
+    request.session["import_phan_bo_valid_data"] = [_session_safe_allocation(x) for x in preview if x["is_valid"]]
     return render(request, "quanly/import_phan_bo.html", {
         "preview_data": preview,
         "valid_count": sum(x["is_valid"] for x in preview),
@@ -1669,13 +1691,13 @@ def confirm_import_phan_bo(request):
             can_bo_id=item["can_bo_id"],
             nhom_hd_id=item["nhom_hd_id"],
             tham_gia_ct=item["tham_gia_ct"],
-            ngay_lap=item["ngay_lap"],
+            ngay_lap=date.fromisoformat(item["ngay_lap"]) if isinstance(item["ngay_lap"], str) else item["ngay_lap"],
             so_tre_phcn=item["so_tre_phcn"],
             so_buoi_phcn=item["so_buoi_phcn"],
-            dinh_muc_di_lai_phcn=item["dmdl_phcn_val"],
+            dinh_muc_di_lai_phcn=Decimal(str(item["dmdl_phcn_val"])),
             so_tre_cs=item["so_tre_cs"],
             so_buoi_cs=item["so_buoi_cs"],
-            dinh_muc_di_lai_cs=item["dmdl_cs_val"],
+            dinh_muc_di_lai_cs=Decimal(str(item["dmdl_cs_val"])),
         ))
     PhanBoChiTieu.objects.bulk_create(records)
     messages.success(request, f"Đã lưu {len(records)} Phân bổ chỉ tiêu.")
@@ -1749,7 +1771,7 @@ def danh_sach_de_xuat(request):
             | Q(phan_bo__nhom_hd__ma_nhom_hd__icontains=query)
             | Q(phan_bo__nhom_hd__ten_nhom_hd__icontains=query)
         )
-    if nhom_id.isdigit():
+    if _is_id(nhom_id):
         qs = qs.filter(phan_bo__nhom_hd_id=int(nhom_id))
     valid_proposal_statuses = {value for value, _ in DeXuatHopDong.TRANG_THAI_CHOICES}
     if trang_thai in valid_proposal_statuses:
@@ -1883,7 +1905,7 @@ def danh_sach_hop_dong(request):
             | Q(nhom_hd__ma_nhom_hd__icontains=query)
             | Q(nhom_hd__ten_nhom_hd__icontains=query)
         )
-    if nhom_id.isdigit():
+    if _is_id(nhom_id):
         qs = qs.filter(nhom_hd_id=int(nhom_id))
     valid_contract_statuses = {value for value, _ in HopDong.TRANG_THAI_CHOICES}
     if trang_thai in valid_contract_statuses:
@@ -2728,18 +2750,18 @@ def tao_dot_thanh_toan_di_lai_phu_huynh_theo_nhom(request):
         "thang": timezone.localdate().month,
     }
     if request.method == "GET":
-        if request.GET.get("nhom_hd", "").isdigit():
+        if _is_id(request.GET.get("nhom_hd", "")):
             initial["nhom_hd"] = int(request.GET["nhom_hd"])
-        if request.GET.get("ky", "").isdigit():
+        if _is_id(request.GET.get("ky", "")):
             initial["ky_can_thiep"] = int(request.GET["ky"])
-        if request.GET.get("nam", "").isdigit():
+        if _is_id(request.GET.get("nam", ""), min_value=1900, max_value=2100):
             initial["nam"] = int(request.GET["nam"])
-        if request.GET.get("thang", "").isdigit():
+        if _is_id(request.GET.get("thang", ""), max_value=12):
             initial["thang"] = int(request.GET["thang"])
     existing_dot = None
     if request.method == "POST":
         raw_scope = [request.POST.get(name, "").strip() for name in ("nhom_hd", "ky_can_thiep", "nam", "thang")]
-        if raw_scope[0].isdigit() and raw_scope[1].isdigit() and raw_scope[2].isdigit() and raw_scope[3].isdigit():
+        if _is_id(raw_scope[0]) and _is_id(raw_scope[1]) and _is_id(raw_scope[2]) and _is_id(raw_scope[3]):
             existing_dot = DotThanhToanDiLaiPhuHuynh.objects.filter(
                 nhom_hd_id=int(raw_scope[0]),
                 ky_can_thiep=int(raw_scope[1]),
@@ -3262,7 +3284,7 @@ def danh_sach_thanh_toan_di_lai_phu_huynh(request):
             | Q(nhom_hd__ma_nhom_hd__icontains=query)
             | Q(nhom_hd__ten_nhom_hd__icontains=query)
         )
-    if nhom_hd.isdigit():
+    if _is_id(nhom_hd):
         qs = qs.filter(Q(nhom_hd_id=int(nhom_hd)) | Q(hop_dong__nhom_hd_id=int(nhom_hd)))
     if trang_thai:
         qs = qs.filter(trang_thai=trang_thai)
@@ -3448,7 +3470,7 @@ def _export_parent_travel(request, pk, category, export_kind="DNTT"):
     try:
         requester = None
         cbda_id = request.GET.get("cbda", "").strip()
-        if cbda_id.isdigit():
+        if _is_id(cbda_id):
             requester = CanBo.objects.filter(pk=int(cbda_id), ma_can_bo__istartswith="AVH").first()
         exporters = {
             "DNTT": export_parent_travel_payment_request,
@@ -3494,13 +3516,13 @@ def nhat_ky_can_thiep(request):
     ).prefetch_related("hop_dong__can_bo", "hop_dong__nhom_hd").order_by("-ngay_thuc_hien", "-id")
     if query:
         qs = qs.filter(Q(phan_cong__tre__ma_tre__icontains=query) | Q(phan_cong__tre__ho_ten__icontains=query) | Q(hop_dong__so_hop_dong__icontains=query) | Q(can_bo_nguon__ho_ten__icontains=query) | Q(phan_cong__phan_bo__can_bo__ho_ten__icontains=query))
-    if cb_id.isdigit():
-        qs = qs.filter(Q(can_bo_nguon_id=int(cb_id)) | Q(can_bo_nguon__isnull=True, phan_cong__phan_bo__can_bo_id=int(cb_id)))
-    if nhom_id.isdigit():
-        qs = qs.filter(Q(nhom_hd_nguon_id=int(nhom_id)) | Q(nhom_hd_nguon__isnull=True, phan_cong__nhom_hd_id=int(nhom_id)) | Q(nhom_hd_nguon__isnull=True, phan_cong__nhom_hd__isnull=True, phan_cong__phan_bo__nhom_hd_id=int(nhom_id)))
-    if ky.isdigit(): qs = qs.filter(ky_can_thiep=int(ky))
-    if thang.isdigit(): qs = qs.filter(ngay_thuc_hien__month=int(thang))
-    if nam.isdigit(): qs = qs.filter(ngay_thuc_hien__year=int(nam))
+    if _is_id(cb_id):
+        qs = qs.annotate(can_bo_hieu_luc_pk=effective_staff_id_expression()).filter(can_bo_hieu_luc_pk=int(cb_id))
+    if _is_id(nhom_id):
+        qs = qs.annotate(nhom_hieu_luc_id=effective_group_id_expression()).filter(nhom_hieu_luc_id=int(nhom_id))
+    if _is_id(ky): qs = qs.filter(ky_can_thiep=int(ky))
+    if _is_id(thang, max_value=12): qs = qs.filter(ngay_thuc_hien__month=int(thang))
+    if _is_id(nam, min_value=1900, max_value=2100): qs = qs.filter(ngay_thuc_hien__year=int(nam))
     if only_conflicts:
         qs = qs.filter(canh_bao_trung=True)
     page_obj = Paginator(qs, 25).get_page(request.GET.get("page"))
@@ -3620,7 +3642,7 @@ def tao_phieu_thanh_toan(request):
     nhom_id = request.POST.get("nhom_hd") or request.GET.get("nhom_hd", "")
     ky = request.POST.get("ky") or request.GET.get("ky", "")
     if request.method == "POST":
-        if not str(nhom_id).isdigit() or not str(ky).isdigit():
+        if not _is_id(nhom_id) or not _is_id(ky):
             messages.error(request, "Cần chọn Nhóm HĐ và Kỳ can thiệp.")
         else:
             contracts = HopDong.objects.filter(nhom_hd_id=int(nhom_id), can_bo__isnull=False).exclude(
@@ -3689,7 +3711,12 @@ def xac_nhan_chi_phieu_thanh_toan(request, pk):
 
 @readonly_required
 def thanh_quyet_toan(request):
-    """Tổng hợp và lập hồ sơ thanh toán theo Nhóm HĐ + Kỳ can thiệp."""
+    """Tổng hợp và lập hồ sơ thanh toán theo Nhóm HĐ + Kỳ can thiệp.
+
+    Toàn bộ số liệu được gom bằng GROUP BY ở CSDL (không nạp từng nhật ký vào Python).
+    Thuế TNCN lấy từ ``CauHinhThue`` đang hiệu lực, tính trên tổng tiền công của từng CBCT
+    trong mỗi (Nhóm HĐ, Kỳ).
+    """
     qs, ky, thang, nam = _journal_export_queryset(request)
     query = request.GET.get("q", "").strip()
     if query:
@@ -3700,55 +3727,33 @@ def thanh_quyet_toan(request):
             | Q(can_bo_nguon__ho_ten__icontains=query)
             | Q(phan_cong__phan_bo__can_bo__ho_ten__icontains=query)
         )
+    scope = qs.filter(nhom_hieu_luc_id__isnull=False, can_bo_hieu_luc_pk__isnull=False).order_by()
+    staff_rows = scope.values("nhom_hieu_luc_id", "ky_can_thiep", "can_bo_hieu_luc_pk").annotate(
+        journal_count=Count("pk"), so_buoi=Sum("so_buoi_thuc_hien"), di_lai=Sum("so_luot_di_lai_cbct"),
+        tien_cong=Sum(labor_expression()), tien_di_lai=Sum(travel_expression()),
+    )
+    contract_counts = {
+        (row["nhom_hieu_luc_id"], row["ky_can_thiep"]): row["so_hd"]
+        for row in scope.values("nhom_hieu_luc_id", "ky_can_thiep").annotate(so_hd=Count("hop_dong_id", distinct=True))
+    }
+    groups = {group.pk: group for group in NhomHD.objects.filter(pk__in={group_id for group_id, _ in contract_counts})}
+    tax_config = lay_cau_hinh_thue(timezone.localdate())
     rows = {}
-    for journal in qs.iterator(chunk_size=1000):
-        # Các FK đã được select_related trong _journal_export_queryset; giữ một
-        # lần resolve trong vòng lặp để tránh phát sinh truy vấn N+1 khi tổng
-        # hợp hàng chục nghìn nhật ký.
-        effective_contract = journal.hop_dong_hieu_luc
-        effective_group = journal.nhom_hd_hieu_luc
-        effective_staff = journal.can_bo_hieu_luc
-        if not effective_group or not effective_staff:
-            continue
-        key = (effective_group.pk, journal.ky_can_thiep)
+    for values in staff_rows:
+        key = (values["nhom_hieu_luc_id"], values["ky_can_thiep"])
         item = rows.setdefault(key, {
-            "nhom": effective_group,
-            "ky": journal.ky_can_thiep,
-            "hop_dong_count": set(),
-            "can_bo_count": set(),
-            "journal_count": 0,
-            "so_buoi": Decimal("0"),
-            "di_lai": Decimal("0"),
-            "tien_cong": Decimal("0"),
-            "tien_di_lai": Decimal("0"),
-            "staff_amounts": {},
+            "nhom": groups[key[0]], "ky": key[1], "hop_dong_count": contract_counts.get(key, 0), "can_bo_count": 0,
+            "journal_count": 0, "so_buoi": Decimal("0"), "di_lai": Decimal("0"),
+            "tien_cong": Decimal("0"), "tien_di_lai": Decimal("0"), "tong_truoc_thue": Decimal("0"),
+            "thue_tncn": Decimal("0"), "thuc_linh": Decimal("0"),
         })
-        if effective_contract:
-            item["hop_dong_count"].add(effective_contract.pk)
-        item["can_bo_count"].add(effective_staff.pk)
-        item["journal_count"] += 1
-        item["so_buoi"] += Decimal(journal.so_buoi_thuc_hien)
-        item["di_lai"] += Decimal(journal.so_luot_di_lai_cbct)
-        item["tien_cong"] += Decimal(journal.so_buoi_thuc_hien) * Decimal(journal.don_gia_cong)
-        item["tien_di_lai"] += Decimal(journal.so_luot_di_lai_cbct) * Decimal(journal.dinh_muc_di_lai)
-        staff_amount = item["staff_amounts"].setdefault(
-            effective_staff.pk,
-            {"labor": Decimal("0"), "travel": Decimal("0")},
-        )
-        staff_amount["labor"] += Decimal(journal.so_buoi_thuc_hien) * Decimal(journal.don_gia_cong)
-        staff_amount["travel"] += Decimal(journal.so_luot_di_lai_cbct) * Decimal(journal.dinh_muc_di_lai)
-    for item in rows.values():
-        staff_breakdowns = [
-            calculate_payment_breakdown(amount["labor"], amount["travel"])
-            for amount in item.pop("staff_amounts").values()
-        ]
-        breakdown = {
-            key: sum((value[key] for value in staff_breakdowns), Decimal("0"))
-            for key in ("tien_cong", "tien_di_lai", "tong_truoc_thue", "thue_tncn", "thuc_linh")
-        }
-        item["hop_dong_count"] = len(item["hop_dong_count"])
-        item["can_bo_count"] = len(item["can_bo_count"])
-        item.update(breakdown)
+        breakdown = calculate_payment_breakdown(values["tien_cong"], values["tien_di_lai"], tax_config)
+        item["can_bo_count"] += 1
+        item["journal_count"] += values["journal_count"]
+        item["so_buoi"] += Decimal(values["so_buoi"] or 0)
+        item["di_lai"] += Decimal(values["di_lai"] or 0)
+        for name in ("tien_cong", "tien_di_lai", "tong_truoc_thue", "thue_tncn", "thuc_linh"):
+            item[name] += breakdown[name]
     danh_sach = sorted(rows.values(), key=lambda item: (item["nhom"].ma_nhom_hd, item["ky"]))
     return render(request, "quanly/thanh_quyet_toan.html", {
         "danh_sach": danh_sach,
@@ -3767,7 +3772,7 @@ def de_nghi_thanh_toan(request):
     """Trang xuất hồ sơ cho một Nhóm HĐ + Kỳ can thiệp đã chọn."""
     qs, ky, thang, nam = _journal_export_queryset(request)
     nhom_id = request.GET.get("nhom_hd", "").strip()
-    nhom = get_object_or_404(NhomHD, pk=int(nhom_id)) if nhom_id.isdigit() else None
+    nhom = get_object_or_404(NhomHD, pk=int(nhom_id)) if _is_id(nhom_id) else None
     tu_ngay = request.GET.get("tu_ngay", "").strip()
     den_ngay = request.GET.get("den_ngay", "").strip()
     date_error = ""
@@ -3817,7 +3822,7 @@ def _selected_payment_date_range(request):
 def _selected_cbda(request):
     cbda_id = request.GET.get("cbda", "").strip()
     cbda = CanBo.objects.filter(
-        pk=int(cbda_id) if cbda_id.isdigit() else 0,
+        pk=int(cbda_id) if _is_id(cbda_id) else 0,
         is_active=True,
         ma_can_bo__istartswith="AVH",
     ).first()
@@ -3830,16 +3835,27 @@ def _journal_export_queryset(request):
     qs = NhatKyThucHien.objects.select_related(
         "can_bo_nguon__don_vi", "nhom_hd_nguon", "hop_dong__can_bo__don_vi", "hop_dong__don_vi", "hop_dong__nhom_hd",
         "phan_cong__tre", "phan_cong__nhom_hd", "phan_cong__phan_bo__can_bo__don_vi", "phan_cong__phan_bo__nhom_hd",
+    ).annotate(
+        nhom_hieu_luc_id=effective_group_id_expression(),
+        can_bo_hieu_luc_pk=effective_staff_id_expression(),
     ).order_by("ngay_thuc_hien", "id")
-    cb_id, nhom_id, ky, thang, nam = (request.GET.get(key, "").strip() for key in ("can_bo", "nhom_hd", "ky", "thang", "nam"))
-    if cb_id.isdigit():
-        qs = qs.filter(Q(can_bo_nguon_id=int(cb_id)) | Q(can_bo_nguon__isnull=True, phan_cong__phan_bo__can_bo_id=int(cb_id)))
-    if nhom_id.isdigit():
-        qs = qs.filter(Q(nhom_hd_nguon_id=int(nhom_id)) | Q(nhom_hd_nguon__isnull=True, phan_cong__nhom_hd_id=int(nhom_id)) | Q(nhom_hd_nguon__isnull=True, phan_cong__nhom_hd__isnull=True, phan_cong__phan_bo__nhom_hd_id=int(nhom_id)))
-    if ky.isdigit(): qs = qs.filter(ky_can_thiep=int(ky))
-    if thang.isdigit(): qs = qs.filter(ngay_thuc_hien__month=int(thang))
-    if nam.isdigit(): qs = qs.filter(ngay_thuc_hien__year=int(nam))
-    return qs, ky, thang, nam
+    cb_id = parse_get_int(request.GET.get("can_bo"))
+    nhom_id = parse_get_int(request.GET.get("nhom_hd"))
+    ky = parse_get_int(request.GET.get("ky"), max_value=1000)
+    thang = parse_get_int(request.GET.get("thang"), max_value=12)
+    nam = parse_get_int(request.GET.get("nam"), min_value=1900, max_value=2100)
+    # Lọc theo CBCT/Nhóm hiệu lực đúng thứ tự ưu tiên của model (nguồn -> hợp đồng -> phân công/phân bổ).
+    if cb_id:
+        qs = qs.filter(can_bo_hieu_luc_pk=cb_id)
+    if nhom_id:
+        qs = qs.filter(nhom_hieu_luc_id=nhom_id)
+    if ky:
+        qs = qs.filter(ky_can_thiep=ky)
+    if thang:
+        qs = qs.filter(ngay_thuc_hien__month=thang)
+    if nam:
+        qs = qs.filter(ngay_thuc_hien__year=nam)
+    return qs, str(ky or ""), str(thang or ""), str(nam or "")
 
 
 def _paid_voucher_journal_queryset(queryset):
@@ -3876,7 +3892,7 @@ def xuat_dntt_nhat_ky(request):
                     grouped.setdefault(staff.pk, []).append(journal)
             for journals in grouped.values():
                 staff = journals[0].can_bo_hieu_luc
-                period = int(ky) if ky.isdigit() else journals[0].ky_can_thiep
+                period = int(ky) if _is_id(ky) else journals[0].ky_can_thiep
                 payment_round = max(item.lan_thanh_toan for item in journals)
                 output = export_journal_payment_request(journals, ky=ky, thang=thang, nam=nam, lan_tt=payment_round, nguoi_de_nghi=cbda)
                 safe_name = re.sub(r'[\\/:*?"<>|]+', "_", f"{staff.ma_can_bo} {staff.ho_ten}").strip()
