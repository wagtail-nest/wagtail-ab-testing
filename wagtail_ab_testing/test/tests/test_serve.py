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
            goal_event="foo",
            sample_size=10,
        )

    def test_serves_control(self):
        # Add a participant for variant
        # This will make the new participant use control to balance the numbers
        self.ab_test.add_participant(AbTest.Version.VARIANT)

        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)

        self.assertContains(response, "Welcome to your new Wagtail site!")
        self.assertNotContains(response, "Changed title")

        self.assertEqual(self.client.session[f'wagtail-ab-testing_{self.ab_test.id}_version'], AbTest.Version.CONTROL)

    def test_serves_variant(self):
        # Add a participant for control
        # This will make the new participant use variant to balance the numbers
        self.ab_test.add_participant(AbTest.Version.CONTROL)

        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)

        self.assertNotContains(response, "Welcome to your new Wagtail site!")
        self.assertContains(response, "Changed title")

        self.assertEqual(self.client.session[f'wagtail-ab-testing_{self.ab_test.id}_version'], AbTest.Version.VARIANT)

    def test_doesnt_track_bots(self):
        # Add a participant for control
        # This will make it serve the variant if it does incorrectly decide to track the user
        self.ab_test.add_participant(AbTest.Version.CONTROL)

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
        self.ab_test.add_participant(AbTest.Version.CONTROL)

        response = self.client.get('/', HTTP_DNT='1')
        self.assertEqual(response.status_code, 200)

        # The control should be served
        self.assertContains(response, "Welcome to your new Wagtail site!")
        self.assertNotContains(response, "Changed title")
        self.assertNotIn(f'wagtail-ab-testing_{self.ab_test.id}_version', self.client.session)
