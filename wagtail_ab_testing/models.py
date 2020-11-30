import random

from datetime import datetime, timedelta, timezone as tz

import scipy.stats
import numpy as np
from django.conf import settings
from django.db import connection, models
from django.db.models import Q, Sum
from django.dispatch import receiver
from django.utils import timezone
from django.utils.translation import gettext as _, gettext_lazy as __
from wagtail.core.signals import page_unpublished

from .events import EVENT_TYPES


class AbTestManager(models.Manager):
    def get_current_for_page(self, page):
        return self.get_queryset().filter(page=page).exclude(status__in=[AbTest.Status.CANCELLED, AbTest.Status.COMPLETED]).first()


class AbTest(models.Model):
    """
    Represents an A/B test that has been set up by the user.

    The live page content is used as the control, the revision pointed to in
    the `.treatment_revision` field contains the changes that are being tested.
    """

    class Status(models.TextChoices):
        DRAFT = 'draft', __('Draft')
        RUNNING = 'running', __('Running')
        PAUSED = 'paused', __('Paused')
        CANCELLED = 'cancelled', __('Cancelled')
        COMPLETED = 'completed', __('Completed')

    class Variant(models.TextChoices):
        CONTROL = 'control', __('Control')
        TREATMENT = 'treatment', __('Treatment')

    page = models.ForeignKey('wagtailcore.Page', on_delete=models.CASCADE, related_name='ab_tests')
    name = models.CharField(max_length=255)
    hypothesis = models.TextField(blank=True)
    treatment_revision = models.ForeignKey('wagtailcore.PageRevision', on_delete=models.CASCADE, related_name='+')
    goal_event = models.CharField(max_length=255)
    goal_page = models.ForeignKey('wagtailcore.Page', null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    sample_size = models.PositiveIntegerField()
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    winning_variant = models.CharField(max_length=9, null=True, choices=Variant.choices)
    first_started_at = models.DateTimeField(null=True)

    # Because an admin can pause/resume tests, we need to make sure we record the amount of time it has been running
    previous_run_duration = models.DurationField(default=timedelta(0))
    current_run_started_at = models.DateTimeField(null=True)

    objects = AbTestManager()

    def get_goal_event_display(self):
        """
        Returns the display name of the goal event.
        """
        for event_type_slug, event_type in EVENT_TYPES.items():
            if event_type_slug == self.goal_event:
                return event_type.name

        return self.goal_event

    def start(self):
        """
        Starts/unpauses the test.
        """
        if self.status in [self.Status.DRAFT, self.Status.PAUSED]:
            self.current_run_started_at = timezone.now()

            if self.status == self.Status.DRAFT:
                self.first_started_at = self.current_run_started_at

            self.status = self.Status.RUNNING

            self.save(update_fields=['status', 'current_run_started_at', 'first_started_at'])

    def pause(self):
        """
        Pauses the test.
        """
        if self.status == self.Status.RUNNING:
            self.status = self.Status.PAUSED

            if self.current_run_started_at is not None:
                self.previous_run_duration += timezone.now() - self.current_run_started_at
                self.current_run_started_at = None

            self.save(update_fields=['status', 'previous_run_duration', 'current_run_started_at'])

    def total_running_duration(self):
        """
        Returns the total duration that this test has been running.
        """
        duration = self.previous_run_duration

        if self.status == self.Status.RUNNING:
            duration += timezone.now() - self.current_run_started_at

        return duration

    def finish(self, *, cancel=False):
        """
        Finishes the test.
        """
        self.status = self.Status.CANCELLED if cancel else self.Status.COMPLETED

        if not cancel:
            self.winning_variant = self.check_for_winner()

        self.save(update_fields=['status', 'winning_variant'])

    def add_participant(self, variant=None):
        """
        Inserts a new participant into the log. Returns the variant that they should be shown.
        """
        # Get current numbers of participants for each variant
        stats = self.hourly_logs.aggregate(
            control_participants=Sum('participants', filter=Q(variant=self.Variant.CONTROL)),
            treatment_participants=Sum('participants', filter=Q(variant=self.Variant.TREATMENT)),
        )
        control_participants = stats['control_participants'] or 0
        treatment_participants = stats['treatment_participants'] or 0

        # Create an equal number of participants for each variant
        if variant is None:
            if treatment_participants > control_participants:
                variant = self.Variant.CONTROL

            elif treatment_participants < control_participants:
                variant = self.Variant.TREATMENT

            else:
                variant = random.choice([
                    self.Variant.CONTROL,
                    self.Variant.TREATMENT,
                ])

        # Add new participant to statistics model
        AbTestHourlyLog._increment_stats(self, variant, 1, 0)

        # If we have now reached the required sample size, end the test
        # Note: we don't care too much that the last few participants won't
        # get a chance to turn into conversions. It's unlikely to make a
        # significant difference to the results.
        # Note: Adding 1 to account for the new participant
        if control_participants + treatment_participants + 1 >= self.sample_size:
            self.finish()

        return variant

    def log_conversion(self, variant, *, time=None):
        """
        Logs when a participant completed the goal.

        Note: It's up to the caller to make sure that this doesn't get called more than once
        per participant.
        """
        AbTestHourlyLog._increment_stats(self, variant, 0, 1, time=time)

    def check_for_winner(self):
        """
        Performs a Chi-Squared test to check if there is a clear winner.

        Returns Variant.CONTROL or Variant.TREATMENT if there is one. Otherwise, it returns None.

        For more information on what the Chi-Squared test does, see:
        https://www.evanmiller.org/ab-testing/chi-squared.html
        https://towardsdatascience.com/a-b-testing-with-chi-squared-test-to-maximize-conversions-and-ctrs-6599271a2c31
        """
        # Fetch stats from database
        stats = self.hourly_logs.aggregate(
            control_participants=Sum('participants', filter=Q(variant=self.Variant.CONTROL)),
            control_conversions=Sum('conversions', filter=Q(variant=self.Variant.CONTROL)),
            treatment_participants=Sum('participants', filter=Q(variant=self.Variant.TREATMENT)),
            treatment_conversions=Sum('conversions', filter=Q(variant=self.Variant.TREATMENT)),
        )
        control_participants = stats['control_participants'] or 0
        control_conversions = stats['control_conversions'] or 0
        treatment_participants = stats['treatment_participants'] or 0
        treatment_conversions = stats['treatment_conversions'] or 0

        if not control_conversions and not treatment_conversions:
            return

        if control_conversions > control_participants or treatment_conversions > treatment_participants:
            # Something's up. I'm sure it's already clear in the UI what's going on, so let's not crash
            return

        # Create a numpy array with values to pass in to Chi-Squared test
        control_failures = control_participants - control_conversions
        treatment_failures = treatment_participants - treatment_conversions

        if control_failures == 0 and treatment_failures == 0:
            # Prevent this error: "The internally computed table of expected frequencies has a zero element at (0, 1)."
            return

        T = np.array([[control_conversions, control_failures], [treatment_conversions, treatment_failures]])

        # Perform Chi-Squared test
        p = scipy.stats.chi2_contingency(T, correction=False)[1]

        # Check if there is a clear winner
        required_confidence_level = 0.95  # 95%
        if 1 - p > required_confidence_level:
            # There is a clear winner!
            # Return the one with the highest success rate
            if (control_conversions / control_participants) > (treatment_conversions / treatment_participants):
                return self.Variant.CONTROL
            else:
                return self.Variant.TREATMENT

    def get_status_description(self):
        """
        Returns a string that describes the status in more detail.
        """
        status = self.get_status_display()

        if self.status == AbTest.Status.RUNNING:
            participants = self.hourly_logs.aggregate(participants=Sum('participants'))['participants'] or 0
            completeness_percentange = int((participants * 100) / self.sample_size)
            return status + f" ({completeness_percentange}%)"

        elif self.status == AbTest.Status.COMPLETED:
            if self.winning_variant == AbTest.Variant.CONTROL:
                return status + " (" + _("Control won") + ")"

            elif self.winning_variant == AbTest.Variant.TREATMENT:
                return status + " (" + _("Treatment won") + ")"

            else:
                return status + " (" + _("No clear winner") + ")"

        else:
            return status


class AbTestHourlyLog(models.Model):
    ab_test = models.ForeignKey(AbTest, on_delete=models.CASCADE, related_name='hourly_logs')
    variant = models.CharField(max_length=9, choices=AbTest.Variant.choices)
    date = models.DateField()
    # UTC hour. Values range from 0 to 23
    hour = models.PositiveSmallIntegerField()

    # New participants added in this hour
    participants = models.PositiveIntegerField(default=0)

    # New or existing participants that converted in this hour
    conversions = models.PositiveIntegerField(default=0)

    @classmethod
    def _increment_stats(cls, ab_test, variant, participants, conversions, *, time=None):
        """
        Increments the participants/conversions statistics for the given ab_test/variant.

        This will create a new AbTestHourlyLog record if one doesn't exist for the current hour.
        """
        time = time.astimezone(tz.utc) if time else datetime.utcnow()
        date = time.date()
        hour = time.hour

        if connection.vendor == 'postgresql':
            # Use fast, atomic UPSERT query on PostgreSQL
            with connection.cursor() as cursor:
                table_name = connection.ops.quote_name(cls._meta.db_table)
                query = """
                    INSERT INTO %s (ab_test_id, variant, date, hour, participants, conversions)
                    VALUES (%%s, %%s, %%s, %%s, %%s, %%s)
                    ON CONFLICT (ab_test_id, variant, date, hour)
                        DO UPDATE SET participants = %s.participants + %%s, conversions = %s.conversions + %%s;
                """ % (table_name, table_name, table_name)

                cursor.execute(query, [
                    ab_test.id,
                    variant,
                    date,
                    hour,
                    participants,
                    conversions,
                    participants,
                    conversions
                ])
        else:
            # Fall back to running two queries (with small potential for race conditions if things run slowly)
            hourly_log, created = cls.objects.get_or_create(
                ab_test=ab_test,
                variant=variant,
                date=date,
                hour=hour,
                defaults={
                    'participants': participants,
                    'conversions': conversions,
                }
            )

            if not created:
                hourly_log.participants += participants
                hourly_log.conversions += conversions
                hourly_log.save(update_fields=['participants', 'conversions'])

    class Meta:
        ordering = ['ab_test', 'variant', 'date', 'hour']
        unique_together = [
            ('ab_test', 'variant', 'date', 'hour'),
        ]


@receiver(page_unpublished)
def cancel_on_page_unpublish(instance, **kwargs):
    for ab_test in AbTest.objects.filter(page=instance, status__in=[AbTest.Status.DRAFT, AbTest.Status.RUNNING, AbTest.Status.PAUSED]):
        ab_test.finish(cancel=True)
