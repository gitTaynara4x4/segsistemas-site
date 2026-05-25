from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from ..config import (
    FUNCIONARIO_PERMISSOES,
    FUNCIONARIO_TIPOS,
    MODULOS_INTERNOS,
    OCORRENCIA_PRIORIDADES,
    OCORRENCIA_STATUS,
    OCORRENCIA_TIPOS,
    settings,
)
from ..database import get_db
from ..deps import require_interno_module_html
from ..services.interno import (
    funcionarios_resumo,
    ocorrencias_resumo,
    passagens_resumo,
    plantoes_resumo,
    pontos_resumo,
)

router = APIRouter(tags=["Interno - Páginas"])
templates = Jinja2Templates(directory=settings.templates_dir)


def _is_response(value) -> bool:
    return isinstance(value, (RedirectResponse, HTMLResponse))


@router.get("/interno/dashboard", response_class=HTMLResponse)
async def interno_dashboard(request: Request, db: Session = Depends(get_db)):
    user_or_response = require_interno_module_html(
        request,
        "/interno/dashboard",
        "dashboard",
    )

    if _is_response(user_or_response):
        return user_or_response

    return templates.TemplateResponse(
        "interno-dashboard.html",
        {
            "request": request,
            "user": user_or_response,
            "funcionarios_resumo": funcionarios_resumo(db),
            "pontos_resumo": pontos_resumo(db),
            "plantoes_resumo": plantoes_resumo(db),
            "passagens_resumo": passagens_resumo(db),
            "ocorrencias_resumo": ocorrencias_resumo(db),
        },
    )


@router.get("/interno/funcionarios", response_class=HTMLResponse)
async def interno_funcionarios_page(request: Request):
    user_or_response = require_interno_module_html(
        request,
        "/interno/funcionarios",
        "funcionarios",
    )

    if _is_response(user_or_response):
        return user_or_response

    return templates.TemplateResponse(
        "interno-funcionarios.html",
        {
            "request": request,
            "user": user_or_response,
            "tipos": FUNCIONARIO_TIPOS,
            "permissoes": FUNCIONARIO_PERMISSOES,
            "modulos": MODULOS_INTERNOS,
        },
    )


@router.get("/interno/ponto", response_class=HTMLResponse)
async def interno_ponto_page(request: Request, db: Session = Depends(get_db)):
    user_or_response = require_interno_module_html(
        request,
        "/interno/ponto",
        "ponto",
    )

    if _is_response(user_or_response):
        return user_or_response

    return templates.TemplateResponse(
        "interno-ponto.html",
        {
            "request": request,
            "user": user_or_response,
            "pontos_resumo": pontos_resumo(db),
        },
    )


@router.get("/interno/plantao", response_class=HTMLResponse)
async def interno_plantao_page(request: Request, db: Session = Depends(get_db)):
    user_or_response = require_interno_module_html(
        request,
        "/interno/plantao",
        "plantao",
    )

    if _is_response(user_or_response):
        return user_or_response

    return templates.TemplateResponse(
        "interno-plantao.html",
        {
            "request": request,
            "user": user_or_response,
            "plantoes_resumo": plantoes_resumo(db),
        },
    )


@router.get("/interno/passagem", response_class=HTMLResponse)
async def interno_passagem_page(request: Request, db: Session = Depends(get_db)):
    user_or_response = require_interno_module_html(
        request,
        "/interno/passagem",
        "passagem",
    )

    if _is_response(user_or_response):
        return user_or_response

    return templates.TemplateResponse(
        "interno-passagem.html",
        {
            "request": request,
            "user": user_or_response,
            "passagens_resumo": passagens_resumo(db),
        },
    )


@router.get("/interno/manual", response_class=HTMLResponse)
async def interno_manual_page(request: Request):
    user_or_response = require_interno_module_html(
        request,
        "/interno/manual",
        "manual",
    )

    if _is_response(user_or_response):
        return user_or_response

    return templates.TemplateResponse(
        "interno-manual.html",
        {
            "request": request,
            "user": user_or_response,
        },
    )


@router.get("/interno/ocorrencias", response_class=HTMLResponse)
async def interno_ocorrencias_page(request: Request, db: Session = Depends(get_db)):
    user_or_response = require_interno_module_html(
        request,
        "/interno/ocorrencias",
        "ocorrencias",
    )

    if _is_response(user_or_response):
        return user_or_response

    return templates.TemplateResponse(
        "interno-ocorrencias.html",
        {
            "request": request,
            "user": user_or_response,
            "ocorrencias_resumo": ocorrencias_resumo(db),
            "ocorrencia_tipos": OCORRENCIA_TIPOS,
            "ocorrencia_prioridades": OCORRENCIA_PRIORIDADES,
            "ocorrencia_status": OCORRENCIA_STATUS,
        },
    )