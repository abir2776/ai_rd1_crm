import requests
from django.utils import timezone
from rest_framework import serializers

from organizations.models import OrganizationPlatform, Platform


class OrganizationPlatformTokenSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=100)
    redirect_uri = serializers.CharField(max_length=200)
    platform_slug = serializers.CharField()

    def create(self, validated_data):
        request = self.context.get("request")
        organization = request.user.get_organization()
        code = validated_data.get("code")
        redirect_uri = validated_data.get("redirect_uri")
        platform_slug = validated_data.get("platform_slug")

        try:
            platform = Platform.objects.get(slug=platform_slug)
        except Platform.DoesNotExist:
            raise serializers.ValidationError({"platform_slug": "Platform not found"})

        token_url = "https://id.jobadder.com/connect/token"
        payload = {
            "grant_type": "authorization_code",
            "code": code,
            "client_id": platform.client_id,
            "client_secret": platform.client_secret,
            "redirect_uri": redirect_uri,
        }

        try:
            response = requests.post(
                token_url,
                data=payload,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=30,
            )
            response.raise_for_status()
            token_data = response.json()
            access_token = token_data.get("access_token")
            refresh_token = token_data.get("refresh_token")
            expires_in = token_data.get("expires_in")  # seconds
            token_type = token_data.get("token_type")
            expires_at = None
            if expires_in:
                expires_at = timezone.now() + timezone.timedelta(seconds=expires_in)
            org_platform, created = OrganizationPlatform.objects.update_or_create(
                organization=organization,
                platform=platform,
                defaults={
                    "access_token": access_token,
                    "refresh_token": refresh_token,
                    "token_type": token_type,
                    "expires_at": expires_at,
                    "is_connected": True,
                },
            )

            return org_platform

        except requests.exceptions.HTTPError as e:
            error_detail = "Token exchange failed"
            try:
                error_response = response.json()
                error_detail = error_response.get(
                    "error_description", error_response.get("error", error_detail)
                )
            except:
                error_detail = response.text or str(e)

            raise serializers.ValidationError(
                {"detail": error_detail, "status_code": response.status_code}
            )

        except requests.exceptions.Timeout:
            raise serializers.ValidationError(
                {"detail": "Request to JobAdder timed out. Please try again."}
            )

        except requests.exceptions.RequestException as e:
            raise serializers.ValidationError(
                {"detail": f"Network error occurred: {str(e)}"}
            )

        except Exception as e:
            raise serializers.ValidationError(
                {"detail": f"An unexpected error occurred: {str(e)}"}
            )


class PlatformSerializer(serializers.ModelSerializer):
    class Meta:
        model = Platform
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "base_url",
            "client_id",
            "auth_type",
            "logo",
            "status",
            "redirect_uri",
        ]
