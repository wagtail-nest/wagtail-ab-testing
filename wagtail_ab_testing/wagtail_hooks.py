from django.urls import path, include
from django.views.i18n import JavaScriptCatalog

from wagtail.core import hooks


@hooks.register("register_admin_urls")
def register_admin_urls():
    urls = [
        path('jsi18n/', JavaScriptCatalog.as_view(packages=['wagtail_ab_testing']), name='javascript_catalog'),
        
        # Add your other URLs here, and they will appear under `/admin/ab_testing/`
        # Note: you do not need to check for authentication in views added here, Wagtail does this for you!
    ]

    return [
        path(
            "ab_testing/",
            include(
                (urls, "wagtail_ab_testing"),
                namespace="wagtail_ab_testing",
            ),
        )
    ]
