import datetime

from django.test import TestCase
from freezegun import freeze_time
from wagtail.core.models import Page

from wagtail_ab_testing.models import AbTest, AbTestHourlyLog


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

    def set_up_test(self, control_participants, control_conversions, treatment_participants, treatment_conversions):
        AbTestHourlyLog.objects.create(
            ab_test=self.ab_test,
            variant=AbTest.Variant.CONTROL,
            date=datetime.date(2020, 11, 4),
            hour=22,
            participants=control_participants,
            conversions=control_conversions,
        )

        AbTestHourlyLog.objects.create(
            ab_test=self.ab_test,
            variant=AbTest.Variant.TREATMENT,
            date=datetime.date(2020, 11, 4),
            hour=22,
            participants=treatment_participants,
            conversions=treatment_conversions,
        )

    def test_check_for_winner_no_data(self):
        self.set_up_test(0, 0, 0, 0)

        self.assertIsNone(self.ab_test.check_for_winner())

    def test_check_control_clearly_wins(self):
        self.set_up_test(100, 80, 100, 20)

        self.assertEqual(self.ab_test.check_for_winner(), AbTest.Variant.CONTROL)

    def test_check_treatment_clearly_wins(self):
        self.set_up_test(100, 20, 100, 80)

        self.assertEqual(self.ab_test.check_for_winner(), AbTest.Variant.TREATMENT)

    def test_control_just_wins(self):
        self.set_up_test(100, 64, 100, 50)

        self.assertEqual(self.ab_test.check_for_winner(), AbTest.Variant.CONTROL)

    def test_treatment_just_wins(self):
        self.set_up_test(100, 50, 100, 64)

        self.assertEqual(self.ab_test.check_for_winner(), AbTest.Variant.TREATMENT)

    def test_close_leaning_control(self):
        self.set_up_test(100, 62, 100, 50)

        self.assertIsNone(self.ab_test.check_for_winner())

    def test_close_leaning_treatment(self):
        self.set_up_test(100, 50, 100, 62)

        self.assertIsNone(self.ab_test.check_for_winner())

    def test_confidence_improves_with_more_participants(self):
        # Even though as a percentage, this is less of a win than in previous tests,
        # we can be more confident with a slight difference if there are more paricipants
        self.set_up_test(1000, 550, 1000, 500)

        self.assertEqual(self.ab_test.check_for_winner(), AbTest.Variant.CONTROL)


class TestAutoCancelOnUnpublish(TestCase):
    def setUp(self):
        self.home_page = Page.objects.get(id=2)
        self.home_page.title = "Changed title"
        revision = self.home_page.save_revision()
        self.ab_test = AbTest.objects.create(
            page=self.home_page,
            name="Test",
            treatment_revision=revision,
            goal_event="foo",
            sample_size=10,
        )

    def test_unpublish_draft(self):
        self.ab_test.status = AbTest.Status.DRAFT
        self.ab_test.save()

        self.home_page.unpublish()

        self.ab_test.refresh_from_db()
        self.assertEqual(self.ab_test.status, AbTest.Status.CANCELLED)

    def test_unpublish_running(self):
        self.ab_test.status = AbTest.Status.RUNNING
        self.ab_test.save()

        self.home_page.unpublish()

        self.ab_test.refresh_from_db()
        self.assertEqual(self.ab_test.status, AbTest.Status.CANCELLED)

    def test_unpublish_paused(self):
        self.ab_test.status = AbTest.Status.PAUSED
        self.ab_test.save()

        self.home_page.unpublish()

        self.ab_test.refresh_from_db()
        self.assertEqual(self.ab_test.status, AbTest.Status.CANCELLED)

    def test_unpublish_completed(self):
        self.ab_test.status = AbTest.Status.COMPLETED
        self.ab_test.save()

        self.home_page.unpublish()

        self.ab_test.refresh_from_db()
        self.assertEqual(self.ab_test.status, AbTest.Status.COMPLETED)

    def test_unpublish_cancelled(self):
        self.ab_test.status = AbTest.Status.CANCELLED
        self.ab_test.save()

        self.home_page.unpublish()

        self.ab_test.refresh_from_db()
        self.assertEqual(self.ab_test.status, AbTest.Status.CANCELLED)
