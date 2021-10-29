from django.apps import AppConfig


class WagtailAbTestingAppConfig(AppConfig):
    label = "wagtail_ab_testing"
    name = "wagtail_ab_testing"
    verbose_name = "A/B Testing"
    default_auto_field = "django.db.models.AutoField"
