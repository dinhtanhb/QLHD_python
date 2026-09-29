from django.contrib.auth.decorators import user_passes_test

from .permissions import is_admin_user


def role_required(*roles):
    def check_role(user):

        if not user.is_authenticated:
            return False

        if is_admin_user(user):
            return True

        return user.groups.filter(
            name__in=roles
        ).exists()

    return user_passes_test(
        check_role,
        login_url="/accounts/login/"
    )


def admin_required(view_func):
    return role_required(
        "Admin"
    )(view_func)


def dashboard_required(view_func):
    return role_required(
        "Admin",
        "DieuPhoiVien",
        "CBDA",
        "KeToan",
    )(view_func)


def hopdong_required(view_func):
    return role_required(
        "Admin",
        "DieuPhoiVien",
        "CBDA",
    )(view_func)


def readonly_required(view_func):
    return role_required(
        "Admin",
        "DieuPhoiVien",
        "CBDA",
        "KeToan",
    )(view_func)
