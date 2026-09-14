from django import forms
from .models import DonVi, Tre, CanBo, DonVi, NhomHD, PhanBoChiTieu
from .financial import FinancialConfig

class DonViForm(forms.ModelForm):
    class Meta:
        model = DonVi
        fields = ['ma_don_vi', 'ten_don_vi', 'nguoi_dai_dien', 'mstdv', 'dia_chi', 'dien_thoai', 'email']
        widgets = {
            'ma_don_vi': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nhập mã đơn vị...'}),
            'ten_don_vi': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nhập tên đơn vị...'}),
            'nguoi_dai_dien': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Họ tên người đại diện...'}),
            'mstdv': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Mã số thuế...'}),
            'dia_chi': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Địa chỉ đơn vị...'}),
            'dien_thoai': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Số điện thoại liên hệ...'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Địa chỉ email...'}),
        }

class TreForm(forms.ModelForm):
    class Meta:
        model = Tre
        fields = [
            'ma_tre', 'ho_ten', 'ngay_sinh', 'gioi_tinh', 
            'tinh', 'xa', 'ma_tinh', 'ten_phu_huynh', 'dien_thoai', 
            'ten_tai_khoan', 'tai_khoan', 'ngan_hang', 'chi_nhanh', 'ghi_chu'
        ]
        widgets = {
            'ma_tre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nhập mã trẻ...'}),
            'ho_ten': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nhập họ và tên...'}),
            'ngay_sinh': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'gioi_tinh': forms.Select(attrs={'class': 'form-select'}),
            'tinh': forms.Select(attrs={'class': 'form-select', 'id': 'select-tinh'}),
            'xa': forms.Select(attrs={'class': 'form-select', 'id': 'id_xa'}),
            'ma_tinh': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nhập mã tỉnh...'}),
            'ten_phu_huynh': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nhập tên phụ huynh...'}),
            'dien_thoai': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Số điện thoại...'}),
            'ten_tai_khoan': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Tên chủ tài khoản...'}),
            'tai_khoan': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Số tài khoản ngân hàng...'}),
            'ngan_hang': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Tên ngân hàng...'}),
            'chi_nhanh': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Chi nhánh ngân hàng...'}),
            'ghi_chu': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Ghi chú thêm (nếu có)...'}),
        }

class CanBoForm(forms.ModelForm):
    class Meta:
        model = CanBo
        fields = '__all__'
        widgets = {
            # Ép kiểu trường ngay_cap thành input calendar (chọn ngày)
            'ngay_cap': forms.DateInput(attrs={'type': 'date'}), 
        }

    def __init__(self, *args, **kwargs):
        super(CanBoForm, self).__init__(*args, **kwargs)
        # Tự động thêm class css cho đẹp
        for field_name, field in self.fields.items():
            if isinstance(field.widget, forms.Select):
                field.widget.attrs['class'] = 'form-select'
            else:
                field.widget.attrs['class'] = 'form-control'

class NhomHDForm(forms.ModelForm):
    class Meta:
        model = NhomHD
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super(NhomHDForm, self).__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'

class PhanBoChiTieuForm(forms.ModelForm):
    # Khai báo ChoiceField để người dùng chọn nhanh định mức (50.000 hoặc 100.000)
    dinh_muc_di_lai_phcn = forms.ChoiceField(
        choices=[
            (FinancialConfig.DON_GIA_DI_LAI_DM1, f"Định mức 1 - {FinancialConfig.DON_GIA_DI_LAI_DM1:,.0f}đ"),
            (FinancialConfig.DON_GIA_DI_LAI_DM2, f"Định mức 2 - {FinancialConfig.DON_GIA_DI_LAI_DM2:,.0f}đ"),
        ],
        initial=FinancialConfig.DON_GIA_DI_LAI_DM1,
        label="Định mức đi lại PHCN",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    dinh_muc_di_lai_cs = forms.ChoiceField(
        choices=[
            (FinancialConfig.DON_GIA_DI_LAI_DM1, f"Định mức 1 - {FinancialConfig.DON_GIA_DI_LAI_DM1:,.0f}đ"),
            (FinancialConfig.DON_GIA_DI_LAI_DM2, f"Định mức 2 - {FinancialConfig.DON_GIA_DI_LAI_DM2:,.0f}đ"),
        ],
        initial=FinancialConfig.DON_GIA_DI_LAI_DM1,
        label="Định mức đi lại CSXH",
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    class Meta:
        model = PhanBoChiTieu
        fields = [
            'can_bo', 
            'ngay_lap_de_xuat', 
            'so_tre_phcn', 'so_buoi_phcn', 'dinh_muc_di_lai_phcn',
            'so_tre_cs', 'so_buoi_cs', 'dinh_muc_di_lai_cs',
            'gia_tri_hd_du_kien'
        ]
        widgets = {
            'can_bo': forms.Select(attrs={'class': 'form-select select2-search'}),
            'ngay_lap_de_xuat': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'so_tre_phcn': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'so_buoi_phcn': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'so_tre_cs': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'so_buoi_cs': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'gia_tri_hd_du_kien': forms.NumberInput(attrs={'class': 'form-control', 'step': '1000', 'min': '0'}),
        }
