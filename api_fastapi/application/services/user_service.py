from infrastructure.supabase_db.user_repository import SupabaseUserRepository

user_repo = SupabaseUserRepository()

class UserService:
    @staticmethod
    async def get_profile(user: dict):
        user_id = user.get("id")
        if not user_id: return None
        return await user_repo.get_profile_by_user_id(user_id)

    @staticmethod
    async def update_profile(user: dict, medications: str, allergies: str, diseases: str):
        user_id = user.get("id")
        if not user_id: return None
        success = await user_repo.update_profile(user_id, medications, allergies, diseases)
        if success:
            return await user_repo.get_profile_by_user_id(user_id)
        return None

    @staticmethod
    async def get_user_info(user_id: int):
        user = await user_repo.get_user_by_id(user_id)
        if not user: return None
        profile = await user_repo.get_profile_by_user_id(user_id)
        return {
            "id": user.get("id"),
            "username": user.get("username"),
            "email": user.get("email"),
            "profile": profile
        }
