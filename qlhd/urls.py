from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.urls import path

from quanly import views

urlpatterns = [
    path("accounts/login/", auth_views.LoginView.as_view(template_name="quanly/login.html"), name="login"),
    path("accounts/logout/", auth_views.LogoutView.as_view(next_page="login"), name="logout"),
    path("", login_required(views.trang_chu), name="trang_chu"),
    path("admin/", admin.site.urls),

    path("don-vi/", login_required(views.danh_sach_don_vi), name="danh_sach_don_vi"),
    path("don-vi/them/", login_required(views.them_don_vi), name="them_don_vi"),
    path("don-vi/sua/<int:id>/", login_required(views.sua_don_vi), name="sua_don_vi"),
    path("don-vi/xoa/<int:id>/", login_required(views.xoa_don_vi), name="xoa_don_vi"),

    path("tre/", login_required(views.danh_sach_tre), name="danh_sach_tre"),
    path("tre/them/", login_required(views.them_tre), name="them_tre"),
    path("tre/sua/<int:id>/", login_required(views.sua_tre), name="sua_tre"),
    path("tre/xoa/<int:id>/", login_required(views.xoa_tre), name="xoa_tre"),
    path("tre/import/", login_required(views.import_tre), name="import_tre"),

    path("can-bo/", login_required(views.danh_sach_can_bo), name="danh_sach_can_bo"),
    path("can-bo/them/", login_required(views.them_can_bo), name="them_can_bo"),
    path("can-bo/sua/<int:id>/", login_required(views.sua_can_bo), name="sua_can_bo"),
    path("can-bo/xoa/<int:id>/", login_required(views.xoa_can_bo), name="xoa_can_bo"),
    path("can-bo/import/", login_required(views.import_can_bo), name="import_can_bo"),

    path("nhom-hd/", login_required(views.danh_sach_nhom_hd), name="danh_sach_nhom_hd"),
    path("nhom-hd/them/", login_required(views.them_nhom_hd), name="them_nhom_hd"),
    path("nhom-hd/sua/<int:id>/", login_required(views.sua_nhom_hd), name="sua_nhom_hd"),
    path("nhom-hd/xoa/<int:id>/", login_required(views.xoa_nhom_hd), name="xoa_nhom_hd"),

    path("ajax/lay-xa/", login_required(views.lay_danh_sach_xa), name="lay_danh_sach_xa"),

    path("hop-dong/import-phan-cong/", login_required(views.import_phan_cong), name="import_phan_cong"),
    path("hop-dong/phan-cong/", login_required(views.danh_sach_phan_cong), name="danh_sach_phan_cong"),
    path("hop-dong/phan-cong/them/", login_required(views.them_phan_cong), name="them_phan_cong"),
    path("hop-dong/phan-cong/sua/<int:pk>/", login_required(views.sua_phan_cong), name="sua_phan_cong"),

    path("hop-dong/tao-moi/", login_required(views.phan_bo_chi_tieu), name="phan_bo_chi_tieu"),
    path("hop-dong/danh-sach-phan-bo/", login_required(views.danh_sach_phan_bo), name="danh_sach_phan_bo"),
    path("hop-dong/import-phan-bo/", login_required(views.import_phan_bo), name="import_phan_bo"),
    path("hop-dong/import-phan-bo/confirm/", login_required(views.confirm_import_phan_bo), name="confirm_import_phan_bo"),
    path("phan-bo/<int:pk>/sua/", login_required(views.sua_phan_bo_chi_tieu), name="sua_phan_bo_chi_tieu"),
    path("phan-bo/<int:pk>/khoa/", login_required(views.khoa_phan_bo), name="khoa_phan_bo"),

    path("danh-sach-de-xuat/", login_required(views.danh_sach_de_xuat), name="danh_sach_de_xuat"),
    path("de-xuat/<int:pk>/tao/", login_required(views.tao_de_xuat_hop_dong), name="tao_de_xuat_hop_dong"),
    path("de-xuat/<int:pk>/duyet/", login_required(views.duyet_de_xuat), name="duyet_de_xuat"),

    path("hop-dong/tao-chinh-thuc/<int:pk>/", login_required(views.tao_hop_dong_chinh_thuc), name="tao_hop_dong_chinh_thuc"),
    path("hop-dong/", login_required(views.danh_sach_hop_dong), name="danh_sach_hop_dong"),
    path("hop-dong/<int:pk>/", login_required(views.chi_tiet_hop_dong), name="chi_tiet_hop_dong"),
    path("hop-dong/<int:hop_dong_id>/khoi-luong/them/", login_required(views.them_khoi_luong_hop_dong), name="them_khoi_luong_hop_dong"),
    path("hop-dong/<int:hop_dong_id>/phu-luc/them/", login_required(views.them_phu_luc_hop_dong), name="them_phu_luc_hop_dong"),
]