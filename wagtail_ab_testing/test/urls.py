from django.urls import include, path
from django.contrib import admin

from wagtail.admin import urls as wagtailadmin_urls
from wagtail.documents import urls as wagtaildocs_urls

try:
    from wagtail import urls as wagtail_urls
except ImportError:
    from wagtail.core import urls as wagtail_urls

from wagtail_ab_testing import api as ab_testing_api
from wagtail_ab_testing import urls as ab_testing_urls


urlpatterns = [
    path("django-admin/", admin.site.urls),
    path("admin/", include(wagtailadmin_urls)),
    path("documents/", include(wagtaildocs_urls)),
    path('abtestingapi/', include(ab_testing_api, namespace='ab_testing_api')),
    path('abtesting/', include(ab_testing_urls, namespace='wagtail_ab_testing')),

    path("", include(wagtail_urls)),
]
