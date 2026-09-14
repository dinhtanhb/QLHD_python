# quanly/financial.py

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