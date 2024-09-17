from django import template
from django.urls import reverse

from wagtail_ab_testing.models import AbTest
from wagtail_ab_testing.utils import request_is_trackable

register = template.Library()


@register.inclusion_tag("wagtail_ab_testing/script.html", takes_context=True)
def wagtail_ab_testing_script(context):
    request = context["request"]
    serving_variant = getattr(request, "wagtail_ab_testing_serving_variant", False)

    track = request_is_trackable(request)
    if not track:
        return {
            "track": False,
            "tracking_parameters": None,
        }

    register_participant_url = reverse("wagtail_ab_testing:register_participant")
    goal_reached_url = reverse("wagtail_ab_testing:goal_reached")

    tracking_parameters = {
        "urls": {
            "registerParticipant": register_participant_url,
            "goalReached": goal_reached_url,
        },
    }

    page = context.get("page", None)
    page_id = page.id if page else None
    if page_id:
        tracking_parameters["pageId"] = page_id

    version = AbTest.VERSION_VARIANT if serving_variant else AbTest.VERSION_CONTROL
    test = getattr(request, "wagtail_ab_testing_test", None)

    if test and version:
        tracking_parameters["testId"] = test.id
        tracking_parameters["version"] = version
        tracking_parameters["goalEvent"] = test.goal_event
        tracking_parameters["goalPageId"] = (
            test.goal_page.id if test.goal_page else None
        )

    return {
        "track": track,
        "tracking_parameters": tracking_parameters,
    }
