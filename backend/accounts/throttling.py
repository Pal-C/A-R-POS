"""Throttles for the sign-in endpoint."""

from rest_framework.throttling import SimpleRateThrottle


class LoginUsernameThrottle(SimpleRateThrottle):
    """Limits sign-in attempts per username, whichever address they come from.

    Complements the per-IP ``login`` scope: rotating client addresses (or a
    shared proxy address) cannot be used to guess one account's password
    faster than the configured rate.
    """

    scope = "login_username"

    def get_cache_key(self, request, view):
        username = request.data.get("username") if hasattr(request, "data") else None
        if not isinstance(username, str) or not username.strip():
            return None
        return self.cache_format % {
            "scope": self.scope,
            "ident": username.strip().lower(),
        }
