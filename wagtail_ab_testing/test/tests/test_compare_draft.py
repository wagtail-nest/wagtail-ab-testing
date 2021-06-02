from django.test import TestCase
from django.urls import reverse
from wagtail.core.models import Page
from wagtail.tests.utils import WagtailTestUtils

from wagtail_ab_testing.models import AbTest
from wagtail_ab_testing.test.models import SimplePage


class TestCompareDraftView(WagtailTestUtils, TestCase):
    def setUp(self):
        self.user = self.login()

        # Create test page with a draft revision
        self.page = Page.objects.get(id=1).add_child(instance=SimplePage(title="Test", slug="test"))
        self.page.save_revision().publish()

        # Create an A/B test
        self.ab_test = AbTest.objects.create(
            page=self.page,
            name="Test",
            variant_revision=self.page.get_latest_revision(),
            status=AbTest.STATUS_RUNNING,
            sample_size=100,
        )

    def test_get_compare_draft(self):
        response = self.client.get(reverse('wagtail_ab_testing_admin:compare_draft', args=[self.page.id]))

        self.assertTemplateUsed(response, "wagtail_ab_testing/compare.html")
