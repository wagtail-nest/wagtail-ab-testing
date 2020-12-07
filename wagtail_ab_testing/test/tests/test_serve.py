from django.db.models import Sum, Q
from django.test import TestCase
from wagtail.core.models import Page

from wagtail_ab_testing.models import AbTest


class TestServe(TestCase):
    def setUp(self):
        self.home_page = Page.objects.get(id=2)
        self.home_page.title = "Changed title"
        revision = self.home_page.save_revision()
        self.ab_test = AbTest.objects.create(
            page=self.home_page,
            name="Test",
            variant_revision=revision,
            goal_event="visit-page",
            goal_page=self.home_page.add_child(instance=Page(title="Goal", slug="goal")),
            sample_size=10,
            status=AbTest.STATUS_RUNNING,
        )

    def test_serves_control(self):
        # Add a participant for variant
        # This will make the new participant use control to balance the numbers
        self.ab_test.add_participant(AbTest.VERSION_VARIANT)

        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)

        self.assertContains(response, "Welcome to your new Wagtail site!")
        self.assertNotContains(response, "Changed title")

        self.assertEqual(self.client.session[f'wagtail-ab-testing_{self.ab_test.id}_version'], AbTest.VERSION_CONTROL)

    def test_serves_variant(self):
        # Add a participant for control
        # This will make the new participant use variant to balance the numbers
        self.ab_test.add_participant(AbTest.VERSION_CONTROL)

        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)

        self.assertNotContains(response, "Welcome to your new Wagtail site!")
        self.assertContains(response, "Changed title")

        self.assertEqual(self.client.session[f'wagtail-ab-testing_{self.ab_test.id}_version'], AbTest.VERSION_VARIANT)

    def test_serves_control_when_paused(self):
        self.ab_test.status = AbTest.STATUS_PAUSED
        self.ab_test.save()

        # Add a participant for control
        # This time, the next viewer will still see the control as the test is not running
        self.ab_test.add_participant(AbTest.VERSION_CONTROL)

        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)

        self.assertContains(response, "Welcome to your new Wagtail site!")
        self.assertNotContains(response, "Changed title")

        self.assertNotIn(f'wagtail-ab-testing_{self.ab_test.id}_version', self.client.session)

    def test_doesnt_track_bots(self):
        # Add a participant for control
        # This will make it serve the variant if it does incorrectly decide to track the user
        self.ab_test.add_participant(AbTest.VERSION_CONTROL)

        response = self.client.get(
            '/',
            HTTP_USER_AGENT='Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)'
        )
        self.assertEqual(response.status_code, 200)

        # The control should be served
        self.assertContains(response, "Welcome to your new Wagtail site!")
        self.assertNotContains(response, "Changed title")
        self.assertNotIn(f'wagtail-ab-testing_{self.ab_test.id}_version', self.client.session)

    def test_doesnt_track_dnt_users(self):
        # Add a participant for control
        # This will make it serve the variant if it does incorrectly decide to track the user
        self.ab_test.add_participant(AbTest.VERSION_CONTROL)

        response = self.client.get('/', HTTP_DNT='1')
        self.assertEqual(response.status_code, 200)

        # The control should be served
        self.assertContains(response, "Welcome to your new Wagtail site!")
        self.assertNotContains(response, "Changed title")
        self.assertNotIn(f'wagtail-ab-testing_{self.ab_test.id}_version', self.client.session)

    def test_visit_page_goal_completion(self):
        session = self.client.session
        session[f'wagtail-ab-testing_{self.ab_test.id}_version'] = 'variant'
        session.save()

        response = self.client.get('/goal/')
        self.assertEqual(response.status_code, 200)

        self.assertEqual(self.client.session[f'wagtail-ab-testing_{self.ab_test.id}_completed'], 'yes')

        stats = self.ab_test.hourly_logs.aggregate(
            control_conversions=Sum('conversions', filter=Q(version=AbTest.VERSION_CONTROL)),
            variant_conversions=Sum('conversions', filter=Q(version=AbTest.VERSION_VARIANT)),
        )

        self.assertEqual(stats['control_conversions'] or 0, 0)
        self.assertEqual(stats['variant_conversions'] or 0, 1)

    def test_visit_page_goal_completion_doesnt_count_second_time(self):
        # Shouldn't be counted if test marked as completed in users session
        session = self.client.session
        session[f'wagtail-ab-testing_{self.ab_test.id}_version'] = 'variant'
        session[f'wagtail-ab-testing_{self.ab_test.id}_completed'] = 'yes'
        session.save()

        response = self.client.get('/goal/')
        self.assertEqual(response.status_code, 200)

        stats = self.ab_test.hourly_logs.aggregate(
            control_conversions=Sum('conversions', filter=Q(version=AbTest.VERSION_CONTROL)),
            variant_conversions=Sum('conversions', filter=Q(version=AbTest.VERSION_VARIANT)),
        )

        self.assertEqual(stats['control_conversions'] or 0, 0)
        self.assertEqual(stats['variant_conversions'] or 0, 0)

    def test_visit_page_goal_completion_doesnt_count_if_not_participant(self):
        # Shouldn't be counted if the user is not a participant
        response = self.client.get('/goal/')
        self.assertEqual(response.status_code, 200)

        stats = self.ab_test.hourly_logs.aggregate(
            control_conversions=Sum('conversions', filter=Q(version=AbTest.VERSION_CONTROL)),
            variant_conversions=Sum('conversions', filter=Q(version=AbTest.VERSION_VARIANT)),
        )

        self.assertEqual(stats['control_conversions'] or 0, 0)
        self.assertEqual(stats['variant_conversions'] or 0, 0)
