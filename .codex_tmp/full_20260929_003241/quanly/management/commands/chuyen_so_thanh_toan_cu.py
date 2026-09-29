from collections import defaultdict
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from quanly.financial import calculate_payment_breakdown
from quanly.models import ChiTietPhieuThanhToan, ChiTietThanhToan, PhieuThanhToan
from quanly.services.payment_ledger import lay_cau_hinh_thue


class Command(BaseCommand):
    help = "Migrate the legacy CBCT ledger to the new ledger; dry-run by default."

    def add_arguments(self, parser):
        parser.add_argument("--from", dest="from_date")
        parser.add_argument("--to", dest="to_date")
        parser.add_argument("--force", action="store_true")

    def handle(self, *args, **options):
        queryset = ChiTietThanhToan.objects.select_related(
            "dot_thanh_toan", "nhat_ky__hop_dong", "nhat_ky__phan_cong__phan_bo__can_bo",
            "nhat_ky__can_bo_nguon",
        ).order_by("dot_thanh_toan__ngay_de_nghi", "id")
        groups = defaultdict(list)
        skipped = []
        for detail in queryset:
            dot_date = detail.dot_thanh_toan.ngay_de_nghi
            if options["from_date"] and str(dot_date) < options["from_date"]:
                continue
            if options["to_date"] and str(dot_date) > options["to_date"]:
                continue
            journal = detail.nhat_ky
            contract = journal.hop_dong_hieu_luc or detail.dot_thanh_toan.hop_dong
            staff = journal.can_bo_hieu_luc
            if not contract or not staff:
                skipped.append((detail, "missing current contract or CBCT"))
                continue
            groups[(staff.pk, contract.pk, journal.ky_can_thiep, detail.dot_thanh_toan.pk)].append(detail)

        planned = 0
        created = 0
        for (staff_id, contract_id, ky, dot_id), details in groups.items():
            active = ChiTietPhieuThanhToan.objects.filter(
                nhat_ky_id__in=[item.nhat_ky_id for item in details], hoat_dong=True
            ).exists()
            if active:
                skipped.append((details[0], "already has details in the new voucher"))
                continue
            planned += 1
            if not options["force"]:
                continue
            with transaction.atomic():
                self._create_voucher(staff_id, contract_id, ky, dot_id, details)
                created += 1

        mode = "WRITE" if options["force"] else "DRY-RUN"
        self.stdout.write(self.style.SUCCESS(f"{mode}: planned {planned}, created {created}, skipped {len(skipped)}."))
        for detail, reason in skipped[:100]:
            line = f"Skipped detail #{detail.pk}: {reason}"
            self.stdout.write(line.encode("ascii", "replace").decode("ascii"))

    def _create_voucher(self, staff_id, contract_id, ky, dot_id, details):
        dot = details[0].dot_thanh_toan
        contract = details[0].nhat_ky.hop_dong_hieu_luc or dot.hop_dong
        labor = sum((Decimal(item.so_buoi_thanh_toan) * Decimal(item.nhat_ky.don_gia_cong) for item in details), Decimal("0"))
        travel = sum((Decimal(item.so_luot_di_lai) * Decimal(item.nhat_ky.dinh_muc_di_lai) for item in details), Decimal("0"))
        config = lay_cau_hinh_thue(dot.ngay_de_nghi)
        breakdown = calculate_payment_breakdown(labor, travel, config)
        previous = PhieuThanhToan.objects.filter(can_bo_id=staff_id, hop_dong_id=contract_id).order_by("-lan_thanh_toan").first()
        round_number = (previous.lan_thanh_toan if previous else 0) + 1
        voucher = PhieuThanhToan.objects.create(
            can_bo_id=staff_id,
            hop_dong_id=contract_id,
            ky_can_thiep=ky,
            lan_thanh_toan=round_number,
            tong_tien_cong=breakdown["tien_cong"],
            tong_tien_di_lai=breakdown["tien_di_lai"],
            thue_tncn=breakdown["thue_tncn"],
            thuc_nhan=breakdown["thuc_linh"],
            nguong_thue=Decimal(config.nguong_thue),
            ty_le_thue=Decimal(config.ty_le),
            trang_thai="DA_CHI",
            ngay_lap=dot.ngay_de_nghi,
            ngay_chi=dot.ngay_de_nghi,
            ghi_chu=f"Migrated from legacy ledger #{dot_id}",
        )
        ChiTietPhieuThanhToan.objects.bulk_create([
            ChiTietPhieuThanhToan(
                phieu=voucher,
                nhat_ky=item.nhat_ky,
                so_buoi=item.so_buoi_thanh_toan,
                so_luot_di_lai_cbct=item.so_luot_di_lai,
                don_gia_cong=item.nhat_ky.don_gia_cong,
                dinh_muc_di_lai=item.nhat_ky.dinh_muc_di_lai,
                tien_cong=Decimal(item.so_buoi_thanh_toan) * Decimal(item.nhat_ky.don_gia_cong),
                tien_di_lai=Decimal(item.so_luot_di_lai) * Decimal(item.nhat_ky.dinh_muc_di_lai),
            )
            for item in details
        ])
        return voucher
