import random
from datetime import datetime, timedelta
from datetime import timezone as tz

import numpy as np
import scipy.stats
from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import connection, models, transaction
from django.db.models import Q, Sum
from django.dispatch import receiver
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy as __
from wagtail.signals import page_unpublished

from .events import get_event_types


class AbTestManager(models.Manager):
    def get_current_for_page(self, page):
        return (
            self.get_queryset()
            .filter(page=page)
            .exclude(status__in=[AbTest.STATUS_CANCELLED, AbTest.STATUS_COMPLETED])
            .first()
        )


class AbTest(models.Model):
    """
    Represents an A/B test that has been set up by the user.

    The live page content is used as the control, the revision pointed to in
    the `.variant_revision` field contains the changes that are being tested.
    """

    STATUS_DRAFT = "draft"
    STATUS_RUNNING = "running"
    STATUS_PAUSED = "paused"
    STATUS_CANCELLED = "cancelled"
    # These two sound similar, but there's a difference:
    # 'Finished' means that we've reached the sample size and testing has stopped
    # but the user still needs to decide whether to publish the variant version
    # or revert back to the control.
    # Once they've decided and that action has taken place, the test status is
    # updated to 'Completed'.
    STATUS_FINISHED = "finished"
    STATUS_COMPLETED = "completed"

    STATUS_CHOICES = [
        (STATUS_DRAFT, __("Draft")),
        (STATUS_RUNNING, __("Running")),
        (STATUS_PAUSED, __("Paused")),
        (STATUS_CANCELLED, __("Cancelled")),
        (STATUS_FINISHED, __("Finished")),
        (STATUS_COMPLETED, __("Completed")),
    ]

    VERSION_CONTROL = "control"
    VERSION_VARIANT = "variant"

    VERSION_CHOICES = [
        (VERSION_CONTROL, __("Control")),
        (VERSION_VARIANT, __("Variant")),
    ]

    COMPLETION_ACTION_DO_NOTHING = "do-nothing"
    COMPLETION_ACTION_REVERT = "revert"
    COMPLETION_ACTION_PUBLISH = "publish"

    COMPLETION_ACTION_CHOICES = [
        (COMPLETION_ACTION_DO_NOTHING, "Do nothing"),
        (COMPLETION_ACTION_REVERT, "Revert"),
        (COMPLETION_ACTION_PUBLISH, "Publish"),
    ]

    page = models.ForeignKey(
        "wagtailcore.Page", on_delete=models.CASCADE, related_name="ab_tests"
    )
    name = models.CharField(max_length=255)
    hypothesis = models.TextField(blank=True)
    variant_revision = models.ForeignKey(
        "wagtailcore.Revision", on_delete=models.PROTECT, related_name="+"
    )
    goal_event = models.CharField(max_length=255)
    goal_page = models.ForeignKey(
        "wagtailcore.Page",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    sample_size = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT
    )
    winning_version = models.CharField(max_length=9, null=True, choices=VERSION_CHOICES)
    first_started_at = models.DateTimeField(null=True)

    # Because an admin can pause/resume tests, we need to make sure we record the amount of time it has been running
    previous_run_duration = models.DurationField(default=timedelta(0))
    current_run_started_at = models.DateTimeField(null=True)

    objects = AbTestManager()

    def get_goal_event_display(self):
        """
        Returns the display name of the goal event.
        """
        for event_type_slug, event_type in get_event_types().items():
            if event_type_slug == self.goal_event:
                return event_type.name

        return self.goal_event

    def start(self):
        """
        Starts/unpauses the test.
        """
        if self.status in [self.STATUS_DRAFT, self.STATUS_PAUSED]:
            self.current_run_started_at = timezone.now()

            if self.status == self.STATUS_DRAFT:
                self.first_started_at = self.current_run_started_at

            self.status = self.STATUS_RUNNING

            self.save(
                update_fields=["status", "current_run_started_at", "first_started_at"]
            )

    def pause(self):
        """
        Pauses the test.
        """
        if self.status == self.STATUS_RUNNING:
            self.status = self.STATUS_PAUSED

            if self.current_run_started_at is not None:
                self.previous_run_duration += (
                    timezone.now() - self.current_run_started_at
                )
                self.current_run_started_at = None

            self.save(
                update_fields=[
                    "status",
                    "previous_run_duration",
                    "current_run_started_at",
                ]
            )

    def get_results_url(self):
        """
        Returns the URL to the page wherethe user can see the results.

        While the test is running, this is the URL of the edit view.
        Afterwards, we need to send them to a separate view as the
        page editor returns to normal.
        """
        if self.status in [AbTest.STATUS_COMPLETED, AbTest.STATUS_CANCELLED]:
            return reverse(
                "wagtail_ab_testing_admin:results", args=[self.page_id, self.id]
            )

        else:
            return reverse("wagtailadmin_pages:edit", args=[self.page_id])

    def total_running_duration(self):
        """
        Returns the total duration that this test has been running.
        """
        duration = self.previous_run_duration

        if self.status == self.STATUS_RUNNING:
            duration += timezone.now() - self.current_run_started_at

        return duration

    def cancel(self):
        """
        Cancels the test.
        """
        self.status = self.STATUS_CANCELLED

        self.save(update_fields=["status"])

    def finish(self):
        """
        Finishes the testing.

        Note that this doesn't 'complete' the test: a finished test means
        that testing is no longer happening. The test is not complete until
        the user decides on the outcome of the test (keep the control or
        publish the variant). This decision is set using the .complete()
        method.
        """
        self.status = self.STATUS_FINISHED
        self.winning_version = self.check_for_winner()

        self.save(update_fields=["status", "winning_version"])

    @transaction.atomic
    def complete(self, action, user=None):
        """
        Completes the test and carries out the specificed action.

        Actions can be:
         - AbTest.COMPLETION_ACTION_DO_NOTHING - This just completes
           the test but does nothing to the page. The control will
           remain the published version and the variant will be
           in draft.
         - AbTest.COMPLETION_ACTION_REVERT - This completes the test
           and also creates a new revision to revert the content back
           to what it was in the control while the test was taking
           place.
         - AbTest.COMPLETION_ACTION_PUBLISH - This completes the test
           and also publishes the variant revision.
        """
        self.status = self.STATUS_COMPLETED
        self.save(update_fields=["status"])

        if action == AbTest.COMPLETION_ACTION_DO_NOTHING:
            pass

        elif action == AbTest.COMPLETION_ACTION_REVERT:
            # Create a new revision with the content of the live page and publish it
            self.page.specific.save_revision(
                user=user, previous_revision=self.page.live_revision
            ).publish(user=user)

        elif action == AbTest.COMPLETION_ACTION_PUBLISH:
            self.variant_revision.publish(user=user)

    def get_participation_numbers(self):
        """
        Returns a 2-tuple containing the number of participants who were given the control or variant version of the page respectively.
        """
        stats = self.hourly_logs.aggregate(
            control_participants=Sum(
                "participants", filter=Q(version=self.VERSION_CONTROL)
            ),
            variant_participants=Sum(
                "participants", filter=Q(version=self.VERSION_VARIANT)
            ),
        )
        control_participants = stats["control_participants"] or 0
        variant_participants = stats["variant_participants"] or 0

        return control_participants, variant_participants

    def get_new_participant_version(self, participation_numbers=None):
        """
        Returns the version of the page to display to a new participant.
        This balances the number of participants between the two variants.
        """
        if participation_numbers is None:
            participation_numbers = self.get_participation_numbers()

        control_participants, variant_participants = participation_numbers

        if variant_participants > control_participants:
            return self.VERSION_CONTROL

        elif variant_participants < control_participants:
            return self.VERSION_VARIANT

        else:
            return random.choice(
                [
                    self.VERSION_CONTROL,
                    self.VERSION_VARIANT,
                ]
            )

    def add_participant(self, version=None):
        """
        Inserts a new participant into the log. Returns the version that they should be shown.
        """
        # Get current numbers of participants for each version
        control_participants, variant_participants = self.get_participation_numbers()

        # Create an equal number of participants for each version
        if version is None:
            # Note, pass participation numbers we already have to save a database query
            version = self.get_new_participant_version(
                participation_numbers=(control_participants, variant_participants)
            )

        # Add new participant to statistics model
        AbTestHourlyLog._increment_stats(self, version, 1, 0)

        # If we have now reached the required sample size, end the test
        # Note: we don't care too much that the last few participants won't
        # get a chance to turn into conversions. It's unlikely to make a
        # significant difference to the results.
        # Note: Adding 1 to account for the new participant
        if control_participants + variant_participants + 1 >= self.sample_size:
            self.finish()

        return version

    def log_conversion(self, version, *, time=None):
        """
        Logs when a participant completed the goal.

        Note: It's up to the caller to make sure that this doesn't get called more than once
        per participant.
        """
        AbTestHourlyLog._increment_stats(self, version, 0, 1, time=time)

    def check_for_winner(self):
        """
        Performs a Chi-Squared test to check if there is a clear winner.

        Returns VERSION_CONTROL or VERSION_VARIANT if there is one. Otherwise, it returns None.

        For more information on what the Chi-Squared test does, see:
        https://www.evanmiller.org/ab-testing/chi-squared.html
        https://towardsdatascience.com/a-b-testing-with-chi-squared-test-to-maximize-conversions-and-ctrs-6599271a2c31
        """
        # Fetch stats from database
        stats = self.hourly_logs.aggregate(
            control_participants=Sum(
                "participants", filter=Q(version=self.VERSION_CONTROL)
            ),
            control_conversions=Sum(
                "conversions", filter=Q(version=self.VERSION_CONTROL)
            ),
            variant_participants=Sum(
                "participants", filter=Q(version=self.VERSION_VARIANT)
            ),
            variant_conversions=Sum(
                "conversions", filter=Q(version=self.VERSION_VARIANT)
            ),
        )
        control_participants = stats["control_participants"] or 0
        control_conversions = stats["control_conversions"] or 0
        variant_participants = stats["variant_participants"] or 0
        variant_conversions = stats["variant_conversions"] or 0

        if not control_conversions and not variant_conversions:
            return

        if (
            control_conversions > control_participants
            or variant_conversions > variant_participants
        ):
            # Something's up. I'm sure it's already clear in the UI what's going on, so let's not crash
            return

        # Create a numpy array with values to pass in to Chi-Squared test
        control_failures = control_participants - control_conversions
        variant_failures = variant_participants - variant_conversions

        if control_failures == 0 and variant_failures == 0:
            # Prevent this error: "The internally computed table of expected frequencies has a zero element at (0, 1)."
            return

        T = np.array(
            [
                [control_conversions, control_failures],
                [variant_conversions, variant_failures],
            ]
        )

        # Perform Chi-Squared test
        p = scipy.stats.chi2_contingency(T, correction=False)[1]

        # Check if there is a clear winner
        required_confidence_level = 0.95  # 95%
        if 1 - p > required_confidence_level:
            # There is a clear winner!
            # Return the one with the highest success rate
            if (control_conversions / control_participants) > (
                variant_conversions / variant_participants
            ):
                return self.VERSION_CONTROL
            else:
                return self.VERSION_VARIANT

    def get_status_description(self):
        """
        Returns a string that describes the status in more detail.
        """
        status = self.get_status_display()

        if self.status == AbTest.STATUS_RUNNING:
            participants = (
                self.hourly_logs.aggregate(participants=Sum("participants"))[
                    "participants"
                ]
                or 0
            )
            completeness_percentange = int((participants * 100) / self.sample_size)
            return status + f" ({completeness_percentange}%)"

        elif self.status in [AbTest.STATUS_FINISHED, AbTest.STATUS_COMPLETED]:
            if self.winning_version == AbTest.VERSION_CONTROL:
                return status + " (" + _("Control won") + ")"

            elif self.winning_version == AbTest.VERSION_VARIANT:
                return status + " (" + _("Variant won") + ")"

            else:
                return status + " (" + _("No clear winner") + ")"

        else:
            return status


class AbTestHourlyLog(models.Model):
    ab_test = models.ForeignKey(
        AbTest, on_delete=models.CASCADE, related_name="hourly_logs"
    )
    version = models.CharField(max_length=9, choices=AbTest.VERSION_CHOICES)
    date = models.DateField()
    # UTC hour. Values range from 0 to 23
    hour = models.PositiveSmallIntegerField()

    # New participants added in this hour
    participants = models.PositiveIntegerField(default=0)

    # New or existing participants that converted in this hour
    conversions = models.PositiveIntegerField(default=0)

    @classmethod
    def _increment_stats(
        cls, ab_test, version, participants, conversions, *, time=None
    ):
        """
        Increments the participants/conversions statistics for the given ab_test/version.

        This will create a new AbTestHourlyLog record if one doesn't exist for the current hour.
        """
        time = time.astimezone(tz.utc) if time else datetime.now(tz.utc)
        date = time.date()
        hour = time.hour

        if connection.vendor == "postgresql":
            # Use fast, atomic UPSERT query on PostgreSQL
            # This needs to be done as a raw query because Django's ORM doesn't support atomic UPSERTs
            with connection.cursor() as cursor:
                table_name = connection.ops.quote_name(cls._meta.db_table)

                query = (
                    """
                    INSERT INTO %s (ab_test_id, version, date, hour, participants, conversions)
                    VALUES (%%s, %%s, %%s, %%s, %%s, %%s)
                    ON CONFLICT (ab_test_id, version, date, hour)
                        DO UPDATE SET participants = %s.participants + %%s, conversions = %s.conversions + %%s;
                """  # noqa: UP031 - percent format is fine here
                    % (
                        table_name,
                        table_name,
                        table_name,
                    )
                )

                cursor.execute(
                    query,
                    [
                        ab_test.id,
                        version,
                        date,
                        hour,
                        participants,
                        conversions,
                        participants,
                        conversions,
                    ],
                )
        else:
            # Fall back to running two queries. This is less efficient.
            # We cannot use the simpler update_or_create here
            # because it holds a lock on the row for the duration
            # it takes to run the update query
            hourly_log, created = cls.objects.get_or_create(
                ab_test=ab_test,
                version=version,
                date=date,
                hour=hour,
                defaults={
                    "participants": participants,
                    "conversions": conversions,
                },
            )

            if not created:
                hourly_log.participants = models.F("participants") + participants
                hourly_log.conversions = models.F("conversions") + conversions
                hourly_log.save(update_fields=["participants", "conversions"])

    class Meta:
        ordering = ["ab_test", "version", "date", "hour"]
        unique_together = [
            ("ab_test", "version", "date", "hour"),
        ]


@receiver(page_unpublished)
def cancel_on_page_unpublish(instance, **kwargs):
    for ab_test in AbTest.objects.filter(
        page=instance,
        status__in=[AbTest.STATUS_DRAFT, AbTest.STATUS_RUNNING, AbTest.STATUS_PAUSED],
    ):
        ab_test.cancel()

    for ab_test in AbTest.objects.filter(page=instance, status=AbTest.STATUS_FINISHED):
        ab_test.complete(AbTest.COMPLETION_ACTION_DO_NOTHING)
