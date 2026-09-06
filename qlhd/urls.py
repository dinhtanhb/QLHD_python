from django.contrib import admin
from django.urls import path
from quanly import views  # Nhập bộ xử lý từ ứng dụng quanly

urlpatterns = [
    path('', views.trang_chu, name='trang_chu'),
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
    path('hop-dong/', views.danh_sach_hop_dong, name='danh_sach_hop_dong'),
    path('tre/import/', views.import_tre, name='import_tre'),
    path('can-bo/import/', views.import_can_bo, name='import_can_bo'),
    path('hop-dong/import/', views.import_phan_cong, name='import_phan_cong'),
]