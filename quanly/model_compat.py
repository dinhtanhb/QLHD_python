from .models import ChiTietPhuLucPhanCong, HopDong


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


# Tương thích với view cũ đang truy cập related_name "phu_luc_hop_dong".
# Quan hệ thực tế của PhuLucHopDong.hop_dong có related_name="phu_luc".
# Đây chỉ là alias Python, không thay đổi model/schema/migration.
if not hasattr(HopDong, "phu_luc_hop_dong"):
    HopDong.phu_luc_hop_dong = property(lambda self: self.phu_luc)
