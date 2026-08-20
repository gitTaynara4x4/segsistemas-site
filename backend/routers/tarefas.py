from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..config import TAREFA_PRIORIDADES, TAREFA_STATUS
from ..database import get_db
from ..deps import require_interno_module_api
from ..models import InternoFuncionario, InternoTarefa
from ..services.interno import tarefa_publica, tarefas_resumo, validar_payload_tarefa
from ..services.auditoria import registrar_auditoria
from ..utils import now_utc, read_json_body_safe, safe_lower, safe_str

router = APIRouter(prefix="/api/interno/tarefas", tags=["Interno - Pendências / Tarefas"])


def _responsavel(db: Session, responsavel_id: int | None, responsavel_nome: str = "") -> tuple[int | None, str]:
    if responsavel_id is not None:
        funcionario = (
            db.query(InternoFuncionario)
            .filter(InternoFuncionario.id == responsavel_id, InternoFuncionario.ativo.is_(True))
            .first()
        )
        if funcionario:
            return funcionario.id, funcionario.nome or funcionario.usuario or ""
    return None, safe_str(responsavel_nome)


def _funcionarios_ativos(db: Session) -> list[dict]:
    itens = (
        db.query(InternoFuncionario)
        .filter(InternoFuncionario.ativo.is_(True))
        .order_by(InternoFuncionario.nome.asc())
        .all()
    )
    return [
        {
            "id": item.id,
            "nome": item.nome or item.usuario or "Funcionário",
            "cargo": item.cargo or "",
            "usuario": item.usuario or "",
        }
        for item in itens
    ]


@router.get("")
async def api_interno_listar_tarefas(
    request: Request,
    status: str = Query(""),
    prioridade: str = Query(""),
    responsavel_id: int | None = Query(None),
    busca: str = Query(""),
    limite: int = Query(200),
    db: Session = Depends(get_db),
):
    user_or_response = require_interno_module_api(request, "tarefas")
    if isinstance(user_or_response, JSONResponse):
        return user_or_response

    query = db.query(InternoTarefa)
    status_norm = safe_lower(status)
    prioridade_norm = safe_lower(prioridade)
    busca_norm = safe_str(busca)

    if status_norm:
        query = query.filter(InternoTarefa.status == status_norm)
    if prioridade_norm:
        query = query.filter(InternoTarefa.prioridade == prioridade_norm)
    if responsavel_id is not None:
        query = query.filter(InternoTarefa.responsavel_id == responsavel_id)
    if busca_norm:
        termo = f"%{busca_norm}%"
        query = query.filter(
            or_(
                InternoTarefa.titulo.ilike(termo),
                InternoTarefa.descricao.ilike(termo),
                InternoTarefa.responsavel_nome.ilike(termo),
            )
        )

    itens = (
        query.order_by(
            InternoTarefa.status.in_(["concluida", "cancelada"]),
            InternoTarefa.prazo.is_(None),
            InternoTarefa.prazo.asc(),
            InternoTarefa.id.desc(),
        )
        .limit(max(1, min(int(limite or 200), 500)))
        .all()
    )

    return {
        "ok": True,
        "tarefas": [tarefa_publica(item) for item in itens],
        "resumo": tarefas_resumo(db, user_or_response),
        "funcionarios": _funcionarios_ativos(db),
        "prioridades": TAREFA_PRIORIDADES,
        "status": TAREFA_STATUS,
    }


@router.post("")
async def api_interno_criar_tarefa(request: Request, db: Session = Depends(get_db)):
    user_or_response = require_interno_module_api(request, "tarefas")
    if isinstance(user_or_response, JSONResponse):
        return user_or_response

    try:
        payload = await request.json()
    except Exception:
        payload = {}
    payload = read_json_body_safe(payload)

    dados, erro = validar_payload_tarefa(payload)
    if erro:
        return JSONResponse(status_code=400, content={"ok": False, "detail": erro})

    responsavel_id, responsavel_nome = _responsavel(
        db,
        dados["responsavel_id"],
        dados["responsavel_nome"],
    )

    now = now_utc()
    status = dados["status"]
    tarefa = InternoTarefa(
        titulo=dados["titulo"],
        descricao=dados["descricao"],
        responsavel_id=responsavel_id,
        responsavel_nome=responsavel_nome,
        prioridade=dados["prioridade"],
        status=status,
        prazo=dados["prazo"],
        criado_por_id=user_or_response.get("funcionario_id"),
        criado_por_nome=user_or_response.get("nome") or user_or_response.get("username") or "",
        criado_por_usuario=user_or_response.get("username") or "",
        criado_em=now,
        atualizado_em=now,
        atualizado_por=user_or_response.get("username") or "",
        concluido_por_id=user_or_response.get("funcionario_id") if status == "concluida" else None,
        concluido_por_nome=(user_or_response.get("nome") or user_or_response.get("username") or "") if status == "concluida" else "",
        concluido_por_usuario=(user_or_response.get("username") or "") if status == "concluida" else "",
        concluido_em=now if status == "concluida" else None,
    )
    db.add(tarefa)
    db.flush()
    registrar_auditoria(db, user_or_response, request, modulo="tarefas", entidade="tarefa", entidade_id=tarefa.id, acao="CRIAR", descricao=f"Criou a tarefa: {tarefa.titulo}.")
    db.commit()
    db.refresh(tarefa)
    return JSONResponse(status_code=201, content={"ok": True, "tarefa": tarefa_publica(tarefa)})


@router.put("/{tarefa_id}")
async def api_interno_atualizar_tarefa(tarefa_id: int, request: Request, db: Session = Depends(get_db)):
    user_or_response = require_interno_module_api(request, "tarefas")
    if isinstance(user_or_response, JSONResponse):
        return user_or_response

    try:
        payload = await request.json()
    except Exception:
        payload = {}
    payload = read_json_body_safe(payload)

    dados, erro = validar_payload_tarefa(payload)
    if erro:
        return JSONResponse(status_code=400, content={"ok": False, "detail": erro})

    tarefa = db.query(InternoTarefa).filter(InternoTarefa.id == tarefa_id).first()
    if not tarefa:
        return JSONResponse(status_code=404, content={"ok": False, "detail": "Tarefa não encontrada."})

    responsavel_id, responsavel_nome = _responsavel(
        db,
        dados["responsavel_id"],
        dados["responsavel_nome"],
    )

    now = now_utc()
    tarefa.titulo = dados["titulo"]
    tarefa.descricao = dados["descricao"]
    tarefa.responsavel_id = responsavel_id
    tarefa.responsavel_nome = responsavel_nome
    tarefa.prioridade = dados["prioridade"]
    tarefa.status = dados["status"]
    tarefa.prazo = dados["prazo"]
    tarefa.atualizado_em = now
    tarefa.atualizado_por = user_or_response.get("username") or ""

    if dados["status"] == "concluida" and not tarefa.concluido_em:
        tarefa.concluido_por_id = user_or_response.get("funcionario_id")
        tarefa.concluido_por_nome = user_or_response.get("nome") or user_or_response.get("username") or ""
        tarefa.concluido_por_usuario = user_or_response.get("username") or ""
        tarefa.concluido_em = now
    elif dados["status"] != "concluida":
        tarefa.concluido_por_id = None
        tarefa.concluido_por_nome = ""
        tarefa.concluido_por_usuario = ""
        tarefa.concluido_em = None

    acao_auditoria = "ENCERRAR" if dados["status"] == "concluida" else "ALTERAR"
    descricao_auditoria = f"Encerrou a tarefa: {tarefa.titulo}." if acao_auditoria == "ENCERRAR" else f"Alterou a tarefa: {tarefa.titulo}."
    registrar_auditoria(db, user_or_response, request, modulo="tarefas", entidade="tarefa", entidade_id=tarefa.id, acao=acao_auditoria, descricao=descricao_auditoria)
    db.commit()
    db.refresh(tarefa)
    return {"ok": True, "tarefa": tarefa_publica(tarefa)}


@router.post("/{tarefa_id}/concluir")
async def api_interno_concluir_tarefa(tarefa_id: int, request: Request, db: Session = Depends(get_db)):
    user_or_response = require_interno_module_api(request, "tarefas")
    if isinstance(user_or_response, JSONResponse):
        return user_or_response

    tarefa = db.query(InternoTarefa).filter(InternoTarefa.id == tarefa_id).first()
    if not tarefa:
        return JSONResponse(status_code=404, content={"ok": False, "detail": "Tarefa não encontrada."})

    now = now_utc()
    tarefa.status = "concluida"
    tarefa.concluido_por_id = user_or_response.get("funcionario_id")
    tarefa.concluido_por_nome = user_or_response.get("nome") or user_or_response.get("username") or ""
    tarefa.concluido_por_usuario = user_or_response.get("username") or ""
    tarefa.concluido_em = now
    tarefa.atualizado_em = now
    tarefa.atualizado_por = user_or_response.get("username") or ""
    registrar_auditoria(db, user_or_response, request, modulo="tarefas", entidade="tarefa", entidade_id=tarefa.id, acao="ENCERRAR", descricao=f"Encerrou a tarefa: {tarefa.titulo}.")
    db.commit()
    db.refresh(tarefa)
    return {"ok": True, "tarefa": tarefa_publica(tarefa)}


@router.post("/{tarefa_id}/reabrir")
async def api_interno_reabrir_tarefa(tarefa_id: int, request: Request, db: Session = Depends(get_db)):
    user_or_response = require_interno_module_api(request, "tarefas")
    if isinstance(user_or_response, JSONResponse):
        return user_or_response

    tarefa = db.query(InternoTarefa).filter(InternoTarefa.id == tarefa_id).first()
    if not tarefa:
        return JSONResponse(status_code=404, content={"ok": False, "detail": "Tarefa não encontrada."})

    now = now_utc()
    tarefa.status = "pendente"
    tarefa.concluido_por_id = None
    tarefa.concluido_por_nome = ""
    tarefa.concluido_por_usuario = ""
    tarefa.concluido_em = None
    tarefa.atualizado_em = now
    tarefa.atualizado_por = user_or_response.get("username") or ""
    registrar_auditoria(db, user_or_response, request, modulo="tarefas", entidade="tarefa", entidade_id=tarefa.id, acao="ALTERAR", descricao=f"Reabriu a tarefa: {tarefa.titulo}.")
    db.commit()
    db.refresh(tarefa)
    return {"ok": True, "tarefa": tarefa_publica(tarefa)}


@router.post("/{tarefa_id}/cancelar")
async def api_interno_cancelar_tarefa(tarefa_id: int, request: Request, db: Session = Depends(get_db)):
    user_or_response = require_interno_module_api(request, "tarefas")
    if isinstance(user_or_response, JSONResponse):
        return user_or_response

    tarefa = db.query(InternoTarefa).filter(InternoTarefa.id == tarefa_id).first()
    if not tarefa:
        return JSONResponse(status_code=404, content={"ok": False, "detail": "Tarefa não encontrada."})

    now = now_utc()
    tarefa.status = "cancelada"
    tarefa.concluido_por_id = None
    tarefa.concluido_por_nome = ""
    tarefa.concluido_por_usuario = ""
    tarefa.concluido_em = None
    tarefa.atualizado_em = now
    tarefa.atualizado_por = user_or_response.get("username") or ""
    registrar_auditoria(db, user_or_response, request, modulo="tarefas", entidade="tarefa", entidade_id=tarefa.id, acao="ENCERRAR", descricao=f"Cancelou a tarefa: {tarefa.titulo}.")
    db.commit()
    db.refresh(tarefa)
    return {"ok": True, "tarefa": tarefa_publica(tarefa)}
