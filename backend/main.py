import os
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
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
# Estrutura esperada:
# SITE-SEG-SISTEMAS/
#   backend/main.py
#   frontend/
#     templates/
#     static/
#       css/
#       img/
#       js/
# ============================================================
CURRENT_FILE = os.path.abspath(__file__)
BASE_DIR = os.path.dirname(os.path.dirname(CURRENT_FILE))  # sai do backend e vai para raiz

FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")
TEMPLATES_DIR = os.path.join(FRONTEND_DIR, "templates")
STATIC_DIR = os.path.join(FRONTEND_DIR, "static")

# ============================================================
# 2) TEMPLATES + STATIC (ESSA LINHA RESOLVE url_for('static',...))
# ============================================================
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# IMPORTANTE: name="static" é obrigatório para url_for('static', filename=...)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# ============================================================
# (Opcional) Debug de caminhos no terminal
# ============================================================
print("=== SEG SISTEMAS PATH DEBUG ===")
print("BASE_DIR     :", BASE_DIR)
print("FRONTEND_DIR :", FRONTEND_DIR)
print("TEMPLATES_DIR:", TEMPLATES_DIR)
print("STATIC_DIR   :", STATIC_DIR)
print("===============================")

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return RedirectResponse(url="/static/img/favicon.png")

# ============================================================
# 3) ROTAS (PÁGINAS)
# ============================================================

# Home / Início
@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    return templates.TemplateResponse("inicio.html", {"request": request})

@app.get("/inicio", response_class=HTMLResponse)
async def inicio(request: Request):
    return templates.TemplateResponse("inicio.html", {"request": request})

#ARTIGOS
@app.get("/artigos", response_class=HTMLResponse)
async def inicio(request: Request):
    return templates.TemplateResponse("artigos.html", {"request": request})

# Institucional
@app.get("/empresa", response_class=HTMLResponse)
async def empresa(request: Request):
    return templates.TemplateResponse("empresa.html", {"request": request})

# Serviços
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

# Segmentos (Landing Pages)
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

# Health Check
@app.get("/api/health")
def health():
    return {"status": "ok"}
