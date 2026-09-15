from django import forms

from .financial import FinancialConfig
from .models import (
    CanBo,
    ChiTietKhoiLuongHopDong,
    DeXuatHopDong,
    DonVi,
    HopDong,
    NhomHD,
    PhanBoChiTieu,
    PhanCongTre,
    PhuLucHopDong,
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
            "chi_nhanh", "ghi_chu", "is_active",
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
            "can_bo", "nhom_hd", "tham_gia_ct", "ngay_lap", "so_tre_phcn", "so_buoi_phcn",
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
    class Meta:
        model = PhanCongTre
        fields = [
            "phan_bo", "tre", "loai_dich_vu", "so_buoi_du_kien", "dinh_muc_di_lai", "dia_diem_ct",
            "hinh_thuc_ct", "dot_phan_cong", "ky_phan_cong", "ngay_phan_cong", "trang_thai", "ghi_chu",
        ]
        widgets = {
            "phan_bo": forms.Select(attrs={"class": "form-select select2-search"}),
            "tre": forms.Select(attrs={"class": "form-select select2-search"}),
            "so_buoi_du_kien": forms.NumberInput(attrs={"min": "0"}),
            "dinh_muc_di_lai": forms.NumberInput(attrs={"min": "0", "step": "1"}),
            "dot_phan_cong": forms.NumberInput(attrs={"min": "1"}),
            "ky_phan_cong": forms.NumberInput(attrs={"min": "1"}),
            "ngay_phan_cong": forms.DateInput(attrs={"type": "date"}),
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
        if phan_bo and not phan_bo.can_bo.is_active:
            self.add_error("phan_bo", "Cán bộ của phân bổ đang ở trạng thái ngừng hoạt động.")
        if phan_bo and loai_dich_vu == "CSXH" and phan_bo.so_tre_cs <= 0:
            self.add_error("loai_dich_vu", "Phân bổ không có chỉ tiêu CSXH.")
        if phan_bo and loai_dich_vu != "CSXH" and phan_bo.so_tre_phcn <= 0:
            self.add_error("loai_dich_vu", "Phân bổ không có chỉ tiêu PHCN.")

        if phan_bo and (dinh_muc_di_lai is None or dinh_muc_di_lai <= 0):
            cleaned_data["dinh_muc_di_lai"] = (
                phan_bo.dinh_muc_di_lai_cs
                if loai_dich_vu == "CSXH"
                else phan_bo.dinh_muc_di_lai_phcn
            )

        return cleaned_data


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
            "de_xuat", "can_bo", "nhom_hd", "so_hop_dong", "ngay_ky", "tu_ngay", "den_ngay",
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
