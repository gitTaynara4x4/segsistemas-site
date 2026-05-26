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
    settings,
)
from ..database import get_db
from ..deps import require_interno_user_html
from ..models import (
    InternoOcorrencia,
    InternoPassagem,
    InternoPlantao,
    InternoPonto,
)
from ..services.interno import (
    funcionarios_resumo,
    ocorrencias_resumo,
    passagens_resumo,
    plantoes_resumo,
    pontos_resumo,
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
    "manual": {
        "label": "Manual Interno",
        "nome": "Manual Interno",
        "descricao": "Procedimentos de atendimento, alarme e rotina operacional.",
        "icon": "fa-regular fa-folder-open",
        "icone": "fa-regular fa-folder-open",
        "path": "/interno/manual",
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

    return templates.TemplateResponse(
        "interno-dashboard.html",
        {
            "request": request,
            "user": user_or_redirect,
            "dashboard_filtro": filtro,
            "funcionarios_resumo": funcionarios_resumo(db),
            "pontos_resumo": resumos_periodo["pontos_resumo"],
            "plantoes_resumo": resumos_periodo["plantoes_resumo"],
            "passagens_resumo": resumos_periodo["passagens_resumo"],
            "ocorrencias_resumo": resumos_periodo["ocorrencias_resumo"],
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