"""Single source of truth for CBCT payment vouchers."""

from dataclasses import dataclass
from decimal import Decimal
import logging

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Case, Exists, F, IntegerField, Max, OuterRef, Sum, Value, When
from django.utils import timezone

from ..financial import FinancialConfig, calculate_payment_breakdown
from ..models import CauHinhThue, ChiTietPhieuThanhToan, HopDong, NhatKyThucHien, PhieuThanhToan

logger = logging.getLogger(__name__)


class NoEligiblePaymentJournals(ValidationError):
    """A contract has no new journal for the selected intervention period."""


class PaymentJournalSnapshot:
    """Giao diện tương thích với exporter, dùng số liệu đã chốt trong phiếu."""

    def __init__(self, detail):
        self._detail = detail
        self._journal = detail.nhat_ky
        self.phieu = detail.phieu

    def __getattr__(self, name):
        return getattr(self._journal, name)

    @property
    def pk(self):
        return self._journal.pk

    @property
    def so_buoi_thuc_hien(self):
        return self._detail.so_buoi

    @property
    def so_luot_di_lai_cbct(self):
        return self._detail.so_luot_di_lai_cbct

    @property
    def don_gia_cong(self):
        return self._detail.don_gia_cong

    @property
    def dinh_muc_di_lai(self):
        return self._detail.dinh_muc_di_lai

    @property
    def lan_thanh_toan(self):
        return self.phieu.lan_thanh_toan


def snapshot_journals(journals):
    journals = list(journals)
    if not journals:
        return []
    details = ChiTietPhieuThanhToan.objects.filter(
        nhat_ky_id__in=[journal.pk for journal in journals],
        hoat_dong=True,
    ).select_related(
        "phieu",
        "nhat_ky__can_bo_nguon__don_vi",
        "nhat_ky__nhom_hd_nguon",
        "nhat_ky__hop_dong__can_bo__don_vi",
        "nhat_ky__hop_dong__don_vi",
        "nhat_ky__hop_dong__nhom_hd",
        "nhat_ky__phan_cong__tre",
        "nhat_ky__phan_cong__nhom_hd",
        "nhat_ky__phan_cong__phan_bo__can_bo__don_vi",
        "nhat_ky__phan_cong__phan_bo__nhom_hd",
    )
    by_journal = {detail.nhat_ky_id: detail for detail in details}
    missing = [journal.pk for journal in journals if journal.pk not in by_journal]
    if missing:
        raise ValidationError(f"Nhật ký chưa có snapshot phiếu thanh toán: {', '.join(map(str, missing[:10]))}")
    return [PaymentJournalSnapshot(by_journal[journal.pk]) for journal in journals]


def _effective_staff_annotation(queryset):
    return queryset.annotate(
        _effective_staff_id=Case(
            When(can_bo_nguon_id__isnull=False, then=F("can_bo_nguon_id")),
            When(hop_dong__can_bo_id__isnull=False, then=F("hop_dong__can_bo_id")),
            When(phan_cong__phan_bo__can_bo_id__isnull=False, then=F("phan_cong__phan_bo__can_bo_id")),
            default=Value(None),
            output_field=IntegerField(),
        )
    )


class NhatKyQuerySet:
    """Reusable query helpers; kept as a service wrapper to avoid model cycles."""

    @staticmethod
    def with_effective_staff(queryset):
        return _effective_staff_annotation(queryset)

    @staticmethod
    def chua_thanh_toan(queryset):
        active_detail = ChiTietPhieuThanhToan.objects.filter(nhat_ky_id=OuterRef("pk"), hoat_dong=True)
        return _effective_staff_annotation(queryset).annotate(_da_thanh_toan=Exists(active_detail)).filter(
            _da_thanh_toan=False
        )


def lay_cau_hinh_thue(ngay):
    config = CauHinhThue.objects.filter(tu_ngay__lte=ngay).order_by("-tu_ngay", "-id").first()
    if config:
        return config
    logger.warning("Chưa có CauHinhThue hiệu lực tại %s; dùng cấu hình mặc định.", ngay)
    return type(
        "DefaultTaxConfig",
        (),
        {
            "nguong_thue": Decimal(str(FinancialConfig.THUE_TNCN_NGUONG)),
            "ty_le": Decimal(str(FinancialConfig.THUE_TNCN_TY_LE)),
        },
    )()


def kiem_tra_dieu_kien(nhat_ky, kiem_tra_da_thanh_toan=True):
    errors = []
    hop_dong = nhat_ky.hop_dong_hieu_luc
    if not hop_dong:
        errors.append("Nhật ký chưa có hợp đồng")
    elif hop_dong.trang_thai in {"DU_THAO", "HUY", "THANH_LY"}:
        errors.append(f"Hợp đồng {hop_dong.so_hop_dong} đang ở trạng thái không được thanh toán: {hop_dong.trang_thai}")
    # Không dùng getattr(..., default) vì đối số mặc định luôn được tính (thêm truy vấn cho từng nhật ký).
    if hasattr(nhat_ky, "_effective_staff_id"):
        effective_staff_id = nhat_ky._effective_staff_id
    else:
        effective_staff_id = nhat_ky.can_bo_hieu_luc_id
    if not effective_staff_id:
        errors.append("Không xác định được CBCT hiệu lực")
    if nhat_ky.so_buoi_thuc_hien <= 0:
        errors.append("Nhật ký không có số buổi thực hiện hợp lệ")
    if kiem_tra_da_thanh_toan and ChiTietPhieuThanhToan.objects.filter(nhat_ky_id=nhat_ky.pk, hoat_dong=True).exists():
        errors.append("Nhật ký đã nằm trong phiếu thanh toán hiệu lực")
    return errors


def _eligible_journals(can_bo, hop_dong, ky_can_thiep):
    active_detail = ChiTietPhieuThanhToan.objects.filter(nhat_ky_id=OuterRef("pk"), hoat_dong=True)
    queryset = NhatKyThucHien.objects.filter(
        hop_dong=hop_dong,
        ky_can_thiep=ky_can_thiep,
        so_buoi_thuc_hien__gt=0,
    ).select_related(
        "hop_dong", "can_bo_nguon", "phan_cong__tre", "phan_cong__phan_bo__can_bo"
    )
    queryset = NhatKyQuerySet.chua_thanh_toan(queryset).filter(_effective_staff_id=can_bo.pk)
    # queryset đã loại các nhật ký có chi tiết phiếu hiệu lực (Exists ở trên) nên không cần
    # truy vấn .exists() lần nữa cho từng nhật ký.
    return [item for item in queryset if not kiem_tra_dieu_kien(item, kiem_tra_da_thanh_toan=False)]


def tao_phieu_thanh_toan(can_bo, hop_dong, ky_can_thiep, user=None):
    if not can_bo or not hop_dong:
        raise ValidationError("Cần chọn CBCT và hợp đồng để tạo phiếu thanh toán.")
    try:
        with transaction.atomic():
            locked_contract = HopDong.objects.select_for_update().get(pk=hop_dong.pk)
            if locked_contract.trang_thai in {"DU_THAO", "HUY", "THANH_LY"}:
                raise ValidationError("Hợp đồng chưa ở trạng thái được thanh toán.")
            journals = _eligible_journals(can_bo, locked_contract, ky_can_thiep)
            if not journals:
                raise NoEligiblePaymentJournals(
                    "Không có nhật ký mới đủ điều kiện để tạo phiếu thanh toán."
                )

            # Một kỳ chỉ có một phiếu hiệu lực cho mỗi CBCT và hợp đồng.
            same_period = PhieuThanhToan.objects.filter(
                can_bo=can_bo, hop_dong=locked_contract, ky_can_thiep=ky_can_thiep, hoat_dong=True
            ).first()
            if same_period:
                raise ValidationError(
                    f"Kỳ {ky_can_thiep} của hợp đồng {locked_contract.so_hop_dong} đã có phiếu lần {same_period.lan_thanh_toan} "
                    f"({same_period.get_trang_thai_display().lower()}); mỗi kỳ chỉ thanh toán một lần nhưng còn {len(journals)} nhật ký "
                    "chưa được đưa vào phiếu. Chỉ khi phiếu đang chờ chi và là lần mới nhất, hãy hủy phiếu rồi lập lại "
                    "để gộp đủ nhật ký."
                )

            latest_round = PhieuThanhToan.objects.filter(can_bo=can_bo, hop_dong=locked_contract, hoat_dong=True).aggregate(
                value=Max("lan_thanh_toan")
            )["value"] or 0
            payment_round = latest_round + 1
            labor = sum((Decimal(row.so_buoi_thuc_hien) * Decimal(row.don_gia_cong) for row in journals), Decimal("0"))
            travel = sum((Decimal(row.so_luot_di_lai_cbct) * Decimal(row.dinh_muc_di_lai) for row in journals), Decimal("0"))
            tax_config = lay_cau_hinh_thue(timezone.localdate())
            breakdown = calculate_payment_breakdown(labor, travel, tax_config)
            previous_amounts = PhieuThanhToan.objects.filter(hop_dong=locked_contract, hoat_dong=True).aggregate(
                labor=Sum("tong_tien_cong"), travel=Sum("tong_tien_di_lai")
            )
            previous_total = (previous_amounts["labor"] or Decimal("0")) + (previous_amounts["travel"] or Decimal("0"))
            if previous_total + breakdown["tong_truoc_thue"] > Decimal(locked_contract.gia_tri_hop_dong):
                raise ValidationError(
                    f"Tổng thanh toán {previous_total + breakdown['tong_truoc_thue']:,.0f} vượt giá trị hợp đồng {locked_contract.gia_tri_hop_dong:,.0f}."
                )
            voucher = PhieuThanhToan.objects.create(
                can_bo=can_bo,
                hop_dong=locked_contract,
                ky_can_thiep=ky_can_thiep,
                lan_thanh_toan=payment_round,
                tong_tien_cong=breakdown["tien_cong"],
                tong_tien_di_lai=breakdown["tien_di_lai"],
                thue_tncn=breakdown["thue_tncn"],
                thuc_nhan=breakdown["thuc_linh"],
                nguong_thue=Decimal(tax_config.nguong_thue),
                ty_le_thue=Decimal(tax_config.ty_le),
                lap_boi=user,
            )
            ChiTietPhieuThanhToan.objects.bulk_create([
                ChiTietPhieuThanhToan(
                    phieu=voucher,
                    nhat_ky=row,
                    so_buoi=row.so_buoi_thuc_hien,
                    so_luot_di_lai_cbct=row.so_luot_di_lai_cbct,
                    don_gia_cong=row.don_gia_cong,
                    dinh_muc_di_lai=row.dinh_muc_di_lai,
                    tien_cong=Decimal(row.so_buoi_thuc_hien) * Decimal(row.don_gia_cong),
                    tien_di_lai=Decimal(row.so_luot_di_lai_cbct) * Decimal(row.dinh_muc_di_lai),
                )
                for row in journals
            ])
            for row in journals:
                row.lan_thanh_toan = payment_round
            NhatKyThucHien.objects.bulk_update(journals, ["lan_thanh_toan", "updated_at"])
            return voucher
    except IntegrityError as exc:
        raise ValidationError("Đã có phiếu thanh toán cho kỳ hoặc lần thanh toán này.") from exc


def _sync_instance(target, source, fields):
    for name in fields:
        setattr(target, name, getattr(source, name))


def huy_phieu(phieu, ly_do, user=None):
    """Hủy phiếu chờ chi. Trạng thái được đọc lại dưới khóa dòng để không dựa vào đối tượng cũ."""
    updated_fields = ["trang_thai", "hoat_dong", "ly_do_huy", "huy_boi", "ngay_huy", "updated_at"]
    with transaction.atomic():
        locked = PhieuThanhToan.objects.select_for_update().get(pk=phieu.pk)
        if locked.trang_thai == "DA_CHI":
            raise ValidationError("Phiếu đã chi không thể hủy bằng luồng thông thường.")
        if locked.trang_thai != "CHO_CHI":
            raise ValidationError("Chỉ phiếu chờ chi mới được hủy.")
        if not ly_do or not str(ly_do).strip():
            raise ValidationError("Bắt buộc nhập lý do hủy phiếu.")
        latest = PhieuThanhToan.objects.filter(can_bo=locked.can_bo, hop_dong=locked.hop_dong, hoat_dong=True).aggregate(value=Max("lan_thanh_toan"))["value"]
        if latest != locked.lan_thanh_toan:
            raise ValidationError("Chỉ được hủy phiếu có lần thanh toán mới nhất.")
        locked.trang_thai = "HUY"
        locked.hoat_dong = None
        locked.ly_do_huy = str(ly_do).strip()
        locked.huy_boi = user
        locked.ngay_huy = timezone.localdate()
        locked.save(update_fields=updated_fields)
        locked.chi_tiet.update(hoat_dong=None)
    _sync_instance(phieu, locked, updated_fields)
    return phieu


def xac_nhan_chi(phieu, ngay_chi=None, user=None):
    """Xác nhận đã chi. Trạng thái được đọc lại dưới khóa dòng để không ghi đè phiếu vừa bị hủy."""
    updated_fields = ["trang_thai", "ngay_chi", "xac_nhan_chi_boi", "updated_at"]
    with transaction.atomic():
        locked = PhieuThanhToan.objects.select_for_update().get(pk=phieu.pk)
        if locked.trang_thai != "CHO_CHI":
            raise ValidationError("Chỉ phiếu chờ chi mới được xác nhận.")
        locked.trang_thai = "DA_CHI"
        locked.ngay_chi = ngay_chi or timezone.localdate()
        locked.xac_nhan_chi_boi = user
        locked.save(update_fields=updated_fields)
    _sync_instance(phieu, locked, updated_fields)
    return phieu
