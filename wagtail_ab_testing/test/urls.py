from django.conf.urls import include, url
from django.contrib import admin

from wagtail.admin import urls as wagtailadmin_urls
from wagtail.documents import urls as wagtaildocs_urls
from wagtail.core import urls as wagtail_urls

from wagtail_ab_testing import api as ab_testing_api
from wagtail_ab_testing import urls as ab_testing_urls


urlpatterns = [
    url(r"^django-admin/", admin.site.urls),
    url(r"^admin/", include(wagtailadmin_urls)),
    url(r"^documents/", include(wagtaildocs_urls)),
    url(r'^abtestingapi/', include(ab_testing_api, namespace='ab_testing_api')),
    url(r'^abtesting/', include(ab_testing_urls, namespace='wagtail_ab_testing')),

    url(r"", include(wagtail_urls)),
]
