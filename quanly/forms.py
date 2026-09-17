from django import forms
from django.db.models import Q

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

        if phan_bo and phan_bo.is_locked and not self.instance.pk:
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
        fields = ["phan_cong", "ngay_thuc_hien", "gio_bat_dau", "gio_ket_thuc", "dia_diem_ct", "ky_can_thiep", "so_buoi_thuc_hien", "so_luot_di_lai", "ghi_chu"]
        widgets = {
              "ngay_thuc_hien": forms.DateInput(attrs={"type": "date"}),
              "gio_bat_dau": forms.TimeInput(attrs={"type": "time"}),
              "gio_ket_thuc": forms.TimeInput(attrs={"type": "time"}),
              "ky_can_thiep": forms.NumberInput(attrs={"min": "1", "max": "30"}),
            "so_buoi_thuc_hien": forms.NumberInput(attrs={"min": "1"}),
            "so_luot_di_lai": forms.NumberInput(attrs={"min": "0"}),
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


class NhatKyCanThiepForm(BootstrapModelForm):
    hop_dong = forms.ModelChoiceField(
        queryset=HopDong.objects.select_related("can_bo", "don_vi", "nhom_hd"),
        label="Hợp đồng",
        required=False,
        widget=forms.Select(attrs={"class": "form-select select2-search"}),
    )

    class Meta:
        model = NhatKyThucHien
        fields = ["hop_dong", "phan_cong", "ngay_thuc_hien", "gio_bat_dau", "gio_ket_thuc", "dia_diem_ct", "ky_can_thiep", "so_buoi_thuc_hien", "so_luot_di_lai", "ghi_chu"]
        widgets = {
            "phan_cong": forms.Select(attrs={"class": "form-select select2-search"}),
              "ngay_thuc_hien": forms.DateInput(attrs={"type": "date"}),
              "gio_bat_dau": forms.TimeInput(attrs={"type": "time"}),
              "gio_ket_thuc": forms.TimeInput(attrs={"type": "time"}),
              "ky_can_thiep": forms.NumberInput(attrs={"min": "1", "max": "30"}),
            "so_buoi_thuc_hien": forms.NumberInput(attrs={"min": "1"}),
            "so_luot_di_lai": forms.NumberInput(attrs={"min": "0"}),
            "ghi_chu": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, require_contract=True, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["hop_dong"].required = require_contract

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
    class Meta:
        model = NghiemThu
        fields = ["ngay_nghiem_thu", "ket_qua", "bien_ban_so", "ghi_chu"]
        widgets = {
            "ngay_nghiem_thu": forms.DateInput(attrs={"type": "date"}),
            "ghi_chu": forms.Textarea(attrs={"rows": 3}),
        }


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
        fields = ["nam", "thang", "ngay_de_nghi", "ghi_chu"]
        widgets = {"ngay_de_nghi": forms.DateInput(attrs={"type": "date"}), "ghi_chu": forms.Textarea(attrs={"rows": 3})}


class ChiTietThanhToanDiLaiPhuHuynhForm(BootstrapModelForm):
    class Meta:
        model = ChiTietThanhToanDiLaiPhuHuynh
        fields = ["nhat_ky", "so_luot_di_lai", "ghi_chu"]
        widgets = {"so_luot_di_lai": forms.NumberInput(attrs={"min": "1"}), "ghi_chu": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, hop_dong=None, **kwargs):
        super().__init__(*args, **kwargs)
        if hop_dong is not None:
            self.fields["nhat_ky"].queryset = NhatKyThucHien.objects.filter(hop_dong=hop_dong).select_related("phan_cong__tre")
