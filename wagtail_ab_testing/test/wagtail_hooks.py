from wagtail import VERSION as WAGTAIL_VERSION

if WAGTAIL_VERSION >= (3, 0):
    from wagtail import hooks
else:
    from wagtail.core import hooks
    
from wagtail_ab_testing.events import BaseEvent


class GlobalEvent(BaseEvent):
    name = "Global Event"
    requires_page = False


@hooks.register('register_ab_testing_event_types')
def register_submit_form_event_type():
    return {
        'global-event': GlobalEvent(),
    }
