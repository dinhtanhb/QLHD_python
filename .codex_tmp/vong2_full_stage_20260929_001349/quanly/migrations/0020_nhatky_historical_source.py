from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("quanly", "0019_nhatkythuchien_dia_diem_ct")]

    operations = [
        migrations.AddField(
            model_name="nhatkythuchien",
            name="du_lieu_lich_su",
            field=models.BooleanField(default=False, verbose_name="Dữ liệu lịch sử"),
        ),
        migrations.AddField(
            model_name="nhatkythuchien",
            name="nhom_hd_nguon",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="nhat_ky_lich_su",
                to="quanly.nhomhd",
                verbose_name="Nhóm HĐ theo dữ liệu nguồn",
            ),
        ),
    ]
