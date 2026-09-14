from decimal import Decimal
from django.db import models
from django.utils import timezone
from .financial import FinancialConfig

class Tinh(models.Model):
    ma_tinh = models.CharField(max_length=20, unique=True, verbose_name="Mã Tỉnh")
    ten_tinh = models.CharField(max_length=100, verbose_name="Tên Tỉnh/Thành phố")

    def __str__(self):
        return self.ten_tinh


class Xa(models.Model):
    ma_xa = models.CharField(max_length=20, unique=True, verbose_name="Mã Xã")
    ten_xa = models.CharField(max_length=100, verbose_name="Tên Xã/Phường")
    tinh = models.ForeignKey(Tinh, on_delete=models.CASCADE, verbose_name="Thuộc Tỉnh")

    def __str__(self):
        return self.ten_xa

class DonVi(models.Model):
    ma_don_vi = models.CharField(max_length=20, unique=True, verbose_name="Mã Đơn Vị")
    ten_don_vi = models.CharField(max_length=200, verbose_name="Tên Đơn Vị")
    dia_chi = models.CharField(max_length=500, blank=True, null=True, verbose_name="Địa chỉ")
    mstdv = models.CharField(max_length=20, unique=True, verbose_name="Mã số thuế")
    nguoi_dai_dien = models.CharField(max_length=100, verbose_name="Người đại diện")
    dien_thoai = models.CharField(max_length=15, blank=True, null=True, verbose_name="Điện thoại")
    email = models.EmailField(max_length=100, blank=True, null=True, verbose_name="Email")
    
    def __str__(self):
        return f"{self.ma_don_vi} - {self.ten_don_vi}"

class CanBo(models.Model):
    ma_can_bo = models.CharField(max_length=20, unique=True, verbose_name="Mã CBCT")
    ho_ten = models.CharField(max_length=100, verbose_name="Họ và tên")
    gioi_tinh_choices = [
        ('Nam', 'Nam'),
        ('Nữ', 'Nữ'),
        ('Khác', 'Khác'),
    ]
    tinh = models.ForeignKey(Tinh, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Tỉnh/Thành phố")
    xa = models.ForeignKey(Xa, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Xã/Phường")
    dia_chi = models.CharField(max_length=500, blank=True, null=True, verbose_name="Địa chỉ")
    dien_thoai = models.CharField(max_length=15, blank=True, null=True, verbose_name="Điện thoại")
    email = models.EmailField(max_length=100, blank=True, null=True, verbose_name="Email")
    cccd = models.CharField(max_length=20, unique=True, null=True, blank=True, verbose_name="Số CCCD")
    mst = models.CharField(max_length=50, unique=True, null=True, blank=True, verbose_name="Mã số thuế")
    gioi_tinh = models.CharField(max_length=10, null=True, blank=True, verbose_name="Giới tính")
    ngay_cap = models.DateField(null=True, blank=True, verbose_name="Ngày cấp CCCD")
    noi_cap = models.CharField(max_length=200, verbose_name="Nơi cấp")
    tai_khoan = models.CharField(max_length=50, blank=True, null=True, verbose_name="Tài khoản")
    ngan_hang = models.CharField(max_length=100, blank=True, null=True, verbose_name="Ngân hàng")
    chi_nhanh = models.CharField(max_length=100, blank=True, null=True, verbose_name="Chi nhánh")
    don_vi = models.ForeignKey(DonVi, on_delete=models.CASCADE, verbose_name="Đơn vị trực thuộc")
        
    def __str__(self):
        return f"{self.ma_can_bo} - {self.ho_ten}"

class NhomHD(models.Model):
    ma_nhom_hd = models.CharField(max_length=20, unique=True, verbose_name="Mã nhóm hợp đồng")
    ten_nhom_hd = models.CharField(max_length=200, verbose_name="Tên nhóm hợp đồng")

    def __str__(self):
        return f"{self.ma_nhom_hd} - {self.ten_nhom_hd}"

class Tre(models.Model):
    ma_tre = models.CharField(max_length=20, unique=True, verbose_name="Mã trẻ")
    ho_ten = models.CharField(max_length=100, verbose_name="Họ và tên")
    ngay_sinh = models.DateField(verbose_name="Ngày sinh")
    gioi_tinh_choices = [
            ('Nam', 'Nam'),
            ('Nữ', 'Nữ'),
            ('Khác', 'Khác'),
        ]
    gioi_tinh = models.CharField(max_length=10, choices=gioi_tinh_choices, verbose_name="Giới tính")
    tinh = models.ForeignKey(Tinh, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Tỉnh/Thành phố")
    xa = models.ForeignKey(Xa, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Xã/Phường")
    ma_tinh = models.CharField(max_length=10, verbose_name="Mã tỉnh")
    ten_phu_huynh = models.CharField(max_length=100, verbose_name="Tên phụ huynh")
    dien_thoai = models.CharField(max_length=15, blank=True, null=True, verbose_name="Điện thoại")
    ten_tai_khoan = models.CharField(max_length=100, blank=True, null=True, verbose_name="Tên tài khoản")
    tai_khoan = models.CharField(max_length=50, blank=True, null=True, verbose_name="Tài khoản")
    ngan_hang = models.CharField(max_length=100, blank=True, null=True, verbose_name="Ngân hàng")
    chi_nhanh = models.CharField(max_length=100, blank=True, null=True, verbose_name="Chi nhánh")
    ghi_chu = models.TextField(blank=True, null=True, verbose_name="Ghi chú")

# ==========================================
# CÁC MODEL CHO NGHIỆP VỤ HỢP ĐỒNG & PHÂN CÔNG
# ==========================================

class ChiTieuHopDong(models.Model):
    """Bảng lưu chỉ tiêu phân bổ cho CBCT để tính giá trị hợp đồng khung"""
    can_bo = models.ForeignKey(CanBo, on_delete=models.CASCADE, verbose_name="Cán bộ can thiệp")
    nhom_hd = models.ForeignKey(NhomHD, on_delete=models.CASCADE, verbose_name="Nhóm hợp đồng")
    
    so_tre_phcn = models.PositiveIntegerField(default=0, verbose_name="Số trẻ PHCN")
    so_buoi_phcn = models.PositiveIntegerField(default=20, verbose_name="Số buổi/trẻ PHCN mặc định")
    
    so_tre_cs = models.PositiveIntegerField(default=0, verbose_name="Số trẻ Chăm sóc")
    so_buoi_cs = models.PositiveIntegerField(default=10, verbose_name="Số buổi/trẻ CS mặc định")
    
    ngay_tao = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Chỉ tiêu {self.can_bo.ho_ten} - {self.nhom_hd}"


class PhanBoChiTieu(models.Model):
    TRANG_THAI_CHOICES = [
        ('DE_XUAT', 'Chờ đề xuất HĐ'),
        ('DA_TAO', 'Đã tạo Hợp đồng'),
    ]

    DINH_MUC_CHOICES = [
        (FinancialConfig.DON_GIA_DI_LAI_DM1, f"Định mức 1 ({FinancialConfig.DON_GIA_DI_LAI_DM1:,.0f} đ)"),
        (FinancialConfig.DON_GIA_DI_LAI_DM2, f"Định mức 2 ({FinancialConfig.DON_GIA_DI_LAI_DM2:,.0f} đ)"),
    ]

    can_bo = models.ForeignKey('CanBo', on_delete=models.CASCADE, verbose_name="Cán bộ can thiệp")
    tham_gia_ct = models.BooleanField(default=True, verbose_name="Tham gia can thiệp")
    ngay_lap_de_xuat = models.DateField(default=timezone.now, verbose_name="Ngày lập đề xuất")
    nhom_hd = models.IntegerField(default=1, verbose_name="Nhóm hợp đồng")
    
    # Chỉ tiêu PHCN & Định mức đi lại PHCN (Lấy mặc định là DM1 = 50000 từ FinancialConfig)
    so_tre_phcn = models.IntegerField(default=0)
    so_buoi_phcn = models.IntegerField(default=20)
    dinh_muc_di_lai_phcn = models.DecimalField(
        max_digits=12, decimal_places=0, 
        default=Decimal(str(FinancialConfig.DON_GIA_DI_LAI_DM1)),
        verbose_name="Định mức đi lại PHCN"
    )
    
    # Chỉ tiêu CSXH & Định mức đi lại CSXH (Lấy mặc định là DM1 = 50000 từ FinancialConfig)
    so_tre_cs = models.IntegerField(default=0)
    so_buoi_cs = models.IntegerField(default=10)
    dinh_muc_di_lai_cs = models.DecimalField(
        max_digits=12, decimal_places=0, 
        default=Decimal(str(FinancialConfig.DON_GIA_DI_LAI_DM1)),
        verbose_name="Định mức đi lại CSXH"
    )
    
    # Giá trị HĐ dự kiến
    gia_tri_hd_du_kien = models.DecimalField(max_digits=15, decimal_places=0, default=Decimal('0'))
    
    # Thông tin hợp đồng chính thức
    so_hop_dong = models.CharField(max_length=50, blank=True, null=True)
    ngay_ky = models.DateField(blank=True, null=True)
    tu_ngay = models.DateField(blank=True, null=True)
    den_ngay = models.DateField(blank=True, null=True)
    
    trang_thai = models.CharField(max_length=20, choices=TRANG_THAI_CHOICES, default='DE_XUAT', verbose_name="Trạng thái HĐ")
    is_locked = models.BooleanField(default=False)


class PhanCongTre(models.Model):
    """Danh sách trẻ được phân công cho CBCT trong đợt/kỳ can thiệp"""
    hop_dong = models.ForeignKey(PhanBoChiTieu, on_delete=models.CASCADE, related_name='danh_sach_phan_cong', verbose_name="Hợp đồng")
    tre = models.ForeignKey(Tre, on_delete=models.CASCADE, verbose_name="Trẻ")
    
    LOAI_DV_CHOICES = [
        ('VLTL', 'Vật lý trị liệu'),
        ('HDTL', 'Hoạt động trị liệu'),
        ('NNTL', 'Ngôn ngữ trị liệu'),
        ('GDDB', 'Giáo dục đặc biệt'),
        ('CSXH', 'Chăm sóc xã hội'),
        ('CSYT', 'Chăm sóc y tế'),
    ]
    loai_dich_vu = models.CharField(max_length=10, choices=LOAI_DV_CHOICES, verbose_name="Loại dịch vụ")
    
    so_buoi_du_kien = models.PositiveIntegerField(default=20, verbose_name="Số buổi dự kiến")
    dinh_muc_di_lai = models.DecimalField(max_digits=10, decimal_places=0, default=Decimal('50000'), verbose_name="Định mức đi lại (VNĐ)")
    
    dia_diem_ct = models.CharField(max_length=255, blank=True, null=True, verbose_name="Địa điểm can thiệp")
    hinh_thuc_ct = models.CharField(max_length=100, blank=True, null=True, verbose_name="Hình thức can thiệp")
    dot_phan_cong = models.CharField(max_length=50, blank=True, null=True, verbose_name="Đợt phân công")
    ky_phan_cong = models.CharField(max_length=50, blank=True, null=True, verbose_name="Kỳ phân công")
    ngay_phan_cong = models.DateField(blank=True, null=True, verbose_name="Ngày phân công")
    
    TRANG_THAI_TRE = [
        ('dang_can_thiệp', 'Đang can thiệp'),
        ('da_hoan_thanh', 'Đã hoàn thành'),
        ('khong_can_thiệp', 'Không can thiệp'),
    ]
    trang_thai = models.CharField(max_length=20, choices=TRANG_THAI_TRE, default='dang_can_thiệp', verbose_name="Trạng thái trẻ")

    def __str__(self):
        return f"Phân công {self.tre.ho_ten} cho {self.hop_dong.can_bo.ho_ten if self.hop_dong else ''}"

