from io import BytesIO

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pypdf import PdfReader

from backend.app.core.database.connection import SessionLocal
from backend.app.core.dependencies import require_xvond_admin
from backend.app.models.user import User
from backend.app.modules.ai_agent.models import AIAgent
from backend.app.modules.knowledge.models import AgentKnowledge, KnowledgeDocument
from backend.app.modules.knowledge.service import knowledge_service

router = APIRouter(prefix="/admin/ai-employees", tags=["Xvond Admin - AI Employee Files"])
MAX_PDF_BYTES = 15 * 1024 * 1024
MAX_PDF_PAGES = 250


@router.post("/companies/{company_id}/{agent_id}/knowledge/pdf")
async def upload_pdf_knowledge(
    company_id: int,
    agent_id: int,
    file: UploadFile = File(...),
    current_admin: User = Depends(require_xvond_admin),
):
    db = SessionLocal()
    try:
        agent = db.query(AIAgent).filter(AIAgent.id == agent_id, AIAgent.company_id == company_id).first()
        if agent is None:
            raise HTTPException(404, "AI employee not found")
        filename = (file.filename or "document.pdf").strip()
        if not filename.lower().endswith(".pdf") or file.content_type not in ("application/pdf", "application/octet-stream", None):
            raise HTTPException(400, "Only PDF files are supported")
        raw = await file.read(MAX_PDF_BYTES + 1)
        if not raw:
            raise HTTPException(400, "PDF is empty")
        if len(raw) > MAX_PDF_BYTES:
            raise HTTPException(413, "PDF is larger than 15 MB")
        try:
            reader = PdfReader(BytesIO(raw))
        except Exception as exc:
            raise HTTPException(400, "Invalid or unreadable PDF") from exc
        if reader.is_encrypted:
            try:
                if reader.decrypt("") == 0:
                    raise HTTPException(400, "Password-protected PDFs are not supported")
            except HTTPException:
                raise
            except Exception as exc:
                raise HTTPException(400, "Password-protected PDFs are not supported") from exc
        if len(reader.pages) > MAX_PDF_PAGES:
            raise HTTPException(413, f"PDF has more than {MAX_PDF_PAGES} pages")
        pages = []
        for number, page in enumerate(reader.pages, start=1):
            try:
                text = (page.extract_text() or "").strip()
            except Exception:
                text = ""
            if text:
                pages.append(f"[Page {number}]\n{text}")
        content = "\n\n".join(pages).strip()
        if len(content) < 20:
            raise HTTPException(422, "No readable text found in this PDF. Scanned/image-only PDFs need OCR support.")
        title = f"PDF: {filename}"
        document = KnowledgeDocument(company_id=company_id, title=title, source_type="pdf", content=content, enabled=True)
        db.add(document)
        db.flush()
        knowledge_service.rebuild_document_index(db, document)
        db.add(AgentKnowledge(agent_id=agent_id, document_id=document.id, enabled=True))
        db.commit()
        db.refresh(document)
        return {"status": "uploaded", "document_id": document.id, "title": document.title, "pages": len(reader.pages), "characters": len(content)}
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise
    finally:
        await file.close()
        db.close()
