from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import require_interno_module_api
from ..models import InternoPlantao
from ..services.interno import plantao_aberto_do_usuario, plantao_publico, plantoes_do_dia, plantoes_resumo
from ..utils import client_ip, now_utc, parse_bool, read_json_body_safe, safe_str, today_local_iso

router = APIRouter(prefix="/api/interno", tags=["Interno - Plantão"])


@router.get("/plantao/status")
async def api_interno_plantao_status(request: Request, db: Session = Depends(get_db)):
    user_or_response = require_interno_module_api(request, "plantao")
    if isinstance(user_or_response, JSONResponse):
        return user_or_response

    aberto = plantao_aberto_do_usuario(db, user_or_response)
    hoje = [plantao_publico(p) for p in plantoes_do_dia(db)]
    return {"ok": True, "user": user_or_response, "plantao_aberto": plantao_publico(aberto), "plantoes_hoje": hoje, "resumo": plantoes_resumo(db)}


@router.get("/plantoes")
async def api_interno_listar_plantoes(request: Request, data: str = Query(""), limite: int = Query(50), db: Session = Depends(get_db)):
    user_or_response = require_interno_module_api(request, "plantao")
    if isinstance(user_or_response, JSONResponse):
        return user_or_response

    dia = safe_str(data) or today_local_iso()
    limite_safe = max(1, min(int(limite or 50), 200))
    itens = [plantao_publico(p) for p in plantoes_do_dia(db, dia, limite_safe)]
    return {"ok": True, "data": dia, "plantoes": itens, "resumo": plantoes_resumo(db)}


@router.post("/plantao/iniciar")
async def api_interno_iniciar_plantao(request: Request, db: Session = Depends(get_db)):
    user_or_response = require_interno_module_api(request, "plantao")
    if isinstance(user_or_response, JSONResponse):
        return user_or_response

    try:
        payload = await request.json()
    except Exception:
        payload = {}
    payload = read_json_body_safe(payload)

    if not parse_bool(payload.get("confirmacao")):
        return JSONResponse(status_code=400, content={"ok": False, "detail": "Confirme que você está assumindo o plantão."})

    aberto = plantao_aberto_do_usuario(db, user_or_response)
    if aberto:
        return JSONResponse(
            status_code=409,
            content={"ok": False, "detail": "Você já possui um plantão em andamento. Finalize antes de iniciar outro.", "plantao_aberto": plantao_publico(aberto)},
        )

    now = now_utc()
    plantao = InternoPlantao(
        status="aberto",
        data_plantao=now.date(),
        funcionario_id=user_or_response.get("funcionario_id"),
        funcionario_nome=user_or_response.get("nome") or user_or_response.get("username"),
        usuario=user_or_response.get("username") or "",
        tipo=user_or_response.get("tipo") or "",
        permissao=user_or_response.get("permissao") or "",
        iniciado_em=now,
        finalizado_em=None,
        observacao_inicio=safe_str(payload.get("observacao")),
        observacao_fim="",
        confirmacao_inicio=True,
        confirmacao_fim=False,
        ip_inicio=client_ip(request),
        ip_fim="",
        duracao_segundos=0,
        criado_em=now,
        atualizado_em=now,
    )
    db.add(plantao)
    db.commit()
    db.refresh(plantao)
    return JSONResponse(status_code=201, content={"ok": True, "plantao": plantao_publico(plantao)})


@router.post("/plantao/finalizar")
async def api_interno_finalizar_plantao(request: Request, db: Session = Depends(get_db)):
    user_or_response = require_interno_module_api(request, "plantao")
    if isinstance(user_or_response, JSONResponse):
        return user_or_response

    try:
        payload = await request.json()
    except Exception:
        payload = {}
    payload = read_json_body_safe(payload)

    if not parse_bool(payload.get("confirmacao")):
        return JSONResponse(status_code=400, content={"ok": False, "detail": "Confirme que você está finalizando o plantão."})

    plantao = plantao_aberto_do_usuario(db, user_or_response)
    if not plantao:
        return JSONResponse(status_code=404, content={"ok": False, "detail": "Você não possui plantão em andamento."})

    now = now_utc()
    plantao.status = "finalizado"
    plantao.finalizado_em = now
    plantao.observacao_fim = safe_str(payload.get("observacao"))
    plantao.confirmacao_fim = True
    plantao.ip_fim = client_ip(request)
    plantao.duracao_segundos = max(int((now - plantao.iniciado_em).total_seconds()), 0) if plantao.iniciado_em else 0
    plantao.atualizado_em = now
    plantao.finalizado_por = user_or_response.get("username") or ""
    db.commit()
    db.refresh(plantao)
    return {"ok": True, "plantao": plantao_publico(plantao)}
