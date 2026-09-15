from django import forms

from .financial import FinancialConfig
from .models import CanBo, DonVi, NhomHD, PhanBoChiTieu, Tre


class BootstrapModelForm(forms.ModelForm):
    """Áp dụng class Bootstrap thống nhất cho các form quản trị."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, (forms.Select, forms.SelectMultiple)):
                css_class = "form-select"
            else:
                css_class = "form-control"
            field.widget.attrs.setdefault("class", css_class)


class DonViForm(BootstrapModelForm):
    class Meta:
        model = DonVi
        fields = [
            "ma_don_vi",
            "ten_don_vi",
            "nguoi_dai_dien",
            "mstdv",
            "dia_chi",
            "dien_thoai",
            "email",
            "is_active",
        ]
        widgets = {
            "ma_don_vi": forms.TextInput(attrs={"placeholder": "Nhập mã đơn vị..."}),
            "ten_don_vi": forms.TextInput(attrs={"placeholder": "Nhập tên đơn vị..."}),
            "nguoi_dai_dien": forms.TextInput(attrs={"placeholder": "Họ tên người đại diện..."}),
            "mstdv": forms.TextInput(attrs={"placeholder": "Mã số thuế..."}),
            "dia_chi": forms.TextInput(attrs={"placeholder": "Địa chỉ đơn vị..."}),
            "dien_thoai": forms.TextInput(attrs={"placeholder": "Số điện thoại liên hệ..."}),
            "email": forms.EmailInput(attrs={"placeholder": "Địa chỉ email..."}),
        }


class TreForm(BootstrapModelForm):
    class Meta:
        model = Tre
        fields = [
            "ma_tre",
            "ho_ten",
            "ngay_sinh",
            "gioi_tinh",
            "tinh",
            "xa",
            "ma_tinh",
            "ten_phu_huynh",
            "dien_thoai",
            "ten_tai_khoan",
            "tai_khoan",
            "ngan_hang",
            "chi_nhanh",
            "ghi_chu",
            "is_active",
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
            "ma_can_bo",
            "ho_ten",
            "gioi_tinh",
            "tinh",
            "xa",
            "dia_chi",
            "dien_thoai",
            "email",
            "cccd",
            "mst",
            "ngay_cap",
            "noi_cap",
            "tai_khoan",
            "ngan_hang",
            "chi_nhanh",
            "don_vi",
            "is_active",
        ]
        widgets = {
            "ngay_cap": forms.DateInput(attrs={"type": "date"}),
        }


class NhomHDForm(BootstrapModelForm):
    class Meta:
        model = NhomHD
        fields = ["ma_nhom_hd", "ten_nhom_hd", "is_active"]


class PhanBoChiTieuForm(BootstrapModelForm):
    dinh_muc_di_lai_phcn = forms.ChoiceField(
        choices=[
            (
                str(FinancialConfig.DON_GIA_DI_LAI_DM1),
                f"Định mức 1 - {FinancialConfig.DON_GIA_DI_LAI_DM1:,.0f} đ",
            ),
            (
                str(FinancialConfig.DON_GIA_DI_LAI_DM2),
                f"Định mức 2 - {FinancialConfig.DON_GIA_DI_LAI_DM2:,.0f} đ",
            ),
        ],
        initial=str(FinancialConfig.DON_GIA_DI_LAI_DM1),
        label="Định mức đi lại PHCN",
    )
    dinh_muc_di_lai_cs = forms.ChoiceField(
        choices=[
            (
                str(FinancialConfig.DON_GIA_DI_LAI_DM1),
                f"Định mức 1 - {FinancialConfig.DON_GIA_DI_LAI_DM1:,.0f} đ",
            ),
            (
                str(FinancialConfig.DON_GIA_DI_LAI_DM2),
                f"Định mức 2 - {FinancialConfig.DON_GIA_DI_LAI_DM2:,.0f} đ",
            ),
        ],
        initial=str(FinancialConfig.DON_GIA_DI_LAI_DM1),
        label="Định mức đi lại CSXH",
    )

    class Meta:
        model = PhanBoChiTieu
        fields = [
            "can_bo",
            "nhom_hd",
            "tham_gia_ct",
            "ngay_lap",
            "so_tre_phcn",
            "so_buoi_phcn",
            "dinh_muc_di_lai_phcn",
            "so_tre_cs",
            "so_buoi_cs",
            "dinh_muc_di_lai_cs",
            "ghi_chu",
        ]
        widgets = {
            "can_bo": forms.Select(attrs={"class": "form-select select2-search"}),
            "nhom_hd": forms.Select(attrs={"class": "form-select"}),
            "ngay_lap": forms.DateInput(attrs={"type": "date"}),
            "so_tre_phcn": forms.NumberInput(attrs={"min": "0"}),
            "so_buoi_phcn": forms.NumberInput(attrs={"min": "0"}),
            "so_tre_cs": forms.NumberInput(attrs={"min": "0"}),
            "so_buoi_cs": forms.NumberInput(attrs={"min": "0"}),
            "ghi_chu": forms.Textarea(attrs={"rows": 3}),
        }

    def clean(self):
        cleaned_data = super().clean()
        so_tre_phcn = cleaned_data.get("so_tre_phcn") or 0
        so_buoi_phcn = cleaned_data.get("so_buoi_phcn") or 0
        so_tre_cs = cleaned_data.get("so_tre_cs") or 0
        so_buoi_cs = cleaned_data.get("so_buoi_cs") or 0

        if so_tre_phcn > 0 and so_buoi_phcn <= 0:
            self.add_error("so_buoi_phcn", "Số buổi PHCN phải lớn hơn 0 khi có trẻ PHCN.")
        if so_tre_cs > 0 and so_buoi_cs <= 0:
            self.add_error("so_buoi_cs", "Số buổi CSXH phải lớn hơn 0 khi có trẻ CSXH.")

        return cleaned_data
