import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_settings
from .db import get_db
from .models import DesktopDevice, DesktopPairing
from .security import admin_token_valid, request_admin_token

router = APIRouter(prefix="/api/desktop", tags=["desktop"])
PAIRING_TTL_MINUTES = 10


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _admin(request: Request) -> None:
    if not admin_token_valid(request_admin_token(request), get_settings().admin_api_token):
        raise HTTPException(401, "Authentication required")


@router.post("/pairings")
def create_pairing(request: Request, db: Session = Depends(get_db)):
    _admin(request)
    code = secrets.token_urlsafe(9)
    db.add(DesktopPairing(code_hash=_hash(code), expires_at=datetime.now(timezone.utc) + timedelta(minutes=PAIRING_TTL_MINUTES)))
    db.commit()
    return {"code": code, "expires_in_seconds": PAIRING_TTL_MINUTES * 60}


@router.post("/pairings/redeem")
async def redeem_pairing(request: Request, db: Session = Depends(get_db)):
    body = await request.json()
    code = str(body.get("code", "")).strip()
    label = str(body.get("label", "")).strip()[:96] or None
    pairing = db.execute(select(DesktopPairing).where(DesktopPairing.code_hash == _hash(code))).scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if not pairing or pairing.used_at or pairing.expires_at < now:
        raise HTTPException(401, "Pairing code is invalid or expired")
    token = secrets.token_urlsafe(32)
    pairing.used_at = now
    db.add(DesktopDevice(token_hash=_hash(token), label=label))
    db.commit()
    return {"device_token": token}


@router.post("/session")
async def create_session(request: Request, db: Session = Depends(get_db)):
    body = await request.json()
    token = str(body.get("device_token", "")).strip()
    device = db.execute(select(DesktopDevice).where(DesktopDevice.token_hash == _hash(token), DesktopDevice.revoked_at.is_(None))).scalar_one_or_none()
    if not device:
        raise HTTPException(401, "Desktop device is not authorized")
    device.last_used_at = datetime.now(timezone.utc)
    db.commit()
    response = JSONResponse({"authenticated": True})
    response.set_cookie("stx_desktop", token, httponly=True, secure=get_settings().admin_cookie_secure, samesite="strict", max_age=28800)
    return response
