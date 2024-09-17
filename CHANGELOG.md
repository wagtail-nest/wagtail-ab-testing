# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.11] - 2024-09-17

- [Add Wagtail 6.2 support](https://github.com/wagtail-nest/wagtail-ab-testing/pull/87)
- [Drop Django 3.2 support, Add Wagtail 6.1 support](https://github.com/wagtail-nest/wagtail-ab-testing/pull/83)
- [Drop support for Python 3.8 in preparation for its upcoming end of life](https://github.com/wagtail-nest/wagtail-ab-testing/pull/87)
- [Fix page chooser not working](https://github.com/wagtail-nest/wagtail-ab-testing/pull/85)
- [Fix a potential race condition during increment of AB test statistics when using any database besides PostgreSQL](https://github.com/wagtail-nest/wagtail-ab-testing/pull/87)

**Maintenance**

- [Resolve several deprecation warnings in the codebase](https://github.com/wagtail-nest/wagtail-ab-testing/pull/87)
- [Switch from `setup.py` to `pyproject.toml` for package metadata](https://github.com/wagtail-nest/wagtail-ab-testing/pull/87)
- [Format the codebase with `ruff`](https://github.com/wagtail-nest/wagtail-ab-testing/pull/87)

## [0.10] - 2024-03-22

- [Add support for Wagtail 6.0](https://github.com/wagtail-nest/wagtail-ab-testing/pull/77)
- [Drop support for Wagtail 4.1, 4.2, 5.0, 5.1](https://github.com/wagtail-nest/wagtail-ab-testing/pull/77)
- [Adjust styling of create test page and testing log page to match look and feel of Wagtail 5.2 and up](https://github.com/wagtail-nest/wagtail-ab-testing/pull/80)
- [Add support for dark mode](https://github.com/wagtail-nest/wagtail-ab-testing/pull/76)
- [Update CloudFlare worker setup docs](https://github.com/wagtail-nest/wagtail-ab-testing/pull/72)
- [Move in-page script to `tracker.js`](https://github.com/wagtail-nest/wagtail-ab-testing/pull/73)
- [Maintenance: update all frontend dependencies to latest versions](https://github.com/wagtail-nest/wagtail-ab-testing/pull/78)

## [0.9] - 2023-12-14

- [Add missing migration](https://github.com/wagtail-nest/wagtail-ab-testing/pull/65)
- [Remove outdated css file](https://github.com/wagtail-nest/wagtail-ab-testing/pull/66)
- [Set cookie path to URL of homepage](https://github.com/wagtail-nest/wagtail-ab-testing/pull/67)
- [Fix Safari JS error accessing `window.external`](https://github.com/wagtail-nest/wagtail-ab-testing/pull/68)
- [Support for Python 3.12 and Django 5.0](https://github.com/wagtail-nest/wagtail-ab-testing/pull/69)
- [Test for missing migrations](https://github.com/wagtail-nest/wagtail-ab-testing/pull/71)


## [0.8] - 2023-11-16

- [Wagtail 4.1, 4.2, 5.0, 5.1 and 5.2 support 🎉](https://github.com/wagtail-nest/wagtail-ab-testing/pull/52)
- NO SUPPORT for Wagtail 4.0 and older, sorry
- [Revisions that are part of A/B test are now marked as protected to avoid data loss when the revision is deleted](https://github.com/wagtail-nest/wagtail-ab-testing/pull/54)

**Maintenance**

- The package was moved to Wagtail Nest
- Move to GitHub Actions for CI
- Move to Codecov for coverage
- [Add Trusted Publishing for publishing to PyPI](https://github.com/wagtail-nest/wagtail-ab-testing/pull/60)
- [Upload wheels to PyPI for faster installs](https://github.com/wagtail-nest/wagtail-ab-testing/pull/60)

## [0.7] - 2022-03-31

 - [Add default_auto_field](https://github.com/torchbox/wagtail-ab-testing/pull/42)
 - [Add reuqest obejct to AbTestActionMenu context](https://github.com/torchbox/wagtail-ab-testing/pull/43)]

## [0.6] - 2021-10-27

 - [Support for Wagtail 2.15](https://github.com/torchbox/wagtail-ab-testing/pull/41)

## [0.5] - 2021-09-30

### Added

 - [Support for Wagtail 2.14](https://github.com/torchbox/wagtail-ab-testing/pull/39)

## [0.4] - 2021-07-20

### Added

 - [Support for global goal event types](https://github.com/torchbox/wagtail-ab-testing/pull/37)

### Changed

 - Rewritten the docs in the readme for improved clarity.

### Fixed

 - [Set a long expiry date on cookies so users don't get counted multiple times](https://github.com/torchbox/wagtail-ab-testing/pull/36)

## [0.3.1] - 2021-07-08

### Fixed

 - [API endpoints no longer give CSRF errors when authenticated users visit an A/B testing page](https://github.com/torchbox/wagtail-ab-testing/pull/35)
 - [Fixed incorrect cookie name causing wrong variant to be served to participants](https://github.com/torchbox/wagtail-ab-testing/pull/34)

## [0.3] - 2021-07-08

### Added

 - Support for [Wagtail 2.13](https://github.com/torchbox/wagtail-ab-testing/pull/26), and [Django 3.2](https://github.com/torchbox/wagtail-ab-testing/pull/30)
 - [Add a HTTPS redirect in Cloudflare worker](https://github.com/torchbox/wagtail-ab-testing/pull/31)

### Changed

- The tracking code has been moved into JavaScript to reduce the number of false-positives caused by bots
- The Cloudflare worker has been massively simplified

### Upgrading from 0.2.2

Following the [installation guide](https://github.com/torchbox/wagtail-ab-testing/#installation), add the new URL pattern into your ``urls.py`` (note this is a separate URL to the one used by the old Cloudflare worker).
And add the tracking script HTML tag to your base template

#### If you use the Cloudflare worker

Before deploying the update to 0.3, you must first update the code to match the [latest version in the readme](https://github.com/torchbox/wagtail-ab-testing/#running-ab-tests-on-a-site-that-uses-cloudflare-caching). Note that your A/B tests will temporarily stop working, but this shouldn't have any other impact on your site. They should start working again once you've deployed 0.3.

Remove the following URL pattern from your ``urls.py`` (note this is not the same pattern we added in the previous step!):

```python
url(r'^abtestingapi/', include(ab_testing_api)),
```

And the following setting is no longer required, remove it if you have it in your settings:

```python
WAGTAIL_AB_TESTING = {
    'MODE': 'external',
}
```

[Unreleased]: https://github.com/torchbox/wagtail-ab-testing/compare/v0.6...main
[0.6]: https://github.com/torchbox/wagtail-ab-testing/compare/v0.5...v0.6
[0.5]: https://github.com/torchbox/wagtail-ab-testing/compare/v0.4...v0.5
[0.4]: https://github.com/torchbox/wagtail-ab-testing/compare/v0.3.1...v0.4
[0.3.1]: https://github.com/torchbox/wagtail-ab-testing/compare/v0.3...v0.3.1
[0.3]: https://github.com/torchbox/wagtail-ab-testing/compare/v0.2...v0.3
[0.4]: https://github.com/torchbox/wagtail-ab-testing/compare/v0.3...v0.4
