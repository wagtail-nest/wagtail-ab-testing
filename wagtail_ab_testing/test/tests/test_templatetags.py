from unittest.mock import patch

from django.test import RequestFactory, TestCase
from django.urls import reverse
from wagtail.models import Page

from wagtail_ab_testing.models import AbTest
from wagtail_ab_testing.templatetags.wagtail_ab_testing_tags import (
    wagtail_ab_testing_script,
)


@patch(
    "wagtail_ab_testing.templatetags.wagtail_ab_testing_tags.request_is_trackable",
    return_value=True,
)
class TestWagtailAbTestingScriptTemplateTag(TestCase):
    def setUp(self):
        # Create test page with a draft revision
        self.page = Page.objects.get(id=2).add_child(
            instance=Page(title="Test", slug="test")
        )
        self.page.title = "Changed title"
        self.page.save_revision()

        # Create an A/B test
        self.ab_test = AbTest.objects.create(
            page=self.page,
            name="Test",
            variant_revision=self.page.get_latest_revision(),
            status=AbTest.STATUS_RUNNING,
            goal_page_id=2,
            goal_event="visit-page",
            sample_size=100,
        )

        # Create a request factory:
        self.factory = RequestFactory()

    def test_ab_testing_script_tag_test_with_trackable_urls(
        self, mock_request_is_callable
    ):
        """Test the tag for a page that is part of an A/B test serving a control version."""
        # A/B test page url:
        url = (reverse("wagtail_ab_testing:goal_reached", args=[]),)
        # Create a request
        request = self.factory.post(
            url,
            {
                "test_id": self.ab_test.id,
                "version": "control",
            },
        )

        request.wagtail_ab_testing_test = self.ab_test
        request.wagtail_ab_testing_serving_variant = False

        context = {
            "request": request,
            "page": self.page,
        }

        result = wagtail_ab_testing_script(context)

        expected_tracking_parameters = {
            "urls": {
                "registerParticipant": reverse(
                    "wagtail_ab_testing:register_participant"
                ),
                "goalReached": reverse("wagtail_ab_testing:goal_reached"),
            },
            "pageId": self.page.id,
            "testId": self.ab_test.id,
            "version": AbTest.VERSION_CONTROL,
            "goalEvent": self.ab_test.goal_event,
            "goalPageId": self.ab_test.goal_page.id,
        }

        self.assertEqual(result["track"], True)
        self.assertDictEqual(
            result["tracking_parameters"], expected_tracking_parameters
        )

    def test_ab_testing_script_tag_test_serving_variant(self, mock_request_is_callable):
        """Test the tag for a page serving a variant in an A/B test."""
        # A/B test page url:
        url = (reverse("wagtail_ab_testing:goal_reached", args=[]),)
        # Create a request
        request = self.factory.post(
            url,
            {
                "test_id": self.ab_test.id,
                "version": "variant",
            },
        )

        request.wagtail_ab_testing_test = self.ab_test
        request.wagtail_ab_testing_serving_variant = True

        context = {
            "request": request,
            "page": self.page,
        }

        result = wagtail_ab_testing_script(context)

        expected_tracking_parameters = {
            "urls": {
                "registerParticipant": reverse(
                    "wagtail_ab_testing:register_participant"
                ),
                "goalReached": reverse("wagtail_ab_testing:goal_reached"),
            },
            "pageId": self.page.id,
            "testId": self.ab_test.id,
            "version": AbTest.VERSION_VARIANT,
            "goalEvent": self.ab_test.goal_event,
            "goalPageId": self.ab_test.goal_page.id,
        }

        self.assertEqual(result["track"], True)
        self.assertDictEqual(
            result["tracking_parameters"], expected_tracking_parameters
        )

    def test_ab_testing_script_tag_without_test_in_request(
        self, mock_request_is_callable
    ):
        """Test the tag for a page that is not part of an A/B test."""
        # Create a request for a page that is not part of an A/B test
        request = self.factory.get("/")

        context = {
            "request": request,
            "page": self.page,
        }

        result = wagtail_ab_testing_script(context)

        expected_tracking_parameters = {
            "urls": {
                "registerParticipant": reverse(
                    "wagtail_ab_testing:register_participant"
                ),
                "goalReached": reverse("wagtail_ab_testing:goal_reached"),
            },
            "pageId": self.page.id,
        }

        # There is still a test running and this user is being tracked:
        self.assertEqual(result["track"], True)
        self.assertDictEqual(
            result["tracking_parameters"], expected_tracking_parameters
        )

    def test_ab_testing_script_tag_request_without_tracking(
        self, mock_request_is_callable
    ):
        """Test the tag for a request that should not be tracked."""
        # A/B test page url:
        url = (reverse("wagtail_ab_testing:goal_reached", args=[]),)
        # Create a request
        request = self.factory.get(
            url,
            {
                "test_id": self.ab_test.id,
                "version": "variant",
            },
        )

        request.wagtail_ab_testing_test = self.ab_test
        request.wagtail_ab_testing_serving_variant = True

        context = {
            "request": request,
            "page": self.page,
        }

        # Mock a request from a bot or with a DNT
        mock_request_is_callable.return_value = False

        result = wagtail_ab_testing_script(context)

        self.assertEqual(result["track"], False)
        self.assertIsNone(result["tracking_parameters"])
