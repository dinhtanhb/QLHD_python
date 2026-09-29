from django.core.management.base import BaseCommand

from quanly.models import NhatKyThucHien


class Command(BaseCommand):
    help = "Rebuild travel counts and duplicate-warning flags for intervention journals."

    def add_arguments(self, parser):
        parser.add_argument(
            "--date",
            dest="date_value",
            help="Rebuild one day only, using YYYY-MM-DD.",
        )

    def handle(self, *args, **options):
        date_value = options.get("date_value")
        if date_value:
            dates = [date_value]
        else:
            dates = list(NhatKyThucHien.objects.dates("ngay_thuc_hien", "day", order="ASC"))

        for value in dates:
            NhatKyThucHien.recalculate_day(value)

        self.stdout.write(
            self.style.SUCCESS(
                f"Rebuilt {len(dates)} day(s); "
                f"{NhatKyThucHien.objects.filter(canh_bao_trung=True).count()} journal(s) have duplicate warnings."
            )
        )
