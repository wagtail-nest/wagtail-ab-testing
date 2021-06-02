(function() {
    // Check if Do Not Track is enabled
    if (window.doNotTrack || navigator.doNotTrack || navigator.msDoNotTrack || 'msTrackingProtectionEnabled' in window.external) {
        if (window.doNotTrack == '1' || navigator.doNotTrack == 'yes' || navigator.doNotTrack == '1' || navigator.msDoNotTrack == '1' || 'msTrackingProtectionEnabled' in window.external && window.external.msTrackingProtectionEnabled()) {
            // Don't track this browser
            return;
        }
    }

    function getCookie(cookieName) {
        var cookies = document.cookie.split(';');
        for(var i = 0; i < cookies.length; i++) {
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
            var cookieName = 'abtesting-' + window.wagtailAbTesting.testId + '-version';
            if (!document.cookie.includes(cookieName)) {
                fetch(
                    window.wagtailAbTesting.urls.registerParticipant,
                    {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({
                            test_id: window.wagtailAbTesting.testId,
                            version: window.wagtailAbTesting.version
                        })
                    }
                ).then(function (response) {
                    if (response.status === 200) {
                        // Put the version into a cookie so that Wagtail continues to serve this version
                        document.cookie = cookieName + ' = ' + window.wagtailAbTesting.version;

                        // Save the goal info into local storage
                        // This data structure looks like:
                        // {
                        //   <id of goal page> : {
                        //     <goal event>: [<ids of tests with this goal page/event>]
                        //   }
                        // }
                        var goals = window.localStorage.getItem('abtesting-goals');
                        if (goals) {
                            goals = JSON.parse(goals);
                        } else {
                            goals = {};
                        }

                        goals[window.wagtailAbTesting.pageId] = goals[window.wagtailAbTesting.pageId] || {}
                        goals[window.wagtailAbTesting.pageId][window.wagtailAbTesting.goalEvent] = goals[window.wagtailAbTesting.pageId][window.wagtailAbTesting.goalEvent] || [];
                        goals[window.wagtailAbTesting.pageId][window.wagtailAbTesting.goalEvent].push(window.wagtailAbTesting.testId);

                        window.localStorage.setItem('abtesting-goals', JSON.stringify(goals));
                    }
                });
            }
        }

        window.wagtailAbTesting.triggerEvent = function (event) {
            // Check if any goals were reached
            var goalsJson = window.localStorage.getItem('abtesting-goals');
            if (!goalsJson) {
                return
            }

            var goals = JSON.parse(goalsJson);

            var checkGoalReached = function (pageId) {
                console.log("CHECK GOAL REACHED", pageId, event)
                var goalsForPage = goals[pageId];
                if (!goalsForPage) {
                    return;
                }
                console.log("A")
                var goalsForEvent = goalsForPage[event];
                if (!goalsForEvent) {
                    return;
                }
                console.log("B")

                goalsForEvent.forEach(function (testId) {
                    var version = getCookie('abtesting-' + testId + '-version');

                    if (version) {
                        fetch(
                            window.wagtailAbTesting.urls.goalReached,
                            {
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
            checkGoalReached(null);
        };

        // Trigger visit page event
        window.wagtailAbTesting.triggerEvent('visit-page');
    }
})();
