from django.contrib import admin
from .models import CauHinhThue, ChiTietPhieuThanhToan, DonVi, CanBo, NhomHD, PhieuThanhToan, Tre, Tinh, Xa

admin.site.register(DonVi)
admin.site.register(CanBo)
admin.site.register(NhomHD)
admin.site.register(Tre)
admin.site.register(Tinh)
admin.site.register(Xa)
admin.site.register(CauHinhThue)
admin.site.register(PhieuThanhToan)
admin.site.register(ChiTietPhieuThanhToan)
