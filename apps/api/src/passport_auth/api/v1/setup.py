from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator

from passport_auth.setup.store import OwnerAccount, SetupAlreadyCompleteError, SetupStore

router = APIRouter(prefix="/setup", tags=["setup"])


class OwnerResponse(BaseModel):
    email: str


class SetupStatusResponse(BaseModel):
    setup_complete: bool
    owner: OwnerResponse | None


class OwnerSetupRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=12, max_length=1024)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if "@" not in normalized or normalized.startswith("@") or normalized.endswith("@"):
            raise ValueError("Enter a valid owner email.")
        return normalized


def get_setup_store(request: Request) -> SetupStore:
    return request.app.state.setup_store


def build_setup_status(owner: OwnerAccount | None) -> SetupStatusResponse:
    if not owner:
        return SetupStatusResponse(setup_complete=False, owner=None)

    return SetupStatusResponse(
        setup_complete=True,
        owner=OwnerResponse(email=owner.email),
    )


@router.get("/status")
def setup_status(
    setup_store: Annotated[SetupStore, Depends(get_setup_store)],
) -> SetupStatusResponse:
    return build_setup_status(setup_store.get_owner())


@router.post("/owner", status_code=status.HTTP_201_CREATED)
def create_owner_account(
    payload: OwnerSetupRequest,
    setup_store: Annotated[SetupStore, Depends(get_setup_store)],
) -> SetupStatusResponse:
    try:
        owner = setup_store.create_owner(email=payload.email, password=payload.password)
    except SetupAlreadyCompleteError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Setup is already complete.",
        ) from exc

    return build_setup_status(owner)
