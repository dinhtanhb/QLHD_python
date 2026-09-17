from django.db import migrations, models


AUTO_JOURNAL_NOTE = "Tự tạo từ import nhật ký lịch sử do thiếu phân công đúng dịch vụ."


def mark_technical_assignments(apps, schema_editor):
    PhanCongTre = apps.get_model("quanly", "PhanCongTre")
    PhanCongTre.objects.filter(ghi_chu=AUTO_JOURNAL_NOTE).update(tu_dong_tu_nhat_ky=True)


def unmark_technical_assignments(apps, schema_editor):
    PhanCongTre = apps.get_model("quanly", "PhanCongTre")
    PhanCongTre.objects.filter(ghi_chu=AUTO_JOURNAL_NOTE).update(tu_dong_tu_nhat_ky=False)


class Migration(migrations.Migration):
    dependencies = [
        ("quanly", "0022_backfill_journal_source_group"),
    ]

    operations = [
        migrations.AddField(
            model_name="phancongtre",
            name="tu_dong_tu_nhat_ky",
            field=models.BooleanField(
                db_index=True,
                default=False,
                verbose_name="Phân công kỹ thuật tự tạo từ nhật ký",
            ),
        ),
        migrations.RunPython(mark_technical_assignments, unmark_technical_assignments),
    ]
