from pathlib import Path
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from pydantic import BaseModel

from passport_auth.api.v1.dashboard_auth import get_current_dashboard_user, require_owner
from passport_auth.setup.store import OwnerAccount

router = APIRouter(prefix="/dashboard/assets", tags=["dashboard-assets"])

ALLOWED_LOGO_CONTENT_TYPES = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
}
ALLOWED_LOGO_SLOTS = {"primary", "mark"}
MAX_LOGO_BYTES = 2 * 1024 * 1024


class LogoUploadResponse(BaseModel):
    slot: str
    url: str


def get_dashboard_asset_dir(request: Request) -> Path:
    return request.app.state.settings.dashboard_asset_dir


@router.post(
    "/logos/{slot}",
    status_code=status.HTTP_201_CREATED,
)
async def upload_dashboard_logo(
    slot: str,
    owner: Annotated[OwnerAccount, Depends(get_current_dashboard_user)],
    asset_dir: Annotated[Path, Depends(get_dashboard_asset_dir)],
    file: Annotated[UploadFile, File()],
) -> LogoUploadResponse:
    require_owner(owner)
    if slot not in ALLOWED_LOGO_SLOTS:
        raise HTTPException(status_code=404, detail="Logo slot not found.")

    extension = ALLOWED_LOGO_CONTENT_TYPES.get(file.content_type or "")
    if not extension:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Logo must be a PNG, JPG, or WebP image.",
        )

    content = await file.read(MAX_LOGO_BYTES + 1)
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Logo file is empty.",
        )
    if len(content) > MAX_LOGO_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Logo must be 2 MB or smaller.",
        )

    logo_dir = asset_dir / "logos"
    logo_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{slot}-{uuid4().hex}{extension}"
    path = logo_dir / filename
    path.write_bytes(content)

    return LogoUploadResponse(
        slot=slot,
        url=f"/dashboard-assets/logos/{filename}",
    )
