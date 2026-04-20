from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.auth import get_current_user
from core.database import get_supabase_client

router = APIRouter(prefix="/api/v1/me", tags=["me"])


class ProfileUpdateRequest(BaseModel):
    name: Optional[str] = None
    daily_planned_minutes: Optional[int] = Field(default=None, ge=5, le=240)
    target_exam: Optional[str] = None
    current_level: Optional[str] = None
    focus_topic: Optional[str] = None
    onboarding_completed: Optional[bool] = None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_profile(uid: str, token_payload: dict) -> dict:
    now = _now_iso()
    return {
        "uid": uid,
        "name": token_payload.get("name") or "Learner",
        "phone_number": token_payload.get("phone_number"),
        "photo_url": token_payload.get("picture"),
        "daily_planned_minutes": 24,
        "target_exam": "Semester Mastery",
        "current_level": "Intermediate",
        "focus_topic": "Operating Systems",
        "onboarding_completed": False,
        "created_at": now,
        "updated_at": now,
    }


def _fetch_profile(uid: str) -> Optional[dict]:
    supabase = get_supabase_client()
    response = supabase.table("user_profiles").select("*").eq("uid", uid).limit(1).execute()
    if response.data:
        return response.data[0]
    return None


@router.get("")
async def get_profile(current_user=Depends(get_current_user)):
    uid = current_user.get("uid")
    if not uid:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    profile = _fetch_profile(uid)
    if profile is not None:
        return profile

    profile = _default_profile(uid, current_user)
    supabase = get_supabase_client()
    supabase.table("user_profiles").insert(profile).execute()
    return profile


@router.put("")
async def update_profile(payload: ProfileUpdateRequest, current_user=Depends(get_current_user)):
    uid = current_user.get("uid")
    if not uid:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    existing = _fetch_profile(uid) or _default_profile(uid, current_user)
    merged = dict(existing)
    update_data = payload.model_dump(exclude_none=True)
    merged.update(update_data)
    merged["uid"] = uid
    merged["updated_at"] = _now_iso()
    if not merged.get("created_at"):
        merged["created_at"] = _now_iso()

    supabase = get_supabase_client()
    supabase.table("user_profiles").upsert(merged, on_conflict="uid").execute()
    return merged
