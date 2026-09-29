from .permissions import is_admin_user, user_group_names


def user_roles(request):
    user = request.user

    if not user.is_authenticated:
        return {
            "is_admin": False,
            "is_dieuphoi": False,
            "is_cbda": False,
            "is_ketoan": False,
        }

    names = user_group_names(user)
    return {
        "is_admin": is_admin_user(user),
        "is_dieuphoi": "DieuPhoiVien" in names,
        "is_cbda": "CBDA" in names,
        "is_ketoan": "KeToan" in names,
    }