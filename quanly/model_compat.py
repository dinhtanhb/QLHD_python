from .models import ChiTietPhuLucPhanCong


_original_chi_tiet_phu_luc_init = ChiTietPhuLucPhanCong.__init__


def _chi_tiet_phu_luc_init_compat(self, *args, **kwargs):
    """Tương thích với mã tạo snapshot cũ dùng tên phan_cong.

    Field thực tế của model là source_phan_cong; không thay đổi schema DB.
    """
    if "phan_cong" in kwargs and "source_phan_cong" not in kwargs:
        kwargs["source_phan_cong"] = kwargs.pop("phan_cong")
    else:
        kwargs.pop("phan_cong", None)
    _original_chi_tiet_phu_luc_init(self, *args, **kwargs)


ChiTietPhuLucPhanCong.__init__ = _chi_tiet_phu_luc_init_compat
