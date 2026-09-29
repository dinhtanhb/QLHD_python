from decimal import Decimal

import django.db.models.deletion
from django.db import migrations, models
from django.utils import timezone


class Migration(migrations.Migration):
    dependencies = [("quanly", "0030_dotthanhtoandilaiphuhuynh_date_range")]

    operations = [
        migrations.AddField(
            model_name="phuluchopdong",
            name="den_ngay_cu",
            field=models.DateField(blank=True, null=True, verbose_name="Ngày kết thúc cũ"),
        ),
        migrations.AddField(
            model_name="phuluchopdong",
            name="den_ngay_moi",
            field=models.DateField(blank=True, null=True, verbose_name="Ngày kết thúc mới"),
        ),
        migrations.AddField(
            model_name="phuluchopdong",
            name="tong_tien_moi",
            field=models.DecimalField(decimal_places=0, default=Decimal("0"), max_digits=18, verbose_name="Giá trị sau điều chỉnh"),
        ),
        migrations.AddField(
            model_name="phuluchopdong",
            name="tong_tien_tang_them",
            field=models.DecimalField(decimal_places=0, default=Decimal("0"), max_digits=18, verbose_name="Giá trị tăng thêm"),
        ),
        migrations.AlterField(
            model_name="phuluchopdong",
            name="loai_phu_luc",
            field=models.CharField(
                choices=[
                    ("KY_1", "Phụ lục phân công Kỳ 1"),
                    ("BO_SUNG", "Phụ lục bổ sung"),
                    ("DIEU_CHINH", "Phụ lục điều chỉnh"),
                    ("GIA_HAN_THOI_GIAN", "Gia hạn thời gian"),
                    ("GIA_HAN_KHOI_LUONG", "Gia hạn khối lượng"),
                    ("KHAC", "Phụ lục khác"),
                ],
                max_length=20,
                verbose_name="Loại phụ lục",
            ),
        ),
        migrations.CreateModel(
            name="ChiTietGiaHanKhoiLuong",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Ngày tạo")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Ngày cập nhật")),
                ("loai_dich_vu", models.CharField(choices=[("VLTL", "Vật lý trị liệu"), ("HDTL", "Hoạt động trị liệu"), ("NNTL", "Ngôn ngữ trị liệu"), ("GDDB", "Giáo dục đặc biệt"), ("CSXH", "Chăm sóc xã hội"), ("CSYT", "Chăm sóc y tế")], max_length=10, verbose_name="Loại dịch vụ")),
                ("so_tre_cu", models.PositiveIntegerField(default=0, verbose_name="Số trẻ cũ")),
                ("so_tre_moi", models.PositiveIntegerField(default=0, verbose_name="Số trẻ sau điều chỉnh")),
                ("so_buoi_cu", models.PositiveIntegerField(default=0, verbose_name="Số buổi cũ")),
                ("so_buoi_moi", models.PositiveIntegerField(default=0, verbose_name="Số buổi sau điều chỉnh")),
                ("don_gia_cong", models.DecimalField(decimal_places=0, default=Decimal("0"), max_digits=12, verbose_name="Đơn giá công")),
                ("dinh_muc_di_lai", models.DecimalField(decimal_places=0, default=Decimal("0"), max_digits=12, verbose_name="Định mức đi lại")),
                ("thanh_tien", models.DecimalField(decimal_places=0, default=Decimal("0"), max_digits=18, verbose_name="Thành tiền")),
                ("phu_luc", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="chi_tiet_gia_han_khoi_luong", to="quanly.phuluchopdong", verbose_name="Phụ lục")),
            ],
            options={
                "constraints": [models.UniqueConstraint(fields=("phu_luc", "loai_dich_vu"), name="uq_gia_han_khoi_luong_dv")],
            },
        ),
    ]
