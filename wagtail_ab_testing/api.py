from django.urls import reverse
from rest_framework import fields, routers, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from wagtail.models import Page, Site

from .models import AbTest


class SiteSerializer(serializers.ModelSerializer):
    class Meta:
        fields = ["id", "hostname"]
        model = Site


class PageSerializer(serializers.ModelSerializer):
    path = fields.SerializerMethodField("get_path")

    def get_path(self, page):
        return page.get_url_parts()[2]

    class Meta:
        fields = ["id", "path"]
        model = Page


class AbTestGoalSerializer(serializers.ModelSerializer):
    page = PageSerializer(source="goal_page")
    event = fields.ReadOnlyField(source="goal_event")

    class Meta:
        fields = ["page", "event"]
        model = AbTest


class AbTestSerializer(serializers.ModelSerializer):
    site = SiteSerializer(source="page.get_site")
    page = PageSerializer()
    goal = AbTestGoalSerializer(source="*")
    variant_html_url = fields.SerializerMethodField()
    add_participant_url = fields.SerializerMethodField()
    log_conversion_url = fields.SerializerMethodField()

    def get_variant_html_url(self, test):
        return reverse("wagtail_ab_testing_api:abtest-serve-variant", args=[test.id])

    def get_add_participant_url(self, test):
        return reverse("wagtail_ab_testing_api:abtest-add-participant", args=[test.id])

    def get_log_conversion_url(self, test):
        return reverse("wagtail_ab_testing_api:abtest-log-conversion", args=[test.id])

    class Meta:
        fields = [
            "id",
            "site",
            "page",
            "goal",
            "variant_html_url",
            "add_participant_url",
            "log_conversion_url",
        ]
        model = AbTest


class AbTestViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AbTestSerializer
    queryset = AbTest.objects.filter(status=AbTest.STATUS_RUNNING)

    @action(detail=True, methods=["get"])
    def serve_variant(self, request, pk=None):
        test = self.get_object()
        request.wagtail_ab_testing_test = test
        request.wagtail_ab_testing_serving_variant = True
        return test.variant_revision.as_object().serve(request)

    @action(detail=True, methods=["post"])
    def add_participant(self, request, pk=None):
        test = self.get_object()
        variant = test.add_participant()
        return Response(
            {
                "version": variant,
                "test_finished": test.status != AbTest.STATUS_RUNNING,
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"])
    def log_conversion(self, request, pk=None):
        test = self.get_object()

        if request.data["version"] not in dict(AbTest.VERSION_CHOICES).keys():
            return Response({}, status=status.HTTP_400_BAD_REQUEST)

        test.log_conversion(request.data["version"])
        return Response({}, status=status.HTTP_201_CREATED)


router = routers.SimpleRouter()
router.register(r"tests", AbTestViewSet)

app_name = "wagtail_ab_testing_api"
urlpatterns = router.urls
