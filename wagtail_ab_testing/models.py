from datetime import datetime

from django.db import connection, models
from django.db.models import Sum
from django.utils.translation import gettext_lazy as __


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
    treatment_revision = models.ForeignKey('wagtailcore.PageRevision', on_delete=models.CASCADE, related_name='+')
    goal_type = models.CharField(max_length=255)
    # TODO Page chooser
    goal_page = models.ForeignKey('wagtailcore.Page', null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    sample_size = models.PositiveIntegerField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)

    objects = AbTestManager()

    def finish(self, cancel=False):
        """
        Finishes the test.
        """
        self.status = self.Status.CANCELLED if cancel else self.Status.COMPLETED

        self.save(update_fields=['status'])

    def log_new_participant(self, variant):
        """
        Inserts a new participant into the log.
        """
        AbTestHourlyLog._increment_stats(self, variant, 1, 0)

        # If we have now reached the required sample size, end the test
        # Note: we don't care too much that the last few participants won't
        # get a chance to turn into conversions. It's unlikely to make a
        # significant difference to the results.
        if self.hourly_logs.aggregate(total_participants=Sum('participants'))['total_participants'] >= self.sample_size:
            self.finish()

    def log_new_conversion(self, variant):
        """
        Inserts a conversion into the log.
        """
        AbTestHourlyLog._increment_stats(self, variant, 0, 1)


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
    def _increment_stats(cls, ab_test, variant, participants, conversions):
        """
        Increments the participants/conversions statistics for the given ab_test/variant.

        This will create a new AbTestHourlyLog record if one doesn't exist for the current hour.
        """
        time = datetime.utcnow()
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
