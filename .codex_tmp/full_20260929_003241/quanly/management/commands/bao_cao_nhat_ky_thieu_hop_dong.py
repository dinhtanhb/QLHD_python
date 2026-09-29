from django.core.management.base import BaseCommand

from quanly.models import NhatKyThucHien


class Command(BaseCommand):
    help = "Report journals without a current contract; read-only."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=100)

    def handle(self, *args, **options):
        queryset = NhatKyThucHien.objects.filter(hop_dong__isnull=True).select_related("phan_cong__tre")
        total = queryset.count()
        self.stdout.write(self.style.WARNING(f"Journals without contract: {total}"))
        for item in queryset.order_by("ngay_thuc_hien", "id")[: max(options["limit"], 0)]:
            child = getattr(item.phan_cong, "tre", None)
            line = (
                f"#{item.pk} | date={item.ngay_thuc_hien} | period={item.ky_can_thiep} | "
                f"child={getattr(child, 'ma_tre', '-') } | note={item.ghi_chu or '-'}"
            )
            self.stdout.write(line.encode("ascii", "replace").decode("ascii"))
