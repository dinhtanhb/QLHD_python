import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'qlhd.settings')
django.setup()

from quanly.models import Tinh, Xa

print("Đang khởi tạo dữ liệu Tỉnh và Xã...")

# Tạo Tỉnh Đồng Nai
tinh_dn, created = Tinh.objects.get_or_create(
    ma_tinh='DNN', 
    defaults={'ten_tinh': 'Đồng Nai'}
)

# Danh sách 95 Xã/Phường
danh_sach_xa = [
    ("X01", "Bình Phước"), ("X02", "Đồng Xoài"), ("X03", "Bình Long"), ("X04", "An Lộc"), 
    ("X05", "Chơn Thành"), ("X06", "Minh Hưng"), ("X07", "Nha Bích"), ("X08", "Phước Long"), 
    ("X09", "Phước Bình"), ("X10", "Bù Đăng"), ("X11", "Đak Nhau"), ("X12", "Thọ Sơn"),
    ("X13", "Bom Bo"), ("X14", "Nghĩa Trung"), ("X15", "Phước Sơn"), ("X16", "Thiện Hưng"), 
    ("X17", "Hưng Phước"), ("X18", "Tân Tiến"), ("X19", "Bù Gia Mập"), ("X20", "Đăk Ơ"), 
    ("X21", "Đa Kia"), ("X22", "Phú Nghĩa"), ("X23", "Đồng Phú"), ("X24", "Tân Lợi"),
    ("X25", "Thuận Lợi"), ("X26", "Đồng Tâm"), ("X27", "Tân Hưng"), ("X28", "Minh Đức"), 
    ("X29", "Tân Quan"), ("X30", "Tân Khai"), ("X31", "Lộc Ninh"), ("X32", "Lộc Tấn"), 
    ("X33", "Lộc Thạnh"), ("X34", "Lộc Quang"), ("X35", "Lộc Thành"), ("X36", "Lộc Hưng"),
    ("X37", "Bình Tân"), ("X38", "Phú Riềng"), ("X39", "Long Hà"), ("X40", "Phú Trung"), 
    ("X41", "Trảng Dài"), ("X42", "Hố Nai"), ("X43", "Tam Hiệp"), ("X44", "Long Bình"), 
    ("X45", "Trấn Biên"), ("X46", "Biên Hòa"), ("X47", "Tam Phước"), ("X48", "Phước Tân"),
    ("X49", "Long Hưng"), ("X50", "Long Khánh"), ("X51", "Bình Lộc"), ("X52", "Bảo Vinh"), 
    ("X53", "Xuân Lập"), ("X54", "Hàng Gòn"), ("X55", "Xuân Quế"), ("X56", "Cẩm Mỹ"), 
    ("X57", "Xuân Đường"), ("X58", "Xuân Đông"), ("X59", "Sông Ray"), ("X60", "Định Quán"),
    ("X61", "Thanh Sơn"), ("X62", "Phú Vinh"), ("X63", "Phú Hòa"), ("X64", "La Ngà"), 
    ("X65", "Long Thành"), ("X66", "An Phước"), ("X67", "Bình An"), ("X68", "Long Phước"), 
    ("X69", "Phước Thái"), ("X70", "Nhơn Trạch"), ("X71", "Đại Phước"), ("X72", "Phước An"),
    ("X73", "Tân Phú"), ("X74", "Đak Lua"), ("X75", "Cát Tiên"), ("X76", "Tà Lài"), 
    ("X77", "Phú Lâm"), ("X78", "Thống Nhất"), ("X79", "Gia Kiệm"), ("X80", "Dầu Giây"), 
    ("X81", "Trảng Bom"), ("X82", "Bàu Hàm"), ("X83", "Bình Minh"), ("X84", "Hưng Thịnh"), 
    ("X85", "An Viễn"), ("X86", "Trị An"), ("X87", "Phú Lý"), ("X88", "Tân An"), 
    ("X89", "Tân Triều"), ("X90", "Xuân Lộc"), ("X91", "Xuân Bắc"), ("X92", "Xuân Thành"), 
    ("X93", "Xuân Hòa"), ("X94", "Xuân Phú"), ("X95", "Xuân Định")
]

for ma, ten in danh_sach_xa:
    Xa.objects.get_or_create(
        ma_xa=ma,
        defaults={'ten_xa': ten, 'tinh': tinh_dn}
    )

print("Đã nạp thành công Đồng Nai và 95 xã/phường vào hệ thống!")