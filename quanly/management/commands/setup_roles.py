from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group


class Command(BaseCommand):
    help = "Tạo các nhóm quyền mặc định của hệ thống QLHD"

    def handle(self, *args, **kwargs):

        groups = [
            "Admin",
            "DieuPhoiVien",
            "CBDA",
            "KeToan",
        ]

        for group_name in groups:
            group, created = Group.objects.get_or_create(
                name=group_name
            )

            if created:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Đã tạo group: {group_name}"
                    )
                )
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f"Đã tồn tại group: {group_name}"
                    )
                )

        self.stdout.write(
            self.style.SUCCESS(
                "Hoàn tất khởi tạo nhóm quyền."
            )
        )