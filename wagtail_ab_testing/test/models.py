from wagtail.models import Page


# TODO: once wagtail 8 is the minimum supported version, make it so we actually
# use a custom base page model instead of subclassing Page directly.
class SimplePage(Page):
    pass
