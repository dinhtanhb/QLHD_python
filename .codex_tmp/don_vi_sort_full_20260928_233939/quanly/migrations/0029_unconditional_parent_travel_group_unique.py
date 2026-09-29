from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("quanly", "0028_dotthanhtoanphuhuynh_group_scope")]

    operations = [
        migrations.RemoveConstraint(
            model_name="dotthanhtoandilaiphuhuynh",
            name="uq_dottt_phuhuynh_nhom_ky_nam_thang",
        ),
        migrations.AddConstraint(
            model_name="dotthanhtoandilaiphuhuynh",
            constraint=models.UniqueConstraint(
                fields=("nhom_hd", "ky_can_thiep", "nam", "thang"),
                name="uq_dottt_phuhuynh_nhom_ky_nam_thang",
            ),
        ),
    ]
