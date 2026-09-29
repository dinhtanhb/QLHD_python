from django.db import migrations, models


def copy_assignment_location(apps, schema_editor):
    Journal = apps.get_model("quanly", "NhatKyThucHien")
    pending = []
    for journal in Journal.objects.select_related("phan_cong").iterator(chunk_size=1000):
        journal.dia_diem_ct = journal.phan_cong.dia_diem_ct
        pending.append(journal)
        if len(pending) >= 1000:
            Journal.objects.bulk_update(pending, ["dia_diem_ct"], batch_size=1000)
            pending = []
    if pending:
        Journal.objects.bulk_update(pending, ["dia_diem_ct"], batch_size=1000)


class Migration(migrations.Migration):
    dependencies = [("quanly", "0018_nhatkythuchien_lan_thanh_toan")]

    operations = [
        migrations.AddField(
            model_name="nhatkythuchien",
            name="dia_diem_ct",
            field=models.CharField(blank=True, max_length=100, null=True, verbose_name="Địa điểm can thiệp"),
        ),
        migrations.RunPython(copy_assignment_location, migrations.RunPython.noop),
    ]
