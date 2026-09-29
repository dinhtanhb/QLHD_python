from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("quanly", "0027_nhatky_conflict_flags")]

    operations = [
        migrations.AddField(
            model_name="dotthanhtoandilaiphuhuynh",
            name="ky_can_thiep",
            field=models.PositiveIntegerField(blank=True, null=True, verbose_name="Kỳ can thiệp"),
        ),
        migrations.AddField(
            model_name="dotthanhtoandilaiphuhuynh",
            name="nhom_hd",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="dot_thanh_toan_di_lai_phu_huynh",
                to="quanly.nhomhd",
                verbose_name="Nhóm hợp đồng",
            ),
        ),
        migrations.AlterField(
            model_name="dotthanhtoandilaiphuhuynh",
            name="hop_dong",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="dot_thanh_toan_phu_huynh",
                to="quanly.hopdong",
                verbose_name="Hợp đồng",
            ),
        ),
        migrations.AddConstraint(
            model_name="dotthanhtoandilaiphuhuynh",
            constraint=models.UniqueConstraint(
                condition=models.Q(hop_dong__isnull=True),
                fields=("nhom_hd", "ky_can_thiep", "nam", "thang"),
                name="uq_dottt_phuhuynh_nhom_ky_nam_thang",
            ),
        ),
        migrations.AddConstraint(
            model_name="dotthanhtoandilaiphuhuynh",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(hop_dong__isnull=False, nhom_hd__isnull=True, ky_can_thiep__isnull=True)
                    | models.Q(hop_dong__isnull=True, nhom_hd__isnull=False, ky_can_thiep__isnull=False)
                ),
                name="ck_dottt_phuhuynh_scope",
            ),
        ),
    ]
