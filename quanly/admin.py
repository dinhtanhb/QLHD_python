from django.contrib import admin
from .models import CauHinhThue, ChiTietPhieuThanhToan, DonVi, CanBo, NhomHD, PhieuThanhToan, Tre, Tinh, Xa

admin.site.register(DonVi)
admin.site.register(CanBo)
admin.site.register(NhomHD)
admin.site.register(Tre)
admin.site.register(Tinh)
admin.site.register(Xa)
admin.site.register(CauHinhThue)


class ReadOnlyPaymentAdmin(admin.ModelAdmin):
    """Phiếu và chi tiết chỉ thay đổi qua luồng thanh toán có kiểm tra đối chiếu."""

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


admin.site.register(PhieuThanhToan, ReadOnlyPaymentAdmin)
admin.site.register(ChiTietPhieuThanhToan, ReadOnlyPaymentAdmin)
