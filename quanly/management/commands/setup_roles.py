from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group
from django.contrib.auth import get_user_model


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
                        f"Created group: {group_name}"
                    )
                )

        admin_user = get_user_model().objects.filter(username__iexact="admin").first()
        if admin_user:
            changed = []
            if not admin_user.is_active:
                admin_user.is_active = True
                changed.append("is_active")
            if not admin_user.is_staff:
                admin_user.is_staff = True
                changed.append("is_staff")
            if not admin_user.is_superuser:
                admin_user.is_superuser = True
                changed.append("is_superuser")
            if changed:
                admin_user.save(update_fields=changed)
                self.stdout.write(self.style.SUCCESS("Admin account synchronized with full administrator permissions."))
            else:
                self.stdout.write(
                    self.style.WARNING(
                        "Admin account already has full administrator permissions."
                    )
                )

        self.stdout.write(
            self.style.SUCCESS(
                "Role setup completed."
            )
        )
