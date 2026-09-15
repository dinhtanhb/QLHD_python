from django.contrib.auth.decorators import login_required
from django.contrib.auth.decorators import user_passes_test


# ==========================================================
# KIỂM TRA USER THUỘC NHÓM QUYỀN
# ==========================================================

def role_required(*roles):
    """
    Kiểm tra User thuộc một trong các nhóm quyền được phép.

    Ví dụ:

    @role_required("Admin")

    @role_required("Admin", "CBDA")

    @role_required("Admin", "DieuPhoiVien")
    """

    def check_role(user):
        if not user.is_authenticated:
            return False

        # Superuser luôn có toàn quyền
        if user.is_superuser:
            return True

        return user.groups.filter(name__in=roles).exists()

    return user_passes_test(check_role)


# ==========================================================
# CÁC DECORATOR CHUYÊN BIỆT
# ==========================================================

def admin_required(view_func):
    """
    Chỉ Admin hoặc Superuser
    """
    return role_required("Admin")(view_func)


def dieuphoi_required(view_func):
    """
    Admin + Điều phối viên
    """
    return role_required(
        "Admin",
        "DieuPhoiVien"
    )(view_func)


def cbda_required(view_func):
    """
    Admin + CBDA
    """
    return role_required(
        "Admin",
        "CBDA"
    )(view_func)


def ketoan_required(view_func):
    """
    Admin + Kế toán
    """
    return role_required(
        "Admin",
        "KeToan"
    )(view_func)


# ==========================================================
# KẾT HỢP NHIỀU NHÓM QUYỀN
# ==========================================================

def hopdong_required(view_func):
    """
    Các nhóm được xử lý Hợp đồng

    Admin
    Điều phối viên
    CBDA
    """

    return role_required(
        "Admin",
        "DieuPhoiVien",
        "CBDA"
    )(view_func)


def dashboard_required(view_func):
    """
    Các nhóm được xem Dashboard

    Admin
    Điều phối viên
    CBDA
    Kế toán
    """

    return role_required(
        "Admin",
        "DieuPhoiVien",
        "CBDA",
        "KeToan"
    )(view_func)


# ==========================================================
# DECORATOR CHUNG
# ==========================================================

secure_view = login_required