from django.core.management.base import BaseCommand
from django.db.models import Q

from quanly.models import NghiemThu, ThanhLyHopDong


class Command(BaseCommand):
    help = "Liệt kê hồ sơ nghiệm thu/thanh lý còn rỗng để duyệt thủ công; không xóa dữ liệu."

    def handle(self, *args, **options):
        acceptances = NghiemThu.objects.filter(
            Q(ngay_nghiem_thu__isnull=True)
            | Q(bien_ban_so__isnull=True)
            | Q(bien_ban_so="")
            | Q(gia_tri_nghiem_thu=0)
        ).select_related("hop_dong")
        liquidations = ThanhLyHopDong.objects.filter(
            Q(ngay_thanh_ly__isnull=True)
            | Q(bien_ban_so__isnull=True)
            | Q(bien_ban_so="")
            | Q(gia_tri_thanh_ly=0)
        ).select_related("hop_dong")
        acceptance_count = 0
        liquidation_count = 0
        for record in acceptances:
            acceptance_count += 1
            self.stdout.write(
                f"NGHIEM_THU #{record.pk} | HĐ {record.hop_dong.so_hop_dong} | "
                f"ngày={record.ngay_nghiem_thu or '-'} | biên bản={record.bien_ban_so or '-'} | giá trị={record.gia_tri_nghiem_thu}"
            )
        for record in liquidations:
            liquidation_count += 1
            self.stdout.write(
                f"THANH_LY #{record.pk} | HĐ {record.hop_dong.so_hop_dong} | "
                f"ngày={record.ngay_thanh_ly or '-'} | biên bản={record.bien_ban_so or '-'} | giá trị={record.gia_tri_thanh_ly}"
            )
        self.stdout.write(self.style.WARNING(f"Tổng: {acceptance_count} nghiệm thu rỗng, {liquidation_count} thanh lý rỗng."))
