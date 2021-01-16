# Wagtail A/B Testing

An A/B testing package for Wagtail that allows creating A/B tests using revisions.

Key features:

 - Create an A/B test on any page from within Wagtail
 - Tests using page revisions (no need to create separate pages for the variants)
 - Prevents users from editing the page while a test is in progress
 - Calculates confidence using a Pearson's chi squared test

![Screenshot of Wagtail A/B Testing](/screenshot.png)

## Usage

Any user with the "Create A/B test" permission (given to admins and moderators by default) should be able to create an A/B test by clicking "Save and create A/B test" from the page's action menu.

This will show a diff of the content in the latest draft against the current live version of the page (as these will be tested). Once they've confirmed that, the user is taken to a form to insert the test name/hypothesis, select a goal, and a sample size.

While the test is running, user's can pause/restart and end the test at any time. While the test is running/paused, nobody can edit the page as this may affect the accuracy of the test results. If you absolutely must edit the page while a test is running, you should cancel the test, edit the page, and start a new test.

When the number of participants reaches the desired sample size, the test is stopped and the results are displayed to the user. At this point, the user may choose to publish the latest draft (aka the "variant") or revert back to the existing live version (aka the "control").

Wagtail A/B testing will also tell the user if one of the results is a clear winner or if there is no clear winner, this is worked out using a Chi Squared test that takes into account the total sample size (higher sample size means it will accept a smaller difference as a clear result) as well as the conversion rates.

## Installation

Firstly, install the ``wagtail-ab-testing`` package from PyPI:

    pip install wagtail-ab-testing

Then add it into ``INSTALLED_APPS``:

```python
INSTALLED_APPS = [
    # ...
    'wagtail_ab_testing',
    # ...
]
```

## Goal events

Each A/B test has a goal that is measured after a user visits the page that the A/B test is running on.

The goal is defined by a destination page and and event type. For example, if the A/B test needs to measure how a change on the page affects the number of users who go on to submit a "Contact us" form, then the 'destination page' would be the "Contact us" page and the 'event type' would be "Submit form".

Out of the box, the only 'event type' that Wagtail A/B testing supports is visiting the destination page.
If you need to measure something else (such as submitting a form, purchasing someting, or just clicking a link), you can implement a custom 'event type'.

### Implementing a custom goal event type

Custom event types are implemented for specific types of destination page.

Firstly, you need to register the 'event type' using the `register_ab_testing_event_types` hook,
this displays the goal 'event type' in the list of options when an A/B test is being created:


```python
# myapp/wagtail_hooks.py

from wagtail.core import hooks
from wagtail_ab_testing.events import BaseEvent


class CustomEvent(BaseEvent):
    name = "Name of the event type"

    def get_page_types(self):
        return [
            # Return a list of page models that can be used as destination pages for this event type
            # For example, if this 'event type' is for a 'call to action' button that only appears on
            # the homepage, put your `HomePage` model here.
        ]


@hooks.register('register_ab_testing_event_types')
def register_submit_form_event_type():
    return {
        'slug-of-the-event-type': CustomEvent,
    }

```

Next you need to add logic in that logs a conversion when the user reaches that goal.
To do this, you can copy/adapt the following code snippet:

```python
# Check if the user is trackable
if request_is_trackable(request):
    # Check if the page is the goal of any running tests
    tests = AbTest.objects.filter(goal_event='slug-of-the-event-type', goal_page=the_page, status=AbTest.STATUS_RUNNING)
    for test in tests:
        # Is the user a participant in this test?
        if f'wagtail-ab-testing_{test.id}_version' not in request.session:
            continue

        # Has the user already completed the test?
        if f'wagtail-ab-testing_{test.id}_completed' in request.session:
            continue

        # Log a conversion
        test.log_conversion(request.session[f'wagtail-ab-testing_{test.id}_version'])
        request.session[f'wagtail-ab-testing_{test.id}_completed'] = 'yes'
```

#### Example: Adding a "Submit form" event type

In this example, we will add a "Submit form" event type for a ``ContactUsFormPage`` page type.

Firstly, we need to register the event type. To do this, implement a handler for the ``register_ab_testing_event_types`` hook in your app:

```python
# myapp/wagtail_hooks.py

from wagtail.core import hooks
from wagtail_ab_testing.events import BaseEvent

from .models import ContactUsFormPage


class SubmitFormPageEvent(BaseEvent):
    name = "Submit form page"

    def get_page_types(self):
        # Only allow this event type to be used if he user has
        # selected an instance of `ContactUsFormPage` as the goal
        return [
            ContactUsFormPage,
        ]


@hooks.register('register_ab_testing_event_types')
def register_submit_form_event_type():
    return {
        'submit-contact-us-form': SubmitFormPageEvent,
    }
```

This allows users to select the "Submit form page" event type when their goal page is set to any instance of ``ContactUsFormPage``.

Next, we need to add some code to record conversions for this event type.
To do this, we will customise the ``.render_landing_page()`` method that is inherited from the ``AbstractForm`` model.
This method is a view that returns the "thank you" page to the user. It's ideal for this use because user's will can
only get there by submitting the form, and we have the ``request`` object available which is required for some of the logic.:

```python
# myapp/models.py

from wagtail.contrib.forms.models import AbstractFormPage

from wagtail_ab_testing.models import AbTest
from wagtail_ab_testing.utils import request_is_trackable


class ContactUsFormPage(AbstractForm):

    def render_landing_page(self, request, *args, **kwargs):
        # Check if the user is trackable
        if request_is_trackable(request):
            # Check if submitting this form is the goal of any running tests
            tests = AbTest.objects.filter(goal_event='submit-contact-us-form', goal_page=self, status=AbTest.STATUS_RUNNING)
            for test in tests:
                # Is the user a participant in this test?
                if f'wagtail-ab-testing_{test.id}_version' not in request.session:
                    continue

                # Has the user already completed the test?
                if f'wagtail-ab-testing_{test.id}_completed' in request.session:
                    continue

                # Log a conversion
                test.log_conversion(request.session[f'wagtail-ab-testing_{test.id}_version'])
                request.session[f'wagtail-ab-testing_{test.id}_completed'] = 'yes'

        return super().render_landing_page(request, *args, **kwargs)
```
