# Wagtail A/B Testing

[![Version](https://img.shields.io/pypi/v/wagtail-ab-testing.svg?style=flat)](https://pypi.python.org/pypi/wagtail-ab-testing/)
[![License](https://img.shields.io/badge/license-BSD-blue.svg?style=flat)](https://opensource.org/licenses/BSD-3-Clause)
[![codecov](https://img.shields.io/codecov/c/github/torchbox/wagtail-ab-testing?style=flat)](https://codecov.io/gh/torchbox/wagtail-ab-testing)
[![Language grade: Python](https://img.shields.io/lgtm/grade/python/g/torchbox/wagtail-ab-testing.svg?logo=lgtm&logoWidth=18&style=flat)](https://lgtm.com/projects/g/torchbox/wagtail-ab-testing/context:python)

Wagtail A/B Testing is an A/B testing package for Wagtail that allows users to create and manage A/B tests on pages through the Wagtail admin.

Key features:

 - Create an A/B test on any page from within Wagtail
 - Tests using page revisions (no need to create separate pages for the variants)
 - It prevents users from editing the page while a test is in progress
 - Calculates confidence using a Pearson's chi-squared test

[Changelog](https://github.com/torchbox/wagtail-ab-testing/blob/main/CHANGELOG.md)

## Usage

Wagtail A/B Testing works with Django 3.2+, Wagtail 4.1+ on Python 3.7+ environments.

### Creating an A/B test

Any user with the "Create A/B test" permission can create an A/B test by clicking "Save and create A/B test" from the page's action menu.

The first page shows the user the difference between the content in the latest draft against the live version of the page.
This allows them to check what changes on the page are going to be tested.

Once they've confirmed that, the user is taken to a form to insert the test name/hypothesis, select a goal, and sample size.

![Screenshot of Wagtail A/B Testing create page](/screenshot-create.png)

### Monitoring test progress

While the test is running, the page's edit view gets replaced with a dashboard showing the current test progress.
Users cannot edit the page until the test is completed or cancelled.

Any user with permission to publish the page can start, pause, resume or end A/B tests on that page.

![Screenshot of Wagtail A/B Testing](/screenshot.png)

### Finishing the test

The test stops automatically when the number of participants reaches the sample size.
Based on the results shown, a user must decide whether to publish the new changes or revert to the old version of the page.

Once they've chosen, the page edit view returns to normal.
The results from this A/B test remain accessible under the A/B testing tab or from the A/B testing report.

![Screenshot of Wagtail A/B Testing](/screenshot-finish.png)

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

Then add the following to your URLconf:

```python
from wagtail_ab_testing import urls as ab_testing_urls

urlpatterns = [
    ...

    path('abtesting/', include(ab_testing_urls)),
]
```

Finally, add the tracking script to your base HTML template:

```django+HTML
{# Insert this at the top of the template #}
{% load wagtail_ab_testing_tags %}

...

{# Insert this where you would normally insert a <script> tag #}
{% wagtail_ab_testing_script %}
```

## Implementing custom goal event types

Out of the box, Wagtail A/B testing provides a "Visit page" goal event type which you can use to track when users visit a goal page.
It also supports custom goal types, which can be used for tracking other events such as making a purchase, submitting a form, or clicking a link.

To implement a custom goal event type, firstly register your type using the ``register_ab_testing_event_types`` hook, this would
add your goal type to the list of options shown to users when they create A/B tests:

```python
# myapp/wagtail_hooks.py

from wagtail import hooks
from wagtail_ab_testing.events import BaseEvent


class CustomEvent(BaseEvent):
    name = "Name of the event type"
    requires_page = True  # Set to False to create a "Global" event type that could be reached on any page

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

Next, you need to tell Wagtail A/B testing whenever a user triggers the goal. This can be done by calling ``wagtailAbTesting.triggerEvent()``
in the browser:

```javascript
if (window.wagtailAbTesting) {
    wagtailAbTesting.triggerEvent('slug-of-the-event-type');
}
```

The JavaScript library tracks A/B tests using ``localStorage``, so this will only call the server if the user is participating in an A/B test with the provided goal type and the current page is the goal page.

#### Example: Adding a "Submit form" event type

We will add a "Submit form" event type for a ``ContactUsFormPage`` page type in this example.

Firstly, we need to register the event type. To do this, implement a handler for the ``register_ab_testing_event_types`` hook in your app:

```python
# myapp/wagtail_hooks.py

from wagtail import hooks
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

Next, we need to add some code to the frontend to trigger this event whenever a user submits the form:

```django+HTML
# templates/forms/contact_us_form_page.html

<form id="form">
    ...
</form>

<script>
    if (window.wagtailAbTesting) {
        document.getElementById('form').addEventListener('submit', function() {
            wagtailAbTesting.triggerEvent('submit-contact-us-form');
        });
    }
</script>
```

## Running A/B tests on a site that uses Cloudflare caching

To run Wagtail A/B testing on a site that uses Cloudflare, firstly generate a secure random string to use as a token, and configure that token in your Django settings file:

```python
WAGTAIL_AB_TESTING_WORKER_TOKEN = '<token here>'
```

Then set up a Cloudflare Worker based on the following JavaScript. Don't forget to set ``WAGTAIL_DOMAIN``:

```javascript
// Set this to the domain name of your backend server
const WAGTAIL_DOMAIN = "mysite.herokuapp.com";

// Set to false if Cloudflare shouldn't automatically redirect requests to use HTTPS
const ENFORCE_HTTPS = true;

async function handleRequest(request) {
  const url = new URL(request.url)

  if (url.protocol == 'http:' && ENFORCE_HTTPS) {
    url.protocol = 'https:';
    return Response.redirect(url, 301);
  }

  if (request.method === 'GET') {
    const newRequest = new Request(request, {
      headers: {
        ...request.headers,
        'Authorization': 'Token ' + WAGTAIL_AB_TESTING_WORKER_TOKEN,
        'X-Requested-With': 'WagtailAbTestingWorker'
      }
    });

    url.hostname = WAGTAIL_DOMAIN;
    response = await fetch(url.toString(), newRequest);

    // If there is a test running at the URL, the worker would return
    // a JSON response containing both versions of the page. Also, it
    // returns the test ID in the X-WagtailAbTesting-Test header.
    const testId = response.headers.get('X-WagtailAbTesting-Test');
    if (testId) {
      // Participants of a test would have a cookie that tells us which
      // version of the page being tested on that they should see
      // If they don't have this cookie, serve a random version
      const versionCookieName = `abtesting-${testId}-version`;
      const cookie = request.headers.get('cookie');
      let version;
      if (cookie && cookie.includes(`${versionCookieName}=control`)) {
        version = 'control';
      } else if (cookie && cookie.includes(`${versionCookieName}=variant`)) {
        version = 'variant';
      } else if (Math.random() < 0.5) {
        version = 'control';
      } else {
        version = 'variant';
      }

      return response.json().then(json => {
        return new Response(json[version], {
          headers: {
            ...response.headers,
            'Content-Type': 'text/html'
          }
        });
      });
    }

    return response;
  } else {
    return await fetch(url.toString(), request);
  }
}

addEventListener('fetch', event => {
  event.respondWith(handleRequest(event.request));
});
```

Add a variable to the worker called ``WAGTAIL_AB_TESTING_WORKER_TOKEN``, giving it the same token value that you generated earlier.

Finally, add a route into Cloudflare so that it routes all traffic through this worker.
