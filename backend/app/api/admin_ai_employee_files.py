from io import BytesIO

import fitz
import pytesseract
from PIL import Image
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
MAX_OCR_PAGES = 80
MIN_NATIVE_TEXT_CHARS = 24


def _ocr_page(document, page_index: int) -> str:
    try:
        page = document.load_page(page_index)
        matrix = fitz.Matrix(2.0, 2.0)
        pix = page.get_pixmap(matrix=matrix, alpha=False)
        image = Image.open(BytesIO(pix.tobytes("png")))
        text = pytesseract.image_to_string(image, lang="ara+eng", config="--psm 6")
        return (text or "").strip()
    except pytesseract.TesseractNotFoundError as exc:
        raise HTTPException(503, "OCR engine is not installed on this server") from exc
    except HTTPException:
        raise
    except Exception:
        return ""


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

        page_count = len(reader.pages)
        if page_count > MAX_PDF_PAGES:
            raise HTTPException(413, f"PDF has more than {MAX_PDF_PAGES} pages")

        native_pages = {}
        ocr_indexes = []
        for index, page in enumerate(reader.pages):
            try:
                text = (page.extract_text() or "").strip()
            except Exception:
                text = ""
            if len(text) >= MIN_NATIVE_TEXT_CHARS:
                native_pages[index] = text
            else:
                ocr_indexes.append(index)

        if len(ocr_indexes) > MAX_OCR_PAGES:
            raise HTTPException(413, f"Scanned PDF requires OCR on more than {MAX_OCR_PAGES} pages; split the file into smaller documents")

        ocr_pages = {}
        if ocr_indexes:
            try:
                rendered = fitz.open(stream=raw, filetype="pdf")
            except Exception as exc:
                raise HTTPException(400, "PDF could not be rendered for OCR") from exc
            try:
                for index in ocr_indexes:
                    text = _ocr_page(rendered, index)
                    if text:
                        ocr_pages[index] = text
            finally:
                rendered.close()

        pages = []
        ocr_used = 0
        for index in range(page_count):
            text = native_pages.get(index) or ocr_pages.get(index) or ""
            if index in ocr_pages:
                ocr_used += 1
            if text:
                pages.append(f"[Page {index + 1}]\n{text}")

        content = "\n\n".join(pages).strip()
        if len(content) < 20:
            raise HTTPException(422, "No readable text could be extracted from this PDF")

        title = f"PDF: {filename}"
        existing = (
            db.query(KnowledgeDocument)
            .join(AgentKnowledge, AgentKnowledge.document_id == KnowledgeDocument.id)
            .filter(
                KnowledgeDocument.company_id == company_id,
                AgentKnowledge.agent_id == agent_id,
                KnowledgeDocument.title == title,
            )
            .first()
        )
        if existing is not None:
            raise HTTPException(409, "This PDF is already in the employee knowledge. Delete or rename the existing item first")

        document = KnowledgeDocument(company_id=company_id, title=title, source_type="pdf", content=content, enabled=True)
        db.add(document)
        db.flush()
        chunks = knowledge_service.rebuild_document_index(db, document)
        db.add(AgentKnowledge(agent_id=agent_id, document_id=document.id, enabled=True))
        db.commit()
        db.refresh(document)
        return {
            "status": "uploaded",
            "document_id": document.id,
            "title": document.title,
            "pages": page_count,
            "ocr_pages": ocr_used,
            "chunks": chunks,
            "characters": len(content),
        }
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise
    finally:
        await file.close()
        db.close()
