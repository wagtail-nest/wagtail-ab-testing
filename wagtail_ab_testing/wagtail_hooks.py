import json

from django.conf import settings
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import include, path, reverse
from django.utils.html import escapejs, format_html
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy as __
from django.views.i18n import JavaScriptCatalog
from wagtail import hooks
from wagtail.admin.action_menu import ActionMenuItem
from wagtail.admin.menu import MenuItem
from wagtail.admin.staticfiles import versioned_static

from . import views
from .compat import DATE_FORMAT
from .models import AbTest
from .utils import request_is_trackable


@hooks.register("register_admin_urls")
def register_admin_urls():
    urls = [
        path(
            "jsi18n/",
            JavaScriptCatalog.as_view(packages=["wagtail_ab_testing"]),
            name="javascript_catalog",
        ),
        path(
            "add/<int:page_id>/compare/", views.add_compare, name="add_ab_test_compare"
        ),
        path("<int:page_id>/compare-draft/", views.compare_draft, name="compare_draft"),
        path("add/<int:page_id>/", views.add_form, name="add_ab_test_form"),
        path("report/", views.AbTestingReportView.as_view(), name="report"),
        path(
            "report/results/",
            views.AbTestingReportView.as_view(results_only=True),
            name="report_results",
        ),
        path("results/<int:page_id>/<int:ab_test_id>/", views.results, name="results"),
    ]

    return [
        path(
            "abtests/",
            include(
                (urls, "wagtail_ab_testing_admin"),
                namespace="wagtail_ab_testing_admin",
            ),
        )
    ]


class CreateAbTestActionMenuItem(ActionMenuItem):
    name = "create-ab-test"
    label = __("Save and create A/B Test")
    icon_name = "people-arrows"

    def is_shown(self, context):
        if context["view"] != "edit":
            return False

        # User must have permission to add A/B tests
        if not self.check_user_permissions(context["request"].user):
            return False

        return True

    @staticmethod
    def check_user_permissions(user):
        return user.has_perm("wagtail_ab_testing.add_abtest")


@hooks.register("register_page_action_menu_item")
def register_create_abtest_action_menu_item():
    return CreateAbTestActionMenuItem(order=100)


# This is the only way to inject custom JS into the editor with knowledge of the page being edited
class AbTestingTabActionMenuItem(ActionMenuItem):
    def render_html(self, context):
        if "page" in context:
            return self.format_html(context["request"].user, context)

        return ""

    @staticmethod
    def format_html(user, context):
        return format_html(
            '<script src="{}"></script><script src="{}"></script><script>window.abTestingTabProps = JSON.parse("{}");</script>',
            reverse("wagtail_ab_testing_admin:javascript_catalog"),
            versioned_static("wagtail_ab_testing/js/wagtail-ab-testing.js"),
            escapejs(
                json.dumps(
                    {
                        "tests": [
                            {
                                "id": ab_test.id,
                                "name": ab_test.name,
                                "started_at": (
                                    ab_test.first_started_at.strftime(DATE_FORMAT)
                                    if ab_test.first_started_at
                                    else _("Not started")
                                ),
                                "status": ab_test.get_status_description(),
                                "results_url": reverse(
                                    "wagtail_ab_testing_admin:results",
                                    args=[ab_test.page_id, ab_test.id],
                                ),
                            }
                            for ab_test in AbTest.objects.filter(
                                page=context["page"]
                            ).order_by("-id")
                        ],
                        "can_create_abtest": user.has_perm(
                            "wagtail_ab_testing.add_abtest"
                        ),
                    }
                )
            ),
        )


@hooks.register("register_page_action_menu_item")
def register_ab_testing_tab_action_menu_item():
    return AbTestingTabActionMenuItem()


@hooks.register("after_edit_page")
def redirect_to_create_ab_test(request, page):
    if "create-ab-test" in request.POST:
        return redirect("wagtail_ab_testing_admin:add_ab_test_compare", page.id)


@hooks.register("before_edit_page")
def check_for_running_ab_test(request, page):
    running_experiment = AbTest.objects.get_current_for_page(page=page)
    if running_experiment:
        return views.progress(request, page, running_experiment)


@hooks.register("before_serve_page")
def before_serve_page(page, request, serve_args, serve_kwargs):
    # Check if the user is trackable
    if not request_is_trackable(request):
        return

    # Check for a running A/B test on the requested page
    try:
        test = AbTest.objects.get(page=page, status=AbTest.STATUS_RUNNING)
    except AbTest.DoesNotExist:
        return

    # Save reference to test on request object so it can be found by the {% wagtail_ab_testing_script %} template tag
    request.wagtail_ab_testing_test = test

    # If this request is coming from a frontend worker, return both the control and variant versions
    # The worker will decide which version to serve to the user
    if request.META.get("HTTP_X_REQUESTED_WITH") == "WagtailAbTestingWorker":
        if (
            request.META.get("HTTP_AUTHORIZATION", "")
            != "Token " + settings.WAGTAIL_AB_TESTING_WORKER_TOKEN
        ):
            raise PermissionDenied

        control_response = page.serve(request, *serve_args, **serve_kwargs)

        # Note: we must render the control response before setting `wagtail_ab_testing_serving_variant`
        if hasattr(control_response, "render"):
            control_response.render()

        request.wagtail_ab_testing_serving_variant = True

        variant_response = test.variant_revision.as_object().serve(
            request, *serve_args, **serve_kwargs
        )

        if hasattr(variant_response, "render"):
            variant_response.render()

        response = JsonResponse(
            {
                "control": control_response.content.decode("utf-8"),
                "variant": variant_response.content.decode("utf-8"),
            }
        )

        response["X-WagtailAbTesting-Test"] = str(test.id)

        return response

    # If the user visiting is a participant, show them the same version they saw before
    if f"wagtail-ab-testing_{test.id}_version" in request.COOKIES:
        version = request.COOKIES[f"wagtail-ab-testing_{test.id}_version"]
    else:
        # Otherwise, show them the version of the page that the next participant should see.
        # Note: In order to exclude bots, the browser must call a JavaScript API to sign up as a participant
        # Once they've signed up, they'll get a cookie which keeps them on the same version
        version = test.get_new_participant_version()

    # If the user should be shown the variant, serve that from the revision. Otherwise return to keep the control
    if version == AbTest.VERSION_VARIANT:
        request.wagtail_ab_testing_serving_variant = True
        return test.variant_revision.as_object().serve(
            request, *serve_args, **serve_kwargs
        )


class AbTestingReportMenuItem(MenuItem):
    def is_shown(self, request):
        return True


@hooks.register("register_reports_menu_item")
def register_ab_testing_report_menu_item():
    return AbTestingReportMenuItem(
        _("A/B testing"),
        reverse("wagtail_ab_testing_admin:report"),
        icon_name="people-arrows",
        order=1000,
    )


@hooks.register("register_icons")
def register_icons(icons):
    icons.append("wagtail_ab_testing/icons/people-arrows.svg")
    icons.append("wagtail_ab_testing/icons/crown.svg")
    return icons


@hooks.register("register_permissions")
def register_add_abtest_permission():
    return Permission.objects.filter(
        content_type__app_label="wagtail_ab_testing", codename="add_abtest"
    )
