from sqlalchemy.ext.asyncio import AsyncSession

from app.models.evidence import ExecutionClaim, ExecutionReasoning


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
