from datetime import date

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import require_interno_module_api
from ..models import InternoAuditoria
from ..services.interno import dt_to_iso
from ..utils import now_local

router = APIRouter(prefix="/api/interno/auditoria", tags=["Interno - Auditoria"])


@router.get("")
async def listar_auditoria(
    request: Request,
    modulo: str = Query(""),
    acao: str = Query(""),
    usuario: str = Query(""),
    data_inicio: str = Query(""),
    data_fim: str = Query(""),
    busca: str = Query(""),
    limite: int = Query(100),
    db: Session = Depends(get_db),
):
    user = require_interno_module_api(request, "auditoria")
    if isinstance(user, JSONResponse):
        return user

    query = db.query(InternoAuditoria)
    if modulo.strip():
        query = query.filter(InternoAuditoria.modulo == modulo.strip().lower())
    if acao.strip():
        query = query.filter(InternoAuditoria.acao == acao.strip().upper())
    if usuario.strip():
        term = f"%{usuario.strip().lower()}%"
        query = query.filter(func.lower(InternoAuditoria.usuario_nome).like(term) | func.lower(InternoAuditoria.usuario).like(term))
    if busca.strip():
        term = f"%{busca.strip().lower()}%"
        query = query.filter(
            func.lower(InternoAuditoria.descricao).like(term)
            | func.lower(InternoAuditoria.entidade).like(term)
            | func.lower(InternoAuditoria.usuario_nome).like(term)
        )

    if data_inicio.strip():
        try:
            query = query.filter(InternoAuditoria.criado_em >= date.fromisoformat(data_inicio.strip()))
        except Exception:
            pass
    if data_fim.strip():
        try:
            fim = date.fromisoformat(data_fim.strip())
            from datetime import timedelta
            query = query.filter(InternoAuditoria.criado_em < fim + timedelta(days=1))
        except Exception:
            pass

    limite = max(1, min(int(limite or 100), 500))
    itens = query.order_by(InternoAuditoria.criado_em.desc(), InternoAuditoria.id.desc()).limit(limite).all()

    def public(item):
        return {
            "id": item.id,
            "modulo": item.modulo,
            "entidade": item.entidade,
            "entidade_id": item.entidade_id,
            "acao": item.acao,
            "descricao": item.descricao,
            "usuario_id": item.usuario_id,
            "usuario_nome": item.usuario_nome,
            "usuario": item.usuario,
            "ip": item.ip,
            "criado_em": dt_to_iso(item.criado_em),
            "dados": item.dados or {},
        }

    return {
        "ok": True,
        "auditoria": [public(i) for i in itens],
        "resumo": {
            "total": int(db.query(func.count(InternoAuditoria.id)).scalar() or 0),
            "hoje": int(db.query(func.count(InternoAuditoria.id)).filter(func.date(InternoAuditoria.criado_em) == now_local().date()).scalar() or 0),
        },
    }
