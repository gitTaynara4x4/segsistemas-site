from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import require_interno_module_api
from ..models import InternoPassagem
from ..services.interno import (
    passagem_publica,
    passagens_do_dia,
    passagens_resumo,
    ultima_passagem_pendente,
    validar_payload_passagem,
)
from ..utils import client_ip, now_utc, parse_bool, read_json_body_safe, safe_str, today_local_iso

router = APIRouter(prefix="/api/interno", tags=["Interno - Passagem"])


@router.get("/passagens/status")
async def api_interno_passagens_status(request: Request, db: Session = Depends(get_db)):
    user_or_response = require_interno_module_api(request, "passagem")
    if isinstance(user_or_response, JSONResponse):
        return user_or_response

    hoje = [passagem_publica(p) for p in passagens_do_dia(db)]
    ultima_pendente = ultima_passagem_pendente(db)
    return {"ok": True, "user": user_or_response, "passagens_hoje": hoje, "ultima_pendente": passagem_publica(ultima_pendente), "resumo": passagens_resumo(db)}


@router.get("/passagens")
async def api_interno_listar_passagens(request: Request, data: str = Query(""), limite: int = Query(50), db: Session = Depends(get_db)):
    user_or_response = require_interno_module_api(request, "passagem")
    if isinstance(user_or_response, JSONResponse):
        return user_or_response

    dia = safe_str(data) or today_local_iso()
    limite_safe = max(1, min(int(limite or 50), 200))
    itens = [passagem_publica(p) for p in passagens_do_dia(db, dia, limite_safe)]
    return {"ok": True, "data": dia, "passagens": itens, "resumo": passagens_resumo(db)}


@router.post("/passagens")
async def api_interno_criar_passagem(request: Request, db: Session = Depends(get_db)):
    user_or_response = require_interno_module_api(request, "passagem")
    if isinstance(user_or_response, JSONResponse):
        return user_or_response

    try:
        payload = await request.json()
    except Exception:
        payload = {}
    payload = read_json_body_safe(payload)

    dados, erro = validar_payload_passagem(payload)
    if erro:
        return JSONResponse(status_code=400, content={"ok": False, "detail": erro})

    now = now_utc()
    passagem = InternoPassagem(
        status="pendente",
        data_plantao=now.date(),
        passado_por_id=user_or_response.get("funcionario_id"),
        passado_por_nome=user_or_response.get("nome") or user_or_response.get("username"),
        passado_por_usuario=user_or_response.get("username") or "",
        passado_em=now,
        recebido_por_id=None,
        recebido_por_nome="",
        recebido_por_usuario="",
        recebido_em=None,
        pendencias=dados["pendencias"],
        clientes_observacao=dados["clientes_observacao"],
        falhas_sistema=dados["falhas_sistema"],
        ocorrencias_importantes=dados["ocorrencias_importantes"],
        recado_proximo=dados["recado_proximo"],
        confirmacao_passagem=True,
        confirmacao_recebimento=False,
        ip_passagem=client_ip(request),
        ip_recebimento="",
        criado_em=now,
        atualizado_em=now,
    )
    db.add(passagem)
    db.commit()
    db.refresh(passagem)
    return JSONResponse(status_code=201, content={"ok": True, "passagem": passagem_publica(passagem)})


@router.post("/passagens/{passagem_id}/assumir")
async def api_interno_assumir_passagem(passagem_id: int, request: Request, db: Session = Depends(get_db)):
    user_or_response = require_interno_module_api(request, "passagem")
    if isinstance(user_or_response, JSONResponse):
        return user_or_response

    try:
        payload = await request.json()
    except Exception:
        payload = {}
    payload = read_json_body_safe(payload)

    if not parse_bool(payload.get("confirmacao")):
        return JSONResponse(status_code=400, content={"ok": False, "detail": "Confirme que você leu e está assumindo a passagem."})

    passagem = db.query(InternoPassagem).filter(InternoPassagem.id == passagem_id).first()
    if not passagem:
        return JSONResponse(status_code=404, content={"ok": False, "detail": "Passagem não encontrada."})

    if passagem.status == "recebida":
        return JSONResponse(status_code=409, content={"ok": False, "detail": "Esta passagem já foi recebida."})

    now = now_utc()
    passagem.status = "recebida"
    passagem.recebido_por_id = user_or_response.get("funcionario_id")
    passagem.recebido_por_nome = user_or_response.get("nome") or user_or_response.get("username")
    passagem.recebido_por_usuario = user_or_response.get("username") or ""
    passagem.recebido_em = now
    passagem.confirmacao_recebimento = True
    passagem.ip_recebimento = client_ip(request)
    passagem.atualizado_em = now
    db.commit()
    db.refresh(passagem)
    return {"ok": True, "passagem": passagem_publica(passagem)}
