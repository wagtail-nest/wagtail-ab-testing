import json

from django.contrib.auth.models import Permission
from django.shortcuts import redirect
from django.urls import path, include, reverse
from django.utils.html import format_html, escapejs
from django.utils.translation import gettext as _, gettext_lazy as __
from django.views.i18n import JavaScriptCatalog

from wagtail.admin.action_menu import ActionMenuItem
from wagtail.admin.menu import MenuItem
from wagtail.admin.staticfiles import versioned_static
from wagtail.core import hooks

from . import views
from .compat import DATE_FORMAT
from .models import AbTest
from .utils import request_is_trackable


@hooks.register("register_admin_urls")
def register_admin_urls():
    urls = [
        path('jsi18n/', JavaScriptCatalog.as_view(packages=['wagtail_ab_testing']), name='javascript_catalog'),
        path('add/<int:page_id>/compare/', views.add_compare, name='add_ab_test_compare'),
        path('<int:page_id>/compare-draft/', views.compare_draft, name='compare_draft'),
        path('add/<int:page_id>/', views.add_form, name='add_ab_test_form'),
        path('report/', views.AbTestingReportView.as_view(), name='report'),
        path('results/<int:page_id>/<int:ab_test_id>/', views.results, name='results'),
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
    icon_name = 'people-arrows'

    def is_shown(self, request, context):
        if context['view'] != 'edit':
            return False

        # User must have permission to add A/B tests
        if not request.user.has_perm('wagtail_ab_testing.add_abtest'):
            return False

        return True


@hooks.register('register_page_action_menu_item')
def register_create_abtest_action_menu_item():
    return CreateAbTestActionMenuItem(order=100)


# This is the only way to inject custom JS into the editor with knowledge of the page being edited
class AbTestingTabActionMenuItem(ActionMenuItem):
    def render_html(self, request, context):
        if 'page' in context:
            return format_html(
                '<script src="{}"></script><script src="{}"></script><script>window.abTestingTabProps = JSON.parse("{}");</script>',
                reverse('wagtail_ab_testing:javascript_catalog'),
                versioned_static('wagtail_ab_testing/js/wagtail-ab-testing.js'),
                escapejs(json.dumps({
                    'tests': [
                        {
                            'id': ab_test.id,
                            'name': ab_test.name,
                            'started_at': ab_test.first_started_at.strftime(DATE_FORMAT) if ab_test.first_started_at else _("Not started"),
                            'status': ab_test.get_status_description(),
                            'results_url': reverse('wagtail_ab_testing:results', args=[ab_test.page_id, ab_test.id]),
                        }
                        for ab_test in AbTest.objects.filter(page=context['page']).order_by('-id')
                    ],
                    'can_create_abtest': request.user.has_perm('wagtail_ab_testing.add_abtest'),
                }))
            )

        return ''


@hooks.register('register_page_action_menu_item')
def register_ab_testing_tab_action_menu_item():
    return AbTestingTabActionMenuItem()


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
    # Check if the user is trackable
    if not request_is_trackable(request):
        return

    # Check if visiting the page is the goal of any running tests
    tests = AbTest.objects.filter(goal_event='visit-page', goal_page=page, status=AbTest.STATUS_RUNNING)
    for test in tests:
        # Is the user a participant in this test?
        if f'wagtail-ab-testing_{test.id}_version' not in request.session:
            continue

        # Has the user already completed the test?
        if f'wagtail-ab-testing_{test.id}_completed' in request.session:
            continue

        # Log a conversion
        test.log_conversion(request.session[f'wagtail-ab-testing_{test.id}_version'])
        request.session[f'wagtail-ab-testing_{test.id}_completed'] = 'yes'

    # Check if the page itself is running any tests
    try:
        test = AbTest.objects.get(page=page, status=AbTest.STATUS_RUNNING)
    except AbTest.DoesNotExist:
        return

    # Make the user a participant if they're not already
    if f'wagtail-ab-testing_{test.id}_version' not in request.session:
        request.session[f'wagtail-ab-testing_{test.id}_version'] = test.add_participant()

    # If the user is visiting the variant version, serve that from the revision
    if request.session[f'wagtail-ab-testing_{test.id}_version'] == AbTest.VERSION_VARIANT:
        return test.variant_revision.as_page_object().serve(request, *serve_args, **serve_kwargs)


class AbTestingReportMenuItem(MenuItem):

    def is_shown(self, request):
        return True


@hooks.register('register_reports_menu_item')
def register_ab_testing_report_menu_item():
    return AbTestingReportMenuItem(_('A/B testing'), reverse('wagtail_ab_testing:report'), icon_name='people-arrows', order=1000)


@hooks.register('register_icons')
def register_icons(icons):
    icons.append('wagtail_ab_testing/icons/people-arrows.svg')
    icons.append('wagtail_ab_testing/icons/crown.svg')
    return icons


@hooks.register('register_permissions')
def register_add_abtest_permission():
    return Permission.objects.filter(content_type__app_label='wagtail_ab_testing', codename='add_abtest')
