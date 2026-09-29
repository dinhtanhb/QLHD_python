from django.db import migrations


def recalculate_journal_amounts(apps, schema_editor):
    Journal = apps.get_model("quanly", "NhatKyThucHien")
    for journal in Journal.objects.select_related("hop_dong", "phan_cong").all().iterator(chunk_size=1000):
        is_cs = journal.phan_cong.loai_dich_vu in {"CSXH", "CSYT"}
        journal.dinh_muc_di_lai = journal.hop_dong.dinh_muc_di_lai_cs if is_cs else journal.hop_dong.dinh_muc_di_lai_phcn
        journal.thanh_tien = (journal.so_buoi_thuc_hien * journal.don_gia_cong) + (journal.so_luot_di_lai * journal.dinh_muc_di_lai)
        Journal.objects.filter(pk=journal.pk).update(dinh_muc_di_lai=journal.dinh_muc_di_lai, thanh_tien=journal.thanh_tien)


class Migration(migrations.Migration):
    dependencies = [("quanly", "0014_phancongtre_cbda_quan_ly_phancongtre_nhom_hd_and_more")]
    operations = [migrations.RunPython(recalculate_journal_amounts, migrations.RunPython.noop)]
