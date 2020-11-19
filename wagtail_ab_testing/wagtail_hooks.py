from django.shortcuts import redirect
from django.urls import path, include
from django.utils.translation import gettext_lazy as __
from django.views.i18n import JavaScriptCatalog

from wagtail.admin.action_menu import ActionMenuItem
from wagtail.core import hooks

from . import views
from .models import AbTest
from .utils import request_is_trackable


@hooks.register("register_admin_urls")
def register_admin_urls():
    urls = [
        path('jsi18n/', JavaScriptCatalog.as_view(packages=['wagtail_ab_testing']), name='javascript_catalog'),
        path('add/<int:page_id>/compare/', views.add_compare, name='add_ab_test_compare'),
        path('add/<int:page_id>/', views.add_form, name='add_ab_test_form'),
        path('add-test-participants/<int:ab_test_id>/', views.add_test_participants, name='add_test_participants'),
        path('add-test-conversions/<int:ab_test_id>/<slug:variant>', views.add_test_conversions, name='add_test_conversions'),
    ]

    return [
        path(
            "abtests/",
            include(
                (urls, "wagtail_ab_testing"),
                namespace="wagtail_ab_testing",
            ),
        )
    ]


class CreateAbTestActionMenuItem(ActionMenuItem):
    name = 'create-ab-test'
    label = __("Save and create A/B Test")

    def is_shown(self, request, context):
        return context['view'] == 'edit'


@hooks.register('register_page_action_menu_item')
def register_create_abtest_action_menu_item():
    return CreateAbTestActionMenuItem(order=100)


@hooks.register('after_edit_page')
def redirect_to_create_ab_test(request, page):
    if 'create-ab-test' in request.POST:
        return redirect('wagtail_ab_testing:add_ab_test_compare', page.id)


@hooks.register('before_edit_page')
def check_for_running_ab_test(request, page):
    running_experiment = AbTest.objects.get_current_for_page(page=page)
    if running_experiment:
        return views.progress(request, page, running_experiment)


@hooks.register('before_serve_page')
def before_serve_page(page, request, serve_args, serve_kwargs):
    # Check if there are any running tests on the page
    try:
        test = AbTest.objects.get(page=page, status=AbTest.Status.DRAFT)
    except AbTest.DoesNotExist:
        return

    # Check if the user is trackable
    if not request_is_trackable(request):
        return

    # Make the user a participant if they're not already
    if f'wagtail-ab-testing_{test.id}_variant' not in request.session:
        request.session[f'wagtail-ab-testing_{test.id}_variant'] = test.add_participant()

    # If the user is visiting the treatment variant, serve that from the revision
    if request.session[f'wagtail-ab-testing_{test.id}_variant'] == AbTest.Variant.TREATMENT:
        return test.treatment_revision.as_page_object().serve(request, *serve_args, **serve_kwargs)
