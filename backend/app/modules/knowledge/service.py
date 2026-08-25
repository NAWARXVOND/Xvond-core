import re
from dataclasses import dataclass

from backend.app.modules.knowledge.models import AgentKnowledge, KnowledgeChunk, KnowledgeDocument

@dataclass
class KnowledgeMatch:
    document_id:int; title:str; chunk_index:int; content:str; score:float

class KnowledgeService:
    DEFAULT_CHUNK_SIZE=1400; DEFAULT_OVERLAP=180; DEFAULT_MAX_CHUNKS=6; DEFAULT_MAX_CONTEXT_CHARS=7000
    ARABIC_EQUIVALENTS={
        "اسعار":{"السعر","سعر","الاسعار","أسعار","الأسعار","بكم","تكلفة","تكلفه"},
        "خدمات":{"خدمة","الخدمات","خدمات","بتعملو","تقدمون"},
        "حجز":{"موعد","مواعيد","احجز","الحجز","حجز"},
        "دوام":{"ساعات","الدوام","دوام","مفتوح","تفتحون","تسكرون"},
        "موقع":{"العنوان","عنوان","وين","الموقع","موقع"},
    }
    def normalize(self,text):
        text=(text or "").lower().replace("\r"," ").replace("\n"," ")
        text=text.replace("أ","ا").replace("إ","ا").replace("آ","ا").replace("ة","ه").replace("ى","ي")
        text=re.sub(r"[^\w\u0600-\u06FF]+"," ",text)
        return " ".join(text.split())
    def tokenize(self,text):
        tokens={x for x in self.normalize(text).split() if len(x)>=2}; expanded=set(tokens)
        for canonical,variants in self.ARABIC_EQUIVALENTS.items():
            normalized_variants={self.normalize(x) for x in variants}|{self.normalize(canonical)}
            if tokens & normalized_variants: expanded|=normalized_variants
        return expanded
    def split_content(self,content,chunk_size=None,overlap=None):
        chunk_size=chunk_size or self.DEFAULT_CHUNK_SIZE; overlap=self.DEFAULT_OVERLAP if overlap is None else overlap; content=(content or "").strip()
        if not content:return []
        if len(content)<=chunk_size:return [content]
        chunks=[]; start=0
        while start<len(content):
            end=min(len(content),start+chunk_size); piece=content[start:end].strip()
            if piece:chunks.append(piece)
            if end>=len(content):break
            start=max(start+1,end-overlap)
        return chunks
    def rebuild_document_index(self,db,document):
        db.query(KnowledgeChunk).filter(KnowledgeChunk.document_id==document.id).delete(synchronize_session=False)
        chunks=self.split_content(document.content or "")
        for index,content in enumerate(chunks): db.add(KnowledgeChunk(company_id=document.company_id,document_id=document.id,chunk_index=index,content=content,normalized_text=self.normalize(content)))
        db.flush(); return len(chunks)
    def backfill_company_index(self,db,company_id):
        docs=db.query(KnowledgeDocument).filter(KnowledgeDocument.company_id==company_id).all(); indexed=0
        for doc in docs:
            if db.query(KnowledgeChunk).filter(KnowledgeChunk.document_id==doc.id).first() is None:self.rebuild_document_index(db,doc);indexed+=1
        return indexed
    def search_agent_knowledge(self,db,company_id,agent_id,query,max_chunks=None):
        max_chunks=max_chunks or self.DEFAULT_MAX_CHUNKS; qnorm=self.normalize(query); qtokens=self.tokenize(query)
        if not qtokens:return []
        rows=db.query(KnowledgeChunk,KnowledgeDocument).join(KnowledgeDocument,KnowledgeDocument.id==KnowledgeChunk.document_id).join(AgentKnowledge,AgentKnowledge.document_id==KnowledgeDocument.id).filter(KnowledgeChunk.company_id==company_id,KnowledgeDocument.company_id==company_id,KnowledgeDocument.enabled.is_(True),AgentKnowledge.agent_id==agent_id,AgentKnowledge.enabled.is_(True)).all()
        matches=[]
        for chunk,doc in rows:
            ctokens=self.tokenize(chunk.normalized_text); ttokens=self.tokenize(doc.title or ""); common=qtokens&ctokens; title_common=qtokens&ttokens
            # Business Information is intentionally broad structured knowledge. A business-fact question
            # may use it even when colloquial Arabic wording does not literally occur in the stored text.
            broad_business_doc=self.normalize(doc.title)==self.normalize("Business Information")
            exact=bool(qnorm and qnorm in self.normalize(chunk.normalized_text))
            if not common and not title_common and not broad_business_doc:continue
            coverage=len(common)/max(1,len(qtokens)); score=len(common)*3+len(title_common)*5+coverage*6+(12 if exact else 0)+(1 if broad_business_doc else 0)
            if exact or len(common)>=1 or len(title_common)>=1 or broad_business_doc: matches.append(KnowledgeMatch(doc.id,doc.title,chunk.chunk_index,chunk.content,score))
        matches.sort(key=lambda x:(x.score,-x.chunk_index),reverse=True); selected=[]; per={}
        for m in matches:
            if per.get(m.document_id,0)>=3:continue
            selected.append(m);per[m.document_id]=per.get(m.document_id,0)+1
            if len(selected)>=max_chunks:break
        return selected
    def get_agent_context(self,db,company_id,agent_id,query):
        self.backfill_company_index(db,company_id); matches=self.search_agent_knowledge(db,company_id,agent_id,query)
        if not matches:return ""
        parts=[];used=0
        for m in matches:
            block=f"[Knowledge: {m.title} | chunk {m.chunk_index+1}]\n{m.content}"
            if used+len(block)>self.DEFAULT_MAX_CONTEXT_CHARS:
                remain=self.DEFAULT_MAX_CONTEXT_CHARS-used
                if remain>250:parts.append(block[:remain])
                break
            parts.append(block);used+=len(block)
        return "\n\n".join(parts)

knowledge_service=KnowledgeService()
