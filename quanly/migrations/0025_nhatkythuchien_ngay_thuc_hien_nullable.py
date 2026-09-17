from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("quanly", "0024_phancongtre_can_bo_nguon"),
    ]

    operations = [
        migrations.AlterField(
            model_name="nhatkythuchien",
            name="ngay_thuc_hien",
            field=models.DateField(blank=True, null=True, verbose_name="Ngày thực hiện"),
        ),
    ]
