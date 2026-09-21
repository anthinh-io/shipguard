from typing import Literal

from pydantic import BaseModel
from sqlalchemy import Row, insert, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password, verify_password
from app.models.auth import Role, users
from app.services.auth import load_claims, normalize_email, revoke_all_refresh_tokens

MIN_PASSWORD_LENGTH = 8

# Vai trò gán được qua API. Không có super_admin: chỉ một Super Admin, sinh từ cấu hình.
AssignableRole = Literal["operations_staff", "logistics_manager"]


class PasswordTooShortError(ValueError):
    def __init__(self) -> None:
        super().__init__(f"Password must be at least {MIN_PASSWORD_LENGTH} characters")


class WrongCurrentPasswordError(ValueError):
    def __init__(self) -> None:
        super().__init__("Current password is incorrect")


class SuperAdminEmailTakenError(RuntimeError):
    def __init__(self, email: str) -> None:
        super().__init__(
            f"SUPER_ADMIN_EMAIL {email} already belongs to a User who is not the "
            "Super Admin. Set SUPER_ADMIN_EMAIL to an unused address and start again."
        )


class SuperAdminMissingError(RuntimeError):
    def __init__(self) -> None:
        super().__init__(
            "No Super Admin exists yet. Start the backend once to create it from "
            "SUPER_ADMIN_EMAIL, SUPER_ADMIN_PASSWORD and SUPER_ADMIN_NAME."
        )


class EmailTakenError(ValueError):
    def __init__(self) -> None:
        super().__init__("Email is already in use")


class UserNotFoundError(LookupError):
    def __init__(self) -> None:
        super().__init__("User not found")


class SuperAdminProtectedError(PermissionError):
    def __init__(self) -> None:
        super().__init__("The Super Admin cannot be managed")


class LogisticsManagerProtectedError(PermissionError):
    def __init__(self) -> None:
        super().__init__("Only the Super Admin can manage Logistics Manager accounts")


class RoleChangeRequiresSuperAdminError(PermissionError):
    def __init__(self) -> None:
        super().__init__("Only the Super Admin can change roles")


class UserProfile(BaseModel):
    id: int
    email: str
    display_name: str
    role: Role
    claims: list[str]


class UserSummary(BaseModel):
    id: int
    email: str
    display_name: str
    role: Role
    is_locked: bool


def check_password_policy(password: str) -> None:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise PasswordTooShortError


# User không bao giờ bị xóa (CONTEXT.md), nên một user_id lấy từ token đã ký luôn có dòng.
async def get_user_profile(session: AsyncSession, user_id: int) -> UserProfile:
    user = (await session.execute(select(users).where(users.c.id == user_id))).one()
    return UserProfile(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=user.role,
        claims=await load_claims(session, user_id),
    )


async def create_user(
    session: AsyncSession,
    *,
    email: str,
    password: str,
    display_name: str,
    role: Role,
    is_locked: bool = False,
) -> int:
    check_password_policy(password)
    # Dựa vào chỉ mục duy nhất thay vì tra trước: tra trước rồi mới chèn thì hai lần tạo
    # đồng thời cùng email đều qua được bước tra.
    try:
        user_id = await session.scalar(
            insert(users)
            .values(
                email=normalize_email(email),
                display_name=display_name,
                password_hash=await hash_password(password),
                role=role,
                is_locked=is_locked,
            )
            .returning(users.c.id)
        )
    except IntegrityError as error:
        await session.rollback()
        if "uq_users_email_lower" in str(error.orig):
            raise EmailTakenError from None
        raise
    await session.commit()
    return user_id


async def create_managed_user(
    session: AsyncSession,
    *,
    actor_role: Role,
    email: str,
    password: str,
    display_name: str,
    role: AssignableRole,
) -> int:
    """Tạo tài khoản qua API quản trị, nhận vai trò người gọi từ access token.

    Tách khỏi create_user cấp thấp mà ensure_super_admin và test dùng: luật "ai được
    tạo vai trò nào" (ADR-0011) phụ thuộc người gọi, nên chỉ đường quản trị cần biết.
    AssignableRole chỉ loại super_admin ở tầng lược đồ; phần còn lại của luật nằm ở đây.
    """
    # Kiểm quyền trước chính sách mật khẩu: yêu cầu ngoài quyền bị từ chối vì quyền.
    _check_target_role(actor_role, role)
    return await create_user(
        session, email=email, password=password, display_name=display_name, role=role
    )


def _summary(user: Row) -> UserSummary:
    return UserSummary(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=user.role,
        is_locked=user.is_locked,
    )


async def list_users(session: AsyncSession) -> list[UserSummary]:
    rows = await session.execute(select(users).order_by(users.c.id))
    return [_summary(user) for user in rows]


async def get_user_summary(session: AsyncSession, user_id: int) -> UserSummary:
    user = (await session.execute(select(users).where(users.c.id == user_id))).one()
    return _summary(user)


def _check_target_role(actor_role: Role, target_role: Role) -> None:
    # Phát biểu đúng như ADR-0011: ngoài Super Admin, chỉ chạm được operations_staff.
    # Đừng nới thành "không chạm Logistics Manager khác" — rào chặn tự quản lý chính
    # mình đã bỏ vì câu này bao trùm nó, nới ra là lỗ hổng đó mở lại.
    if actor_role != "super_admin" and target_role != "operations_staff":
        raise LogisticsManagerProtectedError


async def _load_manageable_user(
    session: AsyncSession, actor_role: Role, user_id: int
) -> Row:
    """Kiểm ở đây chứ không chỉ ẩn nút: yêu cầu gửi thẳng tới API cũng phải bị chặn.

    Vai trò của người bị tác động đọc từ cơ sở dữ liệu, không tin thứ gì client gửi;
    actor_role là vai trò người gọi trong access token.
    """
    user = (
        await session.execute(select(users).where(users.c.id == user_id))
    ).one_or_none()
    if user is None:
        raise UserNotFoundError
    # Không ai quản lý được Super Admin — để hệ thống luôn còn một lối vào. Kiểm trước
    # rào theo vai trò để chạm Super Admin luôn nhận đúng thông điệp này.
    if user.role == "super_admin":
        raise SuperAdminProtectedError
    _check_target_role(actor_role, user.role)
    return user


async def update_user(
    session: AsyncSession,
    *,
    actor_role: Role,
    user_id: int,
    role: AssignableRole | None = None,
    is_locked: bool | None = None,
) -> UserSummary:
    user = await _load_manageable_user(session, actor_role, user_id)
    # #52: đổi vai trò là đặc quyền riêng của Super Admin, dù đối tượng đã qua được rào
    # theo phạm vi ở trên. Xét trên `role is not None`, không so với `user.role` — một
    # yêu cầu đổi vai trò vẫn phải bị từ chối kể cả khi giá trị gửi lên trùng vai trò
    # hiện tại, vì đây là yêu cầu đổi vai trò chứ không phải "có đổi thật hay không".
    if role is not None and actor_role != "super_admin":
        raise RoleChangeRequiresSuperAdminError
    changes: dict[str, object] = {}
    if role is not None and role != user.role:
        changes["role"] = role
    if is_locked is not None and is_locked != user.is_locked:
        changes["is_locked"] = is_locked
    if changes:
        await session.execute(
            update(users).where(users.c.id == user_id).values(**changes)
        )
        # Mở khóa không cần thu hồi: lúc khóa đã thu hồi hết. Cùng transaction với
        # UPDATE để không có khoảnh khắc đã khóa mà phiên cũ vẫn làm mới được.
        if "role" in changes or changes.get("is_locked") is True:
            await revoke_all_refresh_tokens(session, user_id)
        await session.commit()
    return await get_user_summary(session, user_id)


async def _super_admin_id(session: AsyncSession) -> int | None:
    return await session.scalar(select(users.c.id).where(users.c.role == "super_admin"))


async def ensure_super_admin(
    session: AsyncSession, *, email: str, password: str, display_name: str
) -> bool:
    """Tạo Super Admin nếu chưa có; trả True khi vừa tạo.

    Đã có thì không đọc cấu hình, không đổi gì — cấu hình chỉ dùng cho lần cài đặt đầu.
    """
    if await _super_admin_id(session) is not None:
        return False
    normalized = normalize_email(email)
    taken = await session.scalar(select(users.c.id).where(users.c.email == normalized))
    if taken is not None:
        raise SuperAdminEmailTakenError(normalized)
    await create_user(
        session,
        email=normalized,
        password=password,
        display_name=display_name,
        role="super_admin",
    )
    return True


async def _set_password_and_sign_out(
    session: AsyncSession, user_id: int, new_password: str
) -> None:
    # Đổi mật khẩu và thu hồi phiên trong cùng một transaction: không có khoảnh khắc nào
    # mật khẩu đã đổi mà phiên cũ vẫn làm mới được.
    await session.execute(
        update(users)
        .where(users.c.id == user_id)
        .values(password_hash=await hash_password(new_password))
    )
    await revoke_all_refresh_tokens(session, user_id)
    await session.commit()


async def reset_super_admin_password(session: AsyncSession, new_password: str) -> None:
    check_password_policy(new_password)
    user_id = await _super_admin_id(session)
    if user_id is None:
        raise SuperAdminMissingError
    await _set_password_and_sign_out(session, user_id, new_password)


async def reset_user_password(
    session: AsyncSession,
    *,
    actor_role: Role,
    user_id: int,
    new_password: str,
) -> None:
    # Kiểm quyền trước chính sách mật khẩu, như ở create_managed_user: yêu cầu ngoài
    # quyền bị từ chối vì quyền.
    await _load_manageable_user(session, actor_role, user_id)
    check_password_policy(new_password)
    await _set_password_and_sign_out(session, user_id, new_password)


async def change_password(
    session: AsyncSession, user_id: int, current_password: str, new_password: str
) -> Row:
    """Trả dòng User để route cấp phiên mới cho chính người vừa đổi."""
    # Kiểm độ dài trước: khỏi tốn một lượt Argon2 cho yêu cầu chắc chắn bị từ chối.
    check_password_policy(new_password)
    user = (await session.execute(select(users).where(users.c.id == user_id))).one()
    if not await verify_password(current_password, user.password_hash):
        raise WrongCurrentPasswordError
    # Thu hồi cả phiên đang dùng; route cấp token mới cho phiên này sau khi commit, nên
    # token đó không bị thu hồi theo.
    await _set_password_and_sign_out(session, user_id, new_password)
    return user
