import json
from urllib import parse as urllib_parse
from urllib import request as urllib_request
from urllib.error import HTTPError, URLError

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

from ..config import settings

router = APIRouter(prefix="/api/area-cliente-publica", tags=["Área do Cliente Pública"])


def _make_valora_url(path: str, query_params: dict | None = None) -> str:
    clean_path = "/" + str(path or "").lstrip("/")
    url = settings.valora_api_base + clean_path

    if query_params:
        clean_query = {
            key: value
            for key, value in query_params.items()
            if value is not None and str(value).strip() != ""
        }
        if clean_query:
            url += "?" + urllib_parse.urlencode(clean_query)
    return url


def _json_response_from_text(status_code: int, text: str) -> JSONResponse:
    try:
        data = json.loads(text) if text else {}
    except Exception:
        data = {"detail": text or "Resposta inválida da API do ValoraCRM."}
    return JSONResponse(status_code=status_code, content=data)


def _proxy_valora_json(method: str, path: str, query_params: dict | None = None, payload: dict | None = None) -> JSONResponse:
    url = _make_valora_url(path, query_params=query_params)
    body = None
    headers = {"Accept": "application/json", "User-Agent": "SEG-Sistemas-Site/area-cliente"}

    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib_request.Request(url=url, data=body, headers=headers, method=method.upper())

    try:
        with urllib_request.urlopen(req, timeout=25) as resp:
            text = resp.read().decode("utf-8", errors="replace")
            return _json_response_from_text(resp.status, text)
    except HTTPError as exc:
        text = exc.read().decode("utf-8", errors="replace")
        return _json_response_from_text(exc.code, text)
    except URLError as exc:
        return JSONResponse(
            status_code=502,
            content={
                "detail": "Não foi possível conectar na API do ValoraCRM.",
                "erro": str(exc.reason),
                "api_base": settings.valora_api_base,
            },
        )
    except Exception as exc:
        return JSONResponse(status_code=500, content={"detail": "Erro ao consultar a API do ValoraCRM.", "erro": str(exc)})


@router.get("/status")
async def area_cliente_status(acesso: str = Query(...)):
    return _proxy_valora_json("GET", "/api/area-cliente-publica/status", query_params={"acesso": acesso})


@router.post("/autenticar")
async def area_cliente_autenticar(request: Request):
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    return _proxy_valora_json("POST", "/api/area-cliente-publica/autenticar", payload=payload)


@router.get("/dados")
async def area_cliente_obter_dados(session_token: str = Query(...)):
    return _proxy_valora_json("GET", "/api/area-cliente-publica/dados", query_params={"session_token": session_token})


@router.put("/dados")
async def area_cliente_salvar_dados(request: Request):
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    return _proxy_valora_json("PUT", "/api/area-cliente-publica/dados", payload=payload)
