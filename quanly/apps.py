from django.apps import AppConfig


class QuanlyConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'quanly'

    def ready(self):
        from . import signals  # noqa: F401
        from . import model_compat  # noqa: F401
