from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import require_interno_module_api, user_is_admin
from ..models import InternoEscala, InternoFuncionario
from ..services.interno import escala_publica, escala_resumo, escalas_periodo
from ..services.auditoria import registrar_auditoria
from ..utils import now_utc, safe_str, today_local_iso

router = APIRouter(prefix="/api/interno/escala", tags=["Interno - Escala"])

STATUS_VALIDOS = {"agendado", "em_andamento", "concluido", "folga", "cancelado"}


def _can_manage(user: dict) -> bool:
    permissao = str(user.get("permissao") or "").strip().lower()
    return user_is_admin(user) or permissao == "supervisor"


def _parse_date(value, default=None):
    raw = safe_str(value)
    if not raw:
        return default
    try:
        return date.fromisoformat(raw)
    except Exception:
        return None


def _valid_time(value: str) -> bool:
    raw = safe_str(value)
    if len(raw) != 5 or raw[2] != ":":
        return False
    try:
        hh = int(raw[:2])
        mm = int(raw[3:])
        return 0 <= hh <= 23 and 0 <= mm <= 59
    except Exception:
        return False


def _funcionario(db: Session, funcionario_id) -> InternoFuncionario | None:
    try:
        fid = int(funcionario_id)
    except Exception:
        return None
    return db.query(InternoFuncionario).filter(InternoFuncionario.id == fid, InternoFuncionario.ativo.is_(True)).first()


def _read_payload(payload: dict, db: Session):
    dia = _parse_date(payload.get("data_escala"))
    funcionario = _funcionario(db, payload.get("funcionario_id"))
    status = safe_str(payload.get("status"), "agendado").lower()
    inicio = safe_str(payload.get("horario_inicio"))
    fim = safe_str(payload.get("horario_fim"))
    substituto = _funcionario(db, payload.get("substituto_id")) if payload.get("substituto_id") else None

    if not dia:
        return None, "Informe a data da escala."
    if not funcionario:
        return None, "Selecione um funcionário ativo."
    if status not in STATUS_VALIDOS:
        return None, "Status da escala inválido."
    if status != "folga":
        if not _valid_time(inicio) or not _valid_time(fim):
            return None, "Informe horário de início e fim no formato HH:MM."
    else:
        inicio = ""
        fim = ""
    if substituto and substituto.id == funcionario.id:
        return None, "O substituto precisa ser outro funcionário."

    return {
        "data_escala": dia,
        "funcionario": funcionario,
        "horario_inicio": inicio,
        "horario_fim": fim,
        "status": status,
        "substituto": substituto,
        "motivo_substituicao": safe_str(payload.get("motivo_substituicao")),
        "observacao": safe_str(payload.get("observacao")),
    }, None


@router.get("")
async def api_listar_escala(
    request: Request,
    inicio: str = Query(""),
    fim: str = Query(""),
    db: Session = Depends(get_db),
):
    user = require_interno_module_api(request, "escala")
    if isinstance(user, JSONResponse):
        return user

    hoje = _parse_date(today_local_iso(), date.today())
    data_inicio = _parse_date(inicio, hoje - timedelta(days=3))
    data_fim = _parse_date(fim, hoje + timedelta(days=14))
    if not data_inicio or not data_fim:
        return JSONResponse(status_code=400, content={"ok": False, "detail": "Período inválido."})
    if data_fim < data_inicio:
        data_inicio, data_fim = data_fim, data_inicio

    itens = [escala_publica(item) for item in escalas_periodo(db, data_inicio, data_fim)]
    return {
        "ok": True,
        "escalas": itens,
        "resumo": escala_resumo(db, user),
        "pode_gerenciar": _can_manage(user),
    }


@router.post("")
async def api_criar_escala(request: Request, db: Session = Depends(get_db)):
    user = require_interno_module_api(request, "escala")
    if isinstance(user, JSONResponse):
        return user
    if not _can_manage(user):
        return JSONResponse(status_code=403, content={"ok": False, "detail": "Somente supervisor ou administrador pode alterar a escala."})

    try:
        payload = await request.json()
    except Exception:
        payload = {}
    dados, erro = _read_payload(payload or {}, db)
    if erro:
        return JSONResponse(status_code=400, content={"ok": False, "detail": erro})

    # Evita duas escalas principais para a mesma pessoa no mesmo dia.
    existente = (
        db.query(InternoEscala)
        .filter(
            InternoEscala.data_escala == dados["data_escala"],
            InternoEscala.funcionario_id == dados["funcionario"].id,
            InternoEscala.status != "cancelado",
        )
        .first()
    )
    if existente:
        return JSONResponse(status_code=409, content={"ok": False, "detail": "Esse funcionário já possui escala registrada nessa data."})

    now = now_utc()
    item = InternoEscala(
        data_escala=dados["data_escala"],
        funcionario_id=dados["funcionario"].id,
        funcionario_nome=dados["funcionario"].nome or "",
        horario_inicio=dados["horario_inicio"],
        horario_fim=dados["horario_fim"],
        status=dados["status"],
        substituto_id=dados["substituto"].id if dados["substituto"] else None,
        substituto_nome=dados["substituto"].nome if dados["substituto"] else "",
        motivo_substituicao=dados["motivo_substituicao"],
        observacao=dados["observacao"],
        criado_em=now,
        atualizado_em=now,
        criado_por=user.get("username") or "",
        atualizado_por=user.get("username") or "",
    )
    db.add(item)
    db.flush()
    registrar_auditoria(db, user, request, modulo="escala", entidade="escala", entidade_id=item.id, acao="CRIAR", descricao=f"Criou a escala de {item.funcionario_nome} para {item.data_escala.strftime('%d/%m/%Y')}.")
    db.commit()
    db.refresh(item)
    return JSONResponse(status_code=201, content={"ok": True, "escala": escala_publica(item), "resumo": escala_resumo(db, user)})


@router.put("/{escala_id}")
async def api_atualizar_escala(escala_id: int, request: Request, db: Session = Depends(get_db)):
    user = require_interno_module_api(request, "escala")
    if isinstance(user, JSONResponse):
        return user
    if not _can_manage(user):
        return JSONResponse(status_code=403, content={"ok": False, "detail": "Somente supervisor ou administrador pode alterar a escala."})

    item = db.query(InternoEscala).filter(InternoEscala.id == escala_id).first()
    if not item:
        return JSONResponse(status_code=404, content={"ok": False, "detail": "Escala não encontrada."})

    try:
        payload = await request.json()
    except Exception:
        payload = {}
    dados, erro = _read_payload(payload or {}, db)
    if erro:
        return JSONResponse(status_code=400, content={"ok": False, "detail": erro})

    conflito = (
        db.query(InternoEscala)
        .filter(
            InternoEscala.data_escala == dados["data_escala"],
            InternoEscala.funcionario_id == dados["funcionario"].id,
            InternoEscala.status != "cancelado",
            InternoEscala.id != escala_id,
        )
        .first()
    )
    if conflito:
        return JSONResponse(status_code=409, content={"ok": False, "detail": "Esse funcionário já possui outra escala nessa data."})

    item.data_escala = dados["data_escala"]
    item.funcionario_id = dados["funcionario"].id
    item.funcionario_nome = dados["funcionario"].nome or ""
    item.horario_inicio = dados["horario_inicio"]
    item.horario_fim = dados["horario_fim"]
    item.status = dados["status"]
    item.substituto_id = dados["substituto"].id if dados["substituto"] else None
    item.substituto_nome = dados["substituto"].nome if dados["substituto"] else ""
    item.motivo_substituicao = dados["motivo_substituicao"]
    item.observacao = dados["observacao"]
    item.atualizado_em = now_utc()
    item.atualizado_por = user.get("username") or ""
    registrar_auditoria(db, user, request, modulo="escala", entidade="escala", entidade_id=item.id, acao="ALTERAR", descricao=f"Alterou a escala de {item.funcionario_nome} para {item.data_escala.strftime('%d/%m/%Y')}.")
    db.commit()
    db.refresh(item)
    return {"ok": True, "escala": escala_publica(item), "resumo": escala_resumo(db, user)}


@router.post("/{escala_id}/cancelar")
async def api_cancelar_escala(escala_id: int, request: Request, db: Session = Depends(get_db)):
    user = require_interno_module_api(request, "escala")
    if isinstance(user, JSONResponse):
        return user
    if not _can_manage(user):
        return JSONResponse(status_code=403, content={"ok": False, "detail": "Somente supervisor ou administrador pode alterar a escala."})

    item = db.query(InternoEscala).filter(InternoEscala.id == escala_id).first()
    if not item:
        return JSONResponse(status_code=404, content={"ok": False, "detail": "Escala não encontrada."})
    item.status = "cancelado"
    item.atualizado_em = now_utc()
    item.atualizado_por = user.get("username") or ""
    registrar_auditoria(db, user, request, modulo="escala", entidade="escala", entidade_id=item.id, acao="ENCERRAR", descricao=f"Cancelou a escala de {item.funcionario_nome} para {item.data_escala.strftime('%d/%m/%Y')}.")
    db.commit()
    db.refresh(item)
    return {"ok": True, "escala": escala_publica(item), "resumo": escala_resumo(db, user)}
