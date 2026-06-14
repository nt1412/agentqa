from fastapi import APIRouter, status

from app.api.deps import CurrentUser, SessionDep
from app.schemas.suite import SuiteCreate, SuiteNode, SuiteOut
from app.services import suites

router = APIRouter(prefix="/api/v1", tags=["suites"])


@router.post(
    "/projects/{project_id}/suites",
    response_model=SuiteOut,
    status_code=status.HTTP_201_CREATED,
)
async def create(project_id: int, body: SuiteCreate, session: SessionDep, user: CurrentUser):
    return await suites.create_suite(session, project_id, body)


@router.get("/projects/{project_id}/suites", response_model=list[SuiteOut])
async def list_all(project_id: int, session: SessionDep, user: CurrentUser):
    return await suites.list_suites(session, project_id)


@router.get("/suites/{suite_id}", response_model=SuiteOut)
async def get_one(suite_id: int, session: SessionDep, user: CurrentUser):
    return await suites.get_suite(session, suite_id)


@router.get("/suites/{suite_id}/tree", response_model=list[SuiteNode])
async def tree(suite_id: int, session: SessionDep, user: CurrentUser):
    suite = await suites.get_suite(session, suite_id)
    full = await suites.get_tree(session, suite.project_id)
    return [n for n in _collect(full, suite_id)]


def _collect(nodes, suite_id):
    for n in nodes:
        if n.id == suite_id:
            return [n]
        found = _collect(n.children, suite_id)
        if found:
            return found
    return []
