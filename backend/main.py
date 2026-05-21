import json
import os
from urllib import parse as urllib_parse
from urllib import request as urllib_request
from urllib.error import HTTPError, URLError

from fastapi import FastAPI, Request, Form, Query
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# ============================================================
# APP
# ============================================================
app = FastAPI(
    title="SEG SISTEMAS Site",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json"
)

# ============================================================
# 1) DIRETÓRIOS (ABSOLUTOS)
# ============================================================
CURRENT_FILE = os.path.abspath(__file__)
BASE_DIR = os.path.dirname(os.path.dirname(CURRENT_FILE))

FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")
TEMPLATES_DIR = os.path.join(FRONTEND_DIR, "templates")
STATIC_DIR = os.path.join(FRONTEND_DIR, "static")

# ============================================================
# 2) TEMPLATES + STATIC
# ============================================================
templates = Jinja2Templates(directory=TEMPLATES_DIR)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# ============================================================
# API ValoraCRM
# ============================================================
VALORA_API_BASE = (
    os.getenv("VALORA_API_BASE")
    or os.getenv("AREA_CLIENTE_API_BASE")
    or "http://127.0.0.1:8000"
).rstrip("/")

print("=== SEG SISTEMAS PATH DEBUG ===")
print("BASE_DIR        :", BASE_DIR)
print("FRONTEND_DIR    :", FRONTEND_DIR)
print("TEMPLATES_DIR   :", TEMPLATES_DIR)
print("STATIC_DIR      :", STATIC_DIR)
print("VALORA_API_BASE :", VALORA_API_BASE)
print("================================")

# ============================================================
# FAVICON
# ============================================================
@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    favicon_path = os.path.join(STATIC_DIR, "img", "favicon.png")
    return FileResponse(favicon_path, media_type="image/png")


# ============================================================
# PROXY DA ÁREA DO CLIENTE
# Evita problema de CORS: o navegador chama o site da SEG,
# e o site da SEG repassa para a API do ValoraCRM.
# ============================================================
def _make_valora_url(path: str, query_params: dict | None = None) -> str:
    clean_path = "/" + str(path or "").lstrip("/")
    url = VALORA_API_BASE + clean_path

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


def _proxy_valora_json(
    method: str,
    path: str,
    query_params: dict | None = None,
    payload: dict | None = None,
) -> JSONResponse:
    url = _make_valora_url(path, query_params=query_params)
    body = None

    headers = {
        "Accept": "application/json",
        "User-Agent": "SEG-Sistemas-Site/area-cliente",
    }

    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib_request.Request(
        url=url,
        data=body,
        headers=headers,
        method=method.upper(),
    )

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
                "api_base": VALORA_API_BASE,
            },
        )

    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={
                "detail": "Erro ao consultar a API do ValoraCRM.",
                "erro": str(exc),
            },
        )


@app.get("/api/area-cliente-publica/status")
async def area_cliente_status(acesso: str = Query(...)):
    return _proxy_valora_json(
        "GET",
        "/api/area-cliente-publica/status",
        query_params={"acesso": acesso},
    )


@app.post("/api/area-cliente-publica/autenticar")
async def area_cliente_autenticar(request: Request):
    try:
        payload = await request.json()
    except Exception:
        payload = {}

    return _proxy_valora_json(
        "POST",
        "/api/area-cliente-publica/autenticar",
        payload=payload,
    )


@app.get("/api/area-cliente-publica/dados")
async def area_cliente_obter_dados(session_token: str = Query(...)):
    return _proxy_valora_json(
        "GET",
        "/api/area-cliente-publica/dados",
        query_params={"session_token": session_token},
    )


@app.put("/api/area-cliente-publica/dados")
async def area_cliente_salvar_dados(request: Request):
    try:
        payload = await request.json()
    except Exception:
        payload = {}

    return _proxy_valora_json(
        "PUT",
        "/api/area-cliente-publica/dados",
        payload=payload,
    )


# ============================================================
# ROTAS DO SITE
# ============================================================
@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    return templates.TemplateResponse("inicio.html", {"request": request})


@app.get("/inicio", response_class=HTMLResponse)
async def inicio(request: Request):
    return templates.TemplateResponse("inicio.html", {"request": request})


@app.get("/area-cliente", response_class=HTMLResponse)
async def area_cliente(request: Request):
    return templates.TemplateResponse(
        "area-cliente.html",
        {
            "request": request,
            "valora_api_base": VALORA_API_BASE,
        },
    )


@app.get("/artigos", response_class=HTMLResponse)
async def artigos(request: Request):
    return templates.TemplateResponse("artigos.html", {"request": request})


@app.get("/parceiros", response_class=HTMLResponse)
async def parceiros(request: Request):
    return templates.TemplateResponse("parceiros.html", {"request": request})


@app.get("/empresa", response_class=HTMLResponse)
async def empresa(request: Request):
    return templates.TemplateResponse("empresa.html", {"request": request})


@app.get("/monitoramento-24-horas", response_class=HTMLResponse)
async def monitoramento(request: Request):
    return templates.TemplateResponse("monitoramento-24-horas.html", {"request": request})


@app.get("/deteccao-de-incendios", response_class=HTMLResponse)
async def incendio(request: Request):
    return templates.TemplateResponse("deteccao-de-incendios.html", {"request": request})


@app.get("/rastreamento-veicular", response_class=HTMLResponse)
async def rastreamento(request: Request):
    return templates.TemplateResponse("rastreamento-veicular.html", {"request": request})


@app.get("/telemetria-predial", response_class=HTMLResponse)
async def telemetria(request: Request):
    return templates.TemplateResponse("telemetria-predial.html", {"request": request})


@app.get("/prevencao-de-perdas", response_class=HTMLResponse)
async def perdas(request: Request):
    return templates.TemplateResponse("prevencao-de-perdas.html", {"request": request})


@app.get("/tele-assistencia-idosos", response_class=HTMLResponse)
async def idosos(request: Request):
    return templates.TemplateResponse("tele-assistencia-idosos.html", {"request": request})


@app.get("/automacao-e-seguranca", response_class=HTMLResponse)
async def automacao(request: Request):
    return templates.TemplateResponse("automacao-e-seguranca.html", {"request": request})


@app.get("/facilities", response_class=HTMLResponse)
async def facilities(request: Request):
    return templates.TemplateResponse("facilities.html", {"request": request})


@app.get("/portaria-virtual", response_class=HTMLResponse)
async def portaria(request: Request):
    return templates.TemplateResponse("portaria-virtual.html", {"request": request})


@app.get("/para-sua-familia-e-residencia", response_class=HTMLResponse)
async def familia(request: Request):
    return templates.TemplateResponse("para-sua-familia-e-residencia.html", {"request": request})


@app.get("/para-sua-empresa", response_class=HTMLResponse)
async def empresa_lp(request: Request):
    return templates.TemplateResponse("para-sua-empresa.html", {"request": request})


@app.get("/para-industrial", response_class=HTMLResponse)
async def industrial(request: Request):
    return templates.TemplateResponse("para-industrial.html", {"request": request})


@app.get("/para-condominios", response_class=HTMLResponse)
async def condominios(request: Request):
    return templates.TemplateResponse("para-condominios.html", {"request": request})


@app.get("/para-estacionamentos", response_class=HTMLResponse)
async def estacionamentos(request: Request):
    return templates.TemplateResponse("para-estacionamentos.html", {"request": request})


@app.get("/agronegocio", response_class=HTMLResponse)
async def agronegocio(request: Request):
    return templates.TemplateResponse("agronegocio.html", {"request": request})


@app.get("/obrigado", response_class=HTMLResponse)
async def obrigado(request: Request):
    return templates.TemplateResponse("obrigado.html", {"request": request})


@app.post("/lead")
async def lead(
    nome: str = Form(...),
    whats: str = Form(...),
    tipo: str = Form(...),
    msg: str = Form(""),
):
    print("NOVO LEAD:", {"nome": nome, "whats": whats, "tipo": tipo, "msg": msg})
    return RedirectResponse(url="/obrigado", status_code=303)


@app.get("/api/health")
def health():
    return {"status": "ok"}
