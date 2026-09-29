from django.core.management.base import BaseCommand

from quanly.models import NhatKyThucHien


class Command(BaseCommand):
    help = "Báo cáo nhật ký chưa khớp hợp đồng hiện hành; chỉ đọc dữ liệu."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=100)

    def handle(self, *args, **options):
        queryset = NhatKyThucHien.objects.filter(hop_dong__isnull=True).select_related("phan_cong__tre")
        total = queryset.count()
        self.stdout.write(self.style.WARNING(f"Nhật ký thiếu hợp đồng: {total}"))
        for item in queryset.order_by("ngay_thuc_hien", "id")[: max(options["limit"], 0)]:
            child = getattr(item.phan_cong, "tre", None)
            self.stdout.write(
                f"#{item.pk} | ngày={item.ngay_thuc_hien} | kỳ={item.ky_can_thiep} | "
                f"trẻ={getattr(child, 'ma_tre', '-') } | ghi_chú={item.ghi_chu or '-'}"
            )
