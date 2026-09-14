from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path
from quanly import views  # Nhập bộ xử lý từ ứng dụng quanly

urlpatterns = [
    path('', views.trang_chu, name='trang_chu'),
    path('accounts/login/', auth_views.LoginView.as_view(template_name='quanly/login.html'), name='login'),
    path('accounts/logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
    path('admin/', admin.site.urls),
    path('don-vi/', views.danh_sach_don_vi, name='danh_sach_don_vi'),
    path('don-vi/them/', views.them_don_vi, name='them_don_vi'),
    path('don-vi/sua/<int:id>/', views.sua_don_vi, name='sua_don_vi'),
    path('don-vi/xoa/<int:id>/', views.xoa_don_vi, name='xoa_don_vi'),
    path('tre/', views.danh_sach_tre, name='danh_sach_tre'),
    path('tre/them/', views.them_tre, name='them_tre'),
    path('tre/sua/<int:id>/', views.sua_tre, name='sua_tre'),
    path('tre/xoa/<int:id>/', views.xoa_tre, name='xoa_tre'),
    path('can-bo/', views.danh_sach_can_bo, name='danh_sach_can_bo'),
    path('can-bo/them/', views.them_can_bo, name='them_can_bo'),
    path('can-bo/sua/<int:id>/', views.sua_can_bo, name='sua_can_bo'),
    path('can-bo/xoa/<int:id>/', views.xoa_can_bo, name='xoa_can_bo'),
    path('nhom-hd/', views.danh_sach_nhom_hd, name='danh_sach_nhom_hd'),
    path('nhom-hd/them/', views.them_nhom_hd, name='them_nhom_hd'),
    path('nhom-hd/sua/<int:id>/', views.sua_nhom_hd, name='sua_nhom_hd'),
    path('nhom-hd/xoa/<int:id>/', views.xoa_nhom_hd, name='xoa_nhom_hd'),
    path('ajax/lay-xa/', views.lay_danh_sach_xa, name='lay_danh_sach_xa'),
    path('tre/import/', views.import_tre, name='import_tre'),
    path('can-bo/import/', views.import_can_bo, name='import_can_bo'),
    path('hop-dong/import-phan-cong/', views.import_phan_cong, name='import_phan_cong'),
    path('hop-dong/tao-moi/', views.phan_bo_chi_tieu, name='phan_bo_chi_tieu'),
    path('hop-dong/danh-sach-phan-bo/', views.danh_sach_phan_bo, name='danh_sach_phan_bo'),
    path('hop-dong/import-phan-bo/', views.import_phan_bo, name='import_phan_bo'),
    path('phan-bo/<int:pk>/sua/', views.sua_phan_bo_chi_tieu, name='sua_phan_bo_chi_tieu'),
    path('danh-sach-de-xuat/', views.danh_sach_de_xuat, name='danh_sach_de_xuat'),
    path('hop-dong/tao-chinh-thuc/<int:pk>/', views.tao_hop_dong_chinh_thuc, name='tao_hop_dong_chinh_thuc'),
    path('hop-dong/', views.danh_sach_hop_dong, name='danh_sach_hop_dong'),
]