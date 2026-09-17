from django.db import migrations, models
import django.db.models.deletion


def repair_historical_journals(apps, schema_editor):
    NhatKy = apps.get_model("quanly", "NhatKyThucHien")
    HopDong = apps.get_model("quanly", "HopDong")
    PhanCong = apps.get_model("quanly", "PhanCongTre")
    PhanBo = apps.get_model("quanly", "PhanBoChiTieu")

    valid_contracts = set(HopDong.objects.values_list("pk", flat=True))
    allocation_staff = dict(PhanBo.objects.values_list("pk", "can_bo_id"))
    assignments = {
        assignment_id: allocation_staff.get(allocation_id)
        for assignment_id, allocation_id in PhanCong.objects.values_list("pk", "phan_bo_id")
    }
    contract_staff = dict(HopDong.objects.values_list("pk", "can_bo_id"))
    for journal in NhatKy.objects.all().iterator(chunk_size=2000):
        updates = {"can_bo_nguon_id": contract_staff.get(journal.hop_dong_id) or assignments.get(journal.phan_cong_id)}
        if journal.hop_dong_id not in valid_contracts:
            updates["hop_dong_id"] = None
            updates["du_lieu_lich_su"] = True
        NhatKy.objects.filter(pk=journal.pk).update(**updates)


class Migration(migrations.Migration):
    dependencies = [("quanly", "0020_nhatky_historical_source")]

    operations = [
        migrations.AddField(
            model_name="nhatkythuchien",
            name="can_bo_nguon",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="nhat_ky_lich_su",
                to="quanly.canbo",
                verbose_name="CBCT theo dữ liệu nguồn",
            ),
        ),
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql="ALTER TABLE quanly_nhatkythuchien MODIFY hop_dong_id bigint NULL",
                    reverse_sql=migrations.RunSQL.noop,
                ),
            ],
            state_operations=[
                migrations.AlterField(
                    model_name="nhatkythuchien",
                    name="hop_dong",
                    field=models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="nhat_ky_thuc_hien",
                        to="quanly.hopdong",
                        verbose_name="Hợp đồng",
                    ),
                ),
            ],
        ),
        migrations.RunPython(repair_historical_journals, migrations.RunPython.noop),
    ]
