from django.db import migrations, models
import django.db.models.deletion


def backfill_source_staff(apps, schema_editor):
    PhanCongTre = apps.get_model("quanly", "PhanCongTre")
    assignments = PhanCongTre.objects.filter(
        can_bo_nguon__isnull=True,
        phan_bo__can_bo__isnull=False,
    ).select_related("phan_bo")
    pending = []
    for assignment in assignments.iterator(chunk_size=1000):
        assignment.can_bo_nguon_id = assignment.phan_bo.can_bo_id
        pending.append(assignment)
        if len(pending) >= 1000:
            PhanCongTre.objects.bulk_update(pending, ["can_bo_nguon"])
            pending.clear()
    if pending:
        PhanCongTre.objects.bulk_update(pending, ["can_bo_nguon"])


class Migration(migrations.Migration):
    dependencies = [
        ("quanly", "0023_phancongtre_tu_dong_tu_nhat_ky"),
    ]

    operations = [
        migrations.AddField(
            model_name="phancongtre",
            name="can_bo_nguon",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="phan_cong_theo_nguon",
                to="quanly.canbo",
                verbose_name="CBCT theo dữ liệu nguồn",
            ),
        ),
        migrations.RunPython(backfill_source_staff, migrations.RunPython.noop),
    ]
