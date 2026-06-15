from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel

from app.agent_orientation import AGENT_ORIENTATION
from app.api.deps import CurrentUser, OptionalUser, SessionDep
from app.services import auth, users

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


class AgentSummary(BaseModel):
    id: int
    login: str
    agent_model: str | None = None
    active: bool

    model_config = {"from_attributes": True}


@router.post(
    "/users/register-agent", response_model=AgentRegistered, status_code=status.HTTP_201_CREATED
)
async def register_agent(
    body: AgentRegister,
    session: SessionDep,
    user: OptionalUser,
    x_enroll_key: Annotated[str | None, Header()] = None,
):
    """Create an agent identity (auth_method='agent'), return a one-time API key
    plus orientation telling the agent how to use the platform.

    Cold-start: an unauthenticated caller may register by supplying a valid
    X-Enroll-Key (the operator's enrollment secret) — so an agent can bootstrap
    its own identity over REST/CLI, matching the MCP register_agent path. Fails
    closed when no enrollment secret is configured."""
    if user is None and not auth.enrollment_allows(x_enroll_key):
        raise HTTPException(
            status_code=401,
            detail="register-agent requires authentication or a valid X-Enroll-Key",
        )
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


@router.get("/users/agents", response_model=list[AgentSummary])
async def list_agents(session: SessionDep, user: CurrentUser):
    """All agent identities (so probe/stale ones can be found and cleaned up)."""
    return await users.list_agents(session)


@router.delete("/users/{user_id}", response_model=AgentSummary)
async def deactivate_user(user_id: int, session: SessionDep, user: CurrentUser):
    """Soft-delete a user (mark inactive). Its recorded work stays attributable."""
    return await users.deactivate_user(session, user_id)
