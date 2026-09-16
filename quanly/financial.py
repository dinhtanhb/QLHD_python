# quanly/financial.py

from decimal import Decimal
from datetime import time

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
        if getattr(other, "child_id", None) == getattr(current, "child_id", None) and getattr(other, "service", None) != getattr(current, "service", None):
            result.append("Trùng lịch CT")
        if getattr(other, "cb_id", None) == getattr(current, "cb_id", None) and getattr(other, "child_id", None) != getattr(current, "child_id", None):
            result.append("Trùng CBCT")
    return sorted(set(result))


def calculate_travel_flags(current, previous_records):
    """Tính lượt đi lại CBCT và PH theo cùng quy tắc với file Excel nghiệp vụ."""
    child = getattr(current, "child_id", None)
    cb = getattr(current, "cb_id", None)
    ace = (getattr(current, "ace", None) or "").strip()
    date_value = getattr(current, "date", None)
    start = getattr(current, "start", None)
    end = getattr(current, "end", None)
    location = (getattr(current, "location", None) or "").strip().lower()
    service = getattr(current, "service", None) or ""
    current_id = getattr(current, "record_id", None)
    ordered = [x for x in previous_records if getattr(x, "date", None) == date_value]

    cbct_repeat = False
    parent_repeat = False
    for other in ordered:
        other_start, other_end = getattr(other, "start", None), getattr(other, "end", None)
        if not all((child, date_value, start, end)):
            continue
        same_location = (getattr(other, "location", None) or "").strip().lower() == location
        prior = current_id is None or getattr(other, "record_id", None) is None or getattr(other, "record_id", 0) < current_id
        same_child = getattr(other, "child_id", None) == child
        same_cb = getattr(other, "cb_id", None) == cb
        other_ace = (getattr(other, "ace", None) or "").strip()
        if same_location and same_cb and same_child and getattr(other, "start", None) and getattr(other, "start") < start and getattr(other, "end", None) >= start:
            cbct_repeat = True
        if same_location and same_cb and same_child and getattr(other, "start", None) == start and (getattr(other, "service", None) or "") < service:
            cbct_repeat = True
        if ace and ace == other_ace and same_location and same_cb and getattr(other, "start", None) and getattr(other, "start") < start and getattr(other, "end", None) >= start:
            cbct_repeat = True
        if ace and ace == other_ace and same_location and same_cb and getattr(other, "start", None) == start and getattr(other, "child_id", None) is not None and getattr(other, "child_id") < child:
            cbct_repeat = True
        if prior and same_location and (same_child or (ace and ace == other_ace)) and times_overlap(start, end, other_start, other_end):
            parent_repeat = True

    cbct_trip = 1 if location in {"nhà", "tại nhà", "khác"} and not cbct_repeat else 0
    parent_trip = 1 if location in {"trường", "tại trường", "khác"} and not parent_repeat else 0
    return {"so_luot_di_lai_cbct": cbct_trip, "so_luot_di_lai_ph": parent_trip}
