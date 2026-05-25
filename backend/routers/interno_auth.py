import hmac
from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from ..config import FUNCIONARIO_PERMISSOES, MODULOS_INTERNOS, settings
from ..database import get_db
from ..deps import interno_login_redirect, require_interno_user_api
from ..models import InternoFuncionario
from ..services.interno import normalizar_acessos
from ..security import (
    cookie_secure,
    create_interno_session,
    interno_user_from_request,
    normalizar_usuario_login,
    verify_password,
)
from ..utils import now_utc, safe_lower


router = APIRouter(tags=["Interno - Auth"])
templates = Jinja2Templates(directory=settings.templates_dir)

LOGIN_ERRO_COOKIE = "seg_interno_login_erro"


def _destino_seguro(next_url: str | None) -> str:
    destino = (next_url or "/interno/dashboard").strip()

    if not destino.startswith("/interno"):
        return "/interno/dashboard"

    if destino.startswith("/interno/login"):
        return "/interno/dashboard"

    return destino


def _login_url(next_url: str | None) -> str:
    destino = _destino_seguro(next_url)
    return "/interno/login?next=" + quote(destino, safe="")


def _buscar_funcionario_por_usuario_ou_email(
    db: Session,
    identificador: str,
) -> InternoFuncionario | None:
    identificador_original = (identificador or "").strip().lower()
    identificador_usuario = normalizar_usuario_login(identificador_original)

    if not identificador_original:
        return None

    return (
        db.query(InternoFuncionario)
        .filter(
            or_(
                func.lower(InternoFuncionario.usuario) == identificador_usuario,
                func.lower(InternoFuncionario.email) == identificador_original,
            )
        )
        .first()
    )


def validar_login_interno(db: Session, usuario: str, senha: str) -> dict | None:
    identificador_original = (usuario or "").strip().lower()
    identificador_usuario = normalizar_usuario_login(identificador_original)
    senha_informada = senha or ""

    if not identificador_original or not senha_informada:
        return None

    admin_env_usuario = normalizar_usuario_login(settings.interno_user)
    admin_env_senha = settings.interno_password or ""

    if admin_env_usuario and admin_env_senha:
        usuario_admin_ok = hmac.compare_digest(identificador_usuario, admin_env_usuario)
        senha_admin_ok = hmac.compare_digest(senha_informada, admin_env_senha)

        if usuario_admin_ok and senha_admin_ok:
            return {
                "username": settings.interno_user,
                "nome": "Administrador SEG",
                "perfil": "Administrador interno",
                "tipo": "admin",
                "permissao": "admin",
                "funcionario_id": None,
                "is_admin": True,
                "acessos": list(MODULOS_INTERNOS.keys()),
            }

    funcionario = _buscar_funcionario_por_usuario_ou_email(db, identificador_original)

    if not funcionario:
        return None

    if not bool(funcionario.ativo):
        return None

    if not verify_password(senha_informada, funcionario.senha_hash or ""):
        return None

    funcionario.ultimo_login_em = now_utc()
    db.commit()

    tipo = safe_lower(funcionario.tipo, "plantonista")
    permissao = safe_lower(funcionario.permissao, "operador")

    acessos = normalizar_acessos(funcionario.acessos, permissao, usar_padrao_se_vazio=True)

    return {
        "username": funcionario.usuario or funcionario.email or funcionario.nome,
        "nome": funcionario.nome,
        "perfil": FUNCIONARIO_PERMISSOES.get(permissao, "Acesso interno"),
        "tipo": tipo,
        "permissao": permissao,
        "funcionario_id": funcionario.id,
        "is_admin": permissao == "admin",
        "acessos": acessos,
    }


@router.get("/interno", response_class=HTMLResponse)
async def interno_root(request: Request):
    user = interno_user_from_request(request)

    if user:
        return RedirectResponse(url="/interno/dashboard", status_code=303)

    return interno_login_redirect("/interno/dashboard")


@router.get("/interno/login", response_class=HTMLResponse)
async def interno_login_page(
    request: Request,
    next: str = Query("/interno/dashboard"),
):
    user = interno_user_from_request(request)
    destino = _destino_seguro(next)

    if user:
        return RedirectResponse(url=destino, status_code=303)

    tem_erro_cookie = request.cookies.get(LOGIN_ERRO_COOKIE) == "1"

    erro = ""
    if tem_erro_cookie:
        erro = "Usuário/e-mail ou senha inválidos, ou funcionário inativo."

    response = templates.TemplateResponse(
        "interno-login.html",
        {
            "request": request,
            "erro": erro,
            "next": destino,
        },
    )

    if tem_erro_cookie:
        response.delete_cookie(LOGIN_ERRO_COOKIE, path="/")

    return response


@router.post("/interno/login")
async def interno_login_submit(
    request: Request,
    usuario: str = Form(""),
    senha: str = Form(""),
    next: str = Form("/interno/dashboard"),
    db: Session = Depends(get_db),
):
    destino = _destino_seguro(next)
    user_data = validar_login_interno(db, usuario, senha)

    if not user_data:
        response = RedirectResponse(url=_login_url(destino), status_code=303)
        response.set_cookie(
            key=LOGIN_ERRO_COOKIE,
            value="1",
            max_age=15,
            httponly=True,
            secure=cookie_secure(request),
            samesite="lax",
            path="/",
        )
        return response

    response = RedirectResponse(url=destino, status_code=303)
    response.set_cookie(
        key=settings.interno_cookie_name,
        value=create_interno_session(user_data),
        max_age=settings.interno_session_ttl_seconds,
        httponly=True,
        secure=cookie_secure(request),
        samesite="lax",
        path="/",
    )
    response.delete_cookie(LOGIN_ERRO_COOKIE, path="/")
    return response


@router.post("/interno/logout")
async def interno_logout():
    response = RedirectResponse(url="/interno/login", status_code=303)
    response.delete_cookie(settings.interno_cookie_name, path="/")
    response.delete_cookie(LOGIN_ERRO_COOKIE, path="/")
    return response


@router.get("/api/interno/me")
async def interno_me(request: Request):
    user_or_response = require_interno_user_api(request)

    if isinstance(user_or_response, JSONResponse):
        return user_or_response

    return {
        "ok": True,
        "user": user_or_response,
    }