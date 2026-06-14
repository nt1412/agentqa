from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import storage
from app.models.evidence import ExecutionArtifact, ExecutionClaim, ExecutionReasoning
from app.models.execution import Execution
from app.services.errors import NotFound


async def record_claims_and_reasoning(
    session: AsyncSession,
    execution_id: int,
    claims: list[str],
    reasoning: dict | None,
    agent_model: str | None,
    session_id: str | None,
) -> None:
    """Persist claims + reasoning for an execution. Does NOT commit (caller owns tx)."""
    for claim_text in claims:
        session.add(ExecutionClaim(execution_id=execution_id, claim_text=claim_text))
    if reasoning is not None or agent_model is not None:
        session.add(
            ExecutionReasoning(
                execution_id=execution_id,
                reasoning=reasoning,
                agent_model=agent_model,
                agent_session_id=session_id,
            )
        )


async def _get_execution(session: AsyncSession, execution_id: int) -> Execution:
    ex = await session.get(Execution, execution_id)
    if ex is None:
        raise NotFound(f"execution {execution_id} not found")
    return ex


async def upload_artifact(
    session: AsyncSession,
    execution_id: int,
    artifact_type: str,
    title: str | None,
    content: bytes,
    mime_type: str | None,
) -> ExecutionArtifact:
    await _get_execution(session, execution_id)
    key = storage.build_key(execution_id, artifact_type, title or artifact_type)
    storage.put_object(key, content, mime_type or "application/octet-stream")
    artifact = ExecutionArtifact(
        execution_id=execution_id,
        artifact_type=artifact_type,
        title=title,
        blob_key=key,
        size=len(content),
        mime_type=mime_type,
    )
    session.add(artifact)
    await session.commit()
    await session.refresh(artifact)
    return artifact


async def list_artifacts(session: AsyncSession, execution_id: int) -> list[ExecutionArtifact]:
    stmt = (
        select(ExecutionArtifact)
        .where(ExecutionArtifact.execution_id == execution_id)
        .order_by(ExecutionArtifact.id)
    )
    return list((await session.execute(stmt)).scalars().all())
