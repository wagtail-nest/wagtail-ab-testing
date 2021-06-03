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

## Running A/B tests on a site that uses Cloudflare caching

To run Wagtail A/B testing on a site that uses Cloudflare:

Set the A/B testing mode to "external". This disables Wagtail A/B testing's hooks that will generate unnecessary cookies.

```python
WAGTAIL_AB_TESTING = {
    'MODE': 'external',
}
```

Next, register the API, the worker will call this to figure out what tests are running.

```python
from wagtail_ab_testing import api as ab_testing_api

urlpatterns = [
    ...

    url(r'^abtestingapi/', include(ab_testing_api)),
]
```

Finally, set up a Cloudflare Worker based on the following JavaScript. Don't forget to set ``WAGTAIL_DOMAIN`` and ``API_BASE``:

```javascript
// Set this to the domain name of your backend server
const WAGTAIL_DOMAIN = "mysite.herokuapp.com";

// Set to false if Cloudflare shouldn't automatically redirect requests to use HTTPS
const ENFORCE_HTTPS = true;

// Set this to the URL of the A/B testing API on your backend server. Don't forget the / at the end!
const API_BASE = `https://${WAGTAIL_DOMAIN}/abtestingapi/`;

async function getRunningTests() {
  const response = await fetch(API_BASE + 'tests/');
  return await response.json();
}

async function addParticipant(test) {
  const response = await fetch(API_BASE + `tests/${test.id}/add_participant/`, {
    method: 'POST'
  });
  return await response.json();
}

async function logConversion(test, version) {
  const response = await fetch(API_BASE + `tests/${test.id}/log_conversion/`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      'version': version
    })
  });
  return await response.json();
}

async function getControlResponse(request) {
  const url = new URL(request.url);
  url.hostname = WAGTAIL_DOMAIN;
  return await fetch(url.toString(), request);
}

async function getVariantResponse(request, test) {
  return await fetch(API_BASE + `tests/${test.id}/serve_variant/`, request);
}

async function handleTest(request, test) {
  // Called when a page being visited has an A/B test running on it
  const cookieName = `experiment-${test.id}`;

  // Determine which group this requester is in.
  const cookie = request.headers.get("cookie");
  if (cookie && cookie.includes(`${cookieName}=control`)) {
    // User is in the control group
    return await getControlResponse(request);
  } else if (cookie && cookie.includes(`${cookieName}=variant`)) {
    // User is in the variant group
    return await getVariantResponse(request, test);
  } else {
    // User is not in any group yet

    // Add a participant
    const {version, test_finished} = await addParticipant(test);

    let response;
    if (version == 'control') {
      response = await getControlResponse(request);
    } else {
      response = await getVariantResponse(request, test);
    }

    // Set cookie in response
    response = response = new Response(response.body, response);
    response.headers.append("Set-Cookie", `${cookieName}=${version}; path=/`);

    return response;
  }
}

async function handleVisitPageGoal(request, response, tests) {
  // Checks if the current page that is being visited is a goal of any experiments that the user is participating in
  const url = new URL(request.url);

  // Find tests with a visit-page goal on the current page
  for (const test of tests) {
    if (test.goal.event === 'visit-page' && test.site.hostname === url.hostname && test.page.path === url.pathname) {
      const cookieName = `experiment-${test.id}`;

      const cookie = request.headers.get("cookie");
      if (cookie) {
        // Check if the user is a participant in this test
        const isParticipant = cookie.includes(`${cookieName}=control`) || cookie.includes(`${cookieName}=variant`);
        if (!isParticipant) {
          continue;
        }

        // Check if the user has already reached the goal so we don't count them twice
        const reachedGoalAlready = cookie.includes(`${cookieName}-reached-goal=yes`);
        if (reachedGoalAlready) {
          continue;
        }

        // Log the conversion
        const version = cookie.includes(`${cookieName}=control`) ? 'control' : 'variant';
        await logConversion(test, version);

        // Set cookie in response
        response = response = new Response(response.body, response);
        response.headers.append("Set-Cookie", `${cookieName}-reached-goal=yes; path=/`);
      }
    }
  }
}

async function handleRequest(request) {
  const url = new URL(request.url)
  
  if(url.protocol == "http:" && ENFORCE_HTTPS) {
    url.protocol == "https:";
    return Response.redirect(url, 301);
  }

  const tests = await getRunningTests();

  // Check if there is a running test on the visited page
  const getRunningTest = () => {
    for (const test of tests) {
      if (test.site.hostname === url.hostname && test.page.path === url.pathname) {
        return test;
      }
    }
  };
  const test = getRunningTest();

  // Handle the test if there is one, or just return the page
  let response;
  if (test) {
    response = await handleTest(request, test);
  } else {
    response = await getControlResponse(request);
  }

  await handleVisitPageGoal(request, response, tests);

  return response;
}

addEventListener("fetch", event => {
  event.respondWith(handleRequest(event.request));
});
```
