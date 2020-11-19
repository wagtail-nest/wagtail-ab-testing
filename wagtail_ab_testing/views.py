import datetime
import json
import random

from django import forms
from django.core.exceptions import PermissionDenied
from django.db.models import Sum, Q
from django.core.serializers.json import DjangoJSONEncoder
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _
from wagtail.admin import messages
from wagtail.core.models import Page, PAGE_MODEL_CLASSES

from .models import AbTest
from .events import EVENT_TYPES


class CreateAbTestForm(forms.ModelForm):
    goal_event = forms.ChoiceField(choices=[])
    hypothesis = forms.CharField(required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['goal_event'].choices = [
            (slug, goal.name)
            for slug, goal in EVENT_TYPES.items()
        ]

    def save(self, page, treatment_revision, user):
        ab_test = super().save(commit=False)
        ab_test.page = page
        ab_test.treatment_revision = treatment_revision
        ab_test.created_by = user
        ab_test.save()
        return ab_test

    class Meta:
        model = AbTest
        fields = ['name', 'hypothesis', 'goal_event', 'goal_page', 'sample_size']


def add_ab_test_checks(request, page):
    # User must have permission to edit the page
    page_perms = page.permissions_for_user(request.user)
    if not page_perms.can_edit():
        raise PermissionDenied

    # User must have permission to add A/B tests
    if not request.user.has_perm('wagtail_ab_testing.add_abtest'):
        raise PermissionDenied

    # Page must not already be running an A/B test
    if AbTest.objects.get_current_for_page(page=page):
        messages.error(request, _("This page already has a running A/B test"))

        return redirect('wagtailadmin_pages:edit', page.id)

    # Page must be published and have a draft revision
    if not page.live or not page.has_unpublished_changes:
        messages.error(request, _("To run an A/B test on this page, it must be live with draft changes."))

        return redirect('wagtailadmin_pages:edit', page.id)


def add_compare(request, page_id):
    page = get_object_or_404(Page, id=page_id)

    # Run some checks
    response = add_ab_test_checks(request, page)
    if response:
        return response

    return render(request, 'wagtail_ab_testing/add_compare.html', {
        'page': page,
    })


def add_form(request, page_id):
    page = get_object_or_404(Page, id=page_id)

    # Run some checks
    response = add_ab_test_checks(request, page)
    if response:
        return response

    if request.method == 'POST':
        form = CreateAbTestForm(request.POST)

        if form.is_valid():
            form.save(page, page.get_latest_revision(), request.user)

            return redirect('wagtailadmin_pages:edit', page.id)
    else:
        form = CreateAbTestForm()

    return render(request, 'wagtail_ab_testing/add_form.html', {
        'page': page,
        'form': form,
        'goal_selector_props': json.dumps({
            'testPageId': page.id,
            'goalTypesByPageType': {
                f'{page_type._meta.app_label}.{page_type._meta.model_name}': [
                    {
                        'slug': slug,
                        'name': event_type.name,
                    }
                    for slug, event_type in EVENT_TYPES.items()
                    if event_type.can_be_triggered_on_page_type(page_type)
                ]
                for page_type in PAGE_MODEL_CLASSES
            }
        }, cls=DjangoJSONEncoder)
    })


def progress(request, page, ab_test):
    # Fetch stats from database
    stats = ab_test.hourly_logs.aggregate(
        control_participants=Sum('participants', filter=Q(variant=AbTest.Variant.CONTROL)),
        control_conversions=Sum('conversions', filter=Q(variant=AbTest.Variant.CONTROL)),
        treatment_participants=Sum('participants', filter=Q(variant=AbTest.Variant.TREATMENT)),
        treatment_conversions=Sum('conversions', filter=Q(variant=AbTest.Variant.TREATMENT)),
    )
    control_participants = stats['control_participants'] or 0
    control_conversions = stats['control_conversions'] or 0
    treatment_participants = stats['treatment_participants'] or 0
    treatment_conversions = stats['treatment_conversions'] or 0

    current_sample_size = control_participants + treatment_participants

    if ab_test.status == AbTest.Status.RUNNING and current_sample_size:
        participants_per_day = current_sample_size / ab_test.total_running_duration()
        estimated_days_remaining = (ab_test.sample_size - current_sample_size) / participants_per_day
        estimated_completion_date = timezone.now().date() + datetime.timedelta(days=estimated_days_remaining)
    else:
        estimated_completion_date = None

    # Generate time series data for the chart
    time_series = []
    control = 0
    treatment = 0
    date = None
    for log in ab_test.hourly_logs.order_by('date', 'hour'):
        # Accumulate the conversions
        if log.variant == AbTest.Variant.CONTROL:
            control += log.conversions
        else:
            treatment += log.conversions

        while date is None or date < log.date:
            if date is None:
                # First record
                date = log.date
            else:
                # Move time forward to match log record
                date += datetime.timedelta(days=1)

            # Generate a log for this time
            time_series.append({
                'date': date,
                'control': control,
                'treatment': treatment,
            })

    return render(request, 'wagtail_ab_testing/progress.html', {
        'page': page,
        'ab_test': ab_test,
        'current_sample_size': current_sample_size,
        'current_sample_size_percent': int(current_sample_size / ab_test.sample_size * 100),
        'control_conversions': control_conversions,
        'control_participants': control_participants,
        'control_conversions_percent': int(control_conversions / control_participants * 100) if control_participants else 0,
        'treatment_conversions': treatment_conversions,
        'treatment_participants': treatment_participants,
        'treatment_conversions_percent': int(treatment_conversions / treatment_participants * 100) if treatment_participants else 0,
        'control_is_winner': ab_test.winning_variant == AbTest.Variant.CONTROL,
        'treatment_is_winner': ab_test.winning_variant == AbTest.Variant.TREATMENT,
        'estimated_completion_date': estimated_completion_date,
        'chart_data': json.dumps({
            'x': 'x',
            'columns': [
                ['x'] + [data_point['date'].isoformat() for data_point in time_series],
                [_("Control")] + [data_point['control'] for data_point in time_series],
                [_("Treatment")] + [data_point['treatment'] for data_point in time_series],
            ],
            'type': 'spline',
        }),
    })


# TEMPORARY
def add_test_participants(request, ab_test_id):
    ab_test = get_object_or_404(AbTest, id=ab_test_id)

    for i in range(int(ab_test.sample_size / 10)):
        ab_test.add_participant()

    return redirect('wagtailadmin_pages:edit', ab_test.page_id)


def add_test_conversions(request, ab_test_id, variant):
    ab_test = get_object_or_404(AbTest, id=ab_test_id)

    for i in range(int(ab_test.sample_size / 10)):
        ab_test.log_conversion(variant, time=timezone.now() - datetime.timedelta(days=random.randint(1, 20), hours=random.randint(0, 24)))

    return redirect('wagtailadmin_pages:edit', ab_test.page_id)
