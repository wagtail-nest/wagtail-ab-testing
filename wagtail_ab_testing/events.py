from django.utils.translation import gettext_lazy as __
from wagtail import hooks


class BaseEvent:
    """
    A base class for events that are linked to Wagtail pages.
    """

    name = None

    # When False, the user won't be asked to select a goal page
    requires_page = True

    # A list of page model classes that this event can be triggered on.
    # This may be overridden by the .get_page_types() method
    # Leave this as None to allow any page
    page_types = None

    def get_page_types(self):
        """
        Returns a list of page model classes that this event can be triggered on.
        """
        return self.page_types

    def can_be_triggered_on_page_type(self, page_type):
        """
        Returns True if this event can be triggered on an instance of the given page model.
        """
        page_types = self.get_page_types()

        if page_types is None:
            return True

        return page_type in page_types


class VisitPageEvent(BaseEvent):
    """
    Triggered when a user visits a page.
    """

    name = __("Visit page")


# TODO: Find a way to hook this into Wagtail
# from wagtail.contrib.forms.utils import get_form_types
# class SubmitFormPageEvent(BaseEvent):
#     """
#     Triggered when a user submits a form page.
#     """
#     name = __("Submit form page")

#     def get_page_types(self):
#         return [
#             ct.model_class()
#             for ct in get_form_types()
#         ]


BUILTIN_EVENT_TYPES = {
    "visit-page": VisitPageEvent(),
    # 'submit-form': SubmitFormPageEvent(),
}


def get_event_types():
    event_types = {}
    event_types.update(BUILTIN_EVENT_TYPES)

    for fn in hooks.get_hooks("register_ab_testing_event_types"):
        event_types.update(fn())

    return event_types
