from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import require_interno_module_api
from ..models import InternoFuncionario
from ..security import hash_password
from ..services.interno import funcionario_publico, funcionarios_resumo, validar_payload_funcionario
from ..utils import now_utc

router = APIRouter(prefix="/api/interno/funcionarios", tags=["Interno - Funcionários"])


@router.get("")
async def api_interno_listar_funcionarios(request: Request, db: Session = Depends(get_db)):
    user_or_response = require_interno_module_api(request, "funcionarios")
    if isinstance(user_or_response, JSONResponse):
        return user_or_response

    funcionarios = db.query(InternoFuncionario).order_by(InternoFuncionario.ativo.desc(), InternoFuncionario.nome.asc()).all()
    return {"ok": True, "funcionarios": [funcionario_publico(f) for f in funcionarios], "resumo": funcionarios_resumo(db)}


@router.post("")
async def api_interno_criar_funcionario(request: Request, db: Session = Depends(get_db)):
    user_or_response = require_interno_module_api(request, "funcionarios")
    if isinstance(user_or_response, JSONResponse):
        return user_or_response

    try:
        payload = await request.json()
    except Exception:
        payload = {}

    dados, erro = validar_payload_funcionario(payload, criando=True)
    if erro:
        return JSONResponse(status_code=400, content={"ok": False, "detail": erro})

    existente = db.query(InternoFuncionario).filter(InternoFuncionario.usuario == dados["usuario"]).first()
    if existente:
        return JSONResponse(status_code=409, content={"ok": False, "detail": "Já existe funcionário com esse usuário."})

    now = now_utc()
    funcionario = InternoFuncionario(
        nome=dados["nome"],
        telefone=dados["telefone"],
        email=dados["email"],
        cargo=dados["cargo"],
        tipo=dados["tipo"],
        usuario=dados["usuario"],
        permissao=dados["permissao"],
        acessos=dados["acessos"],
        ativo=dados["ativo"],
        senha_hash=hash_password(dados["senha"]),
        criado_em=now,
        atualizado_em=now,
        criado_por=user_or_response.get("username") or "",
    )
    db.add(funcionario)
    db.commit()
    db.refresh(funcionario)
    return JSONResponse(status_code=201, content={"ok": True, "funcionario": funcionario_publico(funcionario)})


@router.put("/{funcionario_id}")
async def api_interno_atualizar_funcionario(funcionario_id: int, request: Request, db: Session = Depends(get_db)):
    user_or_response = require_interno_module_api(request, "funcionarios")
    if isinstance(user_or_response, JSONResponse):
        return user_or_response

    try:
        payload = await request.json()
    except Exception:
        payload = {}

    dados, erro = validar_payload_funcionario(payload, criando=False)
    if erro:
        return JSONResponse(status_code=400, content={"ok": False, "detail": erro})

    funcionario = db.query(InternoFuncionario).filter(InternoFuncionario.id == funcionario_id).first()
    if not funcionario:
        return JSONResponse(status_code=404, content={"ok": False, "detail": "Funcionário não encontrado."})

    existente = db.query(InternoFuncionario).filter(InternoFuncionario.usuario == dados["usuario"], InternoFuncionario.id != funcionario_id).first()
    if existente:
        return JSONResponse(status_code=409, content={"ok": False, "detail": "Já existe outro funcionário com esse usuário."})

    funcionario.nome = dados["nome"]
    funcionario.telefone = dados["telefone"]
    funcionario.email = dados["email"]
    funcionario.cargo = dados["cargo"]
    funcionario.tipo = dados["tipo"]
    funcionario.usuario = dados["usuario"]
    funcionario.permissao = dados["permissao"]
    funcionario.acessos = dados["acessos"]
    funcionario.ativo = dados["ativo"]
    funcionario.atualizado_em = now_utc()
    funcionario.atualizado_por = user_or_response.get("username") or ""
    if dados["senha"]:
        funcionario.senha_hash = hash_password(dados["senha"])

    db.commit()
    db.refresh(funcionario)
    return {"ok": True, "funcionario": funcionario_publico(funcionario)}


@router.post("/{funcionario_id}/ativar")
async def api_interno_ativar_funcionario(funcionario_id: int, request: Request, db: Session = Depends(get_db)):
    user_or_response = require_interno_module_api(request, "funcionarios")
    if isinstance(user_or_response, JSONResponse):
        return user_or_response

    funcionario = db.query(InternoFuncionario).filter(InternoFuncionario.id == funcionario_id).first()
    if not funcionario:
        return JSONResponse(status_code=404, content={"ok": False, "detail": "Funcionário não encontrado."})

    funcionario.ativo = True
    funcionario.atualizado_em = now_utc()
    funcionario.atualizado_por = user_or_response.get("username") or ""
    db.commit()
    db.refresh(funcionario)
    return {"ok": True, "funcionario": funcionario_publico(funcionario)}


@router.post("/{funcionario_id}/inativar")
async def api_interno_inativar_funcionario(funcionario_id: int, request: Request, db: Session = Depends(get_db)):
    user_or_response = require_interno_module_api(request, "funcionarios")
    if isinstance(user_or_response, JSONResponse):
        return user_or_response

    funcionario = db.query(InternoFuncionario).filter(InternoFuncionario.id == funcionario_id).first()
    if not funcionario:
        return JSONResponse(status_code=404, content={"ok": False, "detail": "Funcionário não encontrado."})

    funcionario.ativo = False
    funcionario.atualizado_em = now_utc()
    funcionario.atualizado_por = user_or_response.get("username") or ""
    db.commit()
    db.refresh(funcionario)
    return {"ok": True, "funcionario": funcionario_publico(funcionario)}
