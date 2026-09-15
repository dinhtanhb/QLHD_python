def user_roles(request):
    user = request.user

    if not user.is_authenticated:
        return {
            "is_admin": False,
            "is_dieuphoi": False,
            "is_cbda": False,
            "is_ketoan": False,
        }

    return {
        "is_admin": (
            user.is_superuser
            or user.groups.filter(name="Admin").exists()
        ),
        "is_dieuphoi": user.groups.filter(
            name="DieuPhoiVien"
        ).exists(),
        "is_cbda": user.groups.filter(
            name="CBDA"
        ).exists(),
        "is_ketoan": user.groups.filter(
            name="KeToan"
        ).exists(),
    }