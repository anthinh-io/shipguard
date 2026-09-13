from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select

from app.api.deps import CurrentUserDep, SessionDep
from app.models.auth import Role, users
from app.services.auth import load_claims

router = APIRouter(tags=["users"])


class MeResponse(BaseModel):
    id: int
    email: str
    display_name: str
    role: Role
    claims: list[str]


# Đọc từ cơ sở dữ liệu chứ không chép lại token, để "tôi là ai" luôn phản ánh hiện trạng
# — token có thể lệch tên, vai trò, claim tối đa 15 phút.
@router.get("/me")
async def me(current_user: CurrentUserDep, session: SessionDep) -> MeResponse:
    user = (
        await session.execute(select(users).where(users.c.id == current_user.user_id))
    ).one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return MeResponse(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=user.role,
        claims=await load_claims(session, user.id),
    )
