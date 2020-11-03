from django import forms
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from wagtail.admin import messages
from wagtail.core.models import Page

from .models import AbTest


class CreateAbTestForm(forms.ModelForm):

    def save(self, page, variant_revision):
        ab_test = super().save(commit=False)
        ab_test.page = page
        ab_test.variant_revision = variant_revision
        ab_test.save()
        return ab_test

    class Meta:
        model = AbTest
        fields = ['name', 'goal_type', 'goal_page', 'sample_size']


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
            form.save(page, page.get_latest_revision())

            return redirect('wagtailadmin_pages:edit', page.id)
    else:
        form = CreateAbTestForm()

    return render(request, 'wagtail_ab_testing/add_form.html', {
        'page': page,
        'form': form,
    })
