from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import require_interno_module_api
from ..models import InternoChecklistPlantao, InternoPlantao
from ..services.auditoria import registrar_auditoria
from ..services.interno import (
    escala_do_usuario_no_dia,
    escala_publica,
    integrar_escala_fim_plantao,
    integrar_escala_inicio_plantao,
    plantao_aberto_do_usuario,
    plantao_publico,
    plantoes_do_dia,
    plantoes_resumo,
    proxima_escala_usuario,
)
from ..utils import client_ip, now_local, now_utc, parse_bool, read_json_body_safe, safe_str, today_local_iso

router = APIRouter(prefix="/api/interno", tags=["Interno - Plantão"])


CHECKLIST_INICIO = (
    ("sistemas", "Conferi os sistemas principais e estão operacionais."),
    ("ocorrencias", "Revisei as ocorrências e pendências que precisam de atenção."),
    ("passagem", "Li e assumi a passagem de turno do plantão anterior."),
)

CHECKLIST_FIM = (
    ("ocorrencias", "Registrei/revisei as ocorrências e pendências do meu turno."),
    ("passagem", "Registrei a passagem e os recados para o próximo plantonista."),
    ("sistemas", "Conferi sistemas e pendências que precisam ser entregues ao próximo turno."),
)


def _checklist_publico(checklist: InternoChecklistPlantao | None) -> dict:
    if not checklist:
        inicio = {key: False for key, _ in CHECKLIST_INICIO}
        fim = {key: False for key, _ in CHECKLIST_FIM}
        inicio_confirmado = False
        fim_confirmado = False
    else:
        inicio = {
            "sistemas": bool(checklist.inicio_sistemas),
            "ocorrencias": bool(checklist.inicio_ocorrencias),
            "passagem": bool(checklist.inicio_passagem),
        }
        fim = {
            "ocorrencias": bool(checklist.fim_ocorrencias),
            "passagem": bool(checklist.fim_passagem),
            "sistemas": bool(checklist.fim_sistemas),
        }
        inicio_confirmado = bool(checklist.inicio_confirmado_em)
        fim_confirmado = bool(checklist.fim_confirmado_em)

    return {
        "inicio": {
            "itens": [{"id": key, "label": label, "checked": bool(inicio[key])} for key, label in CHECKLIST_INICIO],
            "completo": all(inicio.values()),
            "confirmado": inicio_confirmado,
        },
        "fim": {
            "itens": [{"id": key, "label": label, "checked": bool(fim[key])} for key, label in CHECKLIST_FIM],
            "completo": all(fim.values()),
            "confirmado": fim_confirmado,
        },
    }


def _checklist_payload(payload: dict, etapa: str) -> dict:
    raw = payload.get("checklist_inicio" if etapa == "inicio" else "checklist_fim") or {}
    if not isinstance(raw, dict):
        raw = {}
    required = CHECKLIST_INICIO if etapa == "inicio" else CHECKLIST_FIM
    return {key: parse_bool(raw.get(key)) for key, _ in required}


def _checklist_incompleto(values: dict) -> list[str]:
    labels = dict(CHECKLIST_INICIO) if set(values) == {key for key, _ in CHECKLIST_INICIO} else dict(CHECKLIST_FIM)
    return [labels[key] for key, checked in values.items() if not checked]


@router.get("/plantao/status")
async def api_interno_plantao_status(request: Request, db: Session = Depends(get_db)):
    user_or_response = require_interno_module_api(request, "plantao")
    if isinstance(user_or_response, JSONResponse):
        return user_or_response

    aberto = plantao_aberto_do_usuario(db, user_or_response)
    hoje = [plantao_publico(p) for p in plantoes_do_dia(db)]
    escala_hoje = escala_do_usuario_no_dia(db, user_or_response)
    proxima_escala = proxima_escala_usuario(db, user_or_response)
    checklist = None
    if aberto:
        checklist = db.query(InternoChecklistPlantao).filter(InternoChecklistPlantao.plantao_id == aberto.id).first()
    return {
        "ok": True,
        "user": user_or_response,
        "plantao_aberto": plantao_publico(aberto),
        "plantoes_hoje": hoje,
        "resumo": plantoes_resumo(db),
        "escala_hoje": escala_publica(escala_hoje),
        "proxima_escala": escala_publica(proxima_escala),
        "checklist": _checklist_publico(checklist),
    }


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

    checklist_inicio = _checklist_payload(payload, "inicio")
    if not all(checklist_inicio.values()):
        return JSONResponse(
            status_code=400,
            content={
                "ok": False,
                "detail": "Conclua todos os itens do checklist de início antes de assumir o plantão.",
                "checklist_pendente": _checklist_incompleto(checklist_inicio),
            },
        )

    aberto = plantao_aberto_do_usuario(db, user_or_response)
    if aberto:
        return JSONResponse(
            status_code=409,
            content={"ok": False, "detail": "Você já possui um plantão em andamento. Finalize antes de iniciar outro.", "plantao_aberto": plantao_publico(aberto)},
        )

    now = now_utc()
    plantao = InternoPlantao(
        status="aberto",
        data_plantao=now_local().date(),
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
    db.flush()

    checklist = InternoChecklistPlantao(
        plantao_id=plantao.id,
        inicio_sistemas=checklist_inicio["sistemas"],
        inicio_ocorrencias=checklist_inicio["ocorrencias"],
        inicio_passagem=checklist_inicio["passagem"],
        inicio_confirmado_em=now,
        ip_inicio=client_ip(request),
        fim_ocorrencias=False,
        fim_passagem=False,
        fim_sistemas=False,
        fim_confirmado_em=None,
        ip_fim="",
    )
    db.add(checklist)
    registrar_auditoria(db, user_or_response, request, modulo="plantao", entidade="plantao", entidade_id=plantao.id, acao="CRIAR", descricao=f"Iniciou o plantão de {plantao.funcionario_nome} com checklist de entrada confirmado.")
    db.commit()
    db.refresh(plantao)
    escala = integrar_escala_inicio_plantao(db, user_or_response, plantao)
    if escala:
        db.commit()
        db.refresh(escala)
    return JSONResponse(status_code=201, content={"ok": True, "plantao": plantao_publico(plantao), "escala": escala_publica(escala), "checklist": _checklist_publico(checklist)})


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

    checklist_fim = _checklist_payload(payload, "fim")
    if not all(checklist_fim.values()):
        return JSONResponse(
            status_code=400,
            content={
                "ok": False,
                "detail": "Conclua todos os itens do checklist de encerramento antes de finalizar o plantão.",
                "checklist_pendente": _checklist_incompleto(checklist_fim),
            },
        )

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

    checklist = db.query(InternoChecklistPlantao).filter(InternoChecklistPlantao.plantao_id == plantao.id).first()
    if checklist is None:
        checklist = InternoChecklistPlantao(plantao_id=plantao.id)
        db.add(checklist)

    checklist.fim_ocorrencias = checklist_fim["ocorrencias"]
    checklist.fim_passagem = checklist_fim["passagem"]
    checklist.fim_sistemas = checklist_fim["sistemas"]
    checklist.fim_confirmado_em = now
    checklist.ip_fim = client_ip(request)

    escala = integrar_escala_fim_plantao(db, user_or_response, plantao)
    registrar_auditoria(db, user_or_response, request, modulo="plantao", entidade="plantao", entidade_id=plantao.id, acao="ENCERRAR", descricao=f"Encerrou o plantão de {plantao.funcionario_nome} com checklist de saída confirmado.")
    db.commit()
    db.refresh(plantao)
    return {"ok": True, "plantao": plantao_publico(plantao), "escala": escala_publica(escala), "checklist": _checklist_publico(checklist)}
