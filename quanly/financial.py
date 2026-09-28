# quanly/financial.py

from decimal import Decimal
from datetime import time
import unicodedata

class FinancialConfig:
    # Thuế TNCN
    THUE_TNCN_NGUONG = 5_000_000  # Ngưỡng chịu thuế
    THUE_TNCN_TY_LE = 0.10        # 10%

    # Đơn giá can thiệp & đi lại
    DON_GIA_CONG = 200_000
    DON_GIA_DI_LAI_DM1 = 50_000   
    DON_GIA_DI_LAI_DM2 = 100_000

    # Điều kiện tính phụ cấp đi lại (không phân biệt hoa/thường khi so sánh)
    DI_LAI_CBCT_HOP_LE = ['tại nhà', 'khác']
    DI_LAI_PH_HOP_LE = ['tại trường', 'khác']

    # Kỳ can thiệp có thể vượt 12 vì không đồng nhất với tháng dương lịch.
    KY_CAN_THIEP_CHOICES = range(1, 31)
    NAM_CAN_THIEP_CHOICES = range(2024, 2031)


def calculate_tncn(tien_cong):
    """Tính thuế TNCN trên tiền công, không tính tiền đi lại."""
    tien_cong = Decimal(str(tien_cong or 0))
    if tien_cong < Decimal(str(FinancialConfig.THUE_TNCN_NGUONG)):
        return Decimal("0")
    return tien_cong * Decimal(str(FinancialConfig.THUE_TNCN_TY_LE))


def calculate_payment_breakdown(tien_cong, tien_di_lai):
    """Tách tiền công, đi lại, thuế và thực lĩnh theo quy tắc thanh toán."""
    tien_cong = Decimal(str(tien_cong or 0))
    tien_di_lai = Decimal(str(tien_di_lai or 0))
    thue = calculate_tncn(tien_cong)
    return {
        "tien_cong": tien_cong,
        "tien_di_lai": tien_di_lai,
        "tong_truoc_thue": tien_cong + tien_di_lai,
        "thue_tncn": thue,
        "thuc_linh": tien_cong + tien_di_lai - thue,
    }


def times_overlap(start_a, end_a, start_b, end_b):
    """True khi hai phiên thực sự chồng lấn; hai phiên nối tiếp không chồng lấn."""
    if not all((start_a, end_a, start_b, end_b)):
        return False
    return start_a < end_b and start_b < end_a


def normalize_travel_location(value):
    """Chuẩn hóa địa điểm về nhóm dùng để tính lượt đi lại."""
    text = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode().lower()
    text = " ".join(text.replace("_", " ").split())
    if "truong" in text:
        return "truong"
    if "nha" in text:
        return "nha"
    if "khac" in text:
        return "khac"
    return ""


def sessions_join(start_a, end_a, start_b, end_b):
    """True nếu hai ca chạm nhau hoặc chồng lên nhau trong cùng ngày."""
    if not all((start_a, end_a, start_b, end_b)):
        return False
    return start_a <= end_b and start_b <= end_a


def journal_conflict_types(current, previous_records):
    """Trả về các cảnh báo trùng lịch của một nhật ký với các nhật ký trước đó.

    ``current`` và các phần tử ``previous_records`` chỉ cần có các thuộc tính
    ``child_id``, ``cb_id``, ``service``, ``date``, ``start``, ``end``.
    """
    result = []
    for other in previous_records:
        if getattr(other, "date", None) != getattr(current, "date", None):
            continue
        if not times_overlap(getattr(current, "start", None), getattr(current, "end", None), getattr(other, "start", None), getattr(other, "end", None)):
            continue
        current_child = getattr(current, "child_id", None)
        other_child = getattr(other, "child_id", None)
        if current_child is not None and other_child is not None and other_child == current_child and getattr(other, "service", None) != getattr(current, "service", None):
            result.append("Trùng lịch CT")
        current_cb = getattr(current, "cb_id", None)
        other_cb = getattr(other, "cb_id", None)
        if current_cb is not None and other_cb is not None and other_cb == current_cb and other_child != current_child:
            result.append("Trùng CBCT")
    return sorted(set(result))


def calculate_travel_flags(current, previous_records):
    """Tính lượt đi lại theo cụm ca liên tiếp trong cùng ngày.

    PH đi cùng một trẻ nên được gom theo trẻ. CBCT tại ``Khác`` chỉ di chuyển
    tới một địa điểm trong ngày nên được gom theo CBCT, kể cả khi phục vụ
    nhiều trẻ. Hai ca nối tiếp (ví dụ 8-9 và 9-10) chỉ tính một lượt.
    """
    child = getattr(current, "child_id", None)
    cb = getattr(current, "cb_id", None)
    ace = (getattr(current, "ace", None) or "").strip()
    date_value = getattr(current, "date", None)
    start = getattr(current, "start", None)
    end = getattr(current, "end", None)
    location = normalize_travel_location(getattr(current, "location", None))
    current_id = getattr(current, "record_id", None)
    ordered = [x for x in previous_records if getattr(x, "date", None) == date_value]

    current_order = (start, end, current_id or 0)
    cbct_repeat = False
    parent_repeat = False
    for other in ordered:
        other_start, other_end = getattr(other, "start", None), getattr(other, "end", None)
        if not all((date_value, start, end, other_start, other_end)):
            continue
        if current_id is not None and getattr(other, "record_id", None) == current_id:
            continue
        if normalize_travel_location(getattr(other, "location", None)) != location:
            continue
        other_child = getattr(other, "child_id", None)
        other_cb = getattr(other, "cb_id", None)
        same_child = child is not None and other_child is not None and other_child == child
        same_cb = cb is not None and other_cb is not None and other_cb == cb
        other_ace = (getattr(other, "ace", None) or "").strip()
        same_parent = same_child or (ace and ace == other_ace)
        cbct_scope = same_cb and (location == "khac" or same_child or (ace and ace == other_ace))
        other_order = (other_start, other_end, getattr(other, "record_id", None) or 0)
        is_previous_session = other_order < current_order
        if cbct_scope and is_previous_session and sessions_join(start, end, other_start, other_end):
            cbct_repeat = True
        if same_parent and is_previous_session and sessions_join(start, end, other_start, other_end):
            parent_repeat = True

    cbct_trip = 1 if location in {"nha", "khac"} and not cbct_repeat else 0
    parent_trip = 1 if location in {"truong", "khac"} and not parent_repeat else 0
    return {"so_luot_di_lai_cbct": cbct_trip, "so_luot_di_lai_ph": parent_trip}
