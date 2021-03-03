from django.urls import reverse
from rest_framework.test import APITestCase
from wagtail.core.models import Page

from wagtail_ab_testing.models import AbTest
from wagtail_ab_testing.test.models import SimplePage


class TestAbTestsListingAPI(APITestCase):
    def setUp(self):
        # Create test page with a draft revision
        self.page = Page.objects.get(id=2).add_child(instance=SimplePage(title="Test", slug="test"))
        self.page.save_revision().publish()

        # Create an A/B test
        self.ab_test = AbTest.objects.create(
            page=self.page,
            name="Test",
            variant_revision=self.page.get_latest_revision(),
            status=AbTest.STATUS_RUNNING,
            goal_page_id=2,
            goal_event='visit-page',
            sample_size=100,
        )

    def test_get_list(self):
        response = self.client.get(reverse('ab_testing_api:abtest-list'))

        self.assertEqual(response.json(), [
            {
                'id': self.ab_test.id,
                'site': {
                    'id': self.page.get_site().id,
                    'hostname': 'localhost',
                },
                'page': {
                    'id': self.page.id,
                    'path': '/test/'
                },
                'goal': {
                    'page': {
                        'id': 2,
                        'path': '/'
                    },
                    'event': 'visit-page'
                },
                'variant_html_url': f'/abtestingapi/tests/{self.ab_test.id}/serve_variant/'
            }
        ])

    def test_get_detail(self):
        response = self.client.get(reverse('ab_testing_api:abtest-detail', args=[self.ab_test.id]))

        self.assertEqual(response.json(), {
            'id': self.ab_test.id,
            'site': {
                'id': self.page.get_site().id,
                'hostname': 'localhost',
            },
            'page': {
                'id': self.page.id,
                'path': '/test/'
            },
            'goal': {
                'page': {
                    'id': 2,
                    'path': '/'
                },
                'event': 'visit-page'
            },
            'variant_html_url': f'/abtestingapi/tests/{self.ab_test.id}/serve_variant/'
        })

    def test_doesnt_show_draft(self):
        self.ab_test.status = AbTest.STATUS_DRAFT
        self.ab_test.save()

        response = self.client.get(reverse('ab_testing_api:abtest-list'))

        self.assertEqual(response.json(), [])

    def test_doesnt_show_paused(self):
        self.ab_test.status = AbTest.STATUS_PAUSED
        self.ab_test.save()

        response = self.client.get(reverse('ab_testing_api:abtest-list'))

        self.assertEqual(response.json(), [])

    def test_doesnt_show_cancelled(self):
        self.ab_test.status = AbTest.STATUS_CANCELLED
        self.ab_test.save()

        response = self.client.get(reverse('ab_testing_api:abtest-list'))

        self.assertEqual(response.json(), [])

    def test_doesnt_show_completed(self):
        self.ab_test.status = AbTest.STATUS_COMPLETED
        self.ab_test.save()

        response = self.client.get(reverse('ab_testing_api:abtest-list'))

        self.assertEqual(response.json(), [])


class TestServeVariantAPI(APITestCase):
    def setUp(self):
        # Create test page with a draft revision
        self.page = Page.objects.get(id=2).add_child(instance=Page(title="Test", slug="test"))
        self.page.title = "Changed title"
        self.page.save_revision()

        # Create an A/B test
        self.ab_test = AbTest.objects.create(
            page=self.page,
            name="Test",
            variant_revision=self.page.get_latest_revision(),
            status=AbTest.STATUS_RUNNING,
            goal_page_id=2,
            goal_event='visit-page',
            sample_size=100,
        )

    def test_serve_variant(self):
        response = self.client.get(reverse('ab_testing_api:abtest-serve-variant', args=[self.ab_test.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Changed title")
