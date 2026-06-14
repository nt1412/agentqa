from fastapi import APIRouter, status
from pydantic import BaseModel

from app.agent_orientation import AGENT_ORIENTATION
from app.api.deps import CurrentUser, SessionDep
from app.services import users

router = APIRouter(prefix="/api/v1", tags=["users"])


class AgentRegister(BaseModel):
    login: str
    agent_model: str | None = None
    email: str | None = None
    display_name: str | None = None


class AgentRegistered(BaseModel):
    id: int
    login: str
    agent_model: str | None = None
    auth_method: str
    api_key: str  # returned once — only its hash is stored
    orientation: str  # in-band onboarding so the agent can use the platform at once


@router.post(
    "/users/register-agent", response_model=AgentRegistered, status_code=status.HTTP_201_CREATED
)
async def register_agent(body: AgentRegister, session: SessionDep, user: CurrentUser):
    """Create an agent identity (auth_method='agent'), return a one-time API key
    plus orientation telling the agent how to use the platform."""
    u, api_key = await users.register_agent(
        session,
        login=body.login,
        agent_model=body.agent_model,
        email=body.email,
        display_name=body.display_name,
    )
    return AgentRegistered(
        id=u.id,
        login=u.login,
        agent_model=u.agent_model,
        auth_method=u.auth_method,
        api_key=api_key,
        orientation=AGENT_ORIENTATION,
    )
