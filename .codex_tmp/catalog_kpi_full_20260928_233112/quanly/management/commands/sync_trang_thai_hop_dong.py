from django.core.management.base import BaseCommand
from django.db import transaction

from quanly.models import HopDong
from quanly.services.contract_status import desired_trang_thai, sync_trang_thai_hop_dong


class Command(BaseCommand):
    help = "Đồng bộ trạng thái hợp đồng theo nghiệm thu, thanh lý và thời hạn."

    def add_arguments(self, parser):
        mode = parser.add_mutually_exclusive_group()
        mode.add_argument("--dry-run", action="store_true", help="Chỉ liệt kê thay đổi, không ghi dữ liệu.")
        mode.add_argument("--apply", action="store_true", help="Ghi các thay đổi vào cơ sở dữ liệu.")

    def handle(self, *args, **options):
        apply_changes = options["apply"]
        changes = []
        for contract in HopDong.objects.all().iterator():
            before = (contract.trang_thai, contract.is_locked)
            try:
                if apply_changes:
                    with transaction.atomic():
                        sync_trang_thai_hop_dong(contract)
                else:
                    # The service is deliberately not called in dry-run because it saves.
                    target = desired_trang_thai(contract)
                    after = (target, target == "THANH_LY" or contract.is_locked)
                    if after != before:
                        changes.append((contract.so_hop_dong, before, after))
                    continue
            except Exception as exc:
                self.stderr.write(f"{contract.so_hop_dong}: {exc}")
                continue
            after = (contract.trang_thai, contract.is_locked)
            if after != before:
                changes.append((contract.so_hop_dong, before, after))

        for number, before, after in changes:
            self.stdout.write(f"{number}: {before} -> {after}")
        self.stdout.write(self.style.SUCCESS(f"Đã {'áp dụng' if apply_changes else 'phát hiện'} {len(changes)} thay đổi."))
