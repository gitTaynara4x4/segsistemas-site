from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import require_interno_user_api, user_is_admin
from ..models import (
    InternoComunicado,
    InternoComunicadoLeitura,
    InternoNotificacao,
    InternoOcorrencia,
    InternoPassagem,
    InternoTarefa,
)
from ..services.auditoria import registrar_auditoria
from ..utils import now_utc, now_local, safe_lower, safe_str

router = APIRouter(prefix="/api/interno", tags=["Interno - Notificações"])

DYNAMIC_TYPES = {"tarefa", "passagem", "ocorrencia"}


def _login(user: dict) -> str:
    return safe_lower(user.get("username") or user.get("nome") or "usuario") or "usuario"


def _upsert(db: Session, user: dict, *, chave: str, tipo: str, titulo: str, mensagem: str, url: str, origem_id: int | None = None, criado_em=None):
    login = _login(user)
    item = db.query(InternoNotificacao).filter(InternoNotificacao.chave == chave).first()
    if not item:
        item = InternoNotificacao(
            chave=chave,
            usuario_login=login,
            usuario_id=user.get("funcionario_id"),
            tipo=tipo,
            titulo=titulo,
            mensagem=mensagem,
            url=url,
            origem_id=origem_id,
            criado_em=criado_em or now_utc(),
        )
        db.add(item)
    else:
        item.titulo = titulo
        item.mensagem = mensagem
        item.url = url
        item.origem_id = origem_id
    return item


def sincronizar_notificacoes(db: Session, user: dict) -> None:
    login = _login(user)
    hoje = now_local().date()
    ativos: set[str] = set()

    funcionario_id = user.get("funcionario_id")

    # Tarefas vencidas ou que vencem hoje: apenas as atribuídas ao usuário.
    tarefa_query = db.query(InternoTarefa).filter(InternoTarefa.status.in_(["pendente", "em_andamento"]))
    if funcionario_id is not None:
        tarefa_query = tarefa_query.filter(InternoTarefa.responsavel_id == funcionario_id)
    else:
        # Administrador acompanha todas as tarefas com prazo.
        pass
    for tarefa in tarefa_query.all():
        if not tarefa.prazo or tarefa.prazo > hoje:
            continue
        situacao = "vencida" if tarefa.prazo < hoje else "vence hoje"
        chave = f"tarefa:{login}:{tarefa.id}:{tarefa.prazo.isoformat()}"
        ativos.add(chave)
        _upsert(
            db, user, chave=chave, tipo="tarefa",
            titulo="Tarefa vencendo" if situacao == "vence hoje" else "Tarefa vencida",
            mensagem=f"{tarefa.titulo or 'Tarefa sem título'} · {situacao}.",
            url="/interno/tarefas",
            origem_id=tarefa.id,
            criado_em=tarefa.criado_em,
        )

    # Nova passagem pendente. Se estiver direcionada a alguém, só esse usuário recebe.
    passagens = db.query(InternoPassagem).filter(InternoPassagem.status == "pendente").order_by(InternoPassagem.id.desc()).limit(50).all()
    for passagem in passagens:
        if passagem.recebido_por_id and funcionario_id is not None and passagem.recebido_por_id != funcionario_id:
            continue
        if passagem.recebido_por_id and funcionario_id is None and not user_is_admin(user):
            continue
        chave = f"passagem:{login}:{passagem.id}"
        ativos.add(chave)
        _upsert(
            db, user, chave=chave, tipo="passagem",
            titulo="Nova passagem de plantão",
            mensagem=f"Passagem #{passagem.id} aguardando recebimento.",
            url="/interno/passagem",
            origem_id=passagem.id,
            criado_em=passagem.criado_em,
        )

    # Ocorrências críticas abertas.
    ocorrencias = (
        db.query(InternoOcorrencia)
        .filter(
            InternoOcorrencia.status.in_(["aberta", "em_andamento"]),
            InternoOcorrencia.prioridade.in_(["critica", "crítica"]),
        )
        .order_by(InternoOcorrencia.id.desc())
        .limit(50)
        .all()
    )
    for ocorrencia in ocorrencias:
        chave = f"ocorrencia:{login}:{ocorrencia.id}"
        ativos.add(chave)
        _upsert(
            db, user, chave=chave, tipo="ocorrencia",
            titulo="Ocorrência crítica",
            mensagem=ocorrencia.titulo or f"Ocorrência #{ocorrencia.id}",
            url="/interno/ocorrencias",
            origem_id=ocorrencia.id,
            criado_em=ocorrencia.criado_em,
        )

    # Comunicados publicados recentemente. O módulo visual de comunicados poderá usar a mesma tabela.
    comunicados = (
        db.query(InternoComunicado)
        .filter(InternoComunicado.ativo.is_(True))
        .order_by(InternoComunicado.publicado_em.desc(), InternoComunicado.id.desc())
        .limit(30)
        .all()
    )
    for comunicado in comunicados:
        chave = f"comunicado:{login}:{comunicado.id}"
        ativos.add(chave)
        _upsert(
            db, user, chave=chave, tipo="comunicado",
            titulo="Novo comunicado",
            mensagem=comunicado.titulo or "Novo comunicado interno.",
            url="/interno/dashboard",
            origem_id=comunicado.id,
            criado_em=comunicado.publicado_em or comunicado.criado_em,
        )

    # Remove da fila de não lidos alertas dinâmicos que já não estão ativos.
    antigos = (
        db.query(InternoNotificacao)
        .filter(
            InternoNotificacao.usuario_login == login,
            InternoNotificacao.tipo.in_(DYNAMIC_TYPES),
            InternoNotificacao.lida_em.is_(None),
        )
        .all()
    )
    for item in antigos:
        if item.chave not in ativos:
            item.lida_em = now_utc()

    db.commit()


def _publica(item: InternoNotificacao) -> dict:
    return {
        "id": item.id,
        "tipo": item.tipo,
        "titulo": item.titulo,
        "mensagem": item.mensagem,
        "url": item.url,
        "origem_id": item.origem_id,
        "criado_em": item.criado_em.isoformat() if item.criado_em else None,
        "lida": bool(item.lida_em),
    }


@router.get("/notificacoes")
async def listar_notificacoes(request: Request, db: Session = Depends(get_db)):
    user_or_response = require_interno_user_api(request)
    if isinstance(user_or_response, JSONResponse):
        return user_or_response

    sincronizar_notificacoes(db, user_or_response)
    login = _login(user_or_response)
    itens = (
        db.query(InternoNotificacao)
        .filter(InternoNotificacao.usuario_login == login)
        .order_by(InternoNotificacao.criado_em.desc(), InternoNotificacao.id.desc())
        .limit(40)
        .all()
    )
    return {
        "ok": True,
        "notificacoes": [_publica(item) for item in itens],
        "nao_lidas": sum(1 for item in itens if item.lida_em is None),
    }


@router.post("/notificacoes/{notificacao_id}/ler")
async def marcar_notificacao_lida(notificacao_id: int, request: Request, db: Session = Depends(get_db)):
    user_or_response = require_interno_user_api(request)
    if isinstance(user_or_response, JSONResponse):
        return user_or_response

    item = db.query(InternoNotificacao).filter(
        InternoNotificacao.id == notificacao_id,
        InternoNotificacao.usuario_login == _login(user_or_response),
    ).first()
    if not item:
        return JSONResponse(status_code=404, content={"ok": False, "detail": "Notificação não encontrada."})
    item.lida_em = item.lida_em or now_utc()
    if item.tipo == "comunicado" and item.origem_id:
        leitura = db.query(InternoComunicadoLeitura).filter(
            InternoComunicadoLeitura.comunicado_id == item.origem_id,
            InternoComunicadoLeitura.usuario_login == _login(user_or_response),
        ).first()
        if not leitura:
            db.add(InternoComunicadoLeitura(
                comunicado_id=item.origem_id,
                usuario_login=_login(user_or_response),
                usuario_id=user_or_response.get("funcionario_id"),
                lido_em=now_utc(),
            ))
        else:
            leitura.lido_em = leitura.lido_em or now_utc()
    db.commit()
    return {"ok": True}


@router.post("/notificacoes/ler-todas")
async def marcar_todas_lidas(request: Request, db: Session = Depends(get_db)):
    user_or_response = require_interno_user_api(request)
    if isinstance(user_or_response, JSONResponse):
        return user_or_response

    login = _login(user_or_response)
    now = now_utc()

    # Se o sino marcar comunicados como lidos, o Mural/Dashboard precisa refletir
    # a mesma leitura. Mantém os dois módulos sincronizados.
    comunicados_pendentes = (
        db.query(InternoNotificacao)
        .filter(
            InternoNotificacao.usuario_login == login,
            InternoNotificacao.tipo == "comunicado",
            InternoNotificacao.lida_em.is_(None),
            InternoNotificacao.origem_id.isnot(None),
        )
        .all()
    )
    for notificacao in comunicados_pendentes:
        leitura = db.query(InternoComunicadoLeitura).filter(
            InternoComunicadoLeitura.comunicado_id == notificacao.origem_id,
            InternoComunicadoLeitura.usuario_login == login,
        ).first()
        if not leitura:
            db.add(InternoComunicadoLeitura(
                comunicado_id=notificacao.origem_id,
                usuario_login=login,
                usuario_id=user_or_response.get("funcionario_id"),
                lido_em=now,
            ))
        elif not leitura.lido_em:
            leitura.lido_em = now

    db.query(InternoNotificacao).filter(
        InternoNotificacao.usuario_login == login,
        InternoNotificacao.lida_em.is_(None),
    ).update({"lida_em": now}, synchronize_session=False)
    db.commit()
    return {"ok": True}


@router.get("/comunicados")
async def listar_comunicados(request: Request, db: Session = Depends(get_db)):
    user_or_response = require_interno_user_api(request)
    if isinstance(user_or_response, JSONResponse):
        return user_or_response
    login = _login(user_or_response)
    lidos = {
        int(item.comunicado_id)
        for item in db.query(InternoComunicadoLeitura.comunicado_id)
        .filter(InternoComunicadoLeitura.usuario_login == login)
        .all()
    }
    itens = db.query(InternoComunicado).filter(InternoComunicado.ativo.is_(True)).order_by(InternoComunicado.publicado_em.desc(), InternoComunicado.id.desc()).limit(100).all()
    return {
        "ok": True,
        "comunicados": [
            {
                "id": i.id,
                "titulo": i.titulo,
                "mensagem": i.mensagem,
                "publicado_em": (i.publicado_em or i.criado_em).isoformat() if (i.publicado_em or i.criado_em) else None,
                "lido": i.id in lidos,
            }
            for i in itens
        ],
    }


@router.post("/comunicados/{comunicado_id}/ler")
async def marcar_comunicado_lido(comunicado_id: int, request: Request, db: Session = Depends(get_db)):
    user_or_response = require_interno_user_api(request)
    if isinstance(user_or_response, JSONResponse):
        return user_or_response

    comunicado = db.query(InternoComunicado).filter(InternoComunicado.id == comunicado_id, InternoComunicado.ativo.is_(True)).first()
    if not comunicado:
        return JSONResponse(status_code=404, content={"ok": False, "detail": "Comunicado não encontrado."})

    login = _login(user_or_response)
    leitura = db.query(InternoComunicadoLeitura).filter(
        InternoComunicadoLeitura.comunicado_id == comunicado_id,
        InternoComunicadoLeitura.usuario_login == login,
    ).first()
    if not leitura:
        leitura = InternoComunicadoLeitura(
            comunicado_id=comunicado_id,
            usuario_login=login,
            usuario_id=user_or_response.get("funcionario_id"),
            lido_em=now_utc(),
        )
        db.add(leitura)
    else:
        leitura.lido_em = leitura.lido_em or now_utc()

    notificacao = db.query(InternoNotificacao).filter(
        InternoNotificacao.usuario_login == login,
        InternoNotificacao.tipo == "comunicado",
        InternoNotificacao.origem_id == comunicado_id,
    ).first()
    if notificacao:
        notificacao.lida_em = notificacao.lida_em or now_utc()

    db.commit()
    return {"ok": True, "comunicado_id": comunicado_id, "lido": True}


@router.post("/comunicados")
async def criar_comunicado(request: Request, db: Session = Depends(get_db)):
    user_or_response = require_interno_user_api(request)
    if isinstance(user_or_response, JSONResponse):
        return user_or_response
    if not user_is_admin(user_or_response):
        return JSONResponse(status_code=403, content={"ok": False, "detail": "Somente administradores podem publicar comunicados."})
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    titulo = safe_str(payload.get("titulo"))
    mensagem = safe_str(payload.get("mensagem"))
    if not titulo or not mensagem:
        return JSONResponse(status_code=400, content={"ok": False, "detail": "Informe título e mensagem."})
    now = now_utc()
    comunicado = InternoComunicado(
        titulo=titulo,
        mensagem=mensagem,
        ativo=True,
        publicado_em=now,
        criado_por_id=user_or_response.get("funcionario_id"),
        criado_por_nome=user_or_response.get("nome") or user_or_response.get("username") or "Administrador",
        criado_por_usuario=user_or_response.get("username") or "",
        criado_em=now,
    )
    db.add(comunicado)
    db.flush()
    registrar_auditoria(db, user_or_response, request, modulo="comunicados", entidade="comunicado", entidade_id=comunicado.id, acao="CRIAR", descricao=f"Publicou o comunicado: {comunicado.titulo}.")
    db.commit()
    db.refresh(comunicado)
    return JSONResponse(status_code=201, content={"ok": True, "comunicado": {"id": comunicado.id, "titulo": comunicado.titulo}})
