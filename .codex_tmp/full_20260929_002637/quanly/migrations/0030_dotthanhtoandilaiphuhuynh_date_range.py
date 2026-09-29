from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("quanly", "0029_unconditional_parent_travel_group_unique")]

    operations = [
        migrations.AddField(
            model_name="dotthanhtoandilaiphuhuynh",
            name="tu_ngay",
            field=models.DateField(blank=True, null=True, verbose_name="Từ ngày hồ sơ"),
        ),
        migrations.AddField(
            model_name="dotthanhtoandilaiphuhuynh",
            name="den_ngay",
            field=models.DateField(blank=True, null=True, verbose_name="Đến ngày hồ sơ"),
        ),
    ]
