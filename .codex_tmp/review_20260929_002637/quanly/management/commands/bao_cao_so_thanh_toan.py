from django.core.management.base import BaseCommand
from django.db.models import Sum

from quanly.models import ChiTietPhieuThanhToan, ChiTietThanhToan, PhieuThanhToan


class Command(BaseCommand):
    help = "Đối chiếu sổ thanh toán cũ với sổ thanh toán CBCT mới; chỉ đọc dữ liệu."

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
            f"Sổ cũ: {ChiTietThanhToan.objects.count()} chi tiết, "
            f"{old['tien'] or 0:,.0f} VND theo cột thành tiền."
        )
        self.stdout.write(
            f"Sổ mới: {PhieuThanhToan.objects.filter(hoat_dong=True).count()} phiếu, "
            f"{ChiTietPhieuThanhToan.objects.filter(hoat_dong=True).count()} chi tiết, "
            f"công={new['tien_cong'] or 0:,.0f}, đi lại={new['tien_di_lai'] or 0:,.0f}, "
            f"thuế={new['thue'] or 0:,.0f}, thực nhận={new['thuc_nhan'] or 0:,.0f} VND."
        )
