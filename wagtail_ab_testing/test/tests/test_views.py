import datetime

from django.urls import reverse
from freezegun import freeze_time
from rest_framework.test import APITestCase
from wagtail.core.models import Page

from wagtail_ab_testing.models import AbTest


@freeze_time('2020-11-04T22:37:00Z')
class TestRegisterParticipant(APITestCase):
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

    def test_register_participant(self):
        # Add a participant for variant
        # This will make the new participant use control
        self.ab_test.add_participant(AbTest.VERSION_VARIANT)

        response = self.client.post(
            reverse('wagtail_ab_testing:register_participant'),
            {
                'test_id': self.ab_test.id,
                'version': 'control',
            }
        )

        self.assertEqual(response.status_code, 200)

        # This should've created a history log
        log = self.ab_test.hourly_logs.order_by('id').last()

        self.assertEqual(log.date, datetime.date(2020, 11, 4))
        self.assertEqual(log.hour, 22)
        self.assertEqual(log.version, AbTest.VERSION_CONTROL)
        self.assertEqual(log.participants, 1)
        self.assertEqual(log.conversions, 0)

    def test_register_participant_finish(self):
        # Add a participant for variant
        # This will make the new participant use control
        self.ab_test.add_participant(AbTest.VERSION_VARIANT)

        # Lower sample size to two so the ab test finishes on this request
        self.ab_test.sample_size = 2
        self.ab_test.save()

        response = self.client.post(
            reverse('wagtail_ab_testing:register_participant'),
            {
                'test_id': self.ab_test.id,
                'version': 'control',
            }
        )

        self.assertEqual(response.status_code, 200)

        self.ab_test.refresh_from_db()
        self.assertEqual(self.ab_test.status, AbTest.STATUS_FINISHED)


@freeze_time('2020-11-04T22:37:00Z')
class TestGoalReached(APITestCase):
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
        response = self.client.post(
            reverse('wagtail_ab_testing:goal_reached', args=[]),
            {
                'test_id': self.ab_test.id,
                'version': 'control'
            }
        )

        self.assertEqual(response.status_code, 200)

        # This should've created a history log
        log = self.ab_test.hourly_logs.get()

        self.assertEqual(log.date, datetime.date(2020, 11, 4))
        self.assertEqual(log.hour, 22)
        self.assertEqual(log.version, AbTest.VERSION_CONTROL)
        self.assertEqual(log.participants, 0)
        self.assertEqual(log.conversions, 1)

    def test_log_conversion_for_variant(self):
        response = self.client.post(
            reverse('wagtail_ab_testing:goal_reached', args=[]),
            {
                'test_id': self.ab_test.id,
                'version': 'variant'
            }
        )

        self.assertEqual(response.status_code, 200)

        # This should've created a history log
        log = self.ab_test.hourly_logs.get()

        self.assertEqual(log.date, datetime.date(2020, 11, 4))
        self.assertEqual(log.hour, 22)
        self.assertEqual(log.version, AbTest.VERSION_VARIANT)
        self.assertEqual(log.participants, 0)
        self.assertEqual(log.conversions, 1)

    def test_log_conversion_for_something_else(self):
        response = self.client.post(
            reverse('wagtail_ab_testing:goal_reached', args=[]),
            {
                'test_id': self.ab_test.id,
                'version': 'something-else'
            }
        )

        self.assertEqual(response.status_code, 400)

        # This shouldn't create a history log
        self.assertFalse(self.ab_test.hourly_logs.exists())
