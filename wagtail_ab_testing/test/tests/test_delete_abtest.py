from datetime import datetime

from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.test import RequestFactory, TestCase
from django.urls import reverse
from wagtail.models import GroupPagePermission, Page
from wagtail.test.utils import WagtailTestUtils

from wagtail_ab_testing.models import AbTest
from wagtail_ab_testing.test.models import SimplePage
from wagtail_ab_testing.wagtail_hooks import check_ab_tests_for_page


class TestDeleteAbTestConfirmationPage(WagtailTestUtils, TestCase):
    def setUp(self):
        self.user = self.login()

        self.moderators_group = Group.objects.get(name="Moderators")
        for permission in Permission.objects.filter(
            content_type=ContentType.objects.get_for_model(AbTest)
        ):
            self.moderators_group.permissions.add(permission)

        self.user.is_superuser = False
        self.user.groups.add(self.moderators_group)
        self.user.save()

        self.factory = RequestFactory()

        self.page = Page.objects.get(id=1).add_child(
            instance=SimplePage(title="Test", slug="test")
        )
        self.page.save_revision().publish()

        self.ab_test = AbTest.objects.create(
            page=self.page,
            name="Test AB",
            first_started_at=datetime(2023, 2, 15),
            variant_revision=self.page.get_latest_revision(),
            status=AbTest.STATUS_DRAFT,
            sample_size=10,
        )

    def test_check_ab_tests_hook_with_tests(self):
        response = self.client.get(
            reverse("wagtailadmin_pages:delete", args=[self.page.id])
        )

        self.assertRedirects(
            response,
            reverse("wagtail_ab_testing_admin:ab_test_delete", args=[self.page.id]),
            msg_prefix="Redirection to the delete A/B tests confirmation page failed.",
        )

    def test_check_ab_tests_hook_without_tests(self):
        AbTest.objects.all().delete()
        request = self.factory.get("/")
        response = check_ab_tests_for_page(request, self.page)
        self.assertIsNone(response)

    def test_ab_test_delete_view(self):
        response = self.client.get(
            reverse("wagtailadmin_pages:delete", args=[self.page.id]),
            follow=True,
        )
        self.assertTemplateUsed(response, "wagtail_ab_testing/delete_ab_tests.html")

        response = self.client.post(
            reverse("wagtail_ab_testing_admin:ab_test_delete", args=[self.page.id])
        )

        self.assertEqual(AbTest.objects.filter(page=self.page).count(), 0)

        self.assertRedirects(
            response,
            reverse("wagtailadmin_pages:delete", args=[self.page.id]),
            msg_prefix="The response did not redirect to the expected delete page. A/B Tests were not deleted.",
        )

    def test_ab_test_delete_view_without_delete_abtest_permission(self):
        delete_abtest_permission = Permission.objects.get(codename="delete_abtest")
        self.moderators_group.permissions.remove(delete_abtest_permission)
        self.user.save()

        response = self.client.get(
            reverse("wagtail_ab_testing_admin:ab_test_delete", args=[self.page.id])
        )

        self.assertRedirects(response, reverse("wagtailadmin_home"))
        self.assertEqual(
            response.context["message"],
            "Sorry, you do not have permission to access this area.",
        )

        response = self.client.post(
            reverse("wagtail_ab_testing_admin:ab_test_delete", args=[self.page.id])
        )

        self.assertRedirects(response, reverse("wagtailadmin_home"))
        self.assertEqual(
            response.context["message"],
            "Sorry, you do not have permission to access this area.",
        )

    def test_ab_test_delete_view_without_delete_page_permission(self):
        GroupPagePermission.objects.filter(
            group=self.moderators_group, permission__codename="change_page"
        ).delete()

        response = self.client.get(
            reverse("wagtail_ab_testing_admin:ab_test_delete", args=[self.page.id])
        )

        self.assertRedirects(response, reverse("wagtailadmin_home"))
        self.assertEqual(
            response.context["message"],
            "Sorry, you do not have permission to access this area.",
        )

        response = self.client.post(
            reverse("wagtail_ab_testing_admin:ab_test_delete", args=[self.page.id])
        )

        self.assertRedirects(response, reverse("wagtailadmin_home"))
        self.assertEqual(
            response.context["message"],
            "Sorry, you do not have permission to access this area.",
        )
