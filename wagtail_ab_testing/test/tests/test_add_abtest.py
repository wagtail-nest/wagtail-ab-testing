import json

from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse
from wagtail.core.models import Page
from wagtail.tests.utils import WagtailTestUtils

from wagtail_ab_testing.models import AbTest
from wagtail_ab_testing.test.models import SimplePage

from .utils import assert_permission_denied


class TestSaveAndCreateAbTestButton(WagtailTestUtils, TestCase):
    def setUp(self):
        self.user = self.login()

        # Convert the user into an moderator
        self.moderators_group = Group.objects.get(name="Moderators")
        for permission in Permission.objects.filter(content_type=ContentType.objects.get_for_model(AbTest)):
            self.moderators_group.permissions.add(permission)
        self.user.is_superuser = False
        self.user.groups.add(self.moderators_group)
        self.user.save()

        # Create test page with a draft revision
        self.page = Page.objects.get(id=1).add_child(instance=SimplePage(title="Test", slug="test"))
        self.page.save_revision().publish()

    def test_shows_on_page_edit(self):
        response = self.client.get(reverse('wagtailadmin_pages:edit', args=[self.page.id]))
        self.assertContains(response, "Save and create A/B Test")

    def test_click_on_page_edit(self):
        response = self.client.post(reverse('wagtailadmin_pages:edit', args=[self.page.id]), {
            'title': "Test version",
            'slug': "test",
            'create-ab-test': '',
        })
        self.assertRedirects(response, reverse('wagtail_ab_testing_admin:add_ab_test_compare', args=[self.page.id]))

    def test_doesnt_show_on_page_create(self):
        response = self.client.get(reverse('wagtailadmin_pages:add', args=["wagtail_ab_testing_test", "simplepage", self.page.id]))
        self.assertNotContains(response, "Save and create A/B Test")


# These tests are required for both the compare and form views
class PermissionTests:
    def test_without_page_edit_permission(self):
        self.moderators_group.page_permissions.all().delete()

        response = self.get(self.page.id)
        assert_permission_denied(self, response)

    def test_without_add_abtest_permission(self):
        add_abtest_permission = Permission.objects.get(codename='add_abtest')
        self.moderators_group.permissions.remove(add_abtest_permission)

        response = self.get(self.page.id)
        assert_permission_denied(self, response)

    def _create_abtest(self, status):
        AbTest.objects.create(
            page=self.page,
            name="Test",
            variant_revision=self.page.get_latest_revision(),
            status=status,
            sample_size=100,
        )

    def test_with_existing_draft_abtest(self):
        self._create_abtest(AbTest.STATUS_DRAFT)

        response = self.get(self.page.id)
        self.assertRedirects(response, reverse('wagtailadmin_pages:edit', args=[self.page.id]))

    def test_with_existing_running_abtest(self):
        self._create_abtest(AbTest.STATUS_RUNNING)

        response = self.get(self.page.id)
        self.assertRedirects(response, reverse('wagtailadmin_pages:edit', args=[self.page.id]))

    def test_with_existing_paused_abtest(self):
        self._create_abtest(AbTest.STATUS_PAUSED)

        response = self.get(self.page.id)
        self.assertRedirects(response, reverse('wagtailadmin_pages:edit', args=[self.page.id]))

    def test_with_existing_cancelled_abtest(self):
        self._create_abtest(AbTest.STATUS_CANCELLED)

        response = self.get(self.page.id)
        self.assertEqual(response.status_code, 200)

    def test_with_existing_finished_abtest(self):
        self._create_abtest(AbTest.STATUS_FINISHED)

        response = self.get(self.page.id)
        self.assertRedirects(response, reverse('wagtailadmin_pages:edit', args=[self.page.id]))

    def test_with_existing_completed_abtest(self):
        self._create_abtest(AbTest.STATUS_COMPLETED)

        response = self.get(self.page.id)
        self.assertEqual(response.status_code, 200)


class TestAddAbTestCompareView(WagtailTestUtils, TestCase, PermissionTests):
    def setUp(self):
        self.user = self.login()

        # Convert the user into an moderator
        self.moderators_group = Group.objects.get(name="Moderators")
        for permission in Permission.objects.filter(content_type=ContentType.objects.get_for_model(AbTest)):
            self.moderators_group.permissions.add(permission)
        self.user.is_superuser = False
        self.user.groups.add(self.moderators_group)
        self.user.save()

        # Create test page with a draft revision
        self.page = Page.objects.get(id=1).add_child(instance=SimplePage(title="Test", slug="test"))
        self.page.save_revision().publish()
        self.page.title = "Test version"
        self.latest_revision = self.page.save_revision()

    def get(self, page_id):
        return self.client.get(reverse('wagtail_ab_testing_admin:add_ab_test_compare', args=[page_id]))

    def test_get_add_compare(self):
        response = self.get(self.page.id)
        self.assertEqual(response.status_code, 200)


class TestAddAbTestFormView(WagtailTestUtils, TestCase, PermissionTests):
    def setUp(self):
        self.user = self.login()

        # Convert the user into an moderator
        self.moderators_group = Group.objects.get(name="Moderators")
        for permission in Permission.objects.filter(content_type=ContentType.objects.get_for_model(AbTest)):
            self.moderators_group.permissions.add(permission)
        self.user.is_superuser = False
        self.user.groups.add(self.moderators_group)
        self.user.save()

        # Create test page with a draft revision
        self.page = Page.objects.get(id=1).add_child(instance=SimplePage(title="Test", slug="test"))
        self.page.save_revision().publish()
        self.page.title = "Test version"
        self.latest_revision = self.page.save_revision()

    def get(self, page_id):
        return self.client.get(reverse('wagtail_ab_testing_admin:add_ab_test_form', args=[page_id]))

    def test_get_add_form(self):
        response = self.get(self.page.id)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.context['goal_selector_props']), {
            "goalTypesByPageType": {
                "wagtailcore.page": [{"slug": "visit-page", "name": "Visit page"}],
                "wagtail_ab_testing_test.simplepage": [{"slug": "visit-page", "name": "Visit page"}]
            }
        })

    def test_post_add_form(self):
        response = self.client.post(reverse('wagtail_ab_testing_admin:add_ab_test_form', args=[self.page.id]), {
            'name': 'Test',
            'hypothesis': 'Does changing the title to "Donate now!" increase donations?',
            'goal_event': 'visit-page',
            'goal_page': '',
            'sample_size': '100'
        })
        self.assertRedirects(response, reverse('wagtailadmin_pages:edit', args=[self.page.id]))

        ab_test = AbTest.objects.get()
        self.assertEqual(ab_test.page, self.page.page_ptr)
        self.assertEqual(ab_test.variant_revision, self.latest_revision)
        self.assertEqual(ab_test.name, 'Test')
        self.assertEqual(ab_test.hypothesis, 'Does changing the title to "Donate now!" increase donations?')
        self.assertEqual(ab_test.goal_event, 'visit-page')
        self.assertIsNone(ab_test.goal_page)
        self.assertEqual(ab_test.sample_size, 100)
        self.assertEqual(ab_test.created_by, self.user)
        self.assertEqual(ab_test.status, AbTest.STATUS_DRAFT)

    def test_post_add_form_start(self):
        response = self.client.post(reverse('wagtail_ab_testing_admin:add_ab_test_form', args=[self.page.id]), {
            'name': 'Test',
            'hypothesis': 'Does changing the title to "Donate now!" increase donations?',
            'goal_event': 'visit-page',
            'goal_page': '',
            'sample_size': '100',
            'start': 'on'
        })
        self.assertRedirects(response, reverse('wagtailadmin_pages:edit', args=[self.page.id]))

        ab_test = AbTest.objects.get()
        self.assertEqual(ab_test.status, AbTest.STATUS_RUNNING)

    def test_post_add_form_start_without_publish_permission(self):
        self.moderators_group.page_permissions.filter(permission_type='publish').delete()

        response = self.client.post(reverse('wagtail_ab_testing_admin:add_ab_test_form', args=[self.page.id]), {
            'name': 'Test',
            'hypothesis': 'Does changing the title to "Donate now!" increase donations?',
            'goal_event': 'visit-page',
            'goal_page': '',
            'sample_size': '100',
            'start': 'on'
        })
        self.assertRedirects(response, reverse('wagtailadmin_pages:edit', args=[self.page.id]))

        ab_test = AbTest.objects.get()
        self.assertEqual(ab_test.status, AbTest.STATUS_DRAFT)
