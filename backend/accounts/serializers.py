"""Serializers for the staff auth endpoints."""

from django.contrib.auth import authenticate
from rest_framework import serializers

from .models import User

INVALID_CREDENTIALS = "Invalid username or password."


class LoginSerializer(serializers.Serializer):
    """Validates credentials; ``validated_data["user"]`` holds the authenticated user.

    Wrong passwords, unknown usernames and inactive accounts all produce the same
    message so the endpoint does not reveal which usernames exist.
    """

    username = serializers.CharField()
    password = serializers.CharField(trim_whitespace=False, write_only=True)

    def validate(self, attrs):
        user = authenticate(
            request=self.context.get("request"),
            username=attrs["username"],
            password=attrs["password"],
        )
        if user is None:
            raise serializers.ValidationError(INVALID_CREDENTIALS)
        return {"user": user}


class CurrentUserSerializer(serializers.ModelSerializer):
    """The signed-in staff member as the frontend sees it."""

    display_name = serializers.SerializerMethodField()
    permissions = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "first_name",
            "last_name",
            "display_name",
            "is_superuser",
            "permissions",
        ]
        read_only_fields = fields

    def get_display_name(self, user) -> str:
        return user.get_full_name() or user.username

    def get_permissions(self, user) -> list[str]:
        return sorted(user.get_all_permissions())
