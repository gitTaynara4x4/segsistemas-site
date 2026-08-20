from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .config import settings
from .database import init_db
from .routers import (
    area_cliente_publica,
    auditoria,
    busca,
    escala,
    funcionarios,
    interno_auth,
    interno_pages,
    ocorrencias,
    passagem,
    plantao,
    ponto,
    tarefas,
    notificacoes,
    documentos,
    public,
    proposta_publica,
    status_sistemas,
)


app = FastAPI(
    title=settings.app_title,
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)

app.mount("/static", StaticFiles(directory=settings.static_dir), name="static")


@app.on_event("startup")
def on_startup() -> None:
    # Cria as tabelas internas caso ainda não existam.
    # Depois, quando quiser algo mais profissional, dá para trocar por Alembic.
    init_db()


app.include_router(area_cliente_publica.router)
app.include_router(interno_auth.router)
app.include_router(interno_pages.router)
app.include_router(funcionarios.router)
app.include_router(auditoria.router)
app.include_router(busca.router)
app.include_router(escala.router)
app.include_router(ponto.router)
app.include_router(plantao.router)
app.include_router(passagem.router)
app.include_router(ocorrencias.router)
app.include_router(tarefas.router)
app.include_router(notificacoes.router)
app.include_router(documentos.router)
app.include_router(public.router)
app.include_router(proposta_publica.router)
app.include_router(status_sistemas.router)


print("=== SEG SISTEMAS PATH DEBUG ===")
print("BASE_DIR        :", settings.base_dir)
print("FRONTEND_DIR    :", settings.frontend_dir)
print("TEMPLATES_DIR   :", settings.templates_dir)
print("STATIC_DIR      :", settings.static_dir)
print("VALORA_API_BASE :", settings.valora_api_base)
print("POSTGRES_HOST   :", settings.postgres_host)
print("POSTGRES_PORT   :", settings.postgres_port)
print("POSTGRES_USER   :", settings.postgres_user)
print("POSTGRES_DB     :", settings.postgres_db)
print("================================")
