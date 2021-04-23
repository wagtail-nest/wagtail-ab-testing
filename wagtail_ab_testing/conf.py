from django.conf import settings


def get_conf():
    config = getattr(settings, 'WAGTAIL_AB_TESTING', {}).copy()
    config.setdefault('MODE', 'internal')
    return config
