import asyncio
import sys
from getpass import getpass

from app.core.db import SessionLocal, engine
from app.services.users import (
    PasswordTooShortError,
    SuperAdminMissingError,
    reset_super_admin_password,
)


async def reset(new_password: str) -> None:
    try:
        async with SessionLocal() as session:
            await reset_super_admin_password(session, new_password)
    finally:
        await engine.dispose()


def main() -> None:
    # Hỏi qua getpass thay vì nhận tham số dòng lệnh, để mật khẩu không lọt vào lịch sử
    # shell hay danh sách tiến trình.
    new_password = getpass("New Super Admin password: ")
    if getpass("Repeat the password: ") != new_password:
        sys.exit("Passwords do not match; nothing changed.")
    try:
        asyncio.run(reset(new_password))
    except (PasswordTooShortError, SuperAdminMissingError) as error:
        sys.exit(f"{error}; nothing changed.")
    print("Super Admin password reset; all sessions signed out.")


if __name__ == "__main__":
    main()
