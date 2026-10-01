from collections import defaultdict
from datetime import date
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError, transaction
from django.db.models import Max

from quanly.financial import calculate_payment_breakdown
from quanly.models import ChiTietPhieuThanhToan, ChiTietThanhToan, HopDong, NhatKyThucHien, PhieuThanhToan
from quanly.services.payment_ledger import lay_cau_hinh_thue


class Command(BaseCommand):
    help = "Migrate the legacy CBCT ledger to the new ledger; dry-run by default."

    def add_arguments(self, parser):
        parser.add_argument("--from", dest="from_date")
        parser.add_argument("--to", dest="to_date")
        parser.add_argument("--force", action="store_true")

    def handle(self, *args, **options):
        bounds = {}
        for key in ("from_date", "to_date"):
            try:
                bounds[key] = date.fromisoformat(options[key]) if options[key] else None
            except (ValueError, TypeError) as exc:
                raise CommandError("Date bounds must use YYYY-MM-DD.") from exc
        if bounds["from_date"] and bounds["to_date"] and bounds["from_date"] > bounds["to_date"]:
            raise CommandError("--from must not be after --to.")
        queryset = ChiTietThanhToan.objects.select_related(
            "dot_thanh_toan__hop_dong", "nhat_ky__hop_dong__can_bo",
            "nhat_ky__phan_cong__phan_bo__can_bo", "nhat_ky__can_bo_nguon",
        ).order_by("dot_thanh_toan__ngay_de_nghi", "id")
        if bounds["from_date"]:
            queryset = queryset.filter(dot_thanh_toan__ngay_de_nghi__gte=bounds["from_date"])
        if bounds["to_date"]:
            queryset = queryset.filter(dot_thanh_toan__ngay_de_nghi__lte=bounds["to_date"])
        try:
            with transaction.atomic():
                # Use the same parent lock as normal voucher creation. All writes
                # share one transaction, including failures in a later group.
                if options["force"]:
                    journal_ids = queryset.values_list("nhat_ky_id", flat=True)
                    locked_journal_ids = list(NhatKyThucHien.objects.filter(pk__in=journal_ids).order_by("pk").select_for_update().values_list("pk", flat=True))
                    queryset = queryset.filter(nhat_ky_id__in=locked_journal_ids)
                    contract_ids = queryset.values_list("dot_thanh_toan__hop_dong_id", flat=True).distinct()
                    list(HopDong.objects.filter(pk__in=contract_ids).order_by("pk").select_for_update())
                details = list(queryset)
                plans, skipped, conflicts = self._preflight(details)
                self.stdout.write(
                    f"{'WRITE' if options['force'] else 'DRY-RUN'}: selected {len(details)} details, "
                    f"planned {len(plans)} vouchers / {sum(len(items) for _, items in plans)} details, "
                    f"skipped {len(skipped)} details, conflicted {len(conflicts)} details."
                )
                for detail, reason in skipped + conflicts:
                    self.stdout.write(f"Detail #{detail.pk}: {reason}")
                if conflicts and options["force"]:
                    raise CommandError("Conversion blocked by preflight conflicts; no data written.")
                created = 0
                if options["force"]:
                    for key, items in plans:
                        self._create_voucher(*key, items)
                        created += 1
                self.stdout.write(self.style.SUCCESS(f"Created {created} vouchers."))
        except IntegrityError as exc:
            raise CommandError("Conversion conflicted with an existing voucher; all writes rolled back.") from exc

    def _preflight(self, details):
        groups = defaultdict(list)
        skipped, conflicts = [], []
        active = set(ChiTietPhieuThanhToan.objects.filter(
            nhat_ky_id__in=[item.nhat_ky_id for item in details], hoat_dong=True,
        ).values_list("nhat_ky_id", flat=True))
        for detail in details:
            journal, dot = detail.nhat_ky, detail.dot_thanh_toan
            contract = journal.hop_dong_hieu_luc
            staff = journal.can_bo_hieu_luc
            if not contract or not staff:
                conflicts.append((detail, "missing current contract or CBCT"))
                continue
            if contract.pk != dot.hop_dong_id:
                conflicts.append((detail, "journal contract differs from legacy payment contract"))
                continue
            groups[(staff.pk, contract.pk, journal.ky_can_thiep, dot.pk)].append(detail)

        period_groups = defaultdict(list)
        for key in groups:
            period_groups[key[:3]].append(key)
        plans = []
        for key, items in groups.items():
            staff_id, contract_id, ky, _dot_id = key
            existing = [item for item in items if item.nhat_ky_id in active]
            if len(existing) == len(items):
                skipped.extend((item, "already has an active voucher detail") for item in items)
                continue
            reason = None
            if existing:
                reason = "legacy group is partially converted; reconcile all details before conversion"
            elif len(period_groups[key[:3]]) > 1:
                reason = "multiple legacy batches share one CBCT/contract/period; cannot merge historical payments automatically"
            elif PhieuThanhToan.objects.filter(can_bo_id=staff_id, hop_dong_id=contract_id, ky_can_thiep=ky, hoat_dong=True).exists():
                reason = "an active voucher already exists for this CBCT/contract/period"
            elif not 1 <= ky <= 30:
                reason = "intervention period must be between 1 and 30"
            # Only the pending legacy state is defined by the CBCT model.
            # A request date is not evidence of actual disbursement.
            elif items[0].dot_thanh_toan.trang_thai != "CHO_THANH_TOAN":
                reason = "legacy payment status has no verified mapping; confirm status/date before conversion"
            elif any(item.so_buoi_thanh_toan <= 0 or item.so_buoi_thanh_toan > item.nhat_ky.so_buoi_thuc_hien
                     or item.so_luot_di_lai > item.nhat_ky.so_luot_di_lai_cbct for item in items):
                reason = "legacy payment quantities differ from valid journal quantities"
            elif any(item.so_buoi_thanh_toan < item.nhat_ky.so_buoi_thuc_hien
                     or item.so_luot_di_lai < item.nhat_ky.so_luot_di_lai_cbct for item in items):
                reason = "legacy payment covers only part of a journal; reconcile remaining sessions/travel before conversion"
            elif any(item.thanh_tien != item.tien_cong + item.tien_di_lai for item in items):
                reason = "stored legacy amount differs from current journal rates; historical rates need reconciliation"
            if reason:
                conflicts.extend((item, reason) for item in items)
            else:
                plans.append((key, items))
        return plans, skipped, conflicts

    def _create_voucher(self, staff_id, contract_id, ky, dot_id, details):
        dot = details[0].dot_thanh_toan
        labor = sum((item.tien_cong for item in details), Decimal("0"))
        travel = sum((item.tien_di_lai for item in details), Decimal("0"))
        config = lay_cau_hinh_thue(dot.ngay_de_nghi)
        breakdown = calculate_payment_breakdown(labor, travel, config)
        previous = PhieuThanhToan.objects.filter(can_bo_id=staff_id, hop_dong_id=contract_id, hoat_dong=True).aggregate(value=Max("lan_thanh_toan"))["value"] or 0
        voucher = PhieuThanhToan.objects.create(
            can_bo_id=staff_id, hop_dong_id=contract_id, ky_can_thiep=ky, lan_thanh_toan=previous + 1,
            tong_tien_cong=breakdown["tien_cong"], tong_tien_di_lai=breakdown["tien_di_lai"],
            thue_tncn=breakdown["thue_tncn"], thuc_nhan=breakdown["thuc_linh"],
            nguong_thue=Decimal(config.nguong_thue), ty_le_thue=Decimal(config.ty_le),
            trang_thai="CHO_CHI", ngay_lap=dot.ngay_de_nghi, ngay_chi=None,
            ghi_chu=f"Migrated from legacy ledger #{dot_id}; legacy status {dot.trang_thai}",
        )
        ChiTietPhieuThanhToan.objects.bulk_create([
            ChiTietPhieuThanhToan(
                phieu=voucher, nhat_ky=item.nhat_ky, so_buoi=item.so_buoi_thanh_toan,
                so_luot_di_lai_cbct=item.so_luot_di_lai, don_gia_cong=item.nhat_ky.don_gia_cong,
                dinh_muc_di_lai=item.nhat_ky.dinh_muc_di_lai, tien_cong=item.tien_cong, tien_di_lai=item.tien_di_lai,
            ) for item in details
        ])
        return voucher
