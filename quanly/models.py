from decimal import Decimal
from types import SimpleNamespace

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from .financial import FinancialConfig, calculate_payment_breakdown, calculate_travel_flags, journal_conflict_types


class TimeStampedModel(models.Model):
    """Base model dùng chung cho các bảng nghiệp vụ."""

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Ngày tạo")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Ngày cập nhật")

    class Meta:
        abstract = True


class Tinh(TimeStampedModel):
    ma_tinh = models.CharField(max_length=20, unique=True, verbose_name="Mã Tỉnh")
    ten_tinh = models.CharField(max_length=100, verbose_name="Tên Tỉnh/Thành phố")
    is_active = models.BooleanField(default=True, verbose_name="Đang sử dụng")

    class Meta:
        ordering = ["ten_tinh"]
        verbose_name = "Tỉnh/Thành phố"
        verbose_name_plural = "Tỉnh/Thành phố"

    def __str__(self):
        return f"{self.ma_tinh} - {self.ten_tinh}"


class Xa(TimeStampedModel):
    ma_xa = models.CharField(max_length=20, unique=True, verbose_name="Mã Xã")
    ten_xa = models.CharField(max_length=100, verbose_name="Tên Xã/Phường")
    tinh = models.ForeignKey(
        Tinh,
        on_delete=models.PROTECT,
        related_name="danh_sach_xa",
        verbose_name="Thuộc Tỉnh",
    )
    is_active = models.BooleanField(default=True, verbose_name="Đang sử dụng")

    class Meta:
        ordering = ["ten_xa"]
        verbose_name = "Xã/Phường"
        verbose_name_plural = "Xã/Phường"
        constraints = [
            models.UniqueConstraint(fields=["tinh", "ten_xa"], name="uq_xa_tinh_ten"),
        ]

    def __str__(self):
        return f"{self.ma_xa} - {self.ten_xa}"


class DonVi(TimeStampedModel):
    ma_don_vi = models.CharField(max_length=20, unique=True, verbose_name="Mã Đơn Vị")
    ten_don_vi = models.CharField(max_length=200, verbose_name="Tên Đơn Vị")
    dia_chi = models.CharField(max_length=500, blank=True, null=True, verbose_name="Địa chỉ")
    mstdv = models.CharField(max_length=20, blank=True, null=True, unique=True, verbose_name="Mã số thuế")
    nguoi_dai_dien = models.CharField(max_length=100, verbose_name="Người đại diện")
    dien_thoai = models.CharField(max_length=15, blank=True, null=True, verbose_name="Điện thoại")
    email = models.EmailField(max_length=100, blank=True, null=True, verbose_name="Email")
    is_active = models.BooleanField(default=True, verbose_name="Đang sử dụng")

    class Meta:
        ordering = ["ten_don_vi"]
        verbose_name = "Đơn vị"
        verbose_name_plural = "Đơn vị"

    def __str__(self):
        return f"{self.ma_don_vi} - {self.ten_don_vi}"


class CanBo(TimeStampedModel):
    GIOI_TINH_CHOICES = [
        ("Nam", "Nam"),
        ("Nữ", "Nữ"),
        ("Khác", "Khác"),
    ]

    ma_can_bo = models.CharField(max_length=20, unique=True, verbose_name="Mã CBCT")
    ho_ten = models.CharField(max_length=100, verbose_name="Họ và tên")
    gioi_tinh = models.CharField(max_length=10, choices=GIOI_TINH_CHOICES, blank=True, null=True, verbose_name="Giới tính")
    tinh = models.ForeignKey(Tinh, on_delete=models.PROTECT, null=True, blank=True, verbose_name="Tỉnh/Thành phố")
    xa = models.ForeignKey(Xa, on_delete=models.PROTECT, null=True, blank=True, verbose_name="Xã/Phường")
    dia_chi = models.CharField(max_length=500, blank=True, null=True, verbose_name="Địa chỉ")
    dien_thoai = models.CharField(max_length=15, blank=True, null=True, verbose_name="Điện thoại")
    email = models.EmailField(max_length=100, blank=True, null=True, verbose_name="Email")
    cccd = models.CharField(max_length=20, unique=True, null=True, blank=True, verbose_name="Số CCCD")
    mst = models.CharField(max_length=50, unique=True, null=True, blank=True, verbose_name="Mã số thuế")
    ngay_cap = models.DateField(null=True, blank=True, verbose_name="Ngày cấp CCCD")
    noi_cap = models.CharField(max_length=200, blank=True, null=True, verbose_name="Nơi cấp")
    tai_khoan = models.CharField(max_length=50, blank=True, null=True, verbose_name="Tài khoản")
    ngan_hang = models.CharField(max_length=100, blank=True, null=True, verbose_name="Ngân hàng")
    chi_nhanh = models.CharField(max_length=100, blank=True, null=True, verbose_name="Chi nhánh")
    don_vi = models.ForeignKey(DonVi, on_delete=models.PROTECT, verbose_name="Đơn vị trực thuộc")
    is_active = models.BooleanField(default=True, verbose_name="Đang hoạt động")

    class Meta:
        ordering = ["ho_ten"]
        verbose_name = "Cán bộ can thiệp"
        verbose_name_plural = "Cán bộ can thiệp"

    def __str__(self):
        return f"{self.ma_can_bo} - {self.ho_ten}"


class NhomHD(TimeStampedModel):
    ma_nhom_hd = models.CharField(max_length=20, unique=True, verbose_name="Mã nhóm hợp đồng")
    ten_nhom_hd = models.CharField(max_length=200, verbose_name="Tên nhóm hợp đồng")
    is_active = models.BooleanField(default=True, verbose_name="Đang sử dụng")

    class Meta:
        ordering = ["ma_nhom_hd"]
        verbose_name = "Nhóm hợp đồng"
        verbose_name_plural = "Nhóm hợp đồng"

    def __str__(self):
        return f"{self.ma_nhom_hd} - {self.ten_nhom_hd}"


class Tre(TimeStampedModel):
    GIOI_TINH_CHOICES = [
        ("Nam", "Nam"),
        ("Nữ", "Nữ"),
        ("Khác", "Khác"),
    ]

    ma_tre = models.CharField(max_length=20, unique=True, verbose_name="Mã trẻ")
    ho_ten = models.CharField(max_length=100, verbose_name="Họ và tên")
    ngay_sinh = models.DateField(verbose_name="Ngày sinh")
    gioi_tinh = models.CharField(max_length=10, choices=GIOI_TINH_CHOICES, verbose_name="Giới tính")
    tinh = models.ForeignKey(Tinh, on_delete=models.PROTECT, null=True, blank=True, verbose_name="Tỉnh/Thành phố")
    xa = models.ForeignKey(Xa, on_delete=models.PROTECT, null=True, blank=True, verbose_name="Xã/Phường")
    ma_tinh = models.CharField(max_length=10, blank=True, null=True, verbose_name="Mã tỉnh")
    ten_phu_huynh = models.CharField(max_length=100, blank=True, null=True, verbose_name="Tên phụ huynh")
    dien_thoai = models.CharField(max_length=15, blank=True, null=True, verbose_name="Điện thoại")
    ten_tai_khoan = models.CharField(max_length=100, blank=True, null=True, verbose_name="Tên tài khoản")
    tai_khoan = models.CharField(max_length=50, blank=True, null=True, verbose_name="Tài khoản")
    ngan_hang = models.CharField(max_length=100, blank=True, null=True, verbose_name="Ngân hàng")
    chi_nhanh = models.CharField(max_length=100, blank=True, null=True, verbose_name="Chi nhánh")
    ace_ruot = models.CharField(max_length=100, blank=True, null=True, verbose_name="ACE ruột")
    ghi_chu = models.TextField(blank=True, null=True, verbose_name="Ghi chú")
    is_active = models.BooleanField(default=True, verbose_name="Đang sử dụng")

    class Meta:
        ordering = ["ma_tre"]
        verbose_name = "Trẻ"
        verbose_name_plural = "Trẻ"

    def __str__(self):
        return f"{self.ma_tre} - {self.ho_ten}"


class PhanBoChiTieu(TimeStampedModel):
    """Phân bổ chỉ tiêu. Không chứa thông tin hợp đồng chính thức."""

    can_bo = models.ForeignKey(CanBo, on_delete=models.PROTECT, null=True, blank=True, related_name="phan_bo_chi_tieu", verbose_name="Cán bộ can thiệp")
    cbda_quan_ly = models.CharField(max_length=100, blank=True, null=True, verbose_name="CBDA quản lý")
    nhom_hd = models.ForeignKey(NhomHD, on_delete=models.PROTECT, related_name="phan_bo_chi_tieu", verbose_name="Nhóm hợp đồng")
    tham_gia_ct = models.BooleanField(default=True, verbose_name="Tham gia can thiệp")
    ngay_lap = models.DateField(default=timezone.now, verbose_name="Ngày lập phân bổ")

    so_tre_phcn = models.PositiveIntegerField(default=0, verbose_name="Số trẻ PHCN")
    so_buoi_phcn = models.PositiveIntegerField(default=20, verbose_name="Số buổi/trẻ PHCN")
    dinh_muc_di_lai_phcn = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        default=Decimal(str(FinancialConfig.DON_GIA_DI_LAI_DM1)),
        verbose_name="Định mức đi lại PHCN",
    )

    so_tre_cs = models.PositiveIntegerField(default=0, verbose_name="Số trẻ CSXH")
    so_buoi_cs = models.PositiveIntegerField(default=10, verbose_name="Số buổi/trẻ CSXH")
    dinh_muc_di_lai_cs = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        default=Decimal(str(FinancialConfig.DON_GIA_DI_LAI_DM1)),
        verbose_name="Định mức đi lại CSXH",
    )

    ghi_chu = models.TextField(blank=True, null=True, verbose_name="Ghi chú")
    is_locked = models.BooleanField(default=False, verbose_name="Đã khóa")

    class Meta:
        ordering = ["-ngay_lap", "-id"]
        indexes = [
            models.Index(fields=["can_bo", "ngay_lap"], name="idx_pbct_cb_ngay"),
            models.Index(fields=["nhom_hd", "ngay_lap"], name="idx_pbct_nhom_ngay"),
        ]

    def __str__(self):
        owner = self.can_bo.ho_ten if self.can_bo else (self.cbda_quan_ly or "Chưa phân CBCT")
        return f"PBCT #{self.pk} - {owner}"


class PhanCongTre(TimeStampedModel):
    """Phân công trẻ theo phân bổ; chưa đồng nghĩa với thực tế thực hiện."""

    PHCN_SERVICE_CODES = frozenset({"VLTL", "HDTL", "NNTL", "GDDB"})
    CS_SERVICE_CODES = frozenset({"CSXH", "CSYT"})

    LOAI_DV_CHOICES = [
        ("VLTL", "Vật lý trị liệu"),
        ("HDTL", "Hoạt động trị liệu"),
        ("NNTL", "Ngôn ngữ trị liệu"),
        ("GDDB", "Giáo dục đặc biệt"),
        ("CSXH", "Chăm sóc xã hội"),
        ("CSYT", "Chăm sóc y tế"),
    ]
    TRANG_THAI_CHOICES = [
        ("DANG_CAN_THIEP", "Đang can thiệp"),
        ("DA_HOAN_THANH", "Đã hoàn thành"),
        ("KHONG_CAN_THIEP", "Không can thiệp"),
    ]

    phan_bo = models.ForeignKey(
        PhanBoChiTieu,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="danh_sach_phan_cong",
        verbose_name="Phân bổ chỉ tiêu",
    )
    cbda_quan_ly = models.CharField(max_length=100, blank=True, null=True, verbose_name="CBDA quản lý")
    nhom_hd = models.ForeignKey(NhomHD, on_delete=models.PROTECT, null=True, blank=True, related_name="phan_cong_tre", verbose_name="Nhóm hợp đồng")
    tre = models.ForeignKey(Tre, on_delete=models.PROTECT, related_name="danh_sach_phan_cong", verbose_name="Trẻ")
    loai_dich_vu = models.CharField(max_length=10, choices=LOAI_DV_CHOICES, verbose_name="Loại dịch vụ")
    so_buoi_du_kien = models.PositiveIntegerField(default=0, verbose_name="Số buổi dự kiến")
    dinh_muc_di_lai = models.DecimalField(max_digits=12, decimal_places=0, default=Decimal("0"), verbose_name="Định mức đi lại")
    dia_diem_ct = models.CharField(max_length=255, blank=True, null=True, verbose_name="Địa điểm can thiệp")
    hinh_thuc_ct = models.CharField(max_length=100, blank=True, null=True, verbose_name="Hình thức can thiệp")
    dot_phan_cong = models.PositiveIntegerField(default=1, verbose_name="Đợt phân công")
    ky_phan_cong = models.PositiveIntegerField(default=1, verbose_name="Kỳ phân công")
    ngay_phan_cong = models.DateField(blank=True, null=True, verbose_name="Ngày phân công")
    trang_thai = models.CharField(max_length=20, choices=TRANG_THAI_CHOICES, default="DANG_CAN_THIEP", verbose_name="Trạng thái")
    ghi_chu = models.TextField(blank=True, null=True, verbose_name="Ghi chú")
    tu_dong_tu_nhat_ky = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name="Phân công kỹ thuật tự tạo từ nhật ký",
    )

    class Meta:
        ordering = ["-ngay_phan_cong", "-id"]
        indexes = [
            models.Index(fields=["phan_bo", "dot_phan_cong"], name="idx_pct_pb_dot"),
            models.Index(fields=["tre", "ky_phan_cong"], name="idx_pct_tre_ky"),
            models.Index(fields=["loai_dich_vu", "ngay_phan_cong"], name="idx_pct_dv_ngay"),
        ]

    @classmethod
    def service_group(cls, service_code):
        """Trả về nhóm nghiệp vụ PHCN/CS của một mã dịch vụ."""
        if service_code in cls.PHCN_SERVICE_CODES:
            return "PHCN"
        if service_code in cls.CS_SERVICE_CODES:
            return "CS"
        return None

    @property
    def nhom_dich_vu(self):
        return self.service_group(self.loai_dich_vu)

    def __str__(self):
        return f"Phân công {self.tre.ho_ten} - {self.loai_dich_vu}"


class LichSuDieuChuyenPhanCong(TimeStampedModel):
    phan_cong = models.ForeignKey(PhanCongTre, on_delete=models.CASCADE, related_name="lich_su_dieu_chuyen")
    phan_bo_cu = models.ForeignKey(PhanBoChiTieu, on_delete=models.PROTECT, related_name="lich_su_phan_cong_cu")
    phan_bo_moi = models.ForeignKey(PhanBoChiTieu, on_delete=models.PROTECT, related_name="lich_su_phan_cong_moi")
    nguoi_thuc_hien = models.CharField(max_length=150, blank=True, null=True)
    ly_do = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ["-created_at", "-id"]


class DeXuatHopDong(TimeStampedModel):
    """Đề xuất hợp đồng được tạo từ phân bổ + dữ liệu phân công thực tế."""

    TRANG_THAI_CHOICES = [
        ("CHO_KIEM_TRA", "Chờ kiểm tra"),
        ("DU_DIEU_KIEN", "Đủ điều kiện"),
        ("DA_DUYET", "Đã duyệt"),
        ("DA_TAO_HOP_DONG", "Đã tạo hợp đồng"),
        ("TU_CHOI", "Từ chối"),
        ("HUY", "Hủy"),
    ]

    phan_bo = models.ForeignKey(PhanBoChiTieu, on_delete=models.PROTECT, related_name="de_xuat_hop_dong", verbose_name="Phân bổ chỉ tiêu")
    lan_de_xuat = models.PositiveIntegerField(default=1, verbose_name="Lần đề xuất")
    ngay_de_xuat = models.DateField(default=timezone.now, verbose_name="Ngày đề xuất")
    so_tre_phcn = models.PositiveIntegerField(default=0, verbose_name="Số trẻ PHCN")
    so_buoi_phcn = models.PositiveIntegerField(default=0, verbose_name="Số buổi PHCN")
    so_tre_cs = models.PositiveIntegerField(default=0, verbose_name="Số trẻ CSXH")
    so_buoi_cs = models.PositiveIntegerField(default=0, verbose_name="Số buổi CSXH")
    gia_tri_du_kien = models.DecimalField(max_digits=18, decimal_places=0, default=Decimal("0"), verbose_name="Giá trị dự kiến")
    trang_thai = models.CharField(max_length=30, choices=TRANG_THAI_CHOICES, default="CHO_KIEM_TRA", verbose_name="Trạng thái")
    ly_do = models.TextField(blank=True, null=True, verbose_name="Lý do/Ghi chú")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["phan_bo", "lan_de_xuat"], name="uq_dexuat_phanbo_lan"),
        ]
        indexes = [
            models.Index(fields=["trang_thai", "ngay_de_xuat"], name="idx_dexuat_status_ngay"),
        ]

    def __str__(self):
        return f"Đề xuất #{self.pk} - {self.phan_bo.can_bo.ho_ten}"


class HopDong(TimeStampedModel):
    """Hợp đồng chính thức, độc lập với phân bổ và đề xuất."""

    TRANG_THAI_CHOICES = [
        ("DU_THAO", "Dự thảo"),
        ("DA_KY", "Đã ký"),
        ("DANG_THUC_HIEN", "Đang thực hiện"),
        ("TAM_DUNG", "Tạm dừng"),
        ("HET_HAN", "Hết hạn"),
        ("NGHIEM_THU", "Nghiệm thu"),
        ("THANH_LY", "Thanh lý"),
        ("HUY", "Hủy"),
    ]

    de_xuat = models.ForeignKey(DeXuatHopDong, on_delete=models.PROTECT, related_name="hop_dong", verbose_name="Đề xuất hợp đồng")
    can_bo = models.ForeignKey(CanBo, on_delete=models.PROTECT, related_name="hop_dong", verbose_name="Cán bộ can thiệp")
    nhom_hd = models.ForeignKey(NhomHD, on_delete=models.PROTECT, related_name="hop_dong", verbose_name="Nhóm hợp đồng")
    so_hop_dong = models.CharField(max_length=50, unique=True, verbose_name="Số hợp đồng")
    ngay_ky = models.DateField(null=True, blank=True, verbose_name="Ngày ký")
    tu_ngay = models.DateField(verbose_name="Từ ngày")
    den_ngay = models.DateField(verbose_name="Đến ngày")
    don_gia_cong = models.DecimalField(max_digits=12, decimal_places=0, default=Decimal(str(FinancialConfig.DON_GIA_CONG)), verbose_name="Đơn giá công")
    dinh_muc_di_lai_phcn = models.DecimalField(max_digits=12, decimal_places=0, default=Decimal(str(FinancialConfig.DON_GIA_DI_LAI_DM1)), verbose_name="Định mức đi lại PHCN")
    dinh_muc_di_lai_cs = models.DecimalField(max_digits=12, decimal_places=0, default=Decimal(str(FinancialConfig.DON_GIA_DI_LAI_DM1)), verbose_name="Định mức đi lại CSXH")
    gia_tri_hop_dong = models.DecimalField(max_digits=18, decimal_places=0, default=Decimal("0"), verbose_name="Giá trị hợp đồng")
    trang_thai = models.CharField(max_length=20, choices=TRANG_THAI_CHOICES, default="DU_THAO", verbose_name="Trạng thái")
    is_locked = models.BooleanField(default=False, verbose_name="Đã khóa")
    ghi_chu = models.TextField(blank=True, null=True, verbose_name="Ghi chú")

    class Meta:
        ordering = ["-ngay_ky", "-id"]
        indexes = [
            models.Index(fields=["can_bo", "trang_thai"], name="idx_hd_cb_status"),
            models.Index(fields=["tu_ngay", "den_ngay"], name="idx_hd_range"),
        ]
        constraints = [
            models.CheckConstraint(condition=models.Q(den_ngay__gte=models.F("tu_ngay")), name="ck_hd_ngay_hop_le"),
            models.CheckConstraint(condition=models.Q(gia_tri_hop_dong__gte=0), name="ck_hd_gia_tri_duong"),
        ]

    def clean(self):
        errors = {}
        if self.den_ngay and self.tu_ngay and self.den_ngay < self.tu_ngay:
            errors["den_ngay"] = "Ngày kết thúc phải lớn hơn hoặc bằng ngày bắt đầu."
        if self.de_xuat_id and self.can_bo_id and self.de_xuat.phan_bo.can_bo_id != self.can_bo_id:
            errors["can_bo"] = "Cán bộ của hợp đồng phải khớp cán bộ của đề xuất."
        if self.de_xuat_id and self.nhom_hd_id and self.de_xuat.phan_bo.nhom_hd_id != self.nhom_hd_id:
            errors["nhom_hd"] = "Nhóm hợp đồng phải khớp nhóm của phân bổ."
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return self.so_hop_dong


class ChiTietKhoiLuongHopDong(TimeStampedModel):
    """Khối lượng chính thức và đơn giá đã chốt tại thời điểm ký HĐ."""

    hop_dong = models.ForeignKey(HopDong, on_delete=models.PROTECT, related_name="chi_tiet_khoi_luong", verbose_name="Hợp đồng")
    loai_dich_vu = models.CharField(max_length=10, choices=PhanCongTre.LOAI_DV_CHOICES, verbose_name="Loại dịch vụ")
    so_tre = models.PositiveIntegerField(default=0, verbose_name="Số trẻ")
    so_buoi = models.PositiveIntegerField(default=0, verbose_name="Số buổi")
    don_gia_cong = models.DecimalField(max_digits=12, decimal_places=0, verbose_name="Đơn giá công")
    dinh_muc_di_lai = models.DecimalField(max_digits=12, decimal_places=0, verbose_name="Định mức đi lại")
    thanh_tien = models.DecimalField(max_digits=18, decimal_places=0, default=Decimal("0"), verbose_name="Thành tiền")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["hop_dong", "loai_dich_vu"], name="uq_hd_khoiluong_dv"),
        ]

    def save(self, *args, **kwargs):
        self.thanh_tien = Decimal(self.so_tre) * Decimal(self.so_buoi) * (Decimal(self.don_gia_cong) + Decimal(self.dinh_muc_di_lai))
        super().save(*args, **kwargs)


class PhuLucHopDong(TimeStampedModel):
    LOAI_PHU_LUC_CHOICES = [
        ("KY_1", "Phụ lục phân công Kỳ 1"),
        ("BO_SUNG", "Phụ lục bổ sung"),
        ("DIEU_CHINH", "Phụ lục điều chỉnh"),
        ("KHAC", "Phụ lục khác"),
    ]

    hop_dong = models.ForeignKey(HopDong, on_delete=models.PROTECT, related_name="phu_luc", verbose_name="Hợp đồng")
    loai_phu_luc = models.CharField(max_length=20, choices=LOAI_PHU_LUC_CHOICES, verbose_name="Loại phụ lục")
    so_phu_luc = models.CharField(max_length=50, blank=True, null=True, verbose_name="Số phụ lục")
    ngay_lap = models.DateField(default=timezone.now, verbose_name="Ngày lập")
    is_signed = models.BooleanField(default=False, verbose_name="Đã ký")
    ghi_chu = models.TextField(blank=True, null=True, verbose_name="Ghi chú")

    class Meta:
        ordering = ["-ngay_lap", "-id"]
        indexes = [models.Index(fields=["hop_dong", "loai_phu_luc"], name="idx_pl_hd_loai")]

    def __str__(self):
        return f"{self.hop_dong.so_hop_dong} - {self.get_loai_phu_luc_display()}"


class ChiTietPhuLucPhanCong(TimeStampedModel):
    """Snapshot phân công tại thời điểm tạo/ký phụ lục."""

    phu_luc = models.ForeignKey(PhuLucHopDong, on_delete=models.PROTECT, related_name="chi_tiet_phan_cong", verbose_name="Phụ lục")
    source_phan_cong = models.ForeignKey(PhanCongTre, on_delete=models.SET_NULL, null=True, blank=True, related_name="snapshot_phu_luc", verbose_name="Phân công nguồn")
    ma_tre = models.CharField(max_length=20, verbose_name="Mã trẻ")
    ten_tre = models.CharField(max_length=100, verbose_name="Tên trẻ")
    ma_can_bo = models.CharField(max_length=20, verbose_name="Mã CBCT")
    ten_can_bo = models.CharField(max_length=100, verbose_name="Tên CBCT")
    loai_dich_vu = models.CharField(max_length=10, choices=PhanCongTre.LOAI_DV_CHOICES, verbose_name="Loại dịch vụ")
    dot_phan_cong = models.PositiveIntegerField(default=1, verbose_name="Đợt phân công")
    ky_phan_cong = models.PositiveIntegerField(default=1, verbose_name="Kỳ phân công")
    ngay_phan_cong = models.DateField(null=True, blank=True, verbose_name="Ngày phân công")
    so_buoi_du_kien = models.PositiveIntegerField(default=0, verbose_name="Số buổi dự kiến")
    dinh_muc_di_lai = models.DecimalField(max_digits=12, decimal_places=0, default=Decimal("0"), verbose_name="Định mức đi lại")
    dia_diem_ct = models.CharField(max_length=255, blank=True, null=True, verbose_name="Địa điểm can thiệp")
    hinh_thuc_ct = models.CharField(max_length=100, blank=True, null=True, verbose_name="Hình thức can thiệp")
    ghi_chu = models.TextField(blank=True, null=True, verbose_name="Ghi chú")

    class Meta:
        indexes = [
            models.Index(fields=["phu_luc", "ky_phan_cong"], name="idx_ctpl_ky"),
            models.Index(fields=["ma_tre", "loai_dich_vu"], name="idx_ctpl_tre_dv"),
        ]


class NhatKyThucHien(TimeStampedModel):
    """Ghi nhận thực tế thực hiện, tách khỏi khối lượng hợp đồng và thanh toán."""

    hop_dong = models.ForeignKey(HopDong, on_delete=models.PROTECT, null=True, blank=True, related_name="nhat_ky_thuc_hien", verbose_name="Hợp đồng")
    phan_cong = models.ForeignKey(PhanCongTre, on_delete=models.PROTECT, related_name="nhat_ky_thuc_hien", verbose_name="Phân công")
    can_bo_nguon = models.ForeignKey(
        CanBo,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="nhat_ky_lich_su",
        verbose_name="CBCT theo dữ liệu nguồn",
    )
    nhom_hd_nguon = models.ForeignKey(
        NhomHD,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="nhat_ky_lich_su",
        verbose_name="Nhóm HĐ theo dữ liệu nguồn",
    )
    du_lieu_lich_su = models.BooleanField(default=False, verbose_name="Dữ liệu lịch sử")
    ngay_thuc_hien = models.DateField(verbose_name="Ngày thực hiện")
    gio_bat_dau = models.TimeField(null=True, blank=True, verbose_name="Giờ bắt đầu")
    gio_ket_thuc = models.TimeField(null=True, blank=True, verbose_name="Giờ kết thúc")
    dia_diem_ct = models.CharField(max_length=100, blank=True, null=True, verbose_name="Địa điểm can thiệp")
    ky_can_thiep = models.PositiveIntegerField(default=1, verbose_name="Kỳ can thiệp")
    lan_thanh_toan = models.PositiveIntegerField(default=1, verbose_name="Lần thanh toán")
    so_buoi_thuc_hien = models.PositiveIntegerField(default=1, verbose_name="Số buổi thực hiện")
    # Tên cũ được giữ lại và quy ước là lượt đi lại của phụ huynh.
    so_luot_di_lai = models.PositiveIntegerField(default=1, verbose_name="Số lượt đi lại PH")
    so_luot_di_lai_cbct = models.PositiveIntegerField(default=0, verbose_name="Số lượt đi lại CBCT")
    don_gia_cong = models.DecimalField(max_digits=12, decimal_places=0, verbose_name="Đơn giá công")
    dinh_muc_di_lai = models.DecimalField(max_digits=12, decimal_places=0, verbose_name="Định mức đi lại")
    thanh_tien = models.DecimalField(max_digits=18, decimal_places=0, default=Decimal("0"), verbose_name="Thành tiền")
    ghi_chu = models.TextField(blank=True, null=True, verbose_name="Ghi chú")

    class Meta:
        ordering = ["-ngay_thuc_hien", "-id"]
        indexes = [
            models.Index(fields=["hop_dong", "ngay_thuc_hien"], name="idx_nk_hd_ngay"),
            models.Index(fields=["phan_cong", "ngay_thuc_hien"], name="idx_nk_pc_ngay"),
        ]
        constraints = [
            models.CheckConstraint(condition=models.Q(so_buoi_thuc_hien__gt=0), name="ck_nk_so_buoi_gt0"),
            models.CheckConstraint(condition=models.Q(so_luot_di_lai__gte=0), name="ck_nk_di_lai_gte0"),
            models.CheckConstraint(condition=models.Q(so_luot_di_lai_cbct__gte=0), name="ck_nk_di_lai_cbct_gte0"),
        ]

    def clean(self):
        errors = {}
        hop_dong = self.hop_dong_hieu_luc
        if hop_dong and self.phan_cong_id:
            phan_cong = self.phan_cong
            if not self.du_lieu_lich_su and phan_cong.phan_bo_id != hop_dong.de_xuat.phan_bo_id:
                errors["phan_cong"] = "Phân công không thuộc phân bổ của hợp đồng."
            if not self.du_lieu_lich_su and hop_dong.tu_ngay and self.ngay_thuc_hien < hop_dong.tu_ngay:
                errors["ngay_thuc_hien"] = "Ngày thực hiện trước thời hạn hợp đồng."
            if not self.du_lieu_lich_su and hop_dong.den_ngay and self.ngay_thuc_hien > hop_dong.den_ngay:
                errors["ngay_thuc_hien"] = "Ngày thực hiện sau thời hạn hợp đồng."

            used = (
                type(self).objects.filter(phan_cong_id=self.phan_cong_id, du_lieu_lich_su=False)
                .exclude(pk=self.pk)
                .aggregate(total=models.Sum("so_buoi_thuc_hien"))["total"]
                or 0
            )
            if not self.du_lieu_lich_su and used + (self.so_buoi_thuc_hien or 0) > phan_cong.so_buoi_du_kien:
                errors["so_buoi_thuc_hien"] = (
                    "Tổng số buổi thực hiện của phân công không được vượt số buổi dự kiến."
                )
            if self.gio_bat_dau and self.gio_ket_thuc:
                if self.gio_ket_thuc <= self.gio_bat_dau:
                    errors["gio_ket_thuc"] = "Giờ kết thúc phải lớn hơn giờ bắt đầu."
                current = SimpleNamespace(
                    child_id=phan_cong.tre_id, cb_id=self.can_bo_hieu_luc_id,
                    service=phan_cong.loai_dich_vu, date=self.ngay_thuc_hien,
                    start=self.gio_bat_dau, end=self.gio_ket_thuc,
                )
                other_qs = type(self).objects.filter(ngay_thuc_hien=self.ngay_thuc_hien).exclude(pk=self.pk).select_related("can_bo_nguon", "phan_cong__phan_bo__can_bo")
                previous = [SimpleNamespace(child_id=x.phan_cong.tre_id, cb_id=x.can_bo_hieu_luc_id, service=x.phan_cong.loai_dich_vu, date=x.ngay_thuc_hien, start=x.gio_bat_dau, end=x.gio_ket_thuc) for x in other_qs]
                conflicts = journal_conflict_types(current, previous)
                if conflicts and not self.du_lieu_lich_su:
                    errors["gio_bat_dau"] = "Cảnh báo: " + ", ".join(conflicts) + ". Vui lòng kiểm tra lại lịch."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        if self.gio_bat_dau and self.gio_ket_thuc:
            current = SimpleNamespace(
                child_id=self.phan_cong.tre_id, cb_id=self.can_bo_hieu_luc_id,
                ace=self.phan_cong.tre.ace_ruot or "", service=self.phan_cong.loai_dich_vu,
                date=self.ngay_thuc_hien, start=self.gio_bat_dau, end=self.gio_ket_thuc,
                location=self.dia_diem_ct or self.phan_cong.dia_diem_ct or "", record_id=self.pk,
            )
            existing = type(self).objects.filter(ngay_thuc_hien=self.ngay_thuc_hien).exclude(pk=self.pk).select_related("can_bo_nguon", "phan_cong__tre", "phan_cong__phan_bo__can_bo")
            records = [SimpleNamespace(child_id=x.phan_cong.tre_id, cb_id=x.can_bo_hieu_luc_id, ace=x.phan_cong.tre.ace_ruot or "", service=x.phan_cong.loai_dich_vu, date=x.ngay_thuc_hien, start=x.gio_bat_dau, end=x.gio_ket_thuc, location=x.dia_diem_ct or x.phan_cong.dia_diem_ct or "", record_id=x.pk) for x in existing]
            travel = calculate_travel_flags(current, records)
            self.so_luot_di_lai_cbct = travel["so_luot_di_lai_cbct"]
            self.so_luot_di_lai = travel["so_luot_di_lai_ph"]
        self.thanh_tien = Decimal(self.so_buoi_thuc_hien) * Decimal(self.don_gia_cong) + Decimal(self.so_luot_di_lai_cbct) * Decimal(self.dinh_muc_di_lai)
        super().save(*args, **kwargs)

    @property
    def hop_dong_hieu_luc(self):
        if not self.hop_dong_id:
            return None
        try:
            return self.hop_dong
        except HopDong.DoesNotExist:
            return None

    @property
    def can_bo_hieu_luc(self):
        if self.can_bo_nguon_id:
            return self.can_bo_nguon
        hop_dong = self.hop_dong_hieu_luc
        if hop_dong:
            return hop_dong.can_bo
        return self.phan_cong.phan_bo.can_bo if self.phan_cong.phan_bo_id else None

    @property
    def can_bo_hieu_luc_id(self):
        can_bo = self.can_bo_hieu_luc
        return can_bo.pk if can_bo else None

    @property
    def nhom_hd_hieu_luc(self):
        """Ưu tiên nhóm trong file nguồn cho dữ liệu lịch sử."""
        if self.nhom_hd_nguon_id:
            return self.nhom_hd_nguon
        hop_dong = self.hop_dong_hieu_luc
        if hop_dong:
            return hop_dong.nhom_hd
        return self.phan_cong.nhom_hd or (self.phan_cong.phan_bo.nhom_hd if self.phan_cong.phan_bo_id else None)

    @property
    def so_hop_dong_hieu_luc(self):
        hop_dong = self.hop_dong_hieu_luc
        return hop_dong.so_hop_dong if hop_dong else "Chưa có HĐ"


class DotThanhToan(TimeStampedModel):
    hop_dong = models.ForeignKey(HopDong, on_delete=models.PROTECT, related_name="dot_thanh_toan", verbose_name="Hợp đồng")
    nam = models.PositiveIntegerField(verbose_name="Năm")
    thang = models.PositiveSmallIntegerField(verbose_name="Tháng")
    ngay_de_nghi = models.DateField(default=timezone.now, verbose_name="Ngày đề nghị")
    trang_thai = models.CharField(max_length=30, default="CHO_THANH_TOAN", verbose_name="Trạng thái")
    ghi_chu = models.TextField(blank=True, null=True, verbose_name="Ghi chú")

    class Meta:
        ordering = ["-nam", "-thang", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["hop_dong", "nam", "thang"], name="uq_dottt_hd_nam_thang"),
            models.CheckConstraint(condition=models.Q(thang__gte=1, thang__lte=12), name="ck_dottt_thang"),
        ]


class ChiTietThanhToan(TimeStampedModel):
    dot_thanh_toan = models.ForeignKey(DotThanhToan, on_delete=models.PROTECT, related_name="chi_tiet", verbose_name="Đợt thanh toán")
    nhat_ky = models.OneToOneField(NhatKyThucHien, on_delete=models.PROTECT, related_name="chi_tiet_thanh_toan", verbose_name="Nhật ký thực hiện")
    so_buoi_thanh_toan = models.PositiveIntegerField(default=0, verbose_name="Số buổi thanh toán")
    so_luot_di_lai = models.PositiveIntegerField(default=0, verbose_name="Số lượt đi lại thanh toán")
    thanh_tien = models.DecimalField(max_digits=18, decimal_places=0, default=Decimal("0"), verbose_name="Thành tiền")
    ghi_chu = models.TextField(blank=True, null=True, verbose_name="Ghi chú")

    def clean(self):
        errors = {}
        if self.dot_thanh_toan_id and self.nhat_ky_id:
            if self.dot_thanh_toan.hop_dong_id != self.nhat_ky.hop_dong_id:
                errors["nhat_ky"] = "Nhật ký không thuộc hợp đồng của đợt thanh toán."
            if (self.so_buoi_thanh_toan or 0) > self.nhat_ky.so_buoi_thuc_hien:
                errors["so_buoi_thanh_toan"] = "Số buổi thanh toán không được vượt số buổi thực hiện."
            if (self.so_luot_di_lai or 0) > self.nhat_ky.so_luot_di_lai_cbct:
                errors["so_luot_di_lai"] = "Số lượt đi lại thanh toán không được vượt số lượt thực tế."
        if self.so_buoi_thanh_toan is not None and self.so_buoi_thanh_toan <= 0:
            errors["so_buoi_thanh_toan"] = "Số buổi thanh toán phải lớn hơn 0."
        if errors:
            raise ValidationError(errors)

    @property
    def tien_cong(self):
        return Decimal(self.so_buoi_thanh_toan) * Decimal(self.nhat_ky.don_gia_cong)

    @property
    def tien_di_lai(self):
        return Decimal(self.so_luot_di_lai) * Decimal(self.nhat_ky.dinh_muc_di_lai)

    @property
    def thue_tncn(self):
        return calculate_payment_breakdown(self.tien_cong, self.tien_di_lai)["thue_tncn"]

    @property
    def thuc_linh(self):
        return calculate_payment_breakdown(self.tien_cong, self.tien_di_lai)["thuc_linh"]

    def save(self, *args, **kwargs):
        self.full_clean()
        self.thanh_tien = Decimal(self.so_buoi_thanh_toan) * Decimal(self.nhat_ky.don_gia_cong) + Decimal(self.so_luot_di_lai) * Decimal(self.nhat_ky.dinh_muc_di_lai)
        super().save(*args, **kwargs)


class DotThanhToanDiLaiPhuHuynh(TimeStampedModel):
    """Đợt thanh toán riêng cho khoản đi lại của phụ huynh."""
    hop_dong = models.ForeignKey(HopDong, on_delete=models.PROTECT, related_name="dot_thanh_toan_phu_huynh", verbose_name="Hợp đồng")
    nam = models.PositiveIntegerField(verbose_name="Năm")
    thang = models.PositiveSmallIntegerField(verbose_name="Tháng")
    ngay_de_nghi = models.DateField(default=timezone.now, verbose_name="Ngày đề nghị")
    trang_thai = models.CharField(max_length=30, default="CHO_THANH_TOAN", verbose_name="Trạng thái")
    ghi_chu = models.TextField(blank=True, null=True, verbose_name="Ghi chú")

    class Meta:
        ordering = ["-nam", "-thang", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["hop_dong", "nam", "thang"], name="uq_dottt_phuhuynh_hd_nam_thang"),
            models.CheckConstraint(condition=models.Q(thang__gte=1, thang__lte=12), name="ck_dottt_phuhuynh_thang"),
        ]


class ChiTietThanhToanDiLaiPhuHuynh(TimeStampedModel):
    dot_thanh_toan = models.ForeignKey(DotThanhToanDiLaiPhuHuynh, on_delete=models.PROTECT, related_name="chi_tiet", verbose_name="Đợt thanh toán")
    nhat_ky = models.ForeignKey(NhatKyThucHien, on_delete=models.PROTECT, related_name="chi_tiet_di_lai_phu_huynh", verbose_name="Nhật ký thực hiện")
    so_luot_di_lai = models.PositiveIntegerField(default=0, verbose_name="Số lượt đi lại thanh toán")
    dinh_muc_di_lai = models.DecimalField(max_digits=12, decimal_places=0, default=Decimal("0"), verbose_name="Định mức đi lại")
    thanh_tien = models.DecimalField(max_digits=18, decimal_places=0, default=Decimal("0"), verbose_name="Thành tiền")
    ghi_chu = models.TextField(blank=True, null=True, verbose_name="Ghi chú")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["dot_thanh_toan", "nhat_ky"], name="uq_cttt_phuhuynh_dot_nhatky"),
            models.CheckConstraint(condition=models.Q(so_luot_di_lai__gte=0), name="ck_cttt_phuhuynh_luot_gte0"),
        ]

    def clean(self):
        errors = {}
        if self.dot_thanh_toan_id and self.nhat_ky_id:
            if self.dot_thanh_toan.hop_dong_id != self.nhat_ky.hop_dong_id:
                errors["nhat_ky"] = "Nhật ký không thuộc hợp đồng của đợt thanh toán phụ huynh."
            if (self.so_luot_di_lai or 0) > self.nhat_ky.so_luot_di_lai:
                errors["so_luot_di_lai"] = "Số lượt thanh toán không được vượt số lượt thực tế."
        if self.so_luot_di_lai <= 0:
            errors["so_luot_di_lai"] = "Số lượt đi lại phải lớn hơn 0."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        self.thanh_tien = Decimal(self.so_luot_di_lai) * Decimal(self.dinh_muc_di_lai)
        super().save(*args, **kwargs)

    @property
    def nguoi_nhan(self):
        return self.nhat_ky.phan_cong.tre.ten_phu_huynh or ""

    @property
    def ten_tai_khoan(self):
        return self.nhat_ky.phan_cong.tre.ten_tai_khoan or ""

    @property
    def tai_khoan(self):
        return self.nhat_ky.phan_cong.tre.tai_khoan or ""

    @property
    def ngan_hang(self):
        return self.nhat_ky.phan_cong.tre.ngan_hang or ""

    @property
    def chi_nhanh(self):
        return self.nhat_ky.phan_cong.tre.chi_nhanh or ""


class NghiemThu(TimeStampedModel):
    hop_dong = models.OneToOneField(HopDong, on_delete=models.PROTECT, related_name="nghiem_thu", verbose_name="Hợp đồng")
    ngay_nghiem_thu = models.DateField(null=True, blank=True, verbose_name="Ngày nghiệm thu")
    ket_qua = models.CharField(max_length=30, default="DAT", verbose_name="Kết quả")
    gia_tri_nghiem_thu = models.DecimalField(max_digits=18, decimal_places=0, default=Decimal("0"), verbose_name="Giá trị nghiệm thu")
    bien_ban_so = models.CharField(max_length=50, blank=True, null=True, verbose_name="Số biên bản")
    ghi_chu = models.TextField(blank=True, null=True, verbose_name="Ghi chú")


class ThanhLyHopDong(TimeStampedModel):
    hop_dong = models.OneToOneField(HopDong, on_delete=models.PROTECT, related_name="thanh_ly", verbose_name="Hợp đồng")
    ngay_thanh_ly = models.DateField(null=True, blank=True, verbose_name="Ngày thanh lý")
    gia_tri_thanh_ly = models.DecimalField(max_digits=18, decimal_places=0, default=Decimal("0"), verbose_name="Giá trị thanh lý")
    bien_ban_so = models.CharField(max_length=50, blank=True, null=True, verbose_name="Số biên bản")
    ghi_chu = models.TextField(blank=True, null=True, verbose_name="Ghi chú")
