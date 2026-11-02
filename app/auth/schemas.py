import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, ConfigDict, EmailStr, Field


def _strip(value: object) -> object:
    return value.strip() if isinstance(value, str) else value


Email = Annotated[EmailStr, BeforeValidator(_strip)]
Password = Annotated[str, Field(min_length=8, max_length=128)]  # AUTH-1.4
Token = Annotated[str, Field(min_length=1, max_length=256)]


class RegisterIn(BaseModel):
    email: Email
    password: Password


class LoginIn(BaseModel):
    email: Email
    # Do not enforce length rules on login: old passwords may predate them.
    password: Annotated[str, Field(min_length=1, max_length=1024)]


class EmailIn(BaseModel):
    email: Email


class TokenIn(BaseModel):
    token: Token


class PasswordResetConfirmIn(BaseModel):
    token: Token
    password: Password


class ChangePasswordIn(BaseModel):
    current_password: Annotated[str, Field(min_length=1, max_length=1024)]
    new_password: Password


class UserOut(BaseModel):
    """AUTH-6.1."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    email_verified: bool
    created_at: datetime
