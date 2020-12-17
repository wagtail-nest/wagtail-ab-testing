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

Each A/B test has a goal that is measured after a user visits the page where the A/B test is running.

The goal is defined on the A/B test with a page and and event type. For example, if the A/B test needs to measure how a change on the page affects the number of users who go on to submit a "Contact us" form, then the goal page would be "Contact us" and the goal event would be "Submit form".

Out of the box, Wagtail A/B testing only supports visting another page as a goal event. If you need to measure something else, for example, submitting a form, purchasing someting, or just clicking a link you can implement a custom "goal event type".

### Implementing a custom goal event type

In this example, we will add a "Submit form" goal event for a ``ContactUsFormPage`` type.

Firstly, we need to register the goal event type. To do this, implement a ``register_ab_testing_event_types`` in ``wagtail_hooks.py`` in your app:

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

This allows users to select the "Submit form page" event type when their goal page is set to any instance of ``ContactUsFormPage``. Next, we need to allow it to record a conversion when a user submits a form using that type.

TODO: Finish this
