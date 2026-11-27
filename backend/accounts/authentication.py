"""DRF authentication classes for the staff API."""

from rest_framework import authentication


class SessionAuthentication(authentication.SessionAuthentication):
    """Django session authentication that answers unauthenticated requests with 401.

    DRF derives the status code for unauthenticated requests from the first
    authentication class's ``authenticate_header``. The stock session class returns
    ``None`` there, which makes DRF answer 403, the same as a permission failure,
    so the frontend could not tell an expired session from a forbidden action.
    Returning a non-Basic challenge yields 401 without triggering the browser's
    Basic-auth dialog.
    """

    def authenticate_header(self, request):
        return "Session"
