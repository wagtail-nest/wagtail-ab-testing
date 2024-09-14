from functools import lru_cache

from user_agents import parse


@lru_cache(maxsize=1000)
def is_bot(ua_string):
    return parse(ua_string).is_bot


def request_is_trackable(request):
    """
    Returns True if we can track the specified request.
    """
    # Don't track anyone with HTTP Do-Not-Track enabled
    if "HTTP_DNT" in request.META and request.META["HTTP_DNT"] == "1":
        return False

    # Don't track bots
    ua_string = request.META.get("HTTP_USER_AGENT", "")
    if not isinstance(ua_string, str):
        ua_string = ua_string.decode("utf-8", "ignore")
    if is_bot(ua_string):
        return False

    return True
