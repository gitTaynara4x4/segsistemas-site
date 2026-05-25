from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import require_interno_module_api
from ..models import InternoPonto, InternoPontoPausa
from ..services.interno import (
    ponto_aberto_do_usuario,
    ponto_duracoes,
    ponto_publico,
    pontos_do_dia,
    pontos_resumo,
    ultima_pausa_aberta,
)
from ..utils import client_ip, now_utc, parse_bool, read_json_body_safe, safe_lower, safe_str, today_local_iso

router = APIRouter(prefix="/api/interno", tags=["Interno - Ponto"])


@router.get("/ponto/status")
async def api_interno_ponto_status(request: Request, db: Session = Depends(get_db)):
    user_or_response = require_interno_module_api(request, "ponto")
    if isinstance(user_or_response, JSONResponse):
        return user_or_response

    aberto = ponto_aberto_do_usuario(db, user_or_response)
    hoje = [ponto_publico(p) for p in pontos_do_dia(db)]
    return {"ok": True, "user": user_or_response, "ponto_aberto": ponto_publico(aberto), "pontos_hoje": hoje, "resumo": pontos_resumo(db)}


@router.get("/pontos")
async def api_interno_listar_pontos(request: Request, data: str = Query(""), limite: int = Query(80), db: Session = Depends(get_db)):
    user_or_response = require_interno_module_api(request, "ponto")
    if isinstance(user_or_response, JSONResponse):
        return user_or_response

    dia = safe_str(data) or today_local_iso()
    limite_safe = max(1, min(int(limite or 80), 300))
    itens = [ponto_publico(p) for p in pontos_do_dia(db, dia, limite_safe)]
    return {"ok": True, "data": dia, "pontos": itens, "resumo": pontos_resumo(db)}


@router.post("/ponto/entrada")
async def api_interno_ponto_entrada(request: Request, db: Session = Depends(get_db)):
    user_or_response = require_interno_module_api(request, "ponto")
    if isinstance(user_or_response, JSONResponse):
        return user_or_response

    try:
        payload = await request.json()
    except Exception:
        payload = {}
    payload = read_json_body_safe(payload)

    if not parse_bool(payload.get("confirmacao")):
        return JSONResponse(status_code=400, content={"ok": False, "detail": "Confirme que você está batendo entrada."})

    aberto = ponto_aberto_do_usuario(db, user_or_response)
    if aberto:
        return JSONResponse(
            status_code=409,
            content={"ok": False, "detail": "Você já possui um ponto em andamento. Finalize antes de bater nova entrada.", "ponto_aberto": ponto_publico(aberto)},
        )

    now = now_utc()
    ponto = InternoPonto(
        status="aberto",
        data_ponto=now.date(),
        funcionario_id=user_or_response.get("funcionario_id"),
        funcionario_nome=user_or_response.get("nome") or user_or_response.get("username"),
        usuario=user_or_response.get("username") or "",
        tipo=user_or_response.get("tipo") or "",
        permissao=user_or_response.get("permissao") or "",
        entrada_em=now,
        saida_em=None,
        observacao_entrada=safe_str(payload.get("observacao")),
        observacao_saida="",
        ip_entrada=client_ip(request),
        ip_saida="",
        duracao_total_segundos=0,
        duracao_pausas_segundos=0,
        duracao_liquida_segundos=0,
        criado_em=now,
        atualizado_em=now,
        atualizado_por=user_or_response.get("username") or "",
    )
    db.add(ponto)
    db.commit()
    db.refresh(ponto)
    return JSONResponse(status_code=201, content={"ok": True, "ponto": ponto_publico(ponto)})


@router.post("/ponto/pausa/iniciar")
async def api_interno_ponto_iniciar_pausa(request: Request, db: Session = Depends(get_db)):
    user_or_response = require_interno_module_api(request, "ponto")
    if isinstance(user_or_response, JSONResponse):
        return user_or_response

    try:
        payload = await request.json()
    except Exception:
        payload = {}
    payload = read_json_body_safe(payload)

    ponto = ponto_aberto_do_usuario(db, user_or_response)
    if not ponto:
        return JSONResponse(status_code=404, content={"ok": False, "detail": "Você não possui ponto em andamento."})
    if safe_lower(ponto.status, "aberto") == "pausado":
        return JSONResponse(status_code=409, content={"ok": False, "detail": "Você já está em pausa."})

    now = now_utc()
    pausa = InternoPontoPausa(
        ponto_id=ponto.id,
        inicio_em=now,
        fim_em=None,
        duracao_segundos=0,
        observacao_inicio=safe_str(payload.get("observacao")),
        observacao_fim="",
        ip_inicio=client_ip(request),
        ip_fim="",
    )
    db.add(pausa)
    ponto.status = "pausado"
    ponto.atualizado_em = now
    ponto.atualizado_por = user_or_response.get("username") or ""
    db.commit()
    db.refresh(ponto)
    return {"ok": True, "ponto": ponto_publico(ponto)}


@router.post("/ponto/pausa/finalizar")
async def api_interno_ponto_finalizar_pausa(request: Request, db: Session = Depends(get_db)):
    user_or_response = require_interno_module_api(request, "ponto")
    if isinstance(user_or_response, JSONResponse):
        return user_or_response

    try:
        payload = await request.json()
    except Exception:
        payload = {}
    payload = read_json_body_safe(payload)

    ponto = ponto_aberto_do_usuario(db, user_or_response)
    if not ponto:
        return JSONResponse(status_code=404, content={"ok": False, "detail": "Você não possui ponto em andamento."})
    if safe_lower(ponto.status, "aberto") != "pausado":
        return JSONResponse(status_code=409, content={"ok": False, "detail": "Você não está em pausa."})

    pausa = ultima_pausa_aberta(ponto)
    if not pausa:
        return JSONResponse(status_code=409, content={"ok": False, "detail": "Não existe pausa aberta para finalizar."})

    now = now_utc()
    pausa.fim_em = now
    pausa.duracao_segundos = max(int((now - pausa.inicio_em).total_seconds()), 0) if pausa.inicio_em else 0
    pausa.observacao_fim = safe_str(payload.get("observacao"))
    pausa.ip_fim = client_ip(request)
    ponto.status = "aberto"
    ponto.atualizado_em = now
    ponto.atualizado_por = user_or_response.get("username") or ""
    db.commit()
    db.refresh(ponto)
    return {"ok": True, "ponto": ponto_publico(ponto)}


@router.post("/ponto/saida")
async def api_interno_ponto_saida(request: Request, db: Session = Depends(get_db)):
    user_or_response = require_interno_module_api(request, "ponto")
    if isinstance(user_or_response, JSONResponse):
        return user_or_response

    try:
        payload = await request.json()
    except Exception:
        payload = {}
    payload = read_json_body_safe(payload)

    if not parse_bool(payload.get("confirmacao")):
        return JSONResponse(status_code=400, content={"ok": False, "detail": "Confirme que você está batendo saída."})

    ponto = ponto_aberto_do_usuario(db, user_or_response)
    if not ponto:
        return JSONResponse(status_code=404, content={"ok": False, "detail": "Você não possui ponto em andamento."})

    now = now_utc()
    if safe_lower(ponto.status, "aberto") == "pausado":
        pausa = ultima_pausa_aberta(ponto)
        if pausa:
            pausa.fim_em = now
            pausa.duracao_segundos = max(int((now - pausa.inicio_em).total_seconds()), 0) if pausa.inicio_em else 0
            pausa.observacao_fim = "Pausa encerrada automaticamente na saída."
            pausa.ip_fim = client_ip(request)

    ponto.status = "finalizado"
    ponto.saida_em = now
    ponto.observacao_saida = safe_str(payload.get("observacao"))
    ponto.ip_saida = client_ip(request)
    ponto.atualizado_em = now
    ponto.atualizado_por = user_or_response.get("username") or ""

    duracoes = ponto_duracoes(ponto)
    ponto.duracao_total_segundos = duracoes["duracao_total_segundos"]
    ponto.duracao_pausas_segundos = duracoes["duracao_pausas_segundos"]
    ponto.duracao_liquida_segundos = duracoes["duracao_liquida_segundos"]

    db.commit()
    db.refresh(ponto)
    return {"ok": True, "ponto": ponto_publico(ponto)}
