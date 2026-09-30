from decimal import Decimal

from django import forms
from django.db.models import Q
from django.utils import timezone

from .financial import FinancialConfig
from .models import (
    CanBo,
    ChiTietKhoiLuongHopDong,
    DeXuatHopDong,
    DonVi,
    HopDong,
    NhomHD,
    DotThanhToan,
    PhanBoChiTieu,
    PhanCongTre,
    PhuLucHopDong,
    NghiemThu,
    ThanhLyHopDong,
    DotThanhToanDiLaiPhuHuynh,
    ChiTietThanhToanDiLaiPhuHuynh,
    NhatKyThucHien,
    ChiTietThanhToan,
    Tre,
)


class BootstrapModelForm(forms.ModelForm):
    """Áp dụng class Bootstrap thống nhất cho các form quản trị."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, (forms.Select, forms.SelectMultiple)):
                css_class = "form-select"
            else:
                css_class = "form-control"
            existing = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = f"{existing} {css_class}".strip()


class DonViForm(BootstrapModelForm):
    class Meta:
        model = DonVi
        fields = ["ma_don_vi", "ten_don_vi", "nguoi_dai_dien", "mstdv", "dia_chi", "dien_thoai", "email", "is_active"]


class TreForm(BootstrapModelForm):
    class Meta:
        model = Tre
        fields = [
            "ma_tre", "ho_ten", "ngay_sinh", "gioi_tinh", "tinh", "xa", "ma_tinh",
              "ten_phu_huynh", "dien_thoai", "ten_tai_khoan", "tai_khoan", "ngan_hang",
              "chi_nhanh", "ace_ruot", "ghi_chu", "is_active",
        ]
        widgets = {
            "ngay_sinh": forms.DateInput(attrs={"type": "date"}),
            "tinh": forms.Select(attrs={"id": "select-tinh"}),
            "xa": forms.Select(attrs={"id": "id_xa"}),
            "ghi_chu": forms.Textarea(attrs={"rows": 3}),
        }


class CanBoForm(BootstrapModelForm):
    class Meta:
        model = CanBo
        fields = [
            "ma_can_bo", "ho_ten", "gioi_tinh", "tinh", "xa", "dia_chi", "dien_thoai",
            "email", "cccd", "mst", "ngay_cap", "noi_cap", "tai_khoan", "ngan_hang",
            "chi_nhanh", "don_vi", "is_active",
        ]
        widgets = {"ngay_cap": forms.DateInput(attrs={"type": "date"})}


class NhomHDForm(BootstrapModelForm):
    class Meta:
        model = NhomHD
        fields = ["ma_nhom_hd", "ten_nhom_hd", "is_active"]


class PhanBoChiTieuForm(BootstrapModelForm):
    dinh_muc_di_lai_phcn = forms.ChoiceField(
        choices=[
            (str(FinancialConfig.DON_GIA_DI_LAI_DM1), f"Định mức 1 - {FinancialConfig.DON_GIA_DI_LAI_DM1:,.0f} đ"),
            (str(FinancialConfig.DON_GIA_DI_LAI_DM2), f"Định mức 2 - {FinancialConfig.DON_GIA_DI_LAI_DM2:,.0f} đ"),
        ],
        initial=str(FinancialConfig.DON_GIA_DI_LAI_DM1),
        label="Định mức đi lại PHCN",
    )
    dinh_muc_di_lai_cs = forms.ChoiceField(
        choices=[
            (str(FinancialConfig.DON_GIA_DI_LAI_DM1), f"Định mức 1 - {FinancialConfig.DON_GIA_DI_LAI_DM1:,.0f} đ"),
            (str(FinancialConfig.DON_GIA_DI_LAI_DM2), f"Định mức 2 - {FinancialConfig.DON_GIA_DI_LAI_DM2:,.0f} đ"),
        ],
        initial=str(FinancialConfig.DON_GIA_DI_LAI_DM1),
        label="Định mức đi lại CSXH",
    )

    class Meta:
        model = PhanBoChiTieu
        fields = [
            "can_bo", "cbda_quan_ly", "nhom_hd", "tham_gia_ct", "ngay_lap", "so_tre_phcn", "so_buoi_phcn",
            "dinh_muc_di_lai_phcn", "so_tre_cs", "so_buoi_cs", "dinh_muc_di_lai_cs", "ghi_chu",
        ]
        widgets = {
            "can_bo": forms.Select(attrs={"class": "form-select select2-search"}),
            "ngay_lap": forms.DateInput(attrs={"type": "date"}),
            "so_tre_phcn": forms.NumberInput(attrs={"min": "0"}),
            "so_buoi_phcn": forms.NumberInput(attrs={"min": "0"}),
            "so_tre_cs": forms.NumberInput(attrs={"min": "0"}),
            "so_buoi_cs": forms.NumberInput(attrs={"min": "0"}),
            "ghi_chu": forms.Textarea(attrs={"rows": 3}),
        }

    def clean(self):
        cleaned_data = super().clean()
        if (cleaned_data.get("so_tre_phcn") or 0) > 0 and (cleaned_data.get("so_buoi_phcn") or 0) <= 0:
            self.add_error("so_buoi_phcn", "Số buổi PHCN phải lớn hơn 0 khi có trẻ PHCN.")
        if (cleaned_data.get("so_tre_cs") or 0) > 0 and (cleaned_data.get("so_buoi_cs") or 0) <= 0:
            self.add_error("so_buoi_cs", "Số buổi CSXH phải lớn hơn 0 khi có trẻ CSXH.")
        return cleaned_data


class PhanCongTreForm(BootstrapModelForm):
    LOCATION_CHOICES = [("Trường", "Trường"), ("Nhà", "Nhà"), ("Khác", "Khác")]
    FORM_CHOICES = [("Cá nhân", "Cá nhân"), ("Chuyên gia", "Chuyên gia"), ("Đơn vị", "Đơn vị")]

    class Meta:
        model = PhanCongTre
        fields = [
            "phan_bo", "can_bo_nguon", "nhom_hd", "cbda_quan_ly", "tre", "loai_dich_vu", "so_buoi_du_kien", "dinh_muc_di_lai", "dia_diem_ct",
            "hinh_thuc_ct", "dot_phan_cong", "ky_phan_cong", "ngay_phan_cong", "trang_thai", "ghi_chu",
        ]
        widgets = {
            "phan_bo": forms.Select(attrs={"class": "form-select select2-search"}),
            "can_bo_nguon": forms.Select(attrs={"class": "form-select select2-search"}),
            "tre": forms.Select(attrs={"class": "form-select select2-search"}),
            "so_buoi_du_kien": forms.NumberInput(attrs={"min": "0"}),
            "dinh_muc_di_lai": forms.NumberInput(attrs={"min": "0", "step": "1"}),
            "dot_phan_cong": forms.NumberInput(attrs={"min": "1"}),
            "ky_phan_cong": forms.NumberInput(attrs={"min": "1"}),
            "ngay_phan_cong": forms.DateInput(attrs={"type": "date"}),
            "dia_diem_ct": forms.Select(choices=[("Trường", "Trường"), ("Nhà", "Nhà"), ("Khác", "Khác")], attrs={"class": "form-select select2-search"}),
            "hinh_thuc_ct": forms.Select(choices=[("Cá nhân", "Cá nhân"), ("Chuyên gia", "Chuyên gia"), ("Đơn vị", "Đơn vị")], attrs={"class": "form-select select2-search"}),
            "ghi_chu": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        self.allow_locked = kwargs.pop("allow_locked", False)
        super().__init__(*args, **kwargs)

        phan_bo = self.initial.get("phan_bo")
        if not phan_bo and self.instance and self.instance.pk:
            phan_bo = self.instance.phan_bo

        if phan_bo and not self.instance.pk and not self.initial.get("dinh_muc_di_lai"):
            self.initial["dinh_muc_di_lai"] = phan_bo.dinh_muc_di_lai_phcn

    def clean(self):
        cleaned_data = super().clean()
        phan_bo = cleaned_data.get("phan_bo")
        tre = cleaned_data.get("tre")
        loai_dich_vu = cleaned_data.get("loai_dich_vu")
        dinh_muc_di_lai = cleaned_data.get("dinh_muc_di_lai")

        if phan_bo and phan_bo.is_locked and not self.instance.pk and not self.allow_locked:
            raise forms.ValidationError("Phân bổ đã khóa, không thể thêm phân công mới.")
        if (cleaned_data.get("so_buoi_du_kien") or 0) <= 0:
            self.add_error("so_buoi_du_kien", "Số buổi dự kiến phải lớn hơn 0.")
        if tre and not tre.is_active:
            self.add_error("tre", "Trẻ đang ở trạng thái ngừng sử dụng.")
        if phan_bo and phan_bo.can_bo and not phan_bo.can_bo.is_active:
            self.add_error("phan_bo", "Cán bộ can thiệp của phân bổ đang ở trạng thái ngừng hoạt động.")
        is_cs = PhanCongTre.service_group(loai_dich_vu) == "CS"
        if phan_bo and is_cs and phan_bo.so_tre_cs <= 0:
            self.add_error("loai_dich_vu", "Phân bổ không có chỉ tiêu CS.")
        if phan_bo and not is_cs and phan_bo.so_tre_phcn <= 0:
            self.add_error("loai_dich_vu", "Phân bổ không có chỉ tiêu PHCN.")

        if phan_bo and (dinh_muc_di_lai is None or dinh_muc_di_lai <= 0):
            cleaned_data["dinh_muc_di_lai"] = (
                phan_bo.dinh_muc_di_lai_cs
                if is_cs
                else phan_bo.dinh_muc_di_lai_phcn
            )

        return cleaned_data


class DieuChuyenPhanCongForm(forms.Form):
    phan_bo = forms.ModelChoiceField(queryset=PhanBoChiTieu.objects.select_related("can_bo", "nhom_hd"), label="Phân bổ đích")
    ly_do = forms.CharField(required=False, label="Lý do điều chuyển", widget=forms.Textarea(attrs={"rows": 3}))


class DeXuatHopDongForm(BootstrapModelForm):
    class Meta:
        model = DeXuatHopDong
        fields = [
            "phan_bo", "lan_de_xuat", "ngay_de_xuat", "so_tre_phcn", "so_buoi_phcn", "so_tre_cs",
            "so_buoi_cs", "gia_tri_du_kien", "trang_thai", "ly_do",
        ]
        widgets = {
            "ngay_de_xuat": forms.DateInput(attrs={"type": "date"}),
            "lan_de_xuat": forms.NumberInput(attrs={"min": "1"}),
            "so_tre_phcn": forms.NumberInput(attrs={"min": "0"}),
            "so_buoi_phcn": forms.NumberInput(attrs={"min": "0"}),
            "so_tre_cs": forms.NumberInput(attrs={"min": "0"}),
            "so_buoi_cs": forms.NumberInput(attrs={"min": "0"}),
            "gia_tri_du_kien": forms.NumberInput(attrs={"min": "0", "step": "1"}),
            "ly_do": forms.Textarea(attrs={"rows": 3}),
        }


class HopDongForm(BootstrapModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        hidden_states = {"HET_HAN", "NGHIEM_THU", "THANH_LY"}
        self.fields["trang_thai"].choices = [
            choice for choice in self.fields["trang_thai"].choices if choice[0] not in hidden_states
        ]

    class Meta:
        model = HopDong
        fields = [
            "so_hop_dong", "ngay_ky", "tu_ngay", "den_ngay",
            "don_gia_cong", "dinh_muc_di_lai_phcn", "dinh_muc_di_lai_cs", "gia_tri_hop_dong", "trang_thai", "ghi_chu",
        ]
        widgets = {
            "ngay_ky": forms.DateInput(attrs={"type": "date"}),
            "tu_ngay": forms.DateInput(attrs={"type": "date"}),
            "den_ngay": forms.DateInput(attrs={"type": "date"}),
            "don_gia_cong": forms.NumberInput(attrs={"min": "0", "step": "1"}),
            "dinh_muc_di_lai_phcn": forms.NumberInput(attrs={"min": "0", "step": "1"}),
            "dinh_muc_di_lai_cs": forms.NumberInput(attrs={"min": "0", "step": "1"}),
            "gia_tri_hop_dong": forms.NumberInput(attrs={"min": "0", "step": "1"}),
            "ghi_chu": forms.Textarea(attrs={"rows": 3}),
        }

    def clean(self):
        cleaned_data = super().clean()
        ngay_ky = cleaned_data.get("ngay_ky")
        tu_ngay = cleaned_data.get("tu_ngay")
        den_ngay = cleaned_data.get("den_ngay")
        if ngay_ky and tu_ngay and ngay_ky < tu_ngay:
            self.add_error("ngay_ky", "Ngày ký không được trước ngày bắt đầu hợp đồng.")
        if tu_ngay and den_ngay and den_ngay < tu_ngay:
            self.add_error("den_ngay", "Ngày kết thúc không được trước ngày bắt đầu.")
        return cleaned_data


class ChiTietKhoiLuongHopDongForm(BootstrapModelForm):
    class Meta:
        model = ChiTietKhoiLuongHopDong
        fields = ["loai_dich_vu", "so_tre", "so_buoi", "don_gia_cong", "dinh_muc_di_lai"]
        widgets = {
            "so_tre": forms.NumberInput(attrs={"min": "0"}),
            "so_buoi": forms.NumberInput(attrs={"min": "0"}),
            "don_gia_cong": forms.NumberInput(attrs={"min": "0", "step": "1"}),
            "dinh_muc_di_lai": forms.NumberInput(attrs={"min": "0", "step": "1"}),
        }


class PhuLucHopDongForm(BootstrapModelForm):
    class Meta:
        model = PhuLucHopDong
        fields = ["loai_phu_luc", "so_phu_luc", "ngay_lap", "is_signed", "ghi_chu"]
        widgets = {
            "ngay_lap": forms.DateInput(attrs={"type": "date"}),
            "ghi_chu": forms.Textarea(attrs={"rows": 3}),
        }


class NhatKyThucHienForm(BootstrapModelForm):
    class Meta:
        model = NhatKyThucHien
        fields = ["phan_cong", "ngay_thuc_hien", "gio_bat_dau", "gio_ket_thuc", "dia_diem_ct", "ky_can_thiep", "so_buoi_thuc_hien", "ghi_chu"]
        widgets = {
              "ngay_thuc_hien": forms.DateInput(attrs={"type": "date"}),
              "gio_bat_dau": forms.TimeInput(attrs={"type": "time"}),
              "gio_ket_thuc": forms.TimeInput(attrs={"type": "time"}),
            "ky_can_thiep": forms.NumberInput(attrs={"min": "1", "max": "30"}),
            "so_buoi_thuc_hien": forms.NumberInput(attrs={"min": "1"}),
            "ghi_chu": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, hop_dong=None, **kwargs):
        super().__init__(*args, **kwargs)
        if hop_dong is not None:
            assignments = PhanCongTre.objects.none()
            if hop_dong.de_xuat_id:
                assignments = PhanCongTre.objects.filter(
                    phan_bo_id=hop_dong.de_xuat.phan_bo_id
                )
            elif hop_dong.don_vi_id:
                assignments = PhanCongTre.objects.filter(
                    Q(nhom_hd_id=hop_dong.nhom_hd_id)
                    | Q(phan_bo__nhom_hd_id=hop_dong.nhom_hd_id)
                )
            self.fields["phan_cong"].queryset = assignments.select_related("tre")
            self.fields["phan_cong"].help_text = (
                "Hình thức hồ sơ đi lại lấy từ phân công: Chuyên gia → CG; "
                "ghi chú trẻ có CBDA → CBDA; còn lại → NCS."
            )


class NhatKyCanThiepForm(BootstrapModelForm):
    hop_dong = forms.ModelChoiceField(
        queryset=HopDong.objects.select_related("can_bo", "don_vi", "nhom_hd"),
        label="Hợp đồng",
        required=False,
        widget=forms.Select(attrs={"class": "form-select select2-search"}),
    )

    class Meta:
        model = NhatKyThucHien
        fields = ["hop_dong", "phan_cong", "ngay_thuc_hien", "gio_bat_dau", "gio_ket_thuc", "dia_diem_ct", "ky_can_thiep", "so_buoi_thuc_hien", "ghi_chu"]
        widgets = {
            "phan_cong": forms.Select(attrs={"class": "form-select select2-search"}),
              "ngay_thuc_hien": forms.DateInput(attrs={"type": "date"}),
              "gio_bat_dau": forms.TimeInput(attrs={"type": "time"}),
              "gio_ket_thuc": forms.TimeInput(attrs={"type": "time"}),
            "ky_can_thiep": forms.NumberInput(attrs={"min": "1", "max": "30"}),
            "so_buoi_thuc_hien": forms.NumberInput(attrs={"min": "1"}),
            "ghi_chu": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, require_contract=True, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["hop_dong"].required = require_contract
        self.fields["phan_cong"].help_text = (
            "Hình thức hồ sơ đi lại lấy từ phân công: Chuyên gia → CG; "
            "ghi chú trẻ có CBDA → CBDA; còn lại → NCS."
        )

    def clean(self):
        cleaned = super().clean()
        hop_dong = cleaned.get("hop_dong")
        phan_cong = cleaned.get("phan_cong")
        ngay = cleaned.get("ngay_thuc_hien")
        if hop_dong and phan_cong:
            if hop_dong.de_xuat_id and phan_cong.phan_bo_id != hop_dong.de_xuat.phan_bo_id:
                self.add_error("phan_cong", "Phân công không thuộc phân bổ của hợp đồng đã chọn.")
            elif hop_dong.don_vi_id:
                assignment_group_id = phan_cong.nhom_hd_id or (
                    phan_cong.phan_bo.nhom_hd_id if phan_cong.phan_bo_id else None
                )
                if assignment_group_id != hop_dong.nhom_hd_id:
                    self.add_error("phan_cong", "Phân công không thuộc Nhóm HĐ của hợp đồng đơn vị.")
        if hop_dong and ngay and not (hop_dong.tu_ngay <= ngay <= hop_dong.den_ngay):
            self.add_error("ngay_thuc_hien", "Ngày thực hiện phải nằm trong thời hạn hợp đồng.")
        return cleaned


class NhatKyGhiChuForm(forms.Form):
    """Chỉ ghi chú của nhật ký đã lập phiếu, không kiểm tra lại số liệu lịch sử."""

    ghi_chu = forms.CharField(
        label="Ghi chú", required=False,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}),
    )


class DotThanhToanForm(BootstrapModelForm):
    class Meta:
        model = DotThanhToan
        fields = ["nam", "thang", "ngay_de_nghi", "ghi_chu"]
        widgets = {
            "nam": forms.NumberInput(attrs={"min": "2000"}),
            "thang": forms.NumberInput(attrs={"min": "1", "max": "12"}),
            "ngay_de_nghi": forms.DateInput(attrs={"type": "date"}),
            "ghi_chu": forms.Textarea(attrs={"rows": 3}),
        }


class ChiTietThanhToanForm(BootstrapModelForm):
    class Meta:
        model = ChiTietThanhToan
        fields = ["nhat_ky", "so_buoi_thanh_toan", "so_luot_di_lai", "ghi_chu"]
        widgets = {
            "so_buoi_thanh_toan": forms.NumberInput(attrs={"min": "1"}),
            "so_luot_di_lai": forms.NumberInput(attrs={"min": "0"}),
            "ghi_chu": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, hop_dong=None, **kwargs):
        super().__init__(*args, **kwargs)
        if hop_dong is not None:
            self.fields["nhat_ky"].queryset = NhatKyThucHien.objects.filter(
                hop_dong=hop_dong
            ).select_related("phan_cong__tre")


class NghiemThuForm(BootstrapModelForm):
    def __init__(self, *args, hop_dong=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.hop_dong = hop_dong or getattr(self.instance, "hop_dong", None)

    class Meta:
        model = NghiemThu
        fields = ["ngay_nghiem_thu", "ket_qua", "gia_tri_nghiem_thu", "bien_ban_so", "ghi_chu"]
        widgets = {
            "ngay_nghiem_thu": forms.DateInput(attrs={"type": "date"}),
            "gia_tri_nghiem_thu": forms.NumberInput(attrs={"min": "0", "step": "1"}),
            "ghi_chu": forms.Textarea(attrs={"rows": 3}),
        }

    def clean_gia_tri_nghiem_thu(self):
        value = self.cleaned_data.get("gia_tri_nghiem_thu")
        if value is None:
            raise forms.ValidationError("Cần nhập/xác nhận giá trị nghiệm thu.")
        if value < 0:
            raise forms.ValidationError("Giá trị nghiệm thu không được âm.")
        if self.hop_dong and value > self.hop_dong.gia_tri_hop_dong:
            raise forms.ValidationError("Giá trị nghiệm thu không được vượt giá trị hợp đồng.")
        return value


class ThanhLyHopDongForm(BootstrapModelForm):
    class Meta:
        model = ThanhLyHopDong
        fields = ["ngay_thanh_ly", "bien_ban_so", "ghi_chu"]
        widgets = {
            "ngay_thanh_ly": forms.DateInput(attrs={"type": "date"}),
            "ghi_chu": forms.Textarea(attrs={"rows": 3}),
        }


class DotThanhToanDiLaiPhuHuynhForm(BootstrapModelForm):
    class Meta:
        model = DotThanhToanDiLaiPhuHuynh
        fields = ["nam", "thang", "tu_ngay", "den_ngay", "ngay_de_nghi", "ghi_chu"]
        widgets = {
            "tu_ngay": forms.DateInput(attrs={"type": "date"}),
            "den_ngay": forms.DateInput(attrs={"type": "date"}),
            "ngay_de_nghi": forms.DateInput(attrs={"type": "date"}),
            "ghi_chu": forms.Textarea(attrs={"rows": 3}),
        }


def _current_contract_end(hop_dong, exclude_id=None):
    if not hop_dong:
        return None
    query = hop_dong.phu_luc.filter(
            loai_phu_luc="GIA_HAN_THOI_GIAN",
            den_ngay_moi__isnull=False,
        )
    if exclude_id:
        query = query.exclude(pk=exclude_id)
    return (
        query
        .order_by("-ngay_lap", "-id")
        .values_list("den_ngay_moi", flat=True)
        .first()
        or hop_dong.den_ngay
    )


class GiaHanThoiGianForm(BootstrapModelForm):
    hop_dong = forms.ModelChoiceField(
        queryset=HopDong.objects.filter(can_bo__isnull=False).select_related("can_bo", "nhom_hd"),
        label="Hợp đồng",
        widget=forms.Select(attrs={"class": "form-select select2-search"}),
    )
    den_ngay_cu = forms.DateField(
        label="Ngày kết thúc cũ",
        required=False,
        disabled=True,
        widget=forms.DateInput(attrs={"type": "date", "readonly": True}),
    )
    den_ngay_moi = forms.DateField(
        label="Ngày kết thúc mới",
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    ngay_lap = forms.DateField(
        label="Ngày lập",
        initial=timezone.localdate,
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    is_signed = forms.TypedChoiceField(
        label="Đã ký",
        choices=(("0", "Chưa ký"), ("1", "Đã ký")),
        coerce=lambda value: str(value) == "1",
        initial="0",
        widget=forms.Select,
    )
    ghi_chu = forms.CharField(label="Ghi chú", required=False, widget=forms.Textarea(attrs={"rows": 3}))

    class Meta:
        model = PhuLucHopDong
        fields = ["hop_dong", "den_ngay_cu", "den_ngay_moi", "ngay_lap", "is_signed", "ghi_chu"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.contract_end_dates = {}
        for contract in self.fields["hop_dong"].queryset:
            current_end = _current_contract_end(contract, self.instance.pk)
            self.contract_end_dates[str(contract.pk)] = current_end.isoformat() if current_end else ""
        selected = self.initial.get("hop_dong") or (self.instance.hop_dong if self.instance.pk else None)
        if selected:
            self.initial["den_ngay_cu"] = _current_contract_end(selected, self.instance.pk)

    def clean(self):
        cleaned = super().clean()
        hop_dong = cleaned.get("hop_dong")
        den_ngay_moi = cleaned.get("den_ngay_moi")
        latest_end = _current_contract_end(hop_dong, self.instance.pk)
        if latest_end:
            cleaned["den_ngay_cu"] = latest_end
        if hop_dong and den_ngay_moi and latest_end:
            if self.instance.pk and den_ngay_moi < latest_end:
                self.add_error("den_ngay_moi", "Ngày kết thúc mới không được trước thời hạn hiện hành.")
            elif not self.instance.pk and den_ngay_moi <= latest_end:
                self.add_error("den_ngay_moi", "Ngày kết thúc mới phải sau ngày kết thúc hiện tại của hợp đồng.")
        return cleaned


class GiaHanKhoiLuongForm(BootstrapModelForm):
    hop_dong = forms.ModelChoiceField(
        queryset=HopDong.objects.filter(can_bo__isnull=False).select_related("can_bo", "nhom_hd"),
        label="Hợp đồng",
        widget=forms.Select(attrs={"class": "form-select select2-search"}),
    )
    den_ngay_cu = forms.DateField(
        label="Ngày kết thúc cũ",
        required=False,
        disabled=True,
        widget=forms.DateInput(attrs={"type": "date", "readonly": True}),
    )
    den_ngay_moi = forms.DateField(
        label="Ngày kết thúc mới",
        required=True,
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    ngay_lap = forms.DateField(
        label="Ngày lập",
        initial=timezone.localdate,
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    so_tre_phcn_moi = forms.IntegerField(label="Số trẻ PHCN sau điều chỉnh", min_value=0)
    so_buoi_phcn_moi = forms.IntegerField(label="Số buổi PHCN sau điều chỉnh", min_value=0)
    so_tre_cs_moi = forms.IntegerField(label="Số trẻ CSXH sau điều chỉnh", min_value=0)
    so_buoi_cs_moi = forms.IntegerField(label="Số buổi CSXH sau điều chỉnh", min_value=0)
    is_signed = forms.TypedChoiceField(
        label="Đã ký",
        choices=(("0", "Chưa ký"), ("1", "Đã ký")),
        coerce=lambda value: str(value) == "1",
        initial="0",
        widget=forms.Select,
    )
    thanh_tien_phcn = forms.CharField(label="Thành tiền PHCN", required=False, disabled=True, widget=forms.TextInput(attrs={"readonly": True}))
    thanh_tien_cs = forms.CharField(label="Thành tiền CSXH", required=False, disabled=True, widget=forms.TextInput(attrs={"readonly": True}))
    gia_tri_tang_them = forms.CharField(label="Giá trị hợp đồng tăng thêm", required=False, disabled=True, widget=forms.TextInput(attrs={"readonly": True}))
    tong_gia_tri_moi = forms.CharField(label="Tổng giá trị hợp đồng sau khi tăng", required=False, disabled=True, widget=forms.TextInput(attrs={"readonly": True}))
    ghi_chu = forms.CharField(label="Ghi chú", required=False, widget=forms.Textarea(attrs={"rows": 3}))

    class Meta:
        model = PhuLucHopDong
        fields = [
            "hop_dong", "den_ngay_cu", "den_ngay_moi", "so_tre_phcn_moi", "so_buoi_phcn_moi", "thanh_tien_phcn",
            "so_tre_cs_moi", "so_buoi_cs_moi", "thanh_tien_cs", "gia_tri_tang_them", "tong_gia_tri_moi",
            "ngay_lap", "is_signed", "ghi_chu",
        ]

    @staticmethod
    def baseline(hop_dong, exclude_id=None):
        query = hop_dong.phu_luc.filter(loai_phu_luc="GIA_HAN_KHOI_LUONG")
        if exclude_id:
            query = query.exclude(pk=exclude_id)
        latest = (
            query
            .prefetch_related("chi_tiet_gia_han_khoi_luong")
            .order_by("-ngay_lap", "-id")
            .first()
        )
        if latest:
            values = {"phcn": (0, 0), "cs": (0, 0)}
            for item in latest.chi_tiet_gia_han_khoi_luong.all():
                group = "cs" if PhanCongTre.service_group(item.loai_dich_vu) == "CS" else "phcn"
                values[group] = (item.so_tre_moi, item.so_buoi_moi)
            return values
        if hop_dong.de_xuat_id:
            allocation = hop_dong.de_xuat.phan_bo
            return {
                "phcn": (allocation.so_tre_phcn, allocation.so_buoi_phcn),
                "cs": (allocation.so_tre_cs, allocation.so_buoi_cs),
            }
        values = {"phcn": (0, 0), "cs": (0, 0)}
        for item in hop_dong.chi_tiet_khoi_luong.all():
            group = "CS" if PhanCongTre.service_group(item.loai_dich_vu) == "CS" else "PHCN"
            values[group.lower()] = (item.so_tre, item.so_buoi)
        return values

    def set_contract_initial(self, hop_dong):
        if not hop_dong:
            return
        baseline = self.baseline(hop_dong, self.instance.pk)
        current_end = _current_contract_end(hop_dong, self.instance.pk)
        self.initial.setdefault("den_ngay_cu", current_end)
        self.initial.setdefault("den_ngay_moi", self.instance.den_ngay_moi if self.instance.pk else current_end)
        self.initial.setdefault("so_tre_phcn_moi", baseline["phcn"][0])
        self.initial.setdefault("so_buoi_phcn_moi", baseline["phcn"][1])
        self.initial.setdefault("so_tre_cs_moi", baseline["cs"][0])
        self.initial.setdefault("so_buoi_cs_moi", baseline["cs"][1])
        self.set_amount_initials(hop_dong)

    def calculate_amounts(self, hop_dong, values=None, exclude_id=None):
        baseline = self.baseline(hop_dong, exclude_id)
        values = values or {
            "phcn": (baseline["phcn"][0], baseline["phcn"][1]),
            "cs": (baseline["cs"][0], baseline["cs"][1]),
        }
        rates = {
            "phcn": Decimal(hop_dong.don_gia_cong or 0) + Decimal(hop_dong.dinh_muc_di_lai_phcn or 0),
            "cs": Decimal(hop_dong.don_gia_cong or 0) + Decimal(hop_dong.dinh_muc_di_lai_cs or 0),
        }
        service_totals = {}
        increases = {}
        for group in ("phcn", "cs"):
            old_count, _old_sessions = baseline[group]
            new_count, new_sessions = values[group]
            service_totals[group] = Decimal(new_count or 0) * Decimal(new_sessions or 0) * rates[group]
            increases[group] = max(Decimal(new_count or 0) - Decimal(old_count or 0), Decimal("0")) * Decimal(new_sessions or 0) * rates[group]
        latest_volume_query = hop_dong.phu_luc.filter(loai_phu_luc="GIA_HAN_KHOI_LUONG")
        if exclude_id:
            latest_volume_query = latest_volume_query.exclude(pk=exclude_id)
        latest_volume = latest_volume_query.order_by("-ngay_lap", "-id").first()
        if latest_volume:
            old_total = Decimal(latest_volume.tong_tien_moi)
        elif self.instance.pk and self.instance.tong_tien_moi:
            old_total = Decimal(self.instance.tong_tien_moi) - Decimal(self.instance.tong_tien_tang_them or 0)
        else:
            old_total = Decimal(hop_dong.gia_tri_hop_dong or 0)
        increase = increases["phcn"] + increases["cs"]
        return {
            "thanh_tien_phcn": service_totals["phcn"],
            "thanh_tien_cs": service_totals["cs"],
            "gia_tri_tang_them": increase,
            "tong_gia_tri_moi": old_total + increase,
        }

    def set_amount_initials(self, hop_dong):
        for key, value in self.calculate_amounts(hop_dong, exclude_id=self.instance.pk).items():
            self.initial.setdefault(key, value)

    def contract_metrics(self):
        metrics = {}
        for contract in self.fields["hop_dong"].queryset:
            baseline = self.baseline(contract, self.instance.pk)
            amounts = self.calculate_amounts(contract, exclude_id=self.instance.pk)
            current_end = _current_contract_end(contract, self.instance.pk)
            metrics[str(contract.pk)] = {
                "den_ngay_cu": current_end.isoformat() if current_end else "",
                "old_phcn": list(baseline["phcn"]),
                "old_cs": list(baseline["cs"]),
                "don_gia_cong": str(contract.don_gia_cong or 0),
                "di_lai_phcn": str(contract.dinh_muc_di_lai_phcn or 0),
                "di_lai_cs": str(contract.dinh_muc_di_lai_cs or 0),
                "old_total": str(amounts["tong_gia_tri_moi"] - amounts["gia_tri_tang_them"]),
            }
        return metrics

    def clean(self):
        cleaned = super().clean()
        hop_dong = cleaned.get("hop_dong")
        if not hop_dong:
            return cleaned
        if hop_dong.don_vi_id:
            self.add_error("hop_dong", "Gia hạn khối lượng theo mẫu này chỉ áp dụng cho hợp đồng CBCT.")
            return cleaned
        baseline = self.baseline(hop_dong, self.instance.pk)
        current_end = _current_contract_end(hop_dong, self.instance.pk)
        den_ngay_moi = cleaned.get("den_ngay_moi")
        if current_end and den_ngay_moi and den_ngay_moi < current_end:
            self.add_error("den_ngay_moi", "Ngày kết thúc mới không được trước ngày kết thúc cũ.")
        for group, label in (("phcn", "PHCN"), ("cs", "CSXH")):
            new_count = cleaned.get(f"so_tre_{group}_moi")
            new_sessions = cleaned.get(f"so_buoi_{group}_moi")
            old_count, old_sessions = baseline[group]
            if new_count is not None and new_count < old_count:
                self.add_error(f"so_tre_{group}_moi", f"Số trẻ {label} mới không được thấp hơn số cũ.")
            if new_sessions is not None and new_sessions < old_sessions:
                self.add_error(f"so_buoi_{group}_moi", f"Số buổi {label} mới không được thấp hơn số cũ.")
        values = [
            cleaned.get("so_tre_phcn_moi"), cleaned.get("so_buoi_phcn_moi"),
            cleaned.get("so_tre_cs_moi"), cleaned.get("so_buoi_cs_moi"),
        ]
        old_values = [baseline["phcn"][0], baseline["phcn"][1], baseline["cs"][0], baseline["cs"][1]]
        if not self.instance.pk and all(value == old for value, old in zip(values, old_values)):
            raise forms.ValidationError("Khối lượng mới phải có ít nhất một chỉ tiêu tăng so với hợp đồng hiện tại.")
        return cleaned


class DotThanhToanDiLaiPhuHuynhDateForm(BootstrapModelForm):
    class Meta:
        model = DotThanhToanDiLaiPhuHuynh
        fields = ["tu_ngay", "den_ngay"]
        widgets = {
            "tu_ngay": forms.DateInput(attrs={"type": "date"}),
            "den_ngay": forms.DateInput(attrs={"type": "date"}),
        }


class DotThanhToanDiLaiPhuHuynhTheoNhomForm(BootstrapModelForm):
    class Meta:
        model = DotThanhToanDiLaiPhuHuynh
        fields = ["nhom_hd", "ky_can_thiep", "nam", "thang", "tu_ngay", "den_ngay", "ngay_de_nghi", "ghi_chu"]
        widgets = {
            "ky_can_thiep": forms.NumberInput(attrs={"min": "1", "max": "30"}),
            "nam": forms.NumberInput(attrs={"min": "2000"}),
            "thang": forms.NumberInput(attrs={"min": "1", "max": "12"}),
            "tu_ngay": forms.DateInput(attrs={"type": "date"}),
            "den_ngay": forms.DateInput(attrs={"type": "date"}),
            "ngay_de_nghi": forms.DateInput(attrs={"type": "date"}),
            "ghi_chu": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["nhom_hd"].queryset = NhomHD.objects.filter(is_active=True).order_by("ma_nhom_hd")

    def validate_unique(self):
        # Đợt đã tồn tại được xử lý ở view để có thể tái gom phần nhật ký còn thiếu.
        # Kiểm tra unique tại đây sẽ chặn request trước khi view kịp đồng bộ lại đợt.
        return


class ChiTietThanhToanDiLaiPhuHuynhForm(BootstrapModelForm):
    class Meta:
        model = ChiTietThanhToanDiLaiPhuHuynh
        fields = ["nhat_ky", "so_luot_di_lai", "ghi_chu"]
        widgets = {"so_luot_di_lai": forms.NumberInput(attrs={"min": "1"}), "ghi_chu": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, hop_dong=None, nhom_hd=None, ky_can_thiep=None, nam=None, thang=None, dot=None, **kwargs):
        super().__init__(*args, **kwargs)
        if hop_dong is not None:
            queryset = NhatKyThucHien.objects.filter(hop_dong=hop_dong)
        elif nhom_hd is not None and ky_can_thiep is not None:
            queryset = NhatKyThucHien.objects.filter(
                ky_can_thiep=ky_can_thiep,
                nhom_hd_nguon=nhom_hd,
            ) | NhatKyThucHien.objects.filter(
                ky_can_thiep=ky_can_thiep,
                nhom_hd_nguon__isnull=True,
                phan_cong__nhom_hd=nhom_hd,
            ) | NhatKyThucHien.objects.filter(
                ky_can_thiep=ky_can_thiep,
                nhom_hd_nguon__isnull=True,
                phan_cong__nhom_hd__isnull=True,
                phan_cong__phan_bo__nhom_hd=nhom_hd,
            )
        else:
            queryset = NhatKyThucHien.objects.none()
        if dot is not None:
            if dot.hop_dong_id:
                queryset = queryset.filter(ngay_thuc_hien__year=dot.nam, ngay_thuc_hien__month=dot.thang)
        elif nam and thang:
            queryset = queryset.filter(ngay_thuc_hien__year=nam, ngay_thuc_hien__month=thang)
        self.fields["nhat_ky"].queryset = queryset.select_related("phan_cong__tre")
