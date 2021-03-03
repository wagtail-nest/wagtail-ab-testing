from rest_framework import fields, routers, serializers, viewsets
from wagtail.core.models import Page, Site

from .models import AbTest


class SiteSerializer(serializers.ModelSerializer):
    class Meta:
        fields = ['id', 'hostname']
        model = Site


class PageSerializer(serializers.ModelSerializer):
    path = fields.SerializerMethodField('get_path')

    def get_path(self, page):
        return page.get_url_parts()[2]

    class Meta:
        fields = ['id', 'path']
        model = Page


class AbTestGoalSerializer(serializers.ModelSerializer):
    page = PageSerializer(source='goal_page')
    event = fields.ReadOnlyField(source='goal_event')

    class Meta:
        fields = ['page', 'event']
        model = AbTest


class AbTestSerializer(serializers.ModelSerializer):
    site = SiteSerializer(source='page.get_site')
    page = PageSerializer()
    goal = AbTestGoalSerializer(source='*')

    class Meta:
        fields = ['id', 'site', 'page', 'goal']
        model = AbTest


class AbTestViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AbTestSerializer
    queryset = AbTest.objects.filter(status=AbTest.STATUS_RUNNING)


router = routers.SimpleRouter()
router.register(r'tests', AbTestViewSet)

app_name = 'wagtail_ab_testing_api'
urlpatterns = router.urls
