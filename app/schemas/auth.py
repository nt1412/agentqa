from pydantic import BaseModel


class LoginRequest(BaseModel):
    login: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ApiKeyResponse(BaseModel):
    api_key: str


class UserOut(BaseModel):
    id: int
    login: str
    email: str | None = None
    auth_method: str
    active: bool

    model_config = {"from_attributes": True}
