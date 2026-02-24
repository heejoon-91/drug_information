from asgiref.sync import sync_to_async
from django.contrib.auth.models import User
from drugs.models import UserProfile

class UserService:
    @staticmethod
    @sync_to_async
    def get_profile(user: User):
        try:
            return user.profile
        except UserProfile.DoesNotExist:
            return None

    @staticmethod
    @sync_to_async
    def update_profile(user: User, medications: str, allergies: str, diseases: str):
        profile, created = UserProfile.objects.get_or_create(user=user)
        profile.current_medications = medications
        profile.allergies = allergies
        profile.chronic_diseases = diseases
        profile.save()
        return profile

    @staticmethod
    @sync_to_async
    def get_user_info(user_id: int):
        try:
            user = User.objects.get(pk=user_id)
            profile, _ = UserProfile.objects.get_or_create(user=user)
            return {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "profile": {
                    "current_medications": profile.current_medications,
                    "allergies": profile.allergies,
                    "chronic_diseases": profile.chronic_diseases
                }
            }
        except User.DoesNotExist:
            return None
