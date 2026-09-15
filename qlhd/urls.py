from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.urls import path

from quanly import views

urlpatterns = [

    # ==================================================
    # AUTHENTICATION
    # ==================================================
    path(
        'accounts/login/',
        auth_views.LoginView.as_view(
            template_name='quanly/login.html'
        ),
        name='login'
    ),

    path(
        'accounts/logout/',
        auth_views.LogoutView.as_view(
            next_page='login'
        ),
        name='logout'
    ),

    # ==================================================
    # DASHBOARD
    # ==================================================
    path(
        '',
        login_required(views.trang_chu),
        name='trang_chu'
    ),

    # ==================================================
    # ADMIN
    # ==================================================
    path('admin/', admin.site.urls),

    # ==================================================
    # ĐƠN VỊ
    # ==================================================
    path(
        'don-vi/',
        login_required(views.danh_sach_don_vi),
        name='danh_sach_don_vi'
    ),

    path(
        'don-vi/them/',
        login_required(views.them_don_vi),
        name='them_don_vi'
    ),

    path(
        'don-vi/sua/<int:id>/',
        login_required(views.sua_don_vi),
        name='sua_don_vi'
    ),

    path(
        'don-vi/xoa/<int:id>/',
        login_required(views.xoa_don_vi),
        name='xoa_don_vi'
    ),

    # ==================================================
    # TRẺ
    # ==================================================
    path(
        'tre/',
        login_required(views.danh_sach_tre),
        name='danh_sach_tre'
    ),

    path(
        'tre/them/',
        login_required(views.them_tre),
        name='them_tre'
    ),

    path(
        'tre/sua/<int:id>/',
        login_required(views.sua_tre),
        name='sua_tre'
    ),

    path(
        'tre/xoa/<int:id>/',
        login_required(views.xoa_tre),
        name='xoa_tre'
    ),

    path(
        'tre/import/',
        login_required(views.import_tre),
        name='import_tre'
    ),

    # ==================================================
    # CÁN BỘ
    # ==================================================
    path(
        'can-bo/',
        login_required(views.danh_sach_can_bo),
        name='danh_sach_can_bo'
    ),

    path(
        'can-bo/them/',
        login_required(views.them_can_bo),
        name='them_can_bo'
    ),

    path(
        'can-bo/sua/<int:id>/',
        login_required(views.sua_can_bo),
        name='sua_can_bo'
    ),

    path(
        'can-bo/xoa/<int:id>/',
        login_required(views.xoa_can_bo),
        name='xoa_can_bo'
    ),

    path(
        'can-bo/import/',
        login_required(views.import_can_bo),
        name='import_can_bo'
    ),

    # ==================================================
    # NHÓM HỢP ĐỒNG
    # ==================================================
    path(
        'nhom-hd/',
        login_required(views.danh_sach_nhom_hd),
        name='danh_sach_nhom_hd'
    ),

    path(
        'nhom-hd/them/',
        login_required(views.them_nhom_hd),
        name='them_nhom_hd'
    ),

    path(
        'nhom-hd/sua/<int:id>/',
        login_required(views.sua_nhom_hd),
        name='sua_nhom_hd'
    ),

    path(
        'nhom-hd/xoa/<int:id>/',
        login_required(views.xoa_nhom_hd),
        name='xoa_nhom_hd'
    ),

    # ==================================================
    # AJAX
    # ==================================================
    path(
        'ajax/lay-xa/',
        login_required(views.lay_danh_sach_xa),
        name='lay_danh_sach_xa'
    ),

    # ==================================================
    # PHÂN CÔNG
    # ==================================================
    path(
        'hop-dong/import-phan-cong/',
        login_required(views.import_phan_cong),
        name='import_phan_cong'
    ),

    # ==================================================
    # PHÂN BỔ CHỈ TIÊU
    # ==================================================
    path(
        'hop-dong/tao-moi/',
        login_required(views.phan_bo_chi_tieu),
        name='phan_bo_chi_tieu'
    ),

    path(
        'hop-dong/danh-sach-phan-bo/',
        login_required(views.danh_sach_phan_bo),
        name='danh_sach_phan_bo'
    ),

    path(
        'hop-dong/import-phan-bo/',
        login_required(views.import_phan_bo),
        name='import_phan_bo'
    ),

    path(
        'phan-bo/<int:pk>/sua/',
        login_required(views.sua_phan_bo_chi_tieu),
        name='sua_phan_bo_chi_tieu'
    ),

    # ==================================================
    # ĐỀ XUẤT HỢP ĐỒNG
    # ==================================================
    path(
        'danh-sach-de-xuat/',
        login_required(views.danh_sach_de_xuat),
        name='danh_sach_de_xuat'
    ),

    # ==================================================
    # HỢP ĐỒNG CHÍNH THỨC
    # ==================================================
    path(
        'hop-dong/tao-chinh-thuc/<int:pk>/',
        login_required(views.tao_hop_dong_chinh_thuc),
        name='tao_hop_dong_chinh_thuc'
    ),

    path(
        'hop-dong/',
        login_required(views.danh_sach_hop_dong),
        name='danh_sach_hop_dong'
    ),
]