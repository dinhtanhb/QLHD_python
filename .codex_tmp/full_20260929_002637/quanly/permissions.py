def is_admin_user(user):
    """Nhận diện tài khoản quản trị thống nhất cho view và template."""
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    groups = getattr(user, "groups", None)
    if groups is not None and groups.filter(name="Admin").exists():
        return True
    # Giữ tài khoản vận hành mặc định có quyền quản trị nếu bị mất cờ superuser/group.
    return user.get_username().strip().casefold() == "admin" and user.is_staff
