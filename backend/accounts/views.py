"""Session auth endpoints for the staff frontend (contracts/auth-api.md)."""

from django.contrib.auth import login, logout
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from .serializers import CurrentUserSerializer, LoginSerializer
from .throttling import LoginUsernameThrottle


@method_decorator(ensure_csrf_cookie, name="dispatch")
class CsrfView(APIView):
    """Sets the ``csrftoken`` cookie so the frontend can send ``X-CSRFToken``.

    Side effects: none beyond the cookie.
    """

    permission_classes = [AllowAny]

    def get(self, request):
        return Response(status=status.HTTP_204_NO_CONTENT)


@method_decorator(csrf_protect, name="dispatch")
class LoginView(APIView):
    """Signs a staff member in.

    Side effects: replaces any existing session with a new one (session id and CSRF
    token are rotated). CSRF is enforced even for anonymous callers to prevent
    login-CSRF. Throttled per client IP (scope ``login``) and per username
    (scope ``login_username``).
    """

    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle, LoginUsernameThrottle]
    throttle_scope = "login"

    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        login(request, user)
        return Response(CurrentUserSerializer(user).data)


class LogoutView(APIView):
    """Signs the current staff member out.

    Side effects: flushes the session. Idempotent: returns 204 when no one is signed
    in. CSRF is enforced whenever a session exists.
    """

    permission_classes = [AllowAny]

    def post(self, request):
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    """Returns the signed-in staff member. Side effects: renews the session expiry."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(CurrentUserSerializer(request.user).data)
