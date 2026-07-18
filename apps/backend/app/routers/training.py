import uuid
from difflib import SequenceMatcher

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies import TenantContext, get_tenant, require_roles
from app.models import Agent, Role, TrainingDataset, TrainingExample
from app.schemas import (
    EvaluationRequest,
    TrainingDatasetCreate,
    TrainingDatasetOut,
    TrainingExampleCreate,
    TrainingExampleOut,
)
from app.services.orchestrator import run_agent

router = APIRouter(prefix="/training", tags=["Training"])


@router.get("/datasets", response_model=list[TrainingDatasetOut])
async def list_datasets(
    ctx: TenantContext = Depends(get_tenant), db: AsyncSession = Depends(get_db)
):
    return (
        (
            await db.execute(
                select(TrainingDataset)
                .where(TrainingDataset.organization_id == ctx.organization.id)
                .order_by(TrainingDataset.name)
            )
        )
        .scalars()
        .all()
    )


@router.post("/datasets", response_model=TrainingDatasetOut, status_code=201)
async def create_dataset(
    data: TrainingDatasetCreate,
    ctx: TenantContext = Depends(
        require_roles(Role.organization_owner, Role.organization_admin, Role.developer)
    ),
    db: AsyncSession = Depends(get_db),
):
    dataset = TrainingDataset(organization_id=ctx.organization.id, **data.model_dump())
    db.add(dataset)
    await db.commit()
    await db.refresh(dataset)
    return dataset


@router.get("/datasets/{dataset_id}/examples", response_model=list[TrainingExampleOut])
async def list_examples(
    dataset_id: uuid.UUID,
    ctx: TenantContext = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    return (
        (
            await db.execute(
                select(TrainingExample)
                .where(
                    TrainingExample.organization_id == ctx.organization.id,
                    TrainingExample.dataset_id == dataset_id,
                )
                .order_by(TrainingExample.created_at.desc())
            )
        )
        .scalars()
        .all()
    )


@router.post("/datasets/{dataset_id}/examples", response_model=TrainingExampleOut, status_code=201)
async def create_example(
    dataset_id: uuid.UUID,
    data: TrainingExampleCreate,
    ctx: TenantContext = Depends(
        require_roles(Role.organization_owner, Role.organization_admin, Role.developer)
    ),
    db: AsyncSession = Depends(get_db),
):
    dataset = (
        await db.execute(
            select(TrainingDataset).where(
                TrainingDataset.id == dataset_id,
                TrainingDataset.organization_id == ctx.organization.id,
            )
        )
    ).scalar_one_or_none()
    if not dataset:
        raise HTTPException(status_code=404, detail="Training dataset not found")
    example = TrainingExample(
        organization_id=ctx.organization.id,
        dataset_id=dataset_id,
        **data.model_dump(),
    )
    db.add(example)
    await db.commit()
    await db.refresh(example)
    return example


@router.post("/evaluate")
async def evaluate(
    data: EvaluationRequest,
    ctx: TenantContext = Depends(
        require_roles(Role.organization_owner, Role.organization_admin, Role.developer)
    ),
    db: AsyncSession = Depends(get_db),
):
    agent = (
        await db.execute(
            select(Agent).where(
                Agent.id == data.agent_id,
                Agent.organization_id == ctx.organization.id,
            )
        )
    ).scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    examples = (
        (
            await db.execute(
                select(TrainingExample)
                .where(
                    TrainingExample.organization_id == ctx.organization.id,
                    TrainingExample.dataset_id == data.dataset_id,
                    TrainingExample.enabled.is_(True),
                )
                .limit(data.limit)
            )
        )
        .scalars()
        .all()
    )
    results = []
    for example in examples:
        run = await run_agent(
            db,
            ctx.organization.id,
            agent,
            [{"role": "user", "content": example.input_text}],
            None,
            0,
            min(agent.max_tokens, 1000),
        )
        actual = run.provider_result.content
        score = SequenceMatcher(
            None, actual.lower().strip(), example.expected_output.lower().strip()
        ).ratio()
        results.append(
            {
                "example_id": str(example.id),
                "input": example.input_text,
                "expected": example.expected_output,
                "actual": actual,
                "similarity": round(score, 4),
                "passed": score >= 0.65,
            }
        )
    average = sum(item["similarity"] for item in results) / len(results) if results else 0
    return {"count": len(results), "average_similarity": round(average, 4), "results": results}
