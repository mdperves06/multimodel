import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)
    display_name: str = Field(default="", max_length=100)

    @field_validator("password")
    @classmethod
    def _password_strength(cls, v: str) -> str:
        if v.isalpha() or v.isdigit():
            raise ValueError("Password must mix letters with numbers or symbols")
        return v


def _check_strength(v: str) -> str:
    if v.isalpha() or v.isdigit():
        raise ValueError("Password must mix letters with numbers or symbols")
    return v


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=10, max_length=128)

    _strength = field_validator("new_password")(_check_strength)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    display_name: str
    created_at: datetime


class LoginResponse(BaseModel):
    user: UserOut
    access_token: str
    token_type: str = "bearer"  # noqa: S105
