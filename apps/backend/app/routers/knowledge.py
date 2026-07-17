import json
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.dependencies import TenantContext, get_tenant, require_roles
from app.models import Document, KnowledgeBase, Role
from app.schemas import DocumentOut, DocumentTextCreate, KnowledgeBaseCreate, KnowledgeBaseOut
from app.services.document_loader import UnsupportedDocumentError, extract_document_text
from app.services.knowledge import ingest_text_document

router = APIRouter(prefix="/knowledge-bases", tags=["Knowledge"])


@router.get("", response_model=list[KnowledgeBaseOut])
async def list_knowledge_bases(
    ctx: TenantContext = Depends(get_tenant), db: AsyncSession = Depends(get_db)
):
    return (
        (
            await db.execute(
                select(KnowledgeBase)
                .where(KnowledgeBase.organization_id == ctx.organization.id)
                .order_by(KnowledgeBase.name)
            )
        )
        .scalars()
        .all()
    )


@router.post("", response_model=KnowledgeBaseOut, status_code=201)
async def create_knowledge_base(
    data: KnowledgeBaseCreate,
    ctx: TenantContext = Depends(
        require_roles(Role.organization_owner, Role.organization_admin, Role.developer)
    ),
    db: AsyncSession = Depends(get_db),
):
    kb = KnowledgeBase(organization_id=ctx.organization.id, **data.model_dump())
    db.add(kb)
    await db.commit()
    await db.refresh(kb)
    return kb


@router.get("/{knowledge_base_id}/documents", response_model=list[DocumentOut])
async def list_documents(
    knowledge_base_id: uuid.UUID,
    ctx: TenantContext = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    return (
        (
            await db.execute(
                select(Document)
                .where(
                    Document.organization_id == ctx.organization.id,
                    Document.knowledge_base_id == knowledge_base_id,
                )
                .order_by(Document.created_at.desc())
            )
        )
        .scalars()
        .all()
    )


@router.post("/{knowledge_base_id}/documents/text", response_model=DocumentOut, status_code=201)
async def create_text_document(
    knowledge_base_id: uuid.UUID,
    data: DocumentTextCreate,
    ctx: TenantContext = Depends(
        require_roles(Role.organization_owner, Role.organization_admin, Role.developer)
    ),
    db: AsyncSession = Depends(get_db),
):
    kb = (
        await db.execute(
            select(KnowledgeBase).where(
                KnowledgeBase.id == knowledge_base_id,
                KnowledgeBase.organization_id == ctx.organization.id,
            )
        )
    ).scalar_one_or_none()
    if not kb:
        raise HTTPException(status_code=404, detail="Knowledge base not found")
    return await ingest_text_document(
        db,
        ctx.organization.id,
        knowledge_base_id,
        title=data.title,
        content=data.content,
        source_type=data.source_type,
        mime_type=data.mime_type,
        metadata=data.metadata,
    )


@router.post("/{knowledge_base_id}/documents/upload", response_model=DocumentOut, status_code=201)
async def upload_document(
    knowledge_base_id: uuid.UUID,
    file: UploadFile = File(...),
    ctx: TenantContext = Depends(
        require_roles(Role.organization_owner, Role.organization_admin, Role.developer)
    ),
    db: AsyncSession = Depends(get_db),
):
    kb = (
        await db.execute(
            select(KnowledgeBase).where(
                KnowledgeBase.id == knowledge_base_id,
                KnowledgeBase.organization_id == ctx.organization.id,
            )
        )
    ).scalar_one_or_none()
    if not kb:
        raise HTTPException(status_code=404, detail="Knowledge base not found")
    data = await file.read(settings.knowledge_max_file_bytes + 1)
    if len(data) > settings.knowledge_max_file_bytes:
        raise HTTPException(status_code=413, detail="Document exceeds the configured size limit")
    try:
        content = extract_document_text(file.filename or "document", file.content_type, data)
    except (UnsupportedDocumentError, ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not content.strip():
        raise HTTPException(status_code=400, detail="No readable text was found in the document")
    return await ingest_text_document(
        db,
        ctx.organization.id,
        knowledge_base_id,
        title=file.filename or "Uploaded document",
        content=content,
        source_type="upload",
        mime_type=file.content_type or "application/octet-stream",
        metadata={"filename": file.filename or ""},
    )
