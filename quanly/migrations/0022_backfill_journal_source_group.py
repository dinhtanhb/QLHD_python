from django.db import migrations


def backfill_source_group(apps, schema_editor):
    NhatKy = apps.get_model("quanly", "NhatKyThucHien")
    PhanCong = apps.get_model("quanly", "PhanCongTre")
    PhanBo = apps.get_model("quanly", "PhanBoChiTieu")

    allocation_groups = dict(PhanBo.objects.values_list("pk", "nhom_hd_id"))
    assignment_groups = {}
    for assignment_id, group_id, allocation_id in PhanCong.objects.values_list("pk", "nhom_hd_id", "phan_bo_id"):
        assignment_groups[assignment_id] = group_id or allocation_groups.get(allocation_id)
    for journal_id, assignment_id in NhatKy.objects.filter(nhom_hd_nguon__isnull=True).values_list("pk", "phan_cong_id").iterator(chunk_size=2000):
        group_id = assignment_groups.get(assignment_id)
        if group_id:
            NhatKy.objects.filter(pk=journal_id).update(nhom_hd_nguon_id=group_id)


class Migration(migrations.Migration):
    dependencies = [("quanly", "0021_journal_without_contract")]
    operations = [migrations.RunPython(backfill_source_group, migrations.RunPython.noop)]
