from django.utils import timezone

from django.core.exceptions import ValidationError
from django.db import transaction


STATUS_TRANSITIONS = {
    "DU_THAO": {"DU_THAO", "DA_KY", "DANG_THUC_HIEN", "NGHIEM_THU", "HUY"},
    "DA_KY": {"DA_KY", "DANG_THUC_HIEN", "HET_HAN", "NGHIEM_THU", "HUY"},
    "DANG_THUC_HIEN": {"DANG_THUC_HIEN", "HET_HAN", "NGHIEM_THU", "HUY", "TAM_DUNG"},
    "TAM_DUNG": {"TAM_DUNG", "DANG_THUC_HIEN", "HET_HAN", "HUY"},
    "HET_HAN": {"HET_HAN", "NGHIEM_THU", "HUY"},
    "NGHIEM_THU": {"NGHIEM_THU", "THANH_LY", "DANG_THUC_HIEN", "HET_HAN"},
    "THANH_LY": {"THANH_LY"},
    "HUY": {"HUY"},
}


def transition_hop_dong_status(hop_dong, target):
    validate_status_transition(hop_dong, target)
    current = hop_dong.trang_thai or "DU_THAO"
    if current != target:
        hop_dong.trang_thai = target
        hop_dong.save(update_fields=["trang_thai", "updated_at"])
    return hop_dong


def validate_status_transition(hop_dong, target):
    current = hop_dong.trang_thai or "DU_THAO"
    if target not in {value for value, _ in hop_dong.TRANG_THAI_CHOICES}:
        raise ValidationError(f"Trạng thái hợp đồng không hợp lệ: {target}")
    if target not in STATUS_TRANSITIONS.get(current, {current}):
        raise ValidationError(f"Không thể chuyển hợp đồng từ {current} sang {target}.")


def _has_valid_acceptance(hop_dong):
    acceptance = getattr(hop_dong, "nghiem_thu", None)
    return bool(acceptance and acceptance.ngay_nghiem_thu and acceptance.ket_qua == "DAT")


def _has_valid_liquidation(hop_dong):
    liquidation = getattr(hop_dong, "thanh_ly", None)
    return bool(liquidation and liquidation.ngay_thanh_ly)


def desired_trang_thai(hop_dong):
    if hop_dong.trang_thai in {"TAM_DUNG", "HUY"}:
        return hop_dong.trang_thai
    if _has_valid_liquidation(hop_dong):
        return "THANH_LY"
    if _has_valid_acceptance(hop_dong):
        return "NGHIEM_THU"
    acceptance = getattr(hop_dong, "nghiem_thu", None)
    if acceptance and hop_dong.trang_thai == "NGHIEM_THU":
        return "DANG_THUC_HIEN" if not hop_dong.den_ngay or hop_dong.den_ngay >= timezone.localdate() else "HET_HAN"
    if hop_dong.den_ngay and hop_dong.den_ngay < timezone.localdate():
        return "HET_HAN"
    if hop_dong.ngay_ky:
        return "DANG_THUC_HIEN"
    return hop_dong.trang_thai


def is_het_han(hop_dong):
    return bool(
        hop_dong
        and hop_dong.den_ngay
        and hop_dong.den_ngay < timezone.localdate()
        and hop_dong.trang_thai not in {"THANH_LY", "HUY"}
    )


@transaction.atomic
def sync_trang_thai_hop_dong(hop_dong):
    """Derive the legal lifecycle state without allowing a liquidation rollback."""
    hop_dong = type(hop_dong).objects.select_for_update().get(pk=hop_dong.pk)
    target = desired_trang_thai(hop_dong)
    if target == "THANH_LY":
        hop_dong.is_locked = True
        hop_dong.save(update_fields=["is_locked", "updated_at"])
        if hop_dong.trang_thai not in {"NGHIEM_THU", "THANH_LY"}:
            transition_hop_dong_status(hop_dong, "NGHIEM_THU")
        return transition_hop_dong_status(hop_dong, "THANH_LY")
    return transition_hop_dong_status(hop_dong, target)
