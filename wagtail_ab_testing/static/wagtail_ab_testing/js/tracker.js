(function() {
    // Check if Do Not Track is enabled
    if (window.doNotTrack || navigator.doNotTrack || navigator.msDoNotTrack) {
        if (window.doNotTrack == '1' || navigator.doNotTrack == 'yes' || navigator.doNotTrack == '1' || navigator.msDoNotTrack == '1' || 'msTrackingProtectionEnabled' in window.external && window.external.msTrackingProtectionEnabled()) {
            // Don't track this browser
            return;
        }
    }

    // Read the tracking parameters from JSON script
    let trackingParams = null;
    if (document.getElementById('abtesting-tracking-params')) {
        trackingParams = JSON.parse(document.getElementById('abtesting-tracking-params').textContent);
        // Attach the wagtailAbTesting object to the window
        window.wagtailAbTesting = trackingParams;
    }

    function getCookie(cookieName) {
        var cookies = document.cookie.split(';');
        for (var i = 0; i < cookies.length; i++) {
            var cookie = cookies[i];
            while (cookie.charAt(0) == ' ') {
                cookie = cookie.substring(1);
            }
            if (cookie.indexOf(cookieName + '=') == 0) {
                return cookie.substring(cookieName.length + 1, cookie.length);
            }
        }
        return '';
    }

    // Does the current page have an A/B test running?
    if (window.wagtailAbTesting) {
        // Register the user as a participant if they haven't registered yet
        if (window.wagtailAbTesting.testId) {
            // Fetch the goal info from local storage
            // This data structure looks like:
            // {
            //   <id of goal page> : {
            //     <goal event>: [<ids of tests with this goal page/eveqnt>]
            //   }
            // }
            var goals = window.localStorage.getItem('abtesting-goals');
            if (goals) {
                goals = JSON.parse(goals);
            } else {
                goals = {};
            }

            // Add this goal page/event into the goals data structure
            goals[window.wagtailAbTesting.goalPageId] = goals[window.wagtailAbTesting.goalPageId] || {};
            goals[window.wagtailAbTesting.goalPageId][window.wagtailAbTesting.goalEvent] = goals[window.wagtailAbTesting.goalPageId][window.wagtailAbTesting.goalEvent] || [];

            // Check if this user is already a participant in this test
            // We could check the cookie instead, but it's possible that the user has cleared their cookies but not local storage
            if (goals[window.wagtailAbTesting.goalPageId][window.wagtailAbTesting.goalEvent].indexOf(window.wagtailAbTesting.testId) === -1) {
                var cookieName = 'wagtail-ab-testing_' + window.wagtailAbTesting.testId + '_version';
                if (!document.cookie.includes(cookieName)) {
                    fetch(
                        window.wagtailAbTesting.urls.registerParticipant, {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json'
                            },
                            body: JSON.stringify({
                                test_id: window.wagtailAbTesting.testId,
                                version: window.wagtailAbTesting.version
                            })
                        }
                    ).then(function(response) {
                        if (response.status === 200) {
                            // Put the version into a cookie so that Wagtail continues to serve this version
                            var expires = new Date();
                            expires.setFullYear(expires.getFullYear() + 1);
                            document.cookie = cookieName + '=' + window.wagtailAbTesting.version + '; path=/; expires=' + expires.toUTCString();

                            // Store the test ID against the goal event in the goals data structure
                            // We will use this for knowing when to call the goal reached API later
                            goals[window.wagtailAbTesting.goalPageId][window.wagtailAbTesting.goalEvent].push(window.wagtailAbTesting.testId);
                            window.localStorage.setItem('abtesting-goals', JSON.stringify(goals));
                        }
                    });
                }
            }
        }

        window.wagtailAbTesting.triggerEvent = function(event) {
            // Check if any goals were reached
            var goalsJson = window.localStorage.getItem('abtesting-goals');
            if (!goalsJson) {
                return
            }

            var goals = JSON.parse(goalsJson);

            var checkGoalReached = function(pageId) {
                var goalsForPage = goals[pageId];
                if (!goalsForPage) {
                    return;
                }
                var goalsForEvent = goalsForPage[event];
                if (!goalsForEvent) {
                    return;
                }

                goalsForEvent.forEach(function(testId) {
                    var cookieName = 'wagtail-ab-testing_' + testId + '_version';
                    var version = getCookie(cookieName);

                    if (version) {
                        fetch(
                            window.wagtailAbTesting.urls.goalReached, {
                                method: 'POST',
                                headers: {
                                    'Content-Type': 'application/json'
                                },
                                body: JSON.stringify({
                                    test_id: testId,
                                    version: version
                                })
                            }
                        );
                    }
                });

                // Remove those goals from local storage so we don't use them again
                delete goals[pageId][event];
                window.localStorage.setItem('abtesting-goals', JSON.stringify(goals));
            };

            // Check goals on current page
            if (window.wagtailAbTesting.pageId) {
                checkGoalReached(window.wagtailAbTesting.pageId);
            }

            // Check non-page-specific goals
            // Note: we need to check for the string 'null' as nulls are converted to strings
            // when they are used as keys in JSON
            checkGoalReached('null');
        };

        // Trigger visit page event
        window.wagtailAbTesting.triggerEvent('visit-page');
    }
})();
