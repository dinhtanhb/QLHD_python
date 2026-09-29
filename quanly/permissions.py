def user_group_names(user):
    """Tên các nhóm quyền của người dùng, chỉ truy vấn một lần cho mỗi request/đối tượng user."""
    cached = getattr(user, "_qlhd_group_names", None)
    if cached is not None:
        return cached
    groups = getattr(user, "groups", None)
    names = frozenset(groups.values_list("name", flat=True)) if groups is not None else frozenset()
    try:
        user._qlhd_group_names = names
    except AttributeError:
        pass
    return names


def is_admin_user(user):
    """Nhận diện tài khoản quản trị thống nhất cho view và template."""
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    if "Admin" in user_group_names(user):
        return True
    # Giữ tài khoản vận hành mặc định có quyền quản trị nếu bị mất cờ superuser/group.
    return user.get_username().strip().casefold() == "admin" and user.is_staff