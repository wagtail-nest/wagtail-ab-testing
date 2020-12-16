from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse
from wagtail.core.models import Page
from wagtail.tests.utils import WagtailTestUtils

from wagtail_ab_testing.models import AbTest
from wagtail_ab_testing.test.models import SimplePage


class TestProgressView(WagtailTestUtils, TestCase):
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

        # Edit the page and save a revision
        self.page.title = "Test updated"
        revision = self.page.save_revision()

        # Create an A/B test
        self.ab_test = AbTest.objects.create(
            page=self.page,
            name="Test",
            variant_revision=revision,
            status=AbTest.STATUS_RUNNING,
            sample_size=100,
        )

    def test_get_progress(self):
        response = self.client.get(reverse('wagtailadmin_pages:edit', args=[self.page.id]))

        self.assertNotContains(response, "Save draft")
        self.assertTemplateUsed(response, "wagtail_ab_testing/progress.html")

    def test_post_start(self):
        self.ab_test.status = AbTest.STATUS_DRAFT
        self.ab_test.save()

        response = self.client.post(reverse('wagtailadmin_pages:edit', args=[self.page.id]), {
            'action-start-ab-test': 'on',
        })

        self.assertRedirects(response, reverse('wagtailadmin_pages:edit', args=[self.page.id]))

        self.ab_test.refresh_from_db()

        self.assertEqual(self.ab_test.status, AbTest.STATUS_RUNNING)

    def test_post_pause(self):
        response = self.client.post(reverse('wagtailadmin_pages:edit', args=[self.page.id]), {
            'action-pause-ab-test': 'on',
        })

        self.assertRedirects(response, reverse('wagtailadmin_pages:edit', args=[self.page.id]))

        self.ab_test.refresh_from_db()

        self.assertEqual(self.ab_test.status, AbTest.STATUS_PAUSED)

    def test_post_restart(self):
        self.ab_test.status = AbTest.STATUS_PAUSED
        self.ab_test.save()

        response = self.client.post(reverse('wagtailadmin_pages:edit', args=[self.page.id]), {
            'action-restart-ab-test': 'on',
        })

        self.assertRedirects(response, reverse('wagtailadmin_pages:edit', args=[self.page.id]))

        self.ab_test.refresh_from_db()

        self.assertEqual(self.ab_test.status, AbTest.STATUS_RUNNING)

    def test_post_end(self):
        response = self.client.post(reverse('wagtailadmin_pages:edit', args=[self.page.id]), {
            'action-end-ab-test': 'on',
        })

        self.assertRedirects(response, reverse('wagtailadmin_pages:edit', args=[self.page.id]))

        self.ab_test.refresh_from_db()

        self.assertEqual(self.ab_test.status, AbTest.STATUS_CANCELLED)

    def test_post_start_without_publish_permission(self):
        self.moderators_group.page_permissions.filter(permission_type='publish').delete()

        self.ab_test.status = AbTest.STATUS_DRAFT
        self.ab_test.save()

        response = self.client.post(reverse('wagtailadmin_pages:edit', args=[self.page.id]), {
            'action-start-ab-test': 'on',
        })

        self.assertRedirects(response, reverse('wagtailadmin_pages:edit', args=[self.page.id]))

        self.ab_test.refresh_from_db()

        self.assertEqual(self.ab_test.status, AbTest.STATUS_DRAFT)

    def test_post_pause_without_publish_permission(self):
        self.moderators_group.page_permissions.filter(permission_type='publish').delete()

        response = self.client.post(reverse('wagtailadmin_pages:edit', args=[self.page.id]), {
            'action-pause-ab-test': 'on',
        })

        self.assertRedirects(response, reverse('wagtailadmin_pages:edit', args=[self.page.id]))

        self.ab_test.refresh_from_db()

        self.assertEqual(self.ab_test.status, AbTest.STATUS_RUNNING)

    def test_post_restart_without_publish_permission(self):
        self.moderators_group.page_permissions.filter(permission_type='publish').delete()

        self.ab_test.status = AbTest.STATUS_PAUSED
        self.ab_test.save()

        response = self.client.post(reverse('wagtailadmin_pages:edit', args=[self.page.id]), {
            'action-restart-ab-test': 'on',
        })

        self.assertRedirects(response, reverse('wagtailadmin_pages:edit', args=[self.page.id]))

        self.ab_test.refresh_from_db()
        self.assertEqual(self.ab_test.status, AbTest.STATUS_PAUSED)

    def test_post_end_without_publish_permission(self):
        self.moderators_group.page_permissions.filter(permission_type='publish').delete()

        response = self.client.post(reverse('wagtailadmin_pages:edit', args=[self.page.id]), {
            'action-end-ab-test': 'on',
        })

        self.assertRedirects(response, reverse('wagtailadmin_pages:edit', args=[self.page.id]))

        self.ab_test.refresh_from_db()
        self.assertEqual(self.ab_test.status, AbTest.STATUS_RUNNING)

    def test_post_end_when_finished(self):
        self.ab_test.status = AbTest.STATUS_FINISHED
        self.ab_test.save()

        response = self.client.post(reverse('wagtailadmin_pages:edit', args=[self.page.id]), {
            'action-end-ab-test': 'on',
        })

        self.assertRedirects(response, reverse('wagtailadmin_pages:edit', args=[self.page.id]))

        self.ab_test.refresh_from_db()

        self.assertEqual(self.ab_test.status, AbTest.STATUS_COMPLETED)
        self.assertEqual(self.ab_test.page.title, "Test")
        self.assertTrue(self.ab_test.page.has_unpublished_changes)

    def test_post_select_control(self):
        self.ab_test.status = AbTest.STATUS_FINISHED
        self.ab_test.save()

        response = self.client.post(reverse('wagtailadmin_pages:edit', args=[self.page.id]), {
            'action-select-control': 'on',
        })

        self.assertRedirects(response, reverse('wagtailadmin_pages:edit', args=[self.page.id]))

        self.ab_test.refresh_from_db()
        self.assertEqual(self.ab_test.status, AbTest.STATUS_COMPLETED)
        self.assertEqual(self.ab_test.page.title, "Test")
        self.assertFalse(self.ab_test.page.has_unpublished_changes)

    def test_post_select_variant(self):
        self.ab_test.status = AbTest.STATUS_FINISHED
        self.ab_test.save()

        response = self.client.post(reverse('wagtailadmin_pages:edit', args=[self.page.id]), {
            'action-select-variant': 'on',
        })

        self.assertRedirects(response, reverse('wagtailadmin_pages:edit', args=[self.page.id]))

        self.ab_test.refresh_from_db()
        self.assertEqual(self.ab_test.status, AbTest.STATUS_COMPLETED)
        self.assertEqual(self.ab_test.page.title, "Test updated")
        self.assertFalse(self.ab_test.page.has_unpublished_changes)
