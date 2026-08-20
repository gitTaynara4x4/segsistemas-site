import json
from datetime import timedelta
from urllib import parse as urllib_parse
from urllib import request as urllib_request
from urllib.error import HTTPError, URLError

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..models import AreaClienteConta
from ..security import (
    cookie_secure,
    create_area_cliente_session,
    hash_password,
    read_area_cliente_session,
    verify_password,
)
from ..services.valora_seg import (
    ValoraSegError,
    localizar_cliente_portal,
    obter_cliente_por_id,
    validar_primeiro_acesso_portal,
)
from ..utils import client_ip, now_utc

router = APIRouter(prefix="/api/area-cliente-publica", tags=["Área do Cliente Pública"])

MAX_LOGIN_FAILURES = 5
LOGIN_BLOCK_MINUTES = 15


def _no_store(content: dict, status_code: int = 200) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=content,
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
        },
    )


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
    response = JSONResponse(status_code=status_code, content=data)
    response.headers["Cache-Control"] = "no-store"
    return response


def _proxy_valora_json(method: str, path: str, query_params: dict | None = None, payload: dict | None = None) -> JSONResponse:
    """Compatibilidade com os links antigos enquanto a nova autenticação é adotada."""
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
    except URLError:
        return _no_store({"detail": "Não foi possível conectar na API do ValoraCRM."}, 502)
    except Exception:
        return _no_store({"detail": "Erro ao consultar a API do ValoraCRM."}, 500)


# ---------------------------------------------------------------------------
# Compatibilidade com o acesso antigo por link/token.
# O novo frontend não depende mais destas rotas.
# ---------------------------------------------------------------------------
@router.get("/status")
async def area_cliente_status(acesso: str = Query(...)):
    return _proxy_valora_json("GET", "/api/area-cliente-publica/status", query_params={"acesso": acesso})


@router.post("/autenticar")
async def area_cliente_autenticar_legado(request: Request):
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    return _proxy_valora_json("POST", "/api/area-cliente-publica/autenticar", payload=payload)


@router.get("/dados")
async def area_cliente_obter_dados_legado(session_token: str = Query(...)):
    return _proxy_valora_json("GET", "/api/area-cliente-publica/dados", query_params={"session_token": session_token})


@router.put("/dados")
async def area_cliente_salvar_dados_legado(request: Request):
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    return _proxy_valora_json("PUT", "/api/area-cliente-publica/dados", payload=payload)


# ---------------------------------------------------------------------------
# Nova autenticação da Área do Cliente SEG.
# ---------------------------------------------------------------------------
def _senha_valida(senha: str) -> bool:
    senha = str(senha or "")
    if len(senha) < 8 or len(senha) > 128:
        return False
    return any(ch.isalpha() for ch in senha) and any(ch.isdigit() for ch in senha)


def _set_area_cookie(response: JSONResponse, request: Request, cliente_id: int, codigo: str) -> None:
    response.set_cookie(
        key=settings.area_cliente_cookie_name,
        value=create_area_cliente_session(cliente_id, codigo),
        max_age=settings.area_cliente_session_ttl_seconds,
        httponly=True,
        secure=cookie_secure(request),
        samesite="lax",
        path="/",
    )


def _get_account(db: Session, cliente_id: int) -> AreaClienteConta | None:
    return db.query(AreaClienteConta).filter(AreaClienteConta.cliente_id == int(cliente_id)).first()


@router.post("/primeiro-acesso")
async def area_cliente_primeiro_acesso(request: Request, db: Session = Depends(get_db)):
    try:
        payload = await request.json()
    except Exception:
        payload = {}

    identificador = str(payload.get("identificador") or "").strip()
    verificacao = str(payload.get("verificacao") or "").strip()
    senha = str(payload.get("senha") or "")
    confirmar_senha = str(payload.get("confirmar_senha") or "")

    if not identificador or not verificacao:
        return _no_store({"detail": "Informe seu código/conta e o CPF/CNPJ ou telefone cadastrado."}, 422)
    if senha != confirmar_senha:
        return _no_store({"detail": "As senhas informadas não conferem."}, 422)
    if not _senha_valida(senha):
        return _no_store({"detail": "Crie uma senha de 8 a 128 caracteres contendo letras e números."}, 422)

    identificador_digitos = "".join(ch for ch in identificador if ch.isdigit())
    verificacao_digitos = "".join(ch for ch in verificacao if ch.isdigit())
    if (
        len(identificador_digitos) in {11, 14}
        and identificador_digitos == verificacao_digitos
    ):
        return _no_store(
            {
                "detail": (
                    "Você usou o CPF/CNPJ como identificador. "
                    "Para confirmar o primeiro acesso, informe o telefone cadastrado no Valora."
                )
            },
            422,
        )

    try:
        validacao = await validar_primeiro_acesso_portal(identificador, verificacao)
    except ValoraSegError as exc:
        if exc.status_code == 401:
            # A mensagem do Valora não contém o dado cadastral; apenas orienta o usuário.
            return _no_store({"detail": exc.detail}, 401)
        if exc.status_code == 404:
            return _no_store(
                {
                    "detail": (
                        "Não encontramos um cliente de monitoramento com esse identificador. "
                        "Use o Código do Cliente ou a Conta Monit24hs."
                    )
                },
                404,
            )
        return _no_store({"detail": exc.detail}, exc.status_code)

    cliente_id = int(validacao.get("cliente_id") or 0)
    codigo = str(validacao.get("codigo") or "").strip()
    conta = str(validacao.get("conta_monit24hs") or "").strip()
    if cliente_id <= 0:
        return _no_store({"detail": "O Valora não retornou um cliente válido."}, 502)

    existente = _get_account(db, cliente_id)
    if existente:
        return _no_store({"detail": "Este cliente já possui acesso criado. Entre usando sua senha."}, 409)

    conta_portal = AreaClienteConta(
        cliente_id=cliente_id,
        codigo_cliente=codigo,
        conta_monit24hs=conta,
        senha_hash=hash_password(senha),
        ativo=True,
        tentativas_falhas=0,
        bloqueado_ate=None,
        criado_em=now_utc(),
        atualizado_em=now_utc(),
        ultimo_login_em=now_utc(),
        ultimo_login_ip=client_ip(request),
    )
    db.add(conta_portal)
    try:
        db.commit()
    except Exception:
        db.rollback()
        # Protege contra corrida de dois primeiros acessos simultâneos.
        if _get_account(db, cliente_id):
            return _no_store({"detail": "Este cliente já possui acesso criado. Entre usando sua senha."}, 409)
        return _no_store({"detail": "Não foi possível criar o acesso agora."}, 500)

    response = _no_store({"ok": True, "primeiro_acesso": True, "cliente_id": cliente_id})
    _set_area_cookie(response, request, cliente_id, codigo)
    return response


@router.post("/login")
async def area_cliente_login(request: Request, db: Session = Depends(get_db)):
    try:
        payload = await request.json()
    except Exception:
        payload = {}

    identificador = str(payload.get("identificador") or "").strip()
    senha = str(payload.get("senha") or "")
    if not identificador or not senha:
        return _no_store({"detail": "Informe seu código/conta e sua senha."}, 422)

    try:
        localizado = await localizar_cliente_portal(identificador)
    except ValoraSegError as exc:
        if exc.status_code in {401, 404}:
            return _no_store({"detail": "Código/conta ou senha inválidos."}, 401)
        return _no_store({"detail": exc.detail}, exc.status_code)

    cliente_id = int(localizado.get("cliente_id") or 0)
    codigo = str(localizado.get("codigo") or "").strip()
    conta_monitor = str(localizado.get("conta_monit24hs") or "").strip()
    account = _get_account(db, cliente_id) if cliente_id > 0 else None

    if not account or not bool(account.ativo):
        return _no_store(
            {
                "detail": "O primeiro acesso deste cliente ainda não foi criado.",
                "primeiro_acesso_necessario": True,
            },
            401,
        )

    agora = now_utc()
    if account.bloqueado_ate and account.bloqueado_ate > agora:
        return _no_store({"detail": "Acesso temporariamente bloqueado após várias tentativas. Aguarde alguns minutos."}, 429)

    if not verify_password(senha, account.senha_hash or ""):
        account.tentativas_falhas = int(account.tentativas_falhas or 0) + 1
        if account.tentativas_falhas >= MAX_LOGIN_FAILURES:
            account.bloqueado_ate = agora + timedelta(minutes=LOGIN_BLOCK_MINUTES)
            account.tentativas_falhas = 0
        account.atualizado_em = agora
        db.commit()
        return _no_store({"detail": "Código/conta ou senha inválidos."}, 401)

    account.tentativas_falhas = 0
    account.bloqueado_ate = None
    account.codigo_cliente = codigo or account.codigo_cliente
    account.conta_monit24hs = conta_monitor or account.conta_monit24hs
    account.ultimo_login_em = agora
    account.ultimo_login_ip = client_ip(request)
    account.atualizado_em = agora
    db.commit()

    response = _no_store({"ok": True, "cliente_id": cliente_id})
    _set_area_cookie(response, request, cliente_id, codigo)
    return response


@router.post("/logout")
async def area_cliente_logout():
    response = _no_store({"ok": True})
    response.delete_cookie(settings.area_cliente_cookie_name, path="/")
    return response


@router.get("/sessao")
async def area_cliente_sessao(request: Request, db: Session = Depends(get_db)):
    sessao = read_area_cliente_session(request)
    if not sessao:
        return _no_store({"ok": False, "autenticado": False}, 401)

    cliente_id = int(sessao.get("sub") or 0)
    account = _get_account(db, cliente_id)
    if not account or not bool(account.ativo):
        return _no_store({"ok": False, "autenticado": False}, 401)

    return _no_store({"ok": True, "autenticado": True, "cliente_id": cliente_id})


@router.get("/portal")
async def area_cliente_portal_integrado(request: Request, db: Session = Depends(get_db)):
    """Retorna o portal somente para a sessão HttpOnly criada pela SEG."""
    sessao = read_area_cliente_session(request)
    if not sessao:
        return _no_store({"detail": "Sua sessão expirou. Entre novamente."}, 401)

    cliente_id = int(sessao.get("sub") or 0)
    account = _get_account(db, cliente_id)
    if cliente_id <= 0 or not account or not bool(account.ativo):
        return _no_store({"detail": "Acesso não autorizado."}, 401)

    try:
        dados_privados = await obter_cliente_por_id(cliente_id)
        portal_info = dados_privados.get("portal") if isinstance(dados_privados, dict) else {}
        portal_info = portal_info if isinstance(portal_info, dict) else {}

        if portal_info.get("elegivel") is not True:
            return _no_store(
                {
                    "detail": "Este acesso não está liberado para a Área do Cliente SEG.",
                    "motivo": portal_info.get("motivo"),
                },
                403,
            )

        cliente = dados_privados.get("cliente") or {}
        monitoramento = dados_privados.get("monitoramento") or {}
        codigo = str(cliente.get("codigo") or account.codigo_cliente or "")
        conta_monit = str(monitoramento.get("conta_monit24hs") or account.conta_monit24hs or "")
        if codigo != account.codigo_cliente or conta_monit != account.conta_monit24hs:
            account.codigo_cliente = codigo
            account.conta_monit24hs = conta_monit
            account.atualizado_em = now_utc()
            db.commit()

        payload = {
            "ok": True,
            "fonte": "valora_tempo_real",
            "acesso": {
                "cliente_id": cliente_id,
                "codigo_cliente": codigo,
            },
            "cliente": cliente,
            "portal": dados_privados.get("portal") or {},
            "monitoramento": monitoramento,
            "contatos": dados_privados.get("contatos") or {},
            "endereco": dados_privados.get("endereco") or {},
            "financeiro": dados_privados.get("financeiro") or {
                "disponivel": False,
                "total_titulos": 0,
                "resumo": None,
                "titulos": [],
                "truncado": False,
            },
            "consulta_em": dados_privados.get("consulta_em"),
        }
        return _no_store(payload)

    except ValoraSegError as exc:
        return _no_store({"detail": exc.detail}, exc.status_code)
