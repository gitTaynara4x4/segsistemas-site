import os

from fastapi import APIRouter, Form, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from ..config import settings

router = APIRouter(tags=["Site Público"])
templates = Jinja2Templates(directory=settings.templates_dir)


@router.get("/favicon.ico", include_in_schema=False)
async def favicon():
    favicon_path = os.path.join(settings.static_dir, "img", "favicon.png")
    return FileResponse(favicon_path, media_type="image/png")


@router.get("/", response_class=HTMLResponse)
async def root(request: Request):
    return templates.TemplateResponse("inicio.html", {"request": request})


@router.get("/inicio", response_class=HTMLResponse)
async def inicio(request: Request):
    return templates.TemplateResponse("inicio.html", {"request": request})


@router.get("/area-cliente", response_class=HTMLResponse)
async def area_cliente(request: Request):
    return templates.TemplateResponse("area-cliente.html", {"request": request, "valora_api_base": settings.valora_api_base})


@router.get("/artigos", response_class=HTMLResponse)
async def artigos(request: Request):
    return templates.TemplateResponse("artigos.html", {"request": request})


@router.get("/parceiros", response_class=HTMLResponse)
async def parceiros(request: Request):
    return templates.TemplateResponse("parceiros.html", {"request": request})


@router.get("/empresa", response_class=HTMLResponse)
async def empresa(request: Request):
    return templates.TemplateResponse("empresa.html", {"request": request})


@router.get("/monitoramento-24-horas", response_class=HTMLResponse)
async def monitoramento(request: Request):
    return templates.TemplateResponse("monitoramento-24-horas.html", {"request": request})


@router.get("/deteccao-de-incendios", response_class=HTMLResponse)
async def incendio(request: Request):
    return templates.TemplateResponse("deteccao-de-incendios.html", {"request": request})


@router.get("/rastreamento-veicular", response_class=HTMLResponse)
async def rastreamento(request: Request):
    return templates.TemplateResponse("rastreamento-veicular.html", {"request": request})


@router.get("/telemetria-predial", response_class=HTMLResponse)
async def telemetria(request: Request):
    return templates.TemplateResponse("telemetria-predial.html", {"request": request})


@router.get("/prevencao-de-perdas", response_class=HTMLResponse)
async def perdas(request: Request):
    return templates.TemplateResponse("prevencao-de-perdas.html", {"request": request})


@router.get("/tele-assistencia-idosos", response_class=HTMLResponse)
async def idosos(request: Request):
    return templates.TemplateResponse("tele-assistencia-idosos.html", {"request": request})


@router.get("/automacao-e-seguranca", response_class=HTMLResponse)
async def automacao(request: Request):
    return templates.TemplateResponse("automacao-e-seguranca.html", {"request": request})


@router.get("/facilities", response_class=HTMLResponse)
async def facilities(request: Request):
    return templates.TemplateResponse("facilities.html", {"request": request})


@router.get("/portaria-virtual", response_class=HTMLResponse)
async def portaria(request: Request):
    return templates.TemplateResponse("portaria-virtual.html", {"request": request})


@router.get("/para-sua-familia-e-residencia", response_class=HTMLResponse)
async def familia(request: Request):
    return templates.TemplateResponse("para-sua-familia-e-residencia.html", {"request": request})


@router.get("/para-sua-empresa", response_class=HTMLResponse)
async def empresa_lp(request: Request):
    return templates.TemplateResponse("para-sua-empresa.html", {"request": request})


@router.get("/para-industrial", response_class=HTMLResponse)
async def industrial(request: Request):
    return templates.TemplateResponse("para-industrial.html", {"request": request})


@router.get("/para-condominios", response_class=HTMLResponse)
async def condominios(request: Request):
    return templates.TemplateResponse("para-condominios.html", {"request": request})


@router.get("/para-estacionamentos", response_class=HTMLResponse)
async def estacionamentos(request: Request):
    return templates.TemplateResponse("para-estacionamentos.html", {"request": request})


@router.get("/agronegocio", response_class=HTMLResponse)
async def agronegocio(request: Request):
    return templates.TemplateResponse("agronegocio.html", {"request": request})


@router.get("/obrigado", response_class=HTMLResponse)
async def obrigado(request: Request):
    return templates.TemplateResponse("obrigado.html", {"request": request})


@router.post("/lead")
async def lead(nome: str = Form(...), whats: str = Form(...), tipo: str = Form(...), msg: str = Form("")):
    print("NOVO LEAD:", {"nome": nome, "whats": whats, "tipo": tipo, "msg": msg})
    return RedirectResponse(url="/obrigado", status_code=303)


@router.get("/api/health")
def health():
    return {"status": "ok"}
