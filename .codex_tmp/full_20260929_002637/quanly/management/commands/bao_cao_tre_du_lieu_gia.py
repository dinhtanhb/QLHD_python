from datetime import date

from django.core.management.base import BaseCommand
from django.db.models import Q

from quanly.models import Tre


class Command(BaseCommand):
    help = "Liệt kê trẻ còn dữ liệu giả từ luồng import cũ; không sửa dữ liệu."

    def handle(self, *args, **options):
        rows = Tre.objects.filter(
            Q(ngay_sinh=date(2000, 1, 1)) | Q(ho_ten="Chưa cập nhật")
        ).order_by("ma_tre")
        for child in rows:
            self.stdout.write(f"{child.ma_tre} | {child.ho_ten} | {child.ngay_sinh} | giới tính={child.gioi_tinh}")
        self.stdout.write(self.style.WARNING(f"Tổng: {rows.count()} trẻ cần rà soát."))
