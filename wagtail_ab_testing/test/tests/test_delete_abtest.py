from datetime import datetime

from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.test import RequestFactory, TestCase
from django.urls import reverse
from wagtail.models import Page
from wagtail.test.utils import WagtailTestUtils

from wagtail_ab_testing.models import AbTest
from wagtail_ab_testing.test.models import SimplePage
from wagtail_ab_testing.wagtail_hooks import check_ab_tests_for_page


class TestDeleteAbTestConfirmationPage(WagtailTestUtils, TestCase):
    def setUp(self):
        self.user = self.login()

        # Convert the user into an moderator
        self.moderators_group = Group.objects.get(name="Moderators")
        for permission in Permission.objects.filter(
            content_type=ContentType.objects.get_for_model(AbTest)
        ):
            self.moderators_group.permissions.add(permission)
        self.user.is_superuser = False
        self.user.groups.add(self.moderators_group)
        self.user.save()

        self.factory = RequestFactory()

        # Create test page with a draft revision
        self.page = Page.objects.get(id=1).add_child(
            instance=SimplePage(title="Test", slug="test")
        )
        self.page.save_revision().publish()

    def test_check_ab_tests_hook_with_tests(self):
        # Create A/B tests
        AbTest.objects.create(
            page=self.page,
            name="Test AB 1",
            first_started_at=datetime(2023, 2, 15),
            variant_revision=self.page.get_latest_revision(),
            status=AbTest.STATUS_DRAFT,
            sample_size=10,
        )
        AbTest.objects.create(
            page=self.page,
            name="Test AB 2",
            first_started_at=datetime(2023, 2, 20),
            variant_revision=self.page.get_latest_revision(),
            status=AbTest.STATUS_DRAFT,
            sample_size=10,
        )
        # Simulate visiting the delete page
        response = self.client.get(
            reverse("wagtailadmin_pages:delete", args=[self.page.id])
        )

        # Assert redirection to the A/B test confirmation page
        self.assertRedirects(
            response,
            reverse("wagtail_ab_testing:ab_test_confirm_delete", args=[self.page.id]),
            msg_prefix="Redirection to the delete A/B tests confirmation page failed.",
        )

    def test_check_ab_tests_hook_without_tests(self):
        # Simulate visiting the delete page
        request = self.factory.get("/")
        response = check_ab_tests_for_page(request, self.page)
        self.assertIsNone(response)

    def test_ab_test_confirm_delete_view(self):
        # Create A/B tests
        AbTest.objects.create(
            page=self.page,
            name="Test AB 1",
            first_started_at=datetime(2023, 2, 15),
            variant_revision=self.page.get_latest_revision(),
            status=AbTest.STATUS_DRAFT,
            sample_size=10,
        )
        AbTest.objects.create(
            page=self.page,
            name="Test AB 2",
            first_started_at=datetime(2023, 2, 20),
            variant_revision=self.page.get_latest_revision(),
            status=AbTest.STATUS_DRAFT,
            sample_size=10,
        )

        response = self.client.get(
            reverse("wagtail_ab_testing:ab_test_confirm_delete", args=[self.page.id])
        )
        self.assertTemplateUsed(
            response, "wagtail_ab_testing/confirm_delete_ab_tests.html"
        )

        # Check order of abtests
        ab_tests = response.context["ab_tests"]
        self.assertEqual(len(ab_tests), 2)
        self.assertEqual(ab_tests[0].name, "Test AB 2")
        self.assertEqual(ab_tests[1].name, "Test AB 1")

    def test_ab_test_delete_view(self):
        # Create A/B tests
        AbTest.objects.create(
            page=self.page,
            name="Test AB 1",
            first_started_at=datetime(2023, 2, 15),
            variant_revision=self.page.get_latest_revision(),
            status=AbTest.STATUS_DRAFT,
            sample_size=10,
        )
        AbTest.objects.create(
            page=self.page,
            name="Test AB 2",
            first_started_at=datetime(2023, 2, 20),
            variant_revision=self.page.get_latest_revision(),
            status=AbTest.STATUS_DRAFT,
            sample_size=10,
        )

        response = self.client.post(
            reverse("wagtail_ab_testing:ab_test_delete", args=[self.page.id])
        )

        self.assertEqual(AbTest.objects.filter(page=self.page).count(), 0)

        self.assertRedirects(
            response,
            reverse("wagtailadmin_pages:delete", args=[self.page.id]),
            msg_prefix="The response did not redirect to the expected delete page. A/B Tests were not deleted.",
        )

        response = self.client.get(
            reverse("wagtail_ab_testing:ab_test_delete", args=[self.page.id])
        )

        self.assertRedirects(
            response,
            reverse("wagtail_ab_testing:ab_test_confirm_delete", args=[self.page.id]),
        )
