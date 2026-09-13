from fastapi import APIRouter

from app.api.deps import CurrentUserDep, SessionDep
from app.services.users import UserProfile, get_user_profile

router = APIRouter(tags=["users"])


# Đọc từ cơ sở dữ liệu chứ không chép lại token, để "tôi là ai" luôn phản ánh hiện trạng
# — token có thể lệch tên, vai trò, claim tối đa 15 phút.
@router.get("/me")
async def me(current_user: CurrentUserDep, session: SessionDep) -> UserProfile:
    return await get_user_profile(session, current_user.user_id)
