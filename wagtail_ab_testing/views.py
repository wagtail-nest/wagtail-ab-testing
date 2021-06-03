import datetime
import json

from django import forms
from django.core.exceptions import PermissionDenied
from django.db.models import Sum, Q, F
from django.core.serializers.json import DjangoJSONEncoder
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.functional import cached_property
from django.utils.translation import gettext as _, gettext_lazy
from django.views.decorators.csrf import csrf_exempt
import django_filters
from django_filters.constants import EMPTY_VALUES
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from wagtail.admin import messages
from wagtail.admin.action_menu import ActionMenuItem
from wagtail.admin.filters import DateRangePickerWidget, WagtailFilterSet
from wagtail.admin.views.reports import ReportView
from wagtail.core.models import Page, PAGE_MODEL_CLASSES, UserPagePermissionsProxy

from .models import AbTest
from .events import get_event_types


class CreateAbTestForm(forms.ModelForm):
    goal_event = forms.ChoiceField(choices=[])
    hypothesis = forms.CharField(required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['goal_event'].choices = [
            (slug, goal.name)
            for slug, goal in get_event_types().items()
        ]

    def save(self, page, variant_revision, user):
        ab_test = super().save(commit=False)
        ab_test.page = page
        ab_test.variant_revision = variant_revision
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
    page = get_object_or_404(Page, id=page_id).specific

    # Run some checks
    response = add_ab_test_checks(request, page)
    if response:
        return response

    latest_revision_as_page = page.get_latest_revision().as_page_object()
    comparison = page.get_edit_handler().get_comparison()
    comparison = [comp(page, latest_revision_as_page) for comp in comparison]
    comparison = [comp for comp in comparison if comp.has_changed()]

    return render(request, 'wagtail_ab_testing/add_compare.html', {
        'page': page,
        'latest_revision_as_page': latest_revision_as_page,
        'comparison': comparison,
        'differences': any(comp.has_changed() for comp in comparison),
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
            ab_test = form.save(page, page.get_latest_revision(), request.user)

            if 'start' in request.POST:
                page_perms = page.permissions_for_user(request.user)
                if page_perms.can_publish():
                    ab_test.start()

                    messages.success(request, _("The A/B test has been created and started."))
                else:
                    messages.error(request, _("The A/B test has been created but you do not have permission to publish so it couldn't be started."))

            else:
                messages.success(request, _("The A/B test has been created."))

            return redirect('wagtailadmin_pages:edit', page.id)
    else:
        form = CreateAbTestForm()

    return render(request, 'wagtail_ab_testing/add_form.html', {
        'page': page,
        'form': form,
        'goal_selector_props': json.dumps({
            'goalTypesByPageType': {
                f'{page_type._meta.app_label}.{page_type._meta.model_name}': [
                    {
                        'slug': slug,
                        'name': event_type.name,
                    }
                    for slug, event_type in get_event_types().items()
                    if event_type.can_be_triggered_on_page_type(page_type)
                ]
                for page_type in PAGE_MODEL_CLASSES
            }
        }, cls=DjangoJSONEncoder)
    })


class StartAbTestMenuItem(ActionMenuItem):
    name = 'action-start-ab-test'
    label = _("Start A/B test")

    def is_shown(self, request, context):
        if not context['user_page_permissions'].for_page(context['ab_test'].page).can_publish():
            return False

        return context['ab_test'].status == AbTest.STATUS_DRAFT


class RestartAbTestMenuItem(ActionMenuItem):
    name = 'action-restart-ab-test'
    label = _("Restart A/B test")

    def is_shown(self, request, context):
        if not context['user_page_permissions'].for_page(context['ab_test'].page).can_publish():
            return False

        return context['ab_test'].status == AbTest.STATUS_PAUSED


class EndAbTestMenuItem(ActionMenuItem):
    name = 'action-end-ab-test'
    label = _("End A/B test")

    def is_shown(self, request, context):
        if not context['user_page_permissions'].for_page(context['ab_test'].page).can_publish():
            return False

        return context['ab_test'].status in [AbTest.STATUS_DRAFT, AbTest.STATUS_RUNNING, AbTest.STATUS_PAUSED]


class PauseAbTestMenuItem(ActionMenuItem):
    name = 'action-pause-ab-test'
    label = _("Pause A/B test")

    def is_shown(self, request, context):
        if not context['user_page_permissions'].for_page(context['ab_test'].page).can_publish():
            return False

        return context['ab_test'].status == AbTest.STATUS_RUNNING


class AbTestActionMenu:
    template = 'wagtailadmin/pages/action_menu/menu.html'

    def __init__(self, request, **kwargs):
        self.request = request
        self.context = kwargs
        self.context['user_page_permissions'] = UserPagePermissionsProxy(self.request.user)

        self.menu_items = [
            StartAbTestMenuItem(order=0),
            RestartAbTestMenuItem(order=1),
            EndAbTestMenuItem(order=2),
            PauseAbTestMenuItem(order=3),
        ]

        self.menu_items = [
            menu_item
            for menu_item in self.menu_items
            if menu_item.is_shown(self.request, self.context)
        ]

        try:
            self.default_item = self.menu_items.pop(0)
        except IndexError:
            self.default_item = None

    def render_html(self):
        return render_to_string(self.template, {
            'default_menu_item': self.default_item.render_html(self.request, self.context),
            'show_menu': bool(self.menu_items),
            'rendered_menu_items': [
                menu_item.render_html(self.request, self.context)
                for menu_item in self.menu_items
            ],
        }, request=self.request)

    @cached_property
    def media(self):
        media = forms.Media()
        for item in self.menu_items:
            media += item.media
        return media


def get_progress_and_results_common_context(request, page, ab_test):
    # Fetch stats from database
    stats = ab_test.hourly_logs.aggregate(
        control_participants=Sum('participants', filter=Q(version=AbTest.VERSION_CONTROL)),
        control_conversions=Sum('conversions', filter=Q(version=AbTest.VERSION_CONTROL)),
        variant_participants=Sum('participants', filter=Q(version=AbTest.VERSION_VARIANT)),
        variant_conversions=Sum('conversions', filter=Q(version=AbTest.VERSION_VARIANT)),
    )
    control_participants = stats['control_participants'] or 0
    control_conversions = stats['control_conversions'] or 0
    variant_participants = stats['variant_participants'] or 0
    variant_conversions = stats['variant_conversions'] or 0

    current_sample_size = control_participants + variant_participants

    estimated_completion_date = None
    if ab_test.status == AbTest.STATUS_RUNNING and current_sample_size:
        running_duration_days = ab_test.total_running_duration().days

        if running_duration_days > 0:
            participants_per_day = current_sample_size / ab_test.total_running_duration().days
            estimated_days_remaining = (ab_test.sample_size - current_sample_size) / participants_per_day
            estimated_completion_date = timezone.now().date() + datetime.timedelta(days=estimated_days_remaining)

    # Generate time series data for the chart
    time_series = []
    control = 0
    variant = 0
    date = None
    for log in ab_test.hourly_logs.order_by('date', 'hour'):
        # Accumulate the conversions
        if log.version == AbTest.VERSION_CONTROL:
            control += log.conversions
        else:
            variant += log.conversions

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
                'variant': variant,
            })

    return {
        'page': page,
        'ab_test': ab_test,
        'current_sample_size': current_sample_size,
        'current_sample_size_percent': int(current_sample_size / ab_test.sample_size * 100),
        'control_conversions': control_conversions,
        'control_participants': control_participants,
        'control_conversions_percent': int(control_conversions / control_participants * 100) if control_participants else 0,
        'variant_conversions': variant_conversions,
        'variant_participants': variant_participants,
        'variant_conversions_percent': int(variant_conversions / variant_participants * 100) if variant_participants else 0,
        'control_is_winner': ab_test.winning_version == AbTest.VERSION_CONTROL,
        'variant_is_winner': ab_test.winning_version == AbTest.VERSION_VARIANT,
        'unclear_winner': ab_test.status in [AbTest.STATUS_FINISHED, ab_test.STATUS_COMPLETED] and ab_test.winning_version is None,
        'estimated_completion_date': estimated_completion_date,
        'chart_data': json.dumps({
            'x': 'x',
            'columns': [
                ['x'] + [data_point['date'].isoformat() for data_point in time_series],
                [_("Control")] + [data_point['control'] for data_point in time_series],
                [_("Variant")] + [data_point['variant'] for data_point in time_series],
            ],
            'type': 'spline',
        }),
    }


def progress(request, page, ab_test):
    if request.method == 'POST':
        page_perms = page.permissions_for_user(request.user)

        if 'action-start-ab-test' in request.POST or 'action-restart-ab-test' in request.POST:
            if page_perms.can_publish():
                if ab_test.status in [AbTest.STATUS_DRAFT, AbTest.STATUS_PAUSED]:
                    ab_test.start()

                    messages.success(request, _("The A/B test has been started."))
                else:
                    messages.error(request, _("The A/B test must be in draft or paused in order to be started."))
            else:
                messages.error(request, _("You must have permission to publish in order to start an A/B test."))

        elif 'action-end-ab-test' in request.POST:
            if page_perms.can_publish():
                if ab_test.status in [AbTest.STATUS_DRAFT, AbTest.STATUS_RUNNING, AbTest.STATUS_PAUSED]:
                    ab_test.cancel()

                    messages.success(request, _("The A/B test has been ended."))
                elif ab_test.status == AbTest.STATUS_FINISHED:
                    ab_test.complete(AbTest.COMPLETION_ACTION_DO_NOTHING, user=request.user)
                else:
                    messages.error(request, _("The A/B test has already ended."))
            else:
                messages.error(request, _("You must have permission to publish in order to end an A/B test."))

        elif 'action-pause-ab-test' in request.POST:
            if page_perms.can_publish():
                if ab_test.status == AbTest.STATUS_RUNNING:
                    ab_test.pause()

                    messages.success(request, _("The A/B test has been paused."))
                else:
                    messages.error(request, _("The A/B test cannot be paused because it is not running."))
            else:
                messages.error(request, _("You must have permission to publish in order to pause an A/B test."))

        elif 'action-select-control' in request.POST:
            if ab_test.status == AbTest.STATUS_FINISHED:
                ab_test.complete(AbTest.COMPLETION_ACTION_REVERT, user=request.user)

                messages.success(request, _("The page has been reverted back to the control version."))

            else:
                messages.error(request, _("The A/B test cannot be paused because it is not running."))

        elif 'action-select-variant' in request.POST:
            if ab_test.status == AbTest.STATUS_FINISHED:
                # TODO Permission check?
                ab_test.complete(AbTest.COMPLETION_ACTION_PUBLISH, user=request.user)

                messages.success(request, _("The variant version has been published."))

            else:
                messages.error(request, _("The A/B test cannot be paused because it is not running."))

        else:
            messages.error(request, _("Unknown action"))

        # Redirect back
        return redirect('wagtailadmin_pages:edit', page.id)

    context = get_progress_and_results_common_context(request, page, ab_test)
    context['action_menu'] = AbTestActionMenu(request, view='edit', page=page, ab_test=ab_test)
    return render(request, 'wagtail_ab_testing/progress.html', context)


def results(request, page_id, ab_test_id):
    page = get_object_or_404(Page, id=page_id)
    if not page.permissions_for_user(request.user).can_edit():
        raise PermissionDenied

    ab_test = get_object_or_404(AbTest, page=page, id=ab_test_id)

    context = get_progress_and_results_common_context(request, page, ab_test)
    return render(request, 'wagtail_ab_testing/results.html', context)


def compare_draft(request, page_id):
    page = get_object_or_404(Page, id=page_id).specific

    latest_revision_as_page = page.get_latest_revision().as_page_object()
    comparison = page.get_edit_handler().get_comparison()
    comparison = [comp(page, latest_revision_as_page) for comp in comparison]
    comparison = [comp for comp in comparison if comp.has_changed()]

    return render(request, 'wagtail_ab_testing/compare.html', {
        'page': page,
        'latest_revision_as_page': latest_revision_as_page,
        'comparison': comparison,
    })


class SearchPageTitleFilter(django_filters.CharFilter):
    def filter(self, qs, value):
        if value in EMPTY_VALUES:
            return qs

        return qs.filter(page__title__icontains=value)


class AbTestingReportFilterSet(WagtailFilterSet):
    page = SearchPageTitleFilter()
    first_started_at = django_filters.DateFromToRangeFilter(label=gettext_lazy("Started at"), widget=DateRangePickerWidget)

    class Meta:
        model = AbTest
        fields = ['status', 'page', 'first_started_at']


class AbTestingReportView(ReportView):
    template_name = 'wagtail_ab_testing/report.html'
    title = gettext_lazy('A/B testing')
    header_icon = ''

    filterset_class = AbTestingReportFilterSet

    def get_queryset(self):
        return AbTest.objects.all().order_by(F('first_started_at').desc(nulls_first=True))


@csrf_exempt
@api_view(['POST'])
def register_participant(request):
    test_id = request.data.get('test_id', None)
    if test_id is None:
        return Response("test_id not provided", status=status.HTTP_400_BAD_REQUEST)

    try:
        test_id = int(test_id)
        if test_id < 1:
            raise ValueError
    except ValueError:
        return Response("test_id must be a positive integer", status=status.HTTP_400_BAD_REQUEST)

    test = get_object_or_404(AbTest, id=test_id)

    version = request.data.get('version', None)
    if version is None:
        return Response("version not provided", status=status.HTTP_400_BAD_REQUEST)

    if version not in [AbTest.VERSION_CONTROL, AbTest.VERSION_VARIANT]:
        return Response(
            "version must be either '{}' or '{}'".format(AbTest.VERSION_CONTROL, AbTest.VERSION_VARIANT),
            status=status.HTTP_400_BAD_REQUEST
        )

    # Add participant
    test.add_participant(version=version)

    return Response()


@csrf_exempt
@api_view(['POST'])
def goal_reached(request):
    test_id = request.data.get('test_id', None)
    if test_id is None:
        return Response("test_id not provided", status=status.HTTP_400_BAD_REQUEST)

    test = get_object_or_404(AbTest, id=test_id)

    version = request.data.get('version', None)
    if version is None:
        return Response("version not provided", status=status.HTTP_400_BAD_REQUEST)

    if version not in [AbTest.VERSION_CONTROL, AbTest.VERSION_VARIANT]:
        return Response(
            "version must be either '{}' or '{}'".format(AbTest.VERSION_CONTROL, AbTest.VERSION_VARIANT),
            status=status.HTTP_400_BAD_REQUEST
        )

    # Log conversion
    test.log_conversion(version)

    return Response()
