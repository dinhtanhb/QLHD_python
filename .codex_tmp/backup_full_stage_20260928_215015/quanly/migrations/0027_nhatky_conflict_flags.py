from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("quanly", "0026_hopdong_don_vi")]

    operations = [
        migrations.AddField(
            model_name="nhatkythuchien",
            name="canh_bao_trung",
            field=models.BooleanField(
                db_index=True,
                default=False,
                verbose_name="Có cảnh báo trùng",
            ),
        ),
        migrations.AddField(
            model_name="nhatkythuchien",
            name="chi_tiet_trung",
            field=models.TextField(
                blank=True,
                default="",
                verbose_name="Chi tiết cảnh báo trùng",
            ),
        ),
    ]
