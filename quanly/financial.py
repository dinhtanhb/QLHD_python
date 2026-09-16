# quanly/financial.py

from decimal import Decimal

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
