import datetime

from django.test import TestCase
from freezegun import freeze_time
from wagtail.core.models import Page

from wagtail_ab_testing.models import AbTest


@freeze_time('2020-11-04T22:37:00Z')
class TestAbTestModel(TestCase):
    def setUp(self):
        home_page = Page.objects.get(id=2)
        home_page.title = "Changed title"
        revision = home_page.save_revision()
        self.ab_test = AbTest.objects.create(
            page=home_page,
            name="Test",
            treatment_revision=revision,
            goal_event="foo",
            sample_size=10,
        )

    def test_finish(self):
        self.ab_test.finish()
        self.ab_test.refresh_from_db()
        self.assertEqual(self.ab_test.status, AbTest.Status.COMPLETED)

    def test_finish_cancel(self):
        self.ab_test.finish(cancel=True)
        self.ab_test.refresh_from_db()
        self.assertEqual(self.ab_test.status, AbTest.Status.CANCELLED)

    def test_add_participant(self):
        variant = self.ab_test.add_participant()

        # This should've created a history log
        log = self.ab_test.hourly_logs.get()

        self.assertEqual(log.date, datetime.date(2020, 11, 4))
        self.assertEqual(log.hour, 22)
        self.assertEqual(log.variant, variant)
        self.assertEqual(log.participants, 1)
        self.assertEqual(log.conversions, 0)

    def test_log_conversion(self):
        self.ab_test.log_conversion(AbTest.Variant.CONTROL)

        # This should've created a history log
        log = self.ab_test.hourly_logs.get()

        self.assertEqual(log.date, datetime.date(2020, 11, 4))
        self.assertEqual(log.hour, 22)
        self.assertEqual(log.variant, AbTest.Variant.CONTROL)
        self.assertEqual(log.participants, 0)
        self.assertEqual(log.conversions, 1)

        # Now add another
        self.ab_test.log_conversion(AbTest.Variant.CONTROL)

        log.refresh_from_db()

        self.assertEqual(log.participants, 0)
        self.assertEqual(log.conversions, 2)
