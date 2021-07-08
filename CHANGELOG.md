# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3] - 2021-07-08

### Changed

- The tracking code has been moved into JavaScript to reduce the number of false-positives caused by bots
- The Cloudflare worker has been massively simplified

To upgrade from 0.2.2:

If you are using the CloudFlare worker, you must first update the code to match the [latest version in the readme](https://github.com/torchbox/wagtail-ab-testing/#running-ab-tests-on-a-site-that-uses-cloudflare-caching). Note that your A/B tests will temporarily stop working but this shouldn't have any other impact on your site.

Following the [installation guide](https://github.com/torchbox/wagtail-ab-testing/#installation), add the new URL pattern into your ``urls.py`` (note this is a separate URL to the one used by the old Cloudflare worker).
And add the tracking script HTML tag to your base template

If you were using the CloudFlare worker before, remove the following URL pattern from your ``urls.py`` (note this is not the same pattern we added in the previous step!):

```python
url(r'^abtestingapi/', include(ab_testing_api)),
```

And the following setting is no longer required, remove it if you have it in your settings:

```python
WAGTAIL_AB_TESTING = {
    'MODE': 'external',
}
```

[0.3]: https://github.com/torchbox/wagtail-ab-testing/compare/v0.2...v0.3

