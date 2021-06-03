from django.test import TestCase, override_settings
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

    def test_serves_control_from_cookie(self):
        self.client.cookies[f'wagtail-ab-testing_{self.ab_test.id}_version'] = AbTest.VERSION_CONTROL

        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)

        self.assertContains(response, "Welcome to your new Wagtail site!")
        self.assertNotContains(response, "Changed title")

    def test_serves_variant_from_cookie(self):
        self.client.cookies[f'wagtail-ab-testing_{self.ab_test.id}_version'] = AbTest.VERSION_VARIANT

        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)

        self.assertNotContains(response, "Welcome to your new Wagtail site!")
        self.assertContains(response, "Changed title")

    def test_serves_control_to_new_participant(self):
        # Add a participant for variant
        # This will make the new participant use control to balance the numbers
        self.ab_test.add_participant(AbTest.VERSION_VARIANT)

        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)

        self.assertContains(response, "Welcome to your new Wagtail site!")
        self.assertNotContains(response, "Changed title")

    def test_serves_variant_to_new_participant(self):
        # Add a participant for control
        # This will make the new participant use variant to balance the numbers
        self.ab_test.add_participant(AbTest.VERSION_CONTROL)

        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)

        self.assertNotContains(response, "Welcome to your new Wagtail site!")
        self.assertContains(response, "Changed title")

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

    @override_settings(WAGTAIL_AB_TESTING_WORKER_TOKEN='abc123')
    def test_serves_dual_response_for_worker(self):
        response = self.client.get('/', HTTP_X_REQUESTED_WITH='WagtailAbTestingWorker', HTTP_AUTHORIZATION='Token abc123')
        self.assertEqual(response.status_code, 200)

        self.assertEqual(response['X-WagtailAbTesting-Test'], str(self.ab_test.id))
        response_data = response.json()

        self.assertIn("Welcome to your new Wagtail site!", response_data['control'])
        self.assertIn("Changed title", response_data['variant'])

    @override_settings(WAGTAIL_AB_TESTING_WORKER_TOKEN='abc123')
    def test_worker_requires_token(self):
        response = self.client.get('/', HTTP_X_REQUESTED_WITH='WagtailAbTestingWorker')

        self.assertEqual(response.status_code, 403)

    @override_settings(WAGTAIL_AB_TESTING_WORKER_TOKEN='abc123')
    def test_worker_requires_correct_token(self):
        response = self.client.get('/', HTTP_X_REQUESTED_WITH='WagtailAbTestingWorker', HTTP_AUTHORIZATION='Token wrongtoken')
        self.assertEqual(response.status_code, 403)
