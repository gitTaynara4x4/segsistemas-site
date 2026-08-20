from datetime import date

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import require_interno_user_api
from ..models import (
    InternoDocumento,
    InternoFuncionario,
    InternoOcorrencia,
    InternoPassagem,
    InternoTarefa,
)
from ..services.interno import dt_to_iso
from ..utils import safe_str

router = APIRouter(prefix="/api/interno/busca", tags=["Interno - Busca Geral"])


def _snippet(termo: str, *valores: str, limite: int = 180) -> str:
    q = safe_str(termo).lower()
    for valor in valores:
        texto = safe_str(valor)
        if not texto:
            continue
        pos = texto.lower().find(q) if q else -1
        if pos >= 0:
            inicio = max(0, pos - 60)
            fim = min(len(texto), pos + len(q) + 100)
            trecho = texto[inicio:fim].strip()
            if inicio > 0:
                trecho = "…" + trecho
            if fim < len(texto):
                trecho += "…"
            return trecho[:limite]
    for valor in valores:
        texto = safe_str(valor)
        if texto:
            return texto[:limite] + ("…" if len(texto) > limite else "")
    return ""


def _item(tipo: str, id_: int, titulo: str, subtitulo: str, detalhe: str, url: str, data=None, meta=None) -> dict:
    return {
        "tipo": tipo,
        "id": id_,
        "titulo": safe_str(titulo),
        "subtitulo": safe_str(subtitulo),
        "detalhe": safe_str(detalhe),
        "url": url,
        "data": (data.isoformat() if isinstance(data, date) else dt_to_iso(data)) if data else None,
        "meta": meta or {},
    }


@router.get("")
async def busca_geral(
    request: Request,
    q: str = Query(""),
    limite: int = Query(8),
    db: Session = Depends(get_db),
):
    user = require_interno_user_api(request)
    if isinstance(user, JSONResponse):
        return user

    termo = safe_str(q)
    if len(termo) < 2:
        return {"ok": True, "q": termo, "total": 0, "resultados": {}}

    limite = max(3, min(int(limite or 8), 15))
    like = f"%{termo}%"
    resultados: dict[str, list[dict]] = {}

    acessos = {str(item).strip().lower() for item in (user.get("acessos") or []) if item}
    admin = bool(user.get("is_admin")) or str(user.get("permissao") or "").lower() == "admin"

    # Ocorrências
    if admin or "ocorrencias" in acessos:
        rows = (
            db.query(InternoOcorrencia)
            .filter(
                or_(
                    InternoOcorrencia.titulo.ilike(like),
                    InternoOcorrencia.cliente_nome.ilike(like),
                    InternoOcorrencia.local.ilike(like),
                    InternoOcorrencia.descricao.ilike(like),
                    InternoOcorrencia.providencia.ilike(like),
                    InternoOcorrencia.responsavel.ilike(like),
                )
            )
            .order_by(InternoOcorrencia.data_ocorrencia.desc(), InternoOcorrencia.id.desc())
            .limit(limite)
            .all()
        )
        resultados["ocorrencias"] = [
            _item(
                "Ocorrência",
                row.id,
                row.titulo or "Ocorrência sem título",
                f"{row.cliente_nome or 'Sem cliente'} · {row.local or 'Sem local'}",
                _snippet(termo, row.titulo, row.cliente_nome, row.local, row.descricao, row.providencia, row.responsavel),
                "/interno/ocorrencias",
                row.data_ocorrencia,
                {"status": row.status or "aberta", "prioridade": row.prioridade or "media"},
            )
            for row in rows
        ]

    # Funcionários
    if admin or "funcionarios" in acessos:
        rows = (
            db.query(InternoFuncionario)
            .filter(
                or_(
                    InternoFuncionario.nome.ilike(like),
                    InternoFuncionario.usuario.ilike(like),
                    InternoFuncionario.cargo.ilike(like),
                    InternoFuncionario.email.ilike(like),
                    InternoFuncionario.telefone.ilike(like),
                )
            )
            .order_by(InternoFuncionario.ativo.desc(), InternoFuncionario.nome.asc())
            .limit(limite)
            .all()
        )
        resultados["funcionarios"] = [
            _item(
                "Funcionário",
                row.id,
                row.nome or row.usuario or "Funcionário",
                f"{row.cargo or 'Sem cargo'} · @{row.usuario or '-'}",
                _snippet(termo, row.nome, row.cargo, row.usuario, row.email, row.telefone),
                "/interno/funcionarios",
                row.atualizado_em or row.criado_em,
                {"ativo": bool(row.ativo), "usuario": row.usuario or ""},
            )
            for row in rows
        ]

    # Passagens de plantão
    if admin or "passagem" in acessos:
        rows = (
            db.query(InternoPassagem)
            .filter(
                or_(
                    InternoPassagem.passado_por_nome.ilike(like),
                    InternoPassagem.passado_por_usuario.ilike(like),
                    InternoPassagem.recebido_por_nome.ilike(like),
                    InternoPassagem.recebido_por_usuario.ilike(like),
                    InternoPassagem.pendencias.ilike(like),
                    InternoPassagem.clientes_observacao.ilike(like),
                    InternoPassagem.falhas_sistema.ilike(like),
                    InternoPassagem.ocorrencias_importantes.ilike(like),
                    InternoPassagem.recado_proximo.ilike(like),
                )
            )
            .order_by(InternoPassagem.data_plantao.desc(), InternoPassagem.id.desc())
            .limit(limite)
            .all()
        )
        resultados["passagens"] = [
            _item(
                "Passagem de plantão",
                row.id,
                f"Passagem · {row.data_plantao.strftime('%d/%m/%Y') if row.data_plantao else 'sem data'}",
                f"{row.passado_por_nome or 'Não informado'} → {row.recebido_por_nome or 'Próximo plantonista'}",
                _snippet(termo, row.pendencias, row.clientes_observacao, row.falhas_sistema, row.ocorrencias_importantes, row.recado_proximo, row.passado_por_nome, row.recebido_por_nome),
                "/interno/passagem",
                row.atualizado_em or row.criado_em,
                {"status": row.status or "pendente", "data_plantao": row.data_plantao.isoformat() if row.data_plantao else None},
            )
            for row in rows
        ]

    # Pendências / tarefas
    if admin or "tarefas" in acessos:
        rows = (
            db.query(InternoTarefa)
            .filter(
                or_(
                    InternoTarefa.titulo.ilike(like),
                    InternoTarefa.descricao.ilike(like),
                    InternoTarefa.responsavel_nome.ilike(like),
                )
            )
            .order_by(InternoTarefa.prazo.is_(None), InternoTarefa.prazo.asc(), InternoTarefa.id.desc())
            .limit(limite)
            .all()
        )
        resultados["tarefas"] = [
            _item(
                "Pendência / Tarefa",
                row.id,
                row.titulo or "Tarefa sem título",
                f"{row.responsavel_nome or 'Sem responsável'} · {row.status or 'pendente'}",
                _snippet(termo, row.titulo, row.descricao, row.responsavel_nome),
                "/interno/tarefas",
                row.atualizado_em or row.criado_em,
                {"status": row.status or "pendente", "prioridade": row.prioridade or "media", "prazo": row.prazo.isoformat() if row.prazo else None},
            )
            for row in rows
        ]

    # Documentos internos
    if admin or "documentos" in acessos:
        rows = (
            db.query(InternoDocumento)
            .filter(
                InternoDocumento.ativo.is_(True),
                or_(
                    InternoDocumento.titulo.ilike(like),
                    InternoDocumento.descricao.ilike(like),
                    InternoDocumento.conteudo.ilike(like),
                    InternoDocumento.categoria.ilike(like),
                    InternoDocumento.contato_nome.ilike(like),
                    InternoDocumento.telefone.ilike(like),
                    InternoDocumento.email.ilike(like),
                ),
            )
            .order_by(InternoDocumento.categoria.asc(), InternoDocumento.titulo.asc())
            .limit(limite)
            .all()
        )
        resultados["documentos"] = [
            _item(
                "Documento",
                row.id,
                row.titulo or "Documento sem título",
                f"{row.categoria or 'Geral'} · {row.tipo or 'documento'}",
                _snippet(termo, row.titulo, row.descricao, row.conteudo, row.categoria, row.contato_nome, row.telefone, row.email),
                "/interno/documentos",
                row.atualizado_em or row.criado_em,
                {"tipo": row.tipo or "documento", "categoria": row.categoria or "Geral", "arquivo_url": row.arquivo_url or ""},
            )
            for row in rows
        ]

    # Remove grupos vazios para a UI ficar limpa.
    resultados = {chave: itens for chave, itens in resultados.items() if itens}
    total = sum(len(itens) for itens in resultados.values())

    return {"ok": True, "q": termo, "total": total, "resultados": resultados}
