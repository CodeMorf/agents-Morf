import asyncio
import json
import time
import uuid
from decimal import Decimal

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    encrypt_secret,
    verify_password,
)
from app.dependencies import TenantContext, get_current_user, get_tenant, require_roles
from app.models import (
    Agent,
    CallJob,
    Conversation,
    Lead,
    MenuItem,
    Membership,
    Message,
    Order,
    Organization,
    Provider,
    Reservation,
    Role,
    User,
)
from app.schemas import (
    AgentCreate,
    AgentOut,
    AgentUpdate,
    CallCreate,
    CallOut,
    ChatCompletionRequest,
    ChatCompletionResponse,
    EmailTestRequest,
    LeadCreate,
    LeadOut,
    LoginRequest,
    MenuItemCreate,
    MenuItemOut,
    OrderCreate,
    OrderOut,
    OrganizationCreate,
    OrganizationOut,
    ProviderCreate,
    ProviderOut,
    RefreshRequest,
    ReservationCreate,
    ReservationOut,
    TokenPair,
    UserOut,
)
from app.services.email import EmailDeliveryError, send_email
from app.services.orchestrator import resolve_agent, run_agent
from app.services.providers import ProviderError

router = APIRouter()


@router.get("/health")
async def health(db: AsyncSession = Depends(get_db)):
    await db.execute(select(1))
    return {"status": "ok", "service": "agents-morf-api"}


@router.post("/auth/login", response_model=TokenPair)
async def login(data: LoginRequest, db: AsyncSession = Depends(get_db)):
    user = (
        await db.execute(select(User).where(func.lower(User.email) == data.email.lower()))
    ).scalar_one_or_none()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="User is inactive")
    return TokenPair(
        access_token=create_access_token(str(user.id)),
        refresh_token=create_refresh_token(str(user.id)),
    )


@router.post("/auth/refresh", response_model=TokenPair)
async def refresh(data: RefreshRequest, db: AsyncSession = Depends(get_db)):
    try:
        payload = decode_token(data.refresh_token, "refresh")
        user = await db.get(User, uuid.UUID(payload["sub"]))
    except (jwt.InvalidTokenError, ValueError, KeyError) as exc:
        raise HTTPException(status_code=401, detail="Invalid refresh token") from exc
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User is unavailable")
    return TokenPair(
        access_token=create_access_token(str(user.id)),
        refresh_token=create_refresh_token(str(user.id)),
    )


@router.get("/auth/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)):
    return user


@router.get("/organizations", response_model=list[OrganizationOut])
async def list_organizations(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    if user.is_superuser:
        return (await db.execute(select(Organization).order_by(Organization.name))).scalars().all()
    stmt = (
        select(Organization)
        .join(Membership)
        .where(Membership.user_id == user.id)
        .order_by(Organization.name)
    )
    return (await db.execute(stmt)).scalars().all()


@router.post("/organizations", response_model=OrganizationOut, status_code=201)
async def create_organization(
    data: OrganizationCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not user.is_superuser:
        raise HTTPException(status_code=403, detail="Super administrator required")
    org = Organization(**data.model_dump())
    db.add(org)
    await db.commit()
    await db.refresh(org)
    return org


@router.get("/dashboard")
async def dashboard(ctx: TenantContext = Depends(get_tenant), db: AsyncSession = Depends(get_db)):
    oid = ctx.organization.id

    async def count(model):
        return (
            await db.execute(
                select(func.count()).select_from(model).where(model.organization_id == oid)
            )
        ).scalar_one()

    return {
        "agents": await count(Agent),
        "leads": await count(Lead),
        "reservations": await count(Reservation),
        "orders": await count(Order),
        "calls": await count(CallJob),
        "conversations": await count(Conversation),
    }


@router.get("/agents", response_model=list[AgentOut])
async def list_agents(ctx: TenantContext = Depends(get_tenant), db: AsyncSession = Depends(get_db)):
    return (
        (
            await db.execute(
                select(Agent)
                .where(Agent.organization_id == ctx.organization.id)
                .order_by(Agent.created_at.desc())
            )
        )
        .scalars()
        .all()
    )


@router.post("/agents", response_model=AgentOut, status_code=201)
async def create_agent(
    data: AgentCreate,
    ctx: TenantContext = Depends(
        require_roles(Role.organization_owner, Role.organization_admin, Role.developer)
    ),
    db: AsyncSession = Depends(get_db),
):
    agent = Agent(organization_id=ctx.organization.id, **data.model_dump())
    db.add(agent)
    await db.commit()
    await db.refresh(agent)
    return agent


@router.patch("/agents/{agent_id}", response_model=AgentOut)
async def update_agent(
    agent_id: uuid.UUID,
    data: AgentUpdate,
    ctx: TenantContext = Depends(
        require_roles(Role.organization_owner, Role.organization_admin, Role.developer)
    ),
    db: AsyncSession = Depends(get_db),
):
    agent = (
        await db.execute(
            select(Agent).where(Agent.id == agent_id, Agent.organization_id == ctx.organization.id)
        )
    ).scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(agent, key, value)
    await db.commit()
    await db.refresh(agent)
    return agent


@router.get("/providers", response_model=list[ProviderOut])
async def list_providers(
    ctx: TenantContext = Depends(get_tenant), db: AsyncSession = Depends(get_db)
):
    return (
        (
            await db.execute(
                select(Provider)
                .where(Provider.organization_id == ctx.organization.id)
                .order_by(Provider.priority)
            )
        )
        .scalars()
        .all()
    )


@router.post("/providers", response_model=ProviderOut, status_code=201)
async def create_provider(
    data: ProviderCreate,
    ctx: TenantContext = Depends(
        require_roles(Role.organization_owner, Role.organization_admin, Role.developer)
    ),
    db: AsyncSession = Depends(get_db),
):
    values = data.model_dump(exclude={"api_key"})
    provider = Provider(
        organization_id=ctx.organization.id,
        encrypted_api_key=encrypt_secret(data.api_key),
        **values,
    )
    db.add(provider)
    await db.commit()
    await db.refresh(provider)
    return provider


@router.get("/leads", response_model=list[LeadOut])
async def list_leads(ctx: TenantContext = Depends(get_tenant), db: AsyncSession = Depends(get_db)):
    return (
        (
            await db.execute(
                select(Lead)
                .where(Lead.organization_id == ctx.organization.id)
                .order_by(Lead.created_at.desc())
            )
        )
        .scalars()
        .all()
    )


@router.post("/leads", response_model=LeadOut, status_code=201)
async def create_lead(
    data: LeadCreate, ctx: TenantContext = Depends(get_tenant), db: AsyncSession = Depends(get_db)
):
    lead = Lead(organization_id=ctx.organization.id, **data.model_dump())
    db.add(lead)
    await db.commit()
    await db.refresh(lead)
    return lead


@router.get("/reservations", response_model=list[ReservationOut])
async def list_reservations(
    ctx: TenantContext = Depends(get_tenant), db: AsyncSession = Depends(get_db)
):
    return (
        (
            await db.execute(
                select(Reservation)
                .where(Reservation.organization_id == ctx.organization.id)
                .order_by(Reservation.starts_at)
            )
        )
        .scalars()
        .all()
    )


@router.post("/reservations", response_model=ReservationOut, status_code=201)
async def create_reservation(
    data: ReservationCreate,
    ctx: TenantContext = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    reservation = Reservation(organization_id=ctx.organization.id, **data.model_dump())
    db.add(reservation)
    await db.commit()
    await db.refresh(reservation)
    return reservation


@router.get("/menu-items", response_model=list[MenuItemOut])
async def list_menu(ctx: TenantContext = Depends(get_tenant), db: AsyncSession = Depends(get_db)):
    return (
        (
            await db.execute(
                select(MenuItem)
                .where(MenuItem.organization_id == ctx.organization.id)
                .order_by(MenuItem.category, MenuItem.name)
            )
        )
        .scalars()
        .all()
    )


@router.post("/menu-items", response_model=MenuItemOut, status_code=201)
async def create_menu_item(
    data: MenuItemCreate,
    ctx: TenantContext = Depends(
        require_roles(Role.organization_owner, Role.organization_admin, Role.operator)
    ),
    db: AsyncSession = Depends(get_db),
):
    item = MenuItem(organization_id=ctx.organization.id, **data.model_dump())
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item


@router.get("/orders", response_model=list[OrderOut])
async def list_orders(ctx: TenantContext = Depends(get_tenant), db: AsyncSession = Depends(get_db)):
    return (
        (
            await db.execute(
                select(Order)
                .where(Order.organization_id == ctx.organization.id)
                .order_by(Order.created_at.desc())
            )
        )
        .scalars()
        .all()
    )


@router.post("/orders", response_model=OrderOut, status_code=201)
async def create_order(
    data: OrderCreate, ctx: TenantContext = Depends(get_tenant), db: AsyncSession = Depends(get_db)
):
    total = Decimal("0")
    for item in data.items:
        total += Decimal(str(item.get("unit_price", 0))) * int(item.get("quantity", 1))
    order = Order(organization_id=ctx.organization.id, total=total, **data.model_dump())
    db.add(order)
    await db.commit()
    await db.refresh(order)
    return order


@router.get("/calls", response_model=list[CallOut])
async def list_calls(ctx: TenantContext = Depends(get_tenant), db: AsyncSession = Depends(get_db)):
    return (
        (
            await db.execute(
                select(CallJob)
                .where(CallJob.organization_id == ctx.organization.id)
                .order_by(CallJob.created_at.desc())
            )
        )
        .scalars()
        .all()
    )


@router.post("/calls", response_model=CallOut, status_code=201)
async def create_call(
    data: CallCreate, ctx: TenantContext = Depends(get_tenant), db: AsyncSession = Depends(get_db)
):
    job = CallJob(organization_id=ctx.organization.id, **data.model_dump())
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job


@router.post("/admin/email/test")
async def email_test(
    data: EmailTestRequest,
    ctx: TenantContext = Depends(require_roles(Role.organization_owner, Role.organization_admin)),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await send_email(
            data.to, data.subject, "Agents Morf SMTP2GO configuration is working."
        )
    except EmailDeliveryError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"status": "sent", "result": result}


@router.post("/chat/completions", response_model=ChatCompletionResponse)
async def chat_completions(
    data: ChatCompletionRequest,
    request: Request,
    ctx: TenantContext = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    agent = await resolve_agent(db, ctx.organization.id, data.agent_id)
    if data.agent_id and not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    conversation = (
        await db.get(Conversation, data.conversation_id) if data.conversation_id else None
    )
    if conversation and conversation.organization_id != ctx.organization.id:
        raise HTTPException(status_code=403, detail="Conversation belongs to another organization")
    if not conversation:
        title = next((m.content[:100] for m in data.messages if m.role == "user"), "Conversation")
        conversation = Conversation(
            organization_id=ctx.organization.id, agent_id=agent.id if agent else None, title=title
        )
        db.add(conversation)
        await db.flush()
    for message in data.messages:
        db.add(
            Message(
                organization_id=ctx.organization.id,
                conversation_id=conversation.id,
                role=message.role,
                content=message.content,
            )
        )
    await db.commit()
    try:
        result = await run_agent(
            db,
            ctx.organization.id,
            agent,
            [m.model_dump() for m in data.messages],
            data.model,
            data.temperature,
            data.max_tokens,
        )
    except ProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    assistant = Message(
        organization_id=ctx.organization.id,
        conversation_id=conversation.id,
        role="assistant",
        content=result.content,
        model=result.model,
        provider=result.provider,
        usage=result.usage,
    )
    db.add(assistant)
    await db.commit()
    response_id = f"chatcmpl-{uuid.uuid4().hex}"
    payload = ChatCompletionResponse(
        id=response_id,
        created=int(time.time()),
        model=result.model,
        provider=result.provider,
        conversation_id=conversation.id,
        choices=[
            {
                "index": 0,
                "message": {"role": "assistant", "content": result.content},
                "finish_reason": "stop",
            }
        ],
        usage=result.usage,
    )
    if not data.stream:
        return payload

    async def stream():
        event = {
            "id": response_id,
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": result.model,
            "choices": [
                {
                    "index": 0,
                    "delta": {"role": "assistant", "content": result.content},
                    "finish_reason": None,
                }
            ],
        }
        yield f"data: {json.dumps(event)}\n\n"
        await asyncio.sleep(0)
        yield "data: [DONE]\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")
