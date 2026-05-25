from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from ..config import OCORRENCIA_PRIORIDADES, OCORRENCIA_STATUS, OCORRENCIA_TIPOS
from ..database import get_db
from ..deps import require_interno_module_api
from ..models import InternoOcorrencia
from ..services.interno import (
    ocorrencia_publica,
    ocorrencias_abertas,
    ocorrencias_do_dia,
    ocorrencias_resumo,
    validar_payload_ocorrencia,
)
from ..utils import client_ip, now_utc, read_json_body_safe, safe_lower, safe_str

router = APIRouter(prefix="/api/interno/ocorrencias", tags=["Interno - Ocorrências"])


@router.get("/status")
async def api_interno_ocorrencias_status(request: Request, db: Session = Depends(get_db)):
    user_or_response = require_interno_module_api(request, "ocorrencias")
    if isinstance(user_or_response, JSONResponse):
        return user_or_response

    hoje = [ocorrencia_publica(o) for o in ocorrencias_do_dia(db)]
    abertas = [ocorrencia_publica(o) for o in ocorrencias_abertas(db)]
    return {
        "ok": True,
        "user": user_or_response,
        "ocorrencias_hoje": hoje,
        "ocorrencias_abertas": abertas,
        "resumo": ocorrencias_resumo(db),
        "tipos": OCORRENCIA_TIPOS,
        "prioridades": OCORRENCIA_PRIORIDADES,
        "status": OCORRENCIA_STATUS,
    }


@router.get("")
async def api_interno_listar_ocorrencias(
    request: Request,
    data: str = Query(""),
    status: str = Query(""),
    tipo: str = Query(""),
    prioridade: str = Query(""),
    limite: int = Query(80),
    db: Session = Depends(get_db),
):
    user_or_response = require_interno_module_api(request, "ocorrencias")
    if isinstance(user_or_response, JSONResponse):
        return user_or_response

    limite_safe = max(1, min(int(limite or 80), 300))
    query = db.query(InternoOcorrencia)

    data_limpa = safe_str(data)
    status_limpo = safe_lower(status)
    tipo_limpo = safe_lower(tipo)
    prioridade_limpa = safe_lower(prioridade)

    if data_limpa:
        from datetime import date
        try:
            query = query.filter(InternoOcorrencia.data_ocorrencia == date.fromisoformat(data_limpa))
        except Exception:
            pass
    if status_limpo:
        query = query.filter(InternoOcorrencia.status == status_limpo)
    if tipo_limpo:
        query = query.filter(InternoOcorrencia.tipo == tipo_limpo)
    if prioridade_limpa:
        query = query.filter(InternoOcorrencia.prioridade == prioridade_limpa)

    itens = query.order_by(InternoOcorrencia.id.desc()).limit(limite_safe).all()
    return {
        "ok": True,
        "ocorrencias": [ocorrencia_publica(o) for o in itens],
        "resumo": ocorrencias_resumo(db),
        "tipos": OCORRENCIA_TIPOS,
        "prioridades": OCORRENCIA_PRIORIDADES,
        "status": OCORRENCIA_STATUS,
    }


@router.post("")
async def api_interno_criar_ocorrencia(request: Request, db: Session = Depends(get_db)):
    user_or_response = require_interno_module_api(request, "ocorrencias")
    if isinstance(user_or_response, JSONResponse):
        return user_or_response

    try:
        payload = await request.json()
    except Exception:
        payload = {}
    payload = read_json_body_safe(payload)

    dados, erro = validar_payload_ocorrencia(payload, editando=False)
    if erro:
        return JSONResponse(status_code=400, content={"ok": False, "detail": erro})

    now = now_utc()
    ocorrencia = InternoOcorrencia(
        status=dados["status"] if dados["status"] in {"aberta", "em_andamento"} else "aberta",
        tipo=dados["tipo"],
        prioridade=dados["prioridade"],
        data_ocorrencia=now.date(),
        titulo=dados["titulo"],
        cliente_nome=dados["cliente_nome"],
        local=dados["local"],
        descricao=dados["descricao"],
        providencia=dados["providencia"],
        responsavel=dados["responsavel"],
        criado_por_id=user_or_response.get("funcionario_id"),
        criado_por_nome=user_or_response.get("nome") or user_or_response.get("username"),
        criado_por_usuario=user_or_response.get("username") or "",
        criado_em=now,
        atualizado_em=now,
        atualizado_por=user_or_response.get("username") or "",
        resolvido_por_id=None,
        resolvido_por_nome="",
        resolvido_por_usuario="",
        resolvido_em=None,
        solucao="",
        ip_criacao=client_ip(request),
        ip_atualizacao="",
    )
    db.add(ocorrencia)
    db.commit()
    db.refresh(ocorrencia)
    return JSONResponse(status_code=201, content={"ok": True, "ocorrencia": ocorrencia_publica(ocorrencia)})


@router.put("/{ocorrencia_id}")
async def api_interno_atualizar_ocorrencia(ocorrencia_id: int, request: Request, db: Session = Depends(get_db)):
    user_or_response = require_interno_module_api(request, "ocorrencias")
    if isinstance(user_or_response, JSONResponse):
        return user_or_response

    try:
        payload = await request.json()
    except Exception:
        payload = {}
    payload = read_json_body_safe(payload)

    dados, erro = validar_payload_ocorrencia(payload, editando=True)
    if erro:
        return JSONResponse(status_code=400, content={"ok": False, "detail": erro})

    ocorrencia = db.query(InternoOcorrencia).filter(InternoOcorrencia.id == ocorrencia_id).first()
    if not ocorrencia:
        return JSONResponse(status_code=404, content={"ok": False, "detail": "Ocorrência não encontrada."})

    now = now_utc()
    ocorrencia.titulo = dados["titulo"]
    ocorrencia.cliente_nome = dados["cliente_nome"]
    ocorrencia.local = dados["local"]
    ocorrencia.descricao = dados["descricao"]
    ocorrencia.providencia = dados["providencia"]
    ocorrencia.responsavel = dados["responsavel"]
    ocorrencia.tipo = dados["tipo"]
    ocorrencia.prioridade = dados["prioridade"]
    ocorrencia.status = dados["status"]
    ocorrencia.atualizado_em = now
    ocorrencia.atualizado_por = user_or_response.get("username") or ""
    ocorrencia.ip_atualizacao = client_ip(request)

    if dados["status"] == "resolvida" and not ocorrencia.resolvido_em:
        ocorrencia.resolvido_por_id = user_or_response.get("funcionario_id")
        ocorrencia.resolvido_por_nome = user_or_response.get("nome") or user_or_response.get("username")
        ocorrencia.resolvido_por_usuario = user_or_response.get("username") or ""
        ocorrencia.resolvido_em = now
        ocorrencia.solucao = safe_str(payload.get("solucao")) or ocorrencia.providencia or ""

    if dados["status"] in {"aberta", "em_andamento"}:
        ocorrencia.resolvido_por_id = None
        ocorrencia.resolvido_por_nome = ""
        ocorrencia.resolvido_por_usuario = ""
        ocorrencia.resolvido_em = None
        ocorrencia.solucao = ""

    db.commit()
    db.refresh(ocorrencia)
    return {"ok": True, "ocorrencia": ocorrencia_publica(ocorrencia)}


@router.post("/{ocorrencia_id}/resolver")
async def api_interno_resolver_ocorrencia(ocorrencia_id: int, request: Request, db: Session = Depends(get_db)):
    user_or_response = require_interno_module_api(request, "ocorrencias")
    if isinstance(user_or_response, JSONResponse):
        return user_or_response

    try:
        payload = await request.json()
    except Exception:
        payload = {}
    payload = read_json_body_safe(payload)

    solucao = safe_str(payload.get("solucao"))
    if not solucao:
        return JSONResponse(status_code=400, content={"ok": False, "detail": "Informe a solução da ocorrência."})

    ocorrencia = db.query(InternoOcorrencia).filter(InternoOcorrencia.id == ocorrencia_id).first()
    if not ocorrencia:
        return JSONResponse(status_code=404, content={"ok": False, "detail": "Ocorrência não encontrada."})

    now = now_utc()
    ocorrencia.status = "resolvida"
    ocorrencia.solucao = solucao
    ocorrencia.resolvido_por_id = user_or_response.get("funcionario_id")
    ocorrencia.resolvido_por_nome = user_or_response.get("nome") or user_or_response.get("username")
    ocorrencia.resolvido_por_usuario = user_or_response.get("username") or ""
    ocorrencia.resolvido_em = now
    ocorrencia.atualizado_em = now
    ocorrencia.atualizado_por = user_or_response.get("username") or ""
    ocorrencia.ip_atualizacao = client_ip(request)
    db.commit()
    db.refresh(ocorrencia)
    return {"ok": True, "ocorrencia": ocorrencia_publica(ocorrencia)}


@router.post("/{ocorrencia_id}/reabrir")
async def api_interno_reabrir_ocorrencia(ocorrencia_id: int, request: Request, db: Session = Depends(get_db)):
    user_or_response = require_interno_module_api(request, "ocorrencias")
    if isinstance(user_or_response, JSONResponse):
        return user_or_response

    ocorrencia = db.query(InternoOcorrencia).filter(InternoOcorrencia.id == ocorrencia_id).first()
    if not ocorrencia:
        return JSONResponse(status_code=404, content={"ok": False, "detail": "Ocorrência não encontrada."})

    now = now_utc()
    ocorrencia.status = "aberta"
    ocorrencia.resolvido_por_id = None
    ocorrencia.resolvido_por_nome = ""
    ocorrencia.resolvido_por_usuario = ""
    ocorrencia.resolvido_em = None
    ocorrencia.solucao = ""
    ocorrencia.atualizado_em = now
    ocorrencia.atualizado_por = user_or_response.get("username") or ""
    ocorrencia.ip_atualizacao = client_ip(request)
    db.commit()
    db.refresh(ocorrencia)
    return {"ok": True, "ocorrencia": ocorrencia_publica(ocorrencia)}
