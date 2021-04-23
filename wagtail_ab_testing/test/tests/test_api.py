import datetime

from django.urls import reverse
from freezegun import freeze_time
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
                'variant_html_url': f'/abtestingapi/tests/{self.ab_test.id}/serve_variant/',
                'add_participant_url': f'/abtestingapi/tests/{self.ab_test.id}/add_participant/',
                'log_conversion_url': f'/abtestingapi/tests/{self.ab_test.id}/log_conversion/'
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
            'variant_html_url': f'/abtestingapi/tests/{self.ab_test.id}/serve_variant/',
            'add_participant_url': f'/abtestingapi/tests/{self.ab_test.id}/add_participant/',
            'log_conversion_url': f'/abtestingapi/tests/{self.ab_test.id}/log_conversion/'
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


@freeze_time('2020-11-04T22:37:00Z')
class TestAddParticipantAPI(APITestCase):
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

    def test_add_participant(self):
        # Add a participant for variant
        # This will make the new participant use control
        self.ab_test.add_participant(AbTest.VERSION_VARIANT)

        response = self.client.post(reverse('ab_testing_api:abtest-add-participant', args=[self.ab_test.id]))

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json(), {
            'version': 'control',
            'test_finished': False
        })

        # This should've created a history log
        log = self.ab_test.hourly_logs.order_by('id').last()

        self.assertEqual(log.date, datetime.date(2020, 11, 4))
        self.assertEqual(log.hour, 22)
        self.assertEqual(log.version, AbTest.VERSION_CONTROL)
        self.assertEqual(log.participants, 1)
        self.assertEqual(log.conversions, 0)

    def test_add_participant_finish(self):
        # Add a participant for variant
        # This will make the new participant use control
        self.ab_test.add_participant(AbTest.VERSION_VARIANT)

        # Lower sample size to two so the ab test finishes on this request
        self.ab_test.sample_size = 2
        self.ab_test.save()

        response = self.client.post(reverse('ab_testing_api:abtest-add-participant', args=[self.ab_test.id]))

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json(), {
            'version': 'control',
            'test_finished': True
        })


@freeze_time('2020-11-04T22:37:00Z')
class TestLogConversionAPI(APITestCase):
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

    def test_log_conversion_for_control(self):
        response = self.client.post(reverse('ab_testing_api:abtest-log-conversion', args=[self.ab_test.id]), {
            'version': 'control'
        })

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json(), {})

        # This should've created a history log
        log = self.ab_test.hourly_logs.get()

        self.assertEqual(log.date, datetime.date(2020, 11, 4))
        self.assertEqual(log.hour, 22)
        self.assertEqual(log.version, AbTest.VERSION_CONTROL)
        self.assertEqual(log.participants, 0)
        self.assertEqual(log.conversions, 1)

    def test_log_conversion_for_variant(self):
        response = self.client.post(reverse('ab_testing_api:abtest-log-conversion', args=[self.ab_test.id]), {
            'version': 'variant'
        })

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json(), {})

        # This should've created a history log
        log = self.ab_test.hourly_logs.get()

        self.assertEqual(log.date, datetime.date(2020, 11, 4))
        self.assertEqual(log.hour, 22)
        self.assertEqual(log.version, AbTest.VERSION_VARIANT)
        self.assertEqual(log.participants, 0)
        self.assertEqual(log.conversions, 1)

    def test_log_conversion_for_something_else(self):
        response = self.client.post(reverse('ab_testing_api:abtest-log-conversion', args=[self.ab_test.id]), {
            'version': 'something-else'
        })

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {})

        # This shouldn't create a history log
        self.assertFalse(self.ab_test.hourly_logs.exists())
