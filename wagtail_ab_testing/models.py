from django.db import models
from django.utils.translation import gettext_lazy as __


class AbTestManager(models.Manager):
    def get_current_for_page(self, page):
        return self.get_queryset().filter(page=page).exclude(status__in=[AbTest.Status.CANCELLED, AbTest.Status.COMPLETED]).first()


class AbTest(models.Model):
    class Status(models.TextChoices):
        DRAFT = 'draft', __('Draft')
        RUNNING = 'running', __('Running')
        PAUSED = 'paused', __('Paused')
        CANCELLED = 'cancelled', __('Cancelled')
        COMPLETED = 'completed', __('Completed')

    page = models.ForeignKey('wagtailcore.Page', on_delete=models.CASCADE, related_name='ab_tests')
    name = models.CharField(max_length=255)
    variant_revision = models.ForeignKey('wagtailcore.PageRevision', on_delete=models.CASCADE, related_name='+')
    goal_type = models.CharField(max_length=255)
    # TODO Page chooser
    goal_page = models.ForeignKey('wagtailcore.Page', null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    sample_size = models.PositiveIntegerField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)

    objects = AbTestManager()
