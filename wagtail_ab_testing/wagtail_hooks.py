from django.shortcuts import redirect
from django.urls import path, include
from django.utils.translation import gettext_lazy as __
from django.views.i18n import JavaScriptCatalog

from wagtail.admin.action_menu import ActionMenuItem
from wagtail.core import hooks

from . import views


@hooks.register("register_admin_urls")
def register_admin_urls():
    urls = [
        path('jsi18n/', JavaScriptCatalog.as_view(packages=['wagtail_ab_testing']), name='javascript_catalog'),
        path('add/<int:page_id>/compare/', views.add_compare, name='add_ab_test_compare'),
        path('add/<int:page_id>/', views.add_form, name='add_ab_test_form'),
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
