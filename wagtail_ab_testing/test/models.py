try:
    from wagtail.models import Page
except ImportError:
    from wagtail.core.models import Page


class SimplePage(Page):
    pass
