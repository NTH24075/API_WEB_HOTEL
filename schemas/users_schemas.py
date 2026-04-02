from pydantic import BaseModel, EmailStr, Field
from typing import Optional

class RegisterRequest(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    phone: Optional[str] = None
    password: str = Field(..., min_length=8)
    citizen_id: Optional[str] = None
    address: Optional[str] = None
    avatar_url: Optional[str] = None

class LoginRequest(BaseModel):
    email:EmailStr
    password:str

class UserResponse(BaseModel):
    user_id: int
    full_name: str
    email: str
    phone: Optional[str] = None
    citizen_id: Optional[str] = None
    address: Optional[str] = None
    avatar_url: Optional[str] = None
    role_name: str
    status: str

class UpdateAccountInfoRequest(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=100)
    phone: Optional[str] = None
    citizen_id: Optional[str] = None
    address: Optional[str] = None
    avatar_url: Optional[str] = None


class DeleteAccountRequestBody(BaseModel):
    reason: str | None = None

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

class AdminCreateStaffRequest(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    phone: Optional[str] = None
    password: str = Field(..., min_length=8)
    citizen_id: Optional[str] = None
    address: Optional[str] = None
    avatar_url: Optional[str] = None
    role_name: str
    status: str = "Active"

class AdminUpdateRoleRequest(BaseModel):
    role_name: str

class AdminUpdateStatusRequest(BaseModel):
    status: str

class GoogleAuthRequest(BaseModel):
    credential: str

class FacebookLoginRequest(BaseModel):
    access_token:str