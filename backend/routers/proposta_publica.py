from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, JSONResponse

from ..config import settings
from ..services.valora_seg import (
    ValoraSegError,
    aprovar_proposta_cliente,
    concluir_cadastro_contrato_proposta,
    obter_cadastro_contrato_proposta,
    obter_proposta_cliente,
    solicitar_alteracao_proposta_cliente,
)
from ..utils import client_ip

router = APIRouter(tags=["Proposta pública SEG"])


def _headers() -> dict[str, str]:
    return {
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
        "Pragma": "no-cache",
        "Expires": "0",
        "Referrer-Policy": "no-referrer",
        "X-Robots-Tag": "noindex, nofollow, noarchive",
    }


def _json(payload: dict, status_code: int = 200) -> JSONResponse:
    return JSONResponse(payload, status_code=status_code, headers=_headers())


def _metadata(request: Request) -> dict[str, str]:
    return {
        "client_ip": client_ip(request),
        "user_agent": str(request.headers.get("user-agent") or "")[:500],
    }


def _error(exc: ValoraSegError) -> JSONResponse:
    return _json({"detail": exc.detail}, exc.status_code)


@router.get("/proposta/{token}", include_in_schema=False)
async def proposta_cliente_page(token: str):
    path = Path(settings.templates_dir) / "proposta-cliente.html"
    if not path.exists():
        return _json({"detail": "Página da proposta não encontrada."}, 404)
    return FileResponse(path, headers=_headers())


@router.get("/api/proposta-publica/{token}")
async def proposta_cliente_dados(token: str, request: Request):
    try:
        return _json(await obter_proposta_cliente(token, **_metadata(request)))
    except ValoraSegError as exc:
        return _error(exc)


@router.post("/api/proposta-publica/{token}/aprovar")
async def proposta_cliente_aprovar(token: str, request: Request):
    try:
        return _json(await aprovar_proposta_cliente(token, **_metadata(request)))
    except ValoraSegError as exc:
        return _error(exc)


@router.post("/api/proposta-publica/{token}/solicitar-alteracao")
async def proposta_cliente_solicitar_alteracao(token: str, request: Request):
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    try:
        return _json(
            await solicitar_alteracao_proposta_cliente(
                token,
                str(payload.get("mensagem") or ""),
                **_metadata(request),
            )
        )
    except ValoraSegError as exc:
        return _error(exc)


@router.get("/api/proposta-publica/{token}/cadastro-contrato")
async def proposta_cliente_cadastro(token: str, request: Request):
    try:
        return _json(await obter_cadastro_contrato_proposta(token, **_metadata(request)))
    except ValoraSegError as exc:
        return _error(exc)


@router.post("/api/proposta-publica/{token}/cadastro-contrato")
async def proposta_cliente_cadastro_concluir(token: str, request: Request):
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    try:
        return _json(await concluir_cadastro_contrato_proposta(token, payload, **_metadata(request)))
    except ValoraSegError as exc:
        return _error(exc)
