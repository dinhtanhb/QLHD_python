from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("quanly", "0025_nhatkythuchien_ngay_thuc_hien_nullable"),
    ]

    operations = [
        migrations.AlterField(
            model_name="hopdong",
            name="can_bo",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="hop_dong",
                to="quanly.canbo",
                verbose_name="Cán bộ can thiệp",
            ),
        ),
        migrations.AlterField(
            model_name="hopdong",
            name="de_xuat",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="hop_dong",
                to="quanly.dexuathopdong",
                verbose_name="Đề xuất hợp đồng",
            ),
        ),
        migrations.AddField(
            model_name="hopdong",
            name="don_vi",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="hop_dong",
                to="quanly.donvi",
                verbose_name="Đơn vị ký hợp đồng",
            ),
        ),
        migrations.AddConstraint(
            model_name="hopdong",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(can_bo__isnull=False, don_vi__isnull=True)
                    | models.Q(can_bo__isnull=True, don_vi__isnull=False)
                ),
                name="ck_hd_mot_doi_tac",
            ),
        ),
    ]
