from datetime import date, timedelta

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..config import (
    FUNCIONARIO_PERMISSOES,
    FUNCIONARIO_TIPOS,
    OCORRENCIA_PRIORIDADES,
    OCORRENCIA_STATUS,
    OCORRENCIA_TIPOS,
    TAREFA_PRIORIDADES,
    TAREFA_STATUS,
    settings,
)
from ..database import get_db
from ..deps import require_interno_module_html, require_interno_user_html, user_can_access, user_is_admin
from ..models import (
    InternoComunicado,
    InternoComunicadoLeitura,
    InternoEscala,
    InternoFuncionario,
    InternoOcorrencia,
    InternoPassagem,
    InternoPlantao,
    InternoPonto,
    InternoTarefa,
)
from ..services.interno import (
    escala_publica,
    escala_resumo,
    escalas_do_dia,
    funcionarios_resumo,
    ocorrencias_resumo,
    passagens_resumo,
    plantao_publico,
    plantoes_resumo,
    ponto_publico,
    pontos_resumo,
    proxima_escala_usuario,
    tarefas_dashboard,
    tarefas_resumo,
)
from ..utils import now_local


router = APIRouter(tags=["Interno - Páginas"])
templates = Jinja2Templates(directory=settings.templates_dir)


MODULOS_FUNCIONARIOS = {
    "dashboard": {
        "label": "Dashboard",
        "nome": "Dashboard",
        "descricao": "Visão geral da operação interna.",
        "icon": "fa-solid fa-chart-line",
        "icone": "fa-solid fa-chart-line",
        "path": "/interno/dashboard",
    },
    "funcionarios": {
        "label": "Funcionários",
        "nome": "Funcionários",
        "descricao": "Cadastro, edição e controle de acessos da equipe.",
        "icon": "fa-solid fa-users",
        "icone": "fa-solid fa-users",
        "path": "/interno/funcionarios",
    },
    "ponto": {
        "label": "Ponto Online",
        "nome": "Ponto Online",
        "descricao": "Batidas de ponto, calendário, relatórios e presença.",
        "icon": "fa-solid fa-calendar-check",
        "icone": "fa-solid fa-calendar-check",
        "path": "/interno/ponto",
    },
    "plantao": {
        "label": "Plantão",
        "nome": "Plantão",
        "descricao": "Início, encerramento e histórico dos turnos.",
        "icon": "fa-solid fa-business-time",
        "icone": "fa-solid fa-business-time",
        "path": "/interno/plantao",
    },
    "escala": {
        "label": "Escala da Equipe",
        "nome": "Escala da Equipe",
        "descricao": "Quem trabalha, horários, folgas e substituições.",
        "icon": "fa-solid fa-calendar-days",
        "icone": "fa-solid fa-calendar-days",
        "path": "/interno/escala",
    },
    "passagem": {
        "label": "Passagem de Plantão",
        "nome": "Passagem de Plantão",
        "descricao": "Recados, pendências e observações para o próximo responsável.",
        "icon": "fa-solid fa-right-left",
        "icone": "fa-solid fa-right-left",
        "path": "/interno/passagem",
    },
    "ocorrencias": {
        "label": "Ocorrências",
        "nome": "Ocorrências",
        "descricao": "Registro e acompanhamento de falhas, problemas e pendências.",
        "icon": "fa-regular fa-clipboard",
        "icone": "fa-regular fa-clipboard",
        "path": "/interno/ocorrencias",
    },
    "tarefas": {
        "label": "Pendências / Tarefas",
        "nome": "Pendências / Tarefas",
        "descricao": "Tarefas internas com responsável, prioridade e prazo.",
        "icon": "fa-solid fa-list-check",
        "icone": "fa-solid fa-list-check",
        "path": "/interno/tarefas",
    },
    "comunicados": {
        "label": "Mural / Comunicados",
        "nome": "Mural / Comunicados",
        "descricao": "Avisos internos, comunicados e confirmações de leitura.",
        "icon": "fa-solid fa-bullhorn",
        "icone": "fa-solid fa-bullhorn",
        "path": "/interno/comunicados",
    },
    "documentos": {
        "label": "Documentos internos",
        "nome": "Documentos internos",
        "descricao": "Procedimentos, manuais, PDFs e contatos úteis organizados por categoria.",
        "icon": "fa-regular fa-folder-open",
        "icone": "fa-regular fa-folder-open",
        "path": "/interno/documentos",
    },
    "manual": {
        "label": "Manual Interno",
        "nome": "Manual Interno",
        "descricao": "Procedimentos de atendimento, alarme e rotina operacional.",
        "icon": "fa-regular fa-folder-open",
        "icone": "fa-regular fa-folder-open",
        "path": "/interno/manual",
    },
    "auditoria": {
        "label": "Histórico / Auditoria",
        "nome": "Histórico / Auditoria",
        "descricao": "Histórico das ações realizadas no painel interno.",
        "icon": "fa-solid fa-clock-rotate-left",
        "icone": "fa-solid fa-clock-rotate-left",
        "path": "/interno/auditoria",
    },
    "relatorios": {
        "label": "Relatórios",
        "nome": "Relatórios",
        "descricao": "Relatórios e calendário do ponto online.",
        "icon": "fa-solid fa-file-lines",
        "icone": "fa-solid fa-file-lines",
        "path": "/interno/ponto",
    },
}


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None

    try:
        return date.fromisoformat(str(value).strip())
    except Exception:
        return None


def _fmt_date_br(value: date) -> str:
    return value.strftime("%d/%m/%Y")


def _resolver_periodo_dashboard(periodo: str | None, data: str | None) -> dict:
    hoje = now_local().date()
    periodo_norm = (periodo or "hoje").strip().lower()
    data_custom = _parse_date(data)

    if data_custom:
        return {
            "periodo": "data",
            "data_inicio": data_custom,
            "data_fim": data_custom,
            "data_input": data_custom.isoformat(),
            "label": _fmt_date_br(data_custom),
        }

    if periodo_norm in {"ontem", "yesterday"}:
        ontem = hoje - timedelta(days=1)
        return {
            "periodo": "ontem",
            "data_inicio": ontem,
            "data_fim": ontem,
            "data_input": ontem.isoformat(),
            "label": f"Ontem · {_fmt_date_br(ontem)}",
        }

    if periodo_norm in {"7dias", "ultimos7", "ultimos_7_dias", "semana"}:
        inicio = hoje - timedelta(days=6)
        return {
            "periodo": "7dias",
            "data_inicio": inicio,
            "data_fim": hoje,
            "data_input": "",
            "label": f"Últimos 7 dias · {inicio.strftime('%d/%m')} até {_fmt_date_br(hoje)}",
        }

    return {
        "periodo": "hoje",
        "data_inicio": hoje,
        "data_fim": hoje,
        "data_input": hoje.isoformat(),
        "label": f"Hoje · {_fmt_date_br(hoje)}",
    }


def _count(db: Session, model, *filters) -> int:
    return int(db.query(func.count(model.id)).filter(*filters).scalar() or 0)


def dashboard_resumos_por_periodo(db: Session, data_inicio: date, data_fim: date) -> dict:
    plantao_periodo = (
        InternoPlantao.data_plantao >= data_inicio,
        InternoPlantao.data_plantao <= data_fim,
    )

    passagem_periodo = (
        InternoPassagem.data_plantao >= data_inicio,
        InternoPassagem.data_plantao <= data_fim,
    )

    ocorrencia_periodo = (
        InternoOcorrencia.data_ocorrencia >= data_inicio,
        InternoOcorrencia.data_ocorrencia <= data_fim,
    )

    ponto_periodo = (
        InternoPonto.data_ponto >= data_inicio,
        InternoPonto.data_ponto <= data_fim,
    )

    plantoes_total = _count(db, InternoPlantao, *plantao_periodo)

    plantoes_abertos = _count(
        db,
        InternoPlantao,
        *plantao_periodo,
        func.lower(InternoPlantao.status) == "aberto",
    )

    plantoes_finalizados = _count(
        db,
        InternoPlantao,
        *plantao_periodo,
        func.lower(InternoPlantao.status).in_(["finalizado", "encerrado"]),
    )

    passagens_total = _count(db, InternoPassagem, *passagem_periodo)

    passagens_pendentes = _count(
        db,
        InternoPassagem,
        *passagem_periodo,
        func.lower(InternoPassagem.status) == "pendente",
    )

    passagens_recebidas = _count(
        db,
        InternoPassagem,
        *passagem_periodo,
        func.lower(InternoPassagem.status).in_(["recebida", "recebido", "finalizada"]),
    )

    ocorrencias_total = _count(db, InternoOcorrencia, *ocorrencia_periodo)

    ocorrencias_abertas = _count(
        db,
        InternoOcorrencia,
        *ocorrencia_periodo,
        func.lower(InternoOcorrencia.status).in_(["aberta", "em_andamento"]),
    )

    ocorrencias_criticas_abertas = _count(
        db,
        InternoOcorrencia,
        *ocorrencia_periodo,
        func.lower(InternoOcorrencia.status).in_(["aberta", "em_andamento"]),
        func.lower(InternoOcorrencia.prioridade).in_(["critica", "crítica"]),
    )

    ocorrencias_resolvidas = _count(
        db,
        InternoOcorrencia,
        *ocorrencia_periodo,
        func.lower(InternoOcorrencia.status).in_(["resolvida", "fechada", "finalizada"]),
    )

    pontos_total = _count(db, InternoPonto, *ponto_periodo)

    pontos_trabalhando = _count(
        db,
        InternoPonto,
        *ponto_periodo,
        func.lower(InternoPonto.status).in_(["aberto", "trabalhando"]),
    )

    pontos_pausados = _count(
        db,
        InternoPonto,
        *ponto_periodo,
        func.lower(InternoPonto.status).in_(["pausado", "em_pausa"]),
    )

    pontos_finalizados = _count(
        db,
        InternoPonto,
        *ponto_periodo,
        func.lower(InternoPonto.status).in_(["finalizado", "encerrado"]),
    )

    return {
        "plantoes_resumo": {
            "total_hoje": plantoes_total,
            "abertos": plantoes_abertos,
            "finalizados": plantoes_finalizados,
            "em_andamento": plantoes_abertos,
        },
        "passagens_resumo": {
            "total_hoje": passagens_total,
            "pendentes": passagens_pendentes,
            "recebidas": passagens_recebidas,
            "pendentes_hoje": passagens_pendentes,
            "recebidas_hoje": passagens_recebidas,
            "pendentes_total": passagens_pendentes,
        },
        "ocorrencias_resumo": {
            "total_hoje": ocorrencias_total,
            "abertas": ocorrencias_abertas,
            "criticas": ocorrencias_criticas_abertas,
            "criticas_abertas": ocorrencias_criticas_abertas,
            "resolvidas_hoje": ocorrencias_resolvidas,
        },
        "pontos_resumo": {
            "total_hoje": pontos_total,
            "trabalhando": pontos_trabalhando,
            "em_pausa": pontos_pausados,
            "finalizados": pontos_finalizados,
            "ativos_agora": pontos_trabalhando + pontos_pausados,
        },
    }


def _dashboard_pessoal(db: Session, user: dict, *, pode_ponto: bool, pode_plantao: bool, pode_tarefas: bool, pode_comunicados: bool, pode_escala: bool, leituras_comunicados: set[int] | None = None) -> dict:
    hoje = now_local().date()
    funcionario_id = user.get("funcionario_id")
    username = str(user.get("username") or "").strip().lower()

    meu_ponto = None
    if pode_ponto:
        query = db.query(InternoPonto).filter(InternoPonto.data_ponto == hoje)
        if funcionario_id is not None:
            query = query.filter(InternoPonto.funcionario_id == funcionario_id)
        elif username:
            query = query.filter(func.lower(InternoPonto.usuario) == username)
        meu_ponto = ponto_publico(query.order_by(InternoPonto.id.desc()).first())

    meu_plantao = None
    if pode_plantao:
        query = db.query(InternoPlantao).filter(InternoPlantao.data_plantao == hoje)
        if funcionario_id is not None:
            query = query.filter(InternoPlantao.funcionario_id == funcionario_id)
        elif username:
            query = query.filter(func.lower(InternoPlantao.usuario) == username)
        meu_plantao = plantao_publico(query.order_by(InternoPlantao.id.desc()).first())

    minhas_pendencias = 0
    if pode_tarefas:
        query = db.query(InternoTarefa).filter(InternoTarefa.status.in_(["pendente", "em_andamento"]))
        if funcionario_id is not None:
            query = query.filter(InternoTarefa.responsavel_id == funcionario_id)
        else:
            nome = str(user.get("nome") or "").strip().lower()
            if nome or username:
                query = query.filter(func.lower(InternoTarefa.responsavel_nome).in_([v for v in {nome, username} if v]))
            else:
                query = query.filter(InternoTarefa.id == -1)
        minhas_pendencias = int(query.count() or 0)

    comunicados_nao_lidos = 0
    if pode_comunicados:
        lidos = leituras_comunicados or set()
        query = db.query(InternoComunicado).filter(InternoComunicado.ativo.is_(True))
        if lidos:
            query = query.filter(~InternoComunicado.id.in_(lidos))
        comunicados_nao_lidos = int(query.count() or 0)

    proxima_escala = escala_publica(proxima_escala_usuario(db, user)) if pode_escala else None

    return {
        "ponto": meu_ponto,
        "plantao": meu_plantao,
        "minhas_pendencias": minhas_pendencias,
        "comunicados_nao_lidos": comunicados_nao_lidos,
        "proxima_escala": proxima_escala,
        "pode_ponto": pode_ponto,
        "pode_plantao": pode_plantao,
        "pode_tarefas": pode_tarefas,
        "pode_comunicados": pode_comunicados,
        "pode_escala": pode_escala,
    }


@router.get("/interno/dashboard", response_class=HTMLResponse)
async def interno_dashboard(
    request: Request,
    periodo: str | None = None,
    data: str | None = None,
    db: Session = Depends(get_db),
):
    user_or_redirect = require_interno_user_html(request, "/interno/dashboard")
    if isinstance(user_or_redirect, RedirectResponse):
        return user_or_redirect

    filtro = _resolver_periodo_dashboard(periodo, data)

    resumos_periodo = dashboard_resumos_por_periodo(
        db,
        filtro["data_inicio"],
        filtro["data_fim"],
    )

    pode_escala = user_can_access(user_or_redirect, "escala")
    resumo_escala = escala_resumo(db, user_or_redirect) if pode_escala else {}
    escala_hoje = [escala_publica(item) for item in escalas_do_dia(db)][:6] if pode_escala else []

    pode_tarefas = user_can_access(user_or_redirect, "tarefas")
    resumo_tarefas = tarefas_resumo(db, user_or_redirect) if pode_tarefas else {"abertas": 0, "atrasadas": 0, "vencem_hoje": 0, "minhas": 0}
    lista_tarefas = tarefas_dashboard(db, 5) if pode_tarefas else []

    pode_comunicados = user_can_access(user_or_redirect, "comunicados")
    login_comunicados = str(user_or_redirect.get("username") or user_or_redirect.get("nome") or "usuario").strip().lower()
    leituras_comunicados = set()
    if pode_comunicados:
        leituras_comunicados = {
            int(item.comunicado_id)
            for item in db.query(InternoComunicadoLeitura.comunicado_id)
            .filter(InternoComunicadoLeitura.usuario_login == login_comunicados)
            .all()
        }
    comunicados_ultimos = []
    if pode_comunicados:
        for comunicado in (
            db.query(InternoComunicado)
            .filter(InternoComunicado.ativo.is_(True))
            .order_by(InternoComunicado.publicado_em.desc(), InternoComunicado.id.desc())
            .limit(4)
            .all()
        ):
            comunicados_ultimos.append({
                "id": comunicado.id,
                "titulo": comunicado.titulo or "Novo comunicado",
                "mensagem": comunicado.mensagem or "",
                "publicado_em": comunicado.publicado_em or comunicado.criado_em,
                "lido": comunicado.id in leituras_comunicados,
            })

    pode_ponto = user_can_access(user_or_redirect, "ponto")
    pode_plantao = user_can_access(user_or_redirect, "plantao")
    dashboard_pessoal = _dashboard_pessoal(
        db,
        user_or_redirect,
        pode_ponto=pode_ponto,
        pode_plantao=pode_plantao,
        pode_tarefas=pode_tarefas,
        pode_comunicados=pode_comunicados,
        pode_escala=pode_escala,
        leituras_comunicados=leituras_comunicados,
    )

    return templates.TemplateResponse(
        "interno-dashboard.html",
        {
            "request": request,
            "user": user_or_redirect,
            "dashboard_filtro": filtro,
            "dashboard_pessoal": dashboard_pessoal,
            "funcionarios_resumo": funcionarios_resumo(db),
            "pontos_resumo": resumos_periodo["pontos_resumo"],
            "plantoes_resumo": resumos_periodo["plantoes_resumo"],
            "passagens_resumo": resumos_periodo["passagens_resumo"],
            "ocorrencias_resumo": resumos_periodo["ocorrencias_resumo"],
            "tarefas_resumo": resumo_tarefas,
            "tarefas_dashboard": lista_tarefas,
            "tarefas_pode_acessar": pode_tarefas,
            "escala_pode_acessar": pode_escala,
            "escala_resumo": resumo_escala,
            "escala_hoje": escala_hoje,
            "comunicados_pode_acessar": pode_comunicados,
            "comunicados_ultimos": comunicados_ultimos,
        },
    )


@router.get("/interno/comunicados", response_class=HTMLResponse)
async def interno_comunicados_page(request: Request, db: Session = Depends(get_db)):
    user_or_response = require_interno_module_html(request, "/interno/comunicados", "comunicados")
    if isinstance(user_or_response, (RedirectResponse, HTMLResponse)):
        return user_or_response

    login = str(user_or_response.get("username") or user_or_response.get("nome") or "usuario").strip().lower()
    lidos = {
        int(item.comunicado_id)
        for item in db.query(InternoComunicadoLeitura.comunicado_id)
        .filter(InternoComunicadoLeitura.usuario_login == login)
        .all()
    }
    itens = db.query(InternoComunicado).filter(InternoComunicado.ativo.is_(True)).order_by(InternoComunicado.publicado_em.desc(), InternoComunicado.id.desc()).limit(100).all()
    comunicados = [
        {
            "id": item.id,
            "titulo": item.titulo or "Novo comunicado",
            "mensagem": item.mensagem or "",
            "publicado_em": item.publicado_em or item.criado_em,
            "criado_por_nome": item.criado_por_nome or "Administração",
            "lido": item.id in lidos,
        }
        for item in itens
    ]
    return templates.TemplateResponse(
        "interno-comunicados.html",
        {
            "request": request,
            "user": user_or_response,
            "comunicados": comunicados,
            "comunicados_pode_publicar": user_is_admin(user_or_response),
        },
    )


@router.get("/interno/funcionarios", response_class=HTMLResponse)
async def interno_funcionarios_page(request: Request):
    user_or_redirect = require_interno_user_html(request, "/interno/funcionarios")
    if isinstance(user_or_redirect, RedirectResponse):
        return user_or_redirect

    return templates.TemplateResponse(
        "interno-funcionarios.html",
        {
            "request": request,
            "user": user_or_redirect,
            "tipos": FUNCIONARIO_TIPOS,
            "permissoes": FUNCIONARIO_PERMISSOES,
            "modulos": MODULOS_FUNCIONARIOS,
        },
    )


@router.get("/interno/ponto", response_class=HTMLResponse)
async def interno_ponto_page(request: Request, db: Session = Depends(get_db)):
    user_or_redirect = require_interno_user_html(request, "/interno/ponto")
    if isinstance(user_or_redirect, RedirectResponse):
        return user_or_redirect

    return templates.TemplateResponse(
        "interno-ponto.html",
        {
            "request": request,
            "user": user_or_redirect,
            "pontos_resumo": pontos_resumo(db),
        },
    )


@router.get("/interno/plantao", response_class=HTMLResponse)
async def interno_plantao_page(request: Request, db: Session = Depends(get_db)):
    user_or_redirect = require_interno_user_html(request, "/interno/plantao")
    if isinstance(user_or_redirect, RedirectResponse):
        return user_or_redirect

    return templates.TemplateResponse(
        "interno-plantao.html",
        {
            "request": request,
            "user": user_or_redirect,
            "plantoes_resumo": plantoes_resumo(db),
        },
    )


@router.get("/interno/escala", response_class=HTMLResponse)
async def interno_escala_page(request: Request, db: Session = Depends(get_db)):
    user_or_response = require_interno_module_html(request, "/interno/escala", "escala")
    if isinstance(user_or_response, (RedirectResponse, HTMLResponse)):
        return user_or_response

    funcionarios = (
        db.query(InternoFuncionario)
        .filter(InternoFuncionario.ativo.is_(True))
        .order_by(InternoFuncionario.nome.asc())
        .all()
    )
    permissao = str(user_or_response.get("permissao") or "").lower()
    pode_gerenciar = bool(user_or_response.get("is_admin")) or permissao in {"admin", "supervisor"}
    return templates.TemplateResponse(
        "interno-escala.html",
        {
            "request": request,
            "user": user_or_response,
            "funcionarios": funcionarios,
            "escala_resumo": escala_resumo(db, user_or_response),
            "escala_pode_gerenciar": pode_gerenciar,
        },
    )


@router.get("/interno/passagem", response_class=HTMLResponse)
async def interno_passagem_page(request: Request, db: Session = Depends(get_db)):
    user_or_redirect = require_interno_user_html(request, "/interno/passagem")
    if isinstance(user_or_redirect, RedirectResponse):
        return user_or_redirect

    return templates.TemplateResponse(
        "interno-passagem.html",
        {
            "request": request,
            "user": user_or_redirect,
            "passagens_resumo": passagens_resumo(db),
        },
    )


@router.get("/interno/tarefas", response_class=HTMLResponse)
async def interno_tarefas_page(request: Request, db: Session = Depends(get_db)):
    user_or_response = require_interno_module_html(request, "/interno/tarefas", "tarefas")
    if isinstance(user_or_response, (RedirectResponse, HTMLResponse)):
        return user_or_response

    funcionarios = (
        db.query(InternoFuncionario)
        .filter(InternoFuncionario.ativo.is_(True))
        .order_by(InternoFuncionario.nome.asc())
        .all()
    )

    return templates.TemplateResponse(
        "interno-tarefas.html",
        {
            "request": request,
            "user": user_or_response,
            "tarefas_resumo": tarefas_resumo(db, user_or_response),
            "tarefas_prioridades": TAREFA_PRIORIDADES,
            "tarefas_status": TAREFA_STATUS,
            "funcionarios": funcionarios,
        },
    )


@router.get("/interno/documentos", response_class=HTMLResponse)
async def interno_documentos_page(request: Request):
    user_or_response = require_interno_module_html(request, "/interno/documentos", "documentos")
    if isinstance(user_or_response, (RedirectResponse, HTMLResponse)):
        return user_or_response

    return templates.TemplateResponse(
        "interno-documentos.html",
        {
            "request": request,
            "user": user_or_response,
        },
    )


@router.get("/interno/manual", response_class=HTMLResponse)
async def interno_manual_page(request: Request):
    user_or_redirect = require_interno_user_html(request, "/interno/manual")
    if isinstance(user_or_redirect, RedirectResponse):
        return user_or_redirect

    return templates.TemplateResponse(
        "interno-manual.html",
        {
            "request": request,
            "user": user_or_redirect,
        },
    )


@router.get("/interno/ocorrencias", response_class=HTMLResponse)
async def interno_ocorrencias_page(request: Request, db: Session = Depends(get_db)):
    user_or_redirect = require_interno_user_html(request, "/interno/ocorrencias")
    if isinstance(user_or_redirect, RedirectResponse):
        return user_or_redirect

    return templates.TemplateResponse(
        "interno-ocorrencias.html",
        {
            "request": request,
            "user": user_or_redirect,
            "ocorrencias_resumo": ocorrencias_resumo(db),
            "ocorrencia_tipos": OCORRENCIA_TIPOS,
            "ocorrencia_prioridades": OCORRENCIA_PRIORIDADES,
            "ocorrencia_status": OCORRENCIA_STATUS,
        },
    )

@router.get("/interno/auditoria", response_class=HTMLResponse)
async def interno_auditoria_page(request: Request):
    user_or_redirect = require_interno_user_html(request, "/interno/auditoria")
    if isinstance(user_or_redirect, RedirectResponse):
        return user_or_redirect

    from ..deps import user_can_access
    if not user_can_access(user_or_redirect, "auditoria"):
        from ..deps import acesso_negado_html
        return acesso_negado_html("auditoria")

    return templates.TemplateResponse(
        "interno-auditoria.html",
        {"request": request, "user": user_or_redirect},
    )


@router.get("/interno/busca", response_class=HTMLResponse)
async def interno_busca_page(request: Request):
    user_or_redirect = require_interno_user_html(request, "/interno/busca")
    if isinstance(user_or_redirect, RedirectResponse):
        return user_or_redirect

    return templates.TemplateResponse(
        "interno-busca.html",
        {"request": request, "user": user_or_redirect},
    )
