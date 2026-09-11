from fastapi import Request
from sqlalchemy import select

from .db import SessionLocal
from .desktop_routes import _hash
from .models import DesktopDevice
from .security import admin_token_valid, request_admin_token


def request_is_admin(request: Request, admin_token: str) -> bool:
    if admin_token_valid(request_admin_token(request), admin_token):
        return True
    authorization = request.headers.get("Authorization", "")
    token = authorization[8:].strip() if authorization.startswith("Desktop ") else request.cookies.get("stx_desktop")
    if not token:
        return False
    with SessionLocal() as db:
        device = db.execute(select(DesktopDevice).where(DesktopDevice.token_hash == _hash(token), DesktopDevice.revoked_at.is_(None))).scalar_one_or_none()
    return device is not None
