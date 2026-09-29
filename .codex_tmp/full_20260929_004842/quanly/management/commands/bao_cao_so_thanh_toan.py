from django.core.management.base import BaseCommand
from django.db.models import Sum

from quanly.models import ChiTietPhieuThanhToan, ChiTietThanhToan, PhieuThanhToan


class Command(BaseCommand):
    help = "Compare the legacy payment ledger with the new CBCT ledger; read-only."

    def handle(self, *args, **options):
        old = ChiTietThanhToan.objects.aggregate(tien=Sum("thanh_tien"))
        new = PhieuThanhToan.objects.filter(hoat_dong=True).aggregate(
            so_phieu=Sum("id"),
            tien_cong=Sum("tong_tien_cong"),
            tien_di_lai=Sum("tong_tien_di_lai"),
            thue=Sum("thue_tncn"),
            thuc_nhan=Sum("thuc_nhan"),
        )
        self.stdout.write(
            f"Legacy ledger: {ChiTietThanhToan.objects.count()} details, "
            f"{old['tien'] or 0:,.0f} VND by amount column."
        )
        self.stdout.write(
            f"New ledger: {PhieuThanhToan.objects.filter(hoat_dong=True).count()} vouchers, "
            f"{ChiTietPhieuThanhToan.objects.filter(hoat_dong=True).count()} details, "
            f"labor={new['tien_cong'] or 0:,.0f}, travel={new['tien_di_lai'] or 0:,.0f}, "
            f"tax={new['thue'] or 0:,.0f}, net={new['thuc_nhan'] or 0:,.0f} VND."
        )
