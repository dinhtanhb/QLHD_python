from decimal import Decimal

from django.db.models.signals import pre_save
from django.dispatch import receiver

from .financial import FinancialConfig
from .models import DeXuatHopDong, PhanBoChiTieu


@receiver(pre_save, sender=DeXuatHopDong)
def set_proposal_value_from_allocation(sender, instance, **kwargs):
    """Đề xuất HĐ luôn lấy khối lượng và giá trị từ Phân bổ chỉ tiêu.

    Phân công trẻ chỉ là điều kiện để tạo đề xuất và phục vụ các bước
    thực hiện/phụ lục; không làm thay đổi giá trị HĐ đã phân bổ.
    """
    if not instance.phan_bo_id:
        return

    phan_bo = getattr(instance, "phan_bo", None)
    if phan_bo is None or phan_bo.pk != instance.phan_bo_id:
        phan_bo = PhanBoChiTieu.objects.get(pk=instance.phan_bo_id)

    cong = Decimal(str(FinancialConfig.DON_GIA_CONG))
    dm_phcn = Decimal(str(phan_bo.dinh_muc_di_lai_phcn or 0))
    dm_cs = Decimal(str(phan_bo.dinh_muc_di_lai_cs or 0))

    instance.so_tre_phcn = phan_bo.so_tre_phcn
    instance.so_buoi_phcn = phan_bo.so_buoi_phcn
    instance.so_tre_cs = phan_bo.so_tre_cs
    instance.so_buoi_cs = phan_bo.so_buoi_cs
    instance.gia_tri_du_kien = (
        Decimal(phan_bo.so_tre_phcn)
        * Decimal(phan_bo.so_buoi_phcn)
        * (cong + dm_phcn)
        + Decimal(phan_bo.so_tre_cs)
        * Decimal(phan_bo.so_buoi_cs)
        * (cong + dm_cs)
    )
