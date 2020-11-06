from django.utils.translation import gettext_lazy as __
from wagtail.contrib.forms.utils import get_form_types


class BaseEvent:
    """
    A base class for events that are linked to Wagtail pages.
    """
    name = None

    # A list of page model classes that this event can be triggered on.
    # This may be overridden by the .get_page_types() method
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


class SubmitFormPageEvent(BaseEvent):
    """
    Triggered when a user submits a form page.
    """
    name = __("Submit form page")

    def get_page_types(self):
        return [
            ct.model_class()
            for ct in get_form_types()
        ]


EVENT_TYPES = {
    'visit-page': VisitPageEvent(),
    'submit-form': SubmitFormPageEvent(),
}
