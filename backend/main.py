import base64
import hashlib
import hmac
import json
import os
import time
from datetime import datetime, timezone
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

# Dados simples do painel interno.
# Parte 2: por enquanto usamos JSON local para não misturar com banco.
BACKEND_DIR = os.path.join(BASE_DIR, "backend")
INTERNO_DATA_DIR = os.path.join(BACKEND_DIR, "data")
INTERNO_FUNCIONARIOS_FILE = os.path.join(INTERNO_DATA_DIR, "interno_funcionarios.json")

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

# ============================================================
# LOGIN INTERNO SEG
# Parte 1: login simples, dashboard privado e sessão por cookie.
# Parte 2: cadastro de funcionários em JSON e login pelos funcionários ativos.
# ============================================================
INTERNO_COOKIE_NAME = "seg_interno_session"
INTERNO_SESSION_TTL_SECONDS = int(os.getenv("SEG_INTERNO_SESSION_TTL_SECONDS", "28800"))  # 8 horas

# Admin raiz para primeiro acesso. Depois você cadastra os funcionários pela tela.
# Configure no EasyPanel, se possível:
# SEG_INTERNO_USER=admin
# SEG_INTERNO_PASSWORD=sua-senha-forte
# SEG_INTERNO_SECRET=uma-chave-grande-aleatoria
INTERNO_USER = (os.getenv("SEG_INTERNO_USER") or "admin").strip()
INTERNO_PASSWORD = os.getenv("SEG_INTERNO_PASSWORD") or "seg123"
INTERNO_SECRET = os.getenv("SEG_INTERNO_SECRET") or "troque-essa-chave-interna-seg-sistemas"

FUNCIONARIO_TIPOS = {
    "plantonista": "Plantonista",
    "tecnico": "Técnico",
    "administrativo": "Administrativo",
    "gerente": "Gerente",
}

FUNCIONARIO_PERMISSOES = {
    "operador": "Operador",
    "supervisor": "Supervisor",
    "admin": "Administrador",
}

print("=== SEG SISTEMAS PATH DEBUG ===")
print("BASE_DIR                 :", BASE_DIR)
print("FRONTEND_DIR             :", FRONTEND_DIR)
print("TEMPLATES_DIR            :", TEMPLATES_DIR)
print("STATIC_DIR               :", STATIC_DIR)
print("VALORA_API_BASE          :", VALORA_API_BASE)
print("INTERNO_USER             :", INTERNO_USER)
print("INTERNO_FUNCIONARIOS_FILE:", INTERNO_FUNCIONARIOS_FILE)
print("================================")


# ============================================================
# HELPERS GERAIS
# ============================================================
def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_str(value, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip()


def _safe_lower(value, default: str = "") -> str:
    return _safe_str(value, default).lower()


def _ensure_interno_data_dir() -> None:
    os.makedirs(INTERNO_DATA_DIR, exist_ok=True)


# ============================================================
# HELPERS DE SENHA DOS FUNCIONÁRIOS
# ============================================================
def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode((value + padding).encode("utf-8"))


def _hash_password(password: str) -> str:
    """
    Hash simples e seguro com biblioteca padrão.
    Formato salvo: pbkdf2_sha256$iteracoes$salt$hash
    """
    senha = password or ""
    iterations = 160_000
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", senha.encode("utf-8"), salt, iterations)
    return "pbkdf2_sha256${}${}${}".format(
        iterations,
        _b64url_encode(salt),
        _b64url_encode(digest),
    )


def _verify_password(password: str, stored_hash: str) -> bool:
    try:
        algo, iter_str, salt_b64, digest_b64 = (stored_hash or "").split("$", 3)
        if algo != "pbkdf2_sha256":
            return False

        iterations = int(iter_str)
        salt = _b64url_decode(salt_b64)
        expected = _b64url_decode(digest_b64)
        got = hashlib.pbkdf2_hmac("sha256", (password or "").encode("utf-8"), salt, iterations)
        return hmac.compare_digest(got, expected)
    except Exception:
        return False


# ============================================================
# HELPERS DE FUNCIONÁRIOS EM JSON
# ============================================================
def _load_funcionarios() -> list[dict]:
    _ensure_interno_data_dir()

    if not os.path.exists(INTERNO_FUNCIONARIOS_FILE):
        return []

    try:
        with open(INTERNO_FUNCIONARIOS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, dict):
            funcionarios = data.get("funcionarios") or []
        else:
            funcionarios = data

        if not isinstance(funcionarios, list):
            return []

        return [f for f in funcionarios if isinstance(f, dict)]
    except Exception as exc:
        print("[SEG INTERNO] Falha ao ler funcionários:", exc)
        return []


def _save_funcionarios(funcionarios: list[dict]) -> None:
    _ensure_interno_data_dir()

    payload = {
        "versao": 1,
        "atualizado_em": _now_iso(),
        "funcionarios": funcionarios,
    }

    tmp_file = INTERNO_FUNCIONARIOS_FILE + ".tmp"
    with open(tmp_file, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    os.replace(tmp_file, INTERNO_FUNCIONARIOS_FILE)


def _next_funcionario_id(funcionarios: list[dict]) -> int:
    maior = 0
    for funcionario in funcionarios:
        try:
            maior = max(maior, int(funcionario.get("id") or 0))
        except Exception:
            continue
    return maior + 1


def _normalizar_usuario_login(usuario: str) -> str:
    return _safe_lower(usuario).replace(" ", "")


def _funcionario_publico(funcionario: dict) -> dict:
    tipo = _safe_lower(funcionario.get("tipo"), "plantonista")
    permissao = _safe_lower(funcionario.get("permissao"), "operador")

    return {
        "id": funcionario.get("id"),
        "nome": funcionario.get("nome") or "",
        "telefone": funcionario.get("telefone") or "",
        "email": funcionario.get("email") or "",
        "cargo": funcionario.get("cargo") or "",
        "tipo": tipo,
        "tipo_label": FUNCIONARIO_TIPOS.get(tipo, tipo.title()),
        "usuario": funcionario.get("usuario") or "",
        "permissao": permissao,
        "permissao_label": FUNCIONARIO_PERMISSOES.get(permissao, permissao.title()),
        "ativo": bool(funcionario.get("ativo", True)),
        "criado_em": funcionario.get("criado_em") or "",
        "atualizado_em": funcionario.get("atualizado_em") or "",
        "ultimo_login_em": funcionario.get("ultimo_login_em") or "",
        "tem_senha": bool(funcionario.get("senha_hash")),
    }


def _find_funcionario_by_id(funcionarios: list[dict], funcionario_id: int) -> dict | None:
    for funcionario in funcionarios:
        try:
            if int(funcionario.get("id") or 0) == int(funcionario_id):
                return funcionario
        except Exception:
            continue
    return None


def _find_funcionario_by_usuario(funcionarios: list[dict], usuario: str) -> dict | None:
    usuario_norm = _normalizar_usuario_login(usuario)
    if not usuario_norm:
        return None

    for funcionario in funcionarios:
        if _normalizar_usuario_login(funcionario.get("usuario")) == usuario_norm:
            return funcionario
    return None


def _funcionarios_resumo() -> dict:
    funcionarios = [_funcionario_publico(f) for f in _load_funcionarios()]
    ativos = [f for f in funcionarios if f.get("ativo")]
    inativos = [f for f in funcionarios if not f.get("ativo")]
    plantonistas = [f for f in ativos if f.get("tipo") == "plantonista"]

    return {
        "total": len(funcionarios),
        "ativos": len(ativos),
        "inativos": len(inativos),
        "plantonistas": len(plantonistas),
    }


def _validar_payload_funcionario(payload: dict, criando: bool = True) -> tuple[dict | None, str | None]:
    nome = _safe_str(payload.get("nome"))
    usuario = _normalizar_usuario_login(payload.get("usuario"))
    telefone = _safe_str(payload.get("telefone"))
    email = _safe_lower(payload.get("email"))
    cargo = _safe_str(payload.get("cargo"))
    tipo = _safe_lower(payload.get("tipo"), "plantonista")
    permissao = _safe_lower(payload.get("permissao"), "operador")
    senha = str(payload.get("senha") or "")

    if not nome:
        return None, "Informe o nome do funcionário."

    if not usuario:
        return None, "Informe o usuário de login."

    if len(usuario) < 3:
        return None, "O usuário precisa ter pelo menos 3 caracteres."

    if tipo not in FUNCIONARIO_TIPOS:
        return None, "Tipo de funcionário inválido."

    if permissao not in FUNCIONARIO_PERMISSOES:
        return None, "Permissão inválida."

    if criando and len(senha) < 4:
        return None, "Informe uma senha com pelo menos 4 caracteres."

    if senha and len(senha) < 4:
        return None, "A nova senha precisa ter pelo menos 4 caracteres."

    ativo = payload.get("ativo", True)
    if isinstance(ativo, str):
        ativo = ativo.lower() not in {"false", "0", "nao", "não", "inativo"}
    else:
        ativo = bool(ativo)

    return {
        "nome": nome,
        "usuario": usuario,
        "telefone": telefone,
        "email": email,
        "cargo": cargo,
        "tipo": tipo,
        "permissao": permissao,
        "ativo": ativo,
        "senha": senha,
    }, None


# ============================================================
# HELPERS DE SESSÃO INTERNA
# ============================================================
def _sign_session_payload(payload_b64: str) -> str:
    return hmac.new(
        INTERNO_SECRET.encode("utf-8"),
        payload_b64.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _create_interno_session(user_data: dict) -> str:
    now = int(time.time())
    payload = {
        "sub": user_data.get("username") or user_data.get("usuario") or INTERNO_USER,
        "nome": user_data.get("nome") or user_data.get("username") or INTERNO_USER,
        "perfil": user_data.get("perfil") or "Acesso interno",
        "tipo": user_data.get("tipo") or "admin",
        "permissao": user_data.get("permissao") or "admin",
        "funcionario_id": user_data.get("funcionario_id"),
        "is_admin": bool(user_data.get("is_admin")),
        "iat": now,
        "exp": now + INTERNO_SESSION_TTL_SECONDS,
    }
    payload_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = _sign_session_payload(payload_b64)
    return f"{payload_b64}.{signature}"


def _read_interno_session(request: Request) -> dict | None:
    token = request.cookies.get(INTERNO_COOKIE_NAME)
    if not token or "." not in token:
        return None

    try:
        payload_b64, signature = token.split(".", 1)
        expected = _sign_session_payload(payload_b64)

        if not hmac.compare_digest(signature, expected):
            return None

        payload = json.loads(_b64url_decode(payload_b64).decode("utf-8"))
        exp = int(payload.get("exp") or 0)

        if exp < int(time.time()):
            return None

        username = str(payload.get("sub") or "").strip()
        if not username:
            return None

        return payload

    except Exception:
        return None


def _interno_user_from_request(request: Request) -> dict | None:
    payload = _read_interno_session(request)
    if not payload:
        return None

    username = payload.get("sub") or INTERNO_USER
    nome = payload.get("nome") or username
    perfil = payload.get("perfil") or "Acesso interno"

    return {
        "username": username,
        "nome": nome,
        "perfil": perfil,
        "tipo": payload.get("tipo") or "admin",
        "permissao": payload.get("permissao") or "admin",
        "funcionario_id": payload.get("funcionario_id"),
        "is_admin": bool(payload.get("is_admin")),
    }


def _validar_login_interno(usuario: str, senha: str) -> dict | None:
    usuario_limpo = _normalizar_usuario_login(usuario)
    senha_informada = senha or ""

    # Admin raiz via variável de ambiente.
    usuario_admin_ok = hmac.compare_digest(usuario_limpo, _normalizar_usuario_login(INTERNO_USER))
    senha_admin_ok = hmac.compare_digest(senha_informada, INTERNO_PASSWORD)

    if usuario_admin_ok and senha_admin_ok:
        return {
            "username": INTERNO_USER,
            "nome": "Administrador SEG",
            "perfil": "Administrador interno",
            "tipo": "admin",
            "permissao": "admin",
            "funcionario_id": None,
            "is_admin": True,
        }

    funcionarios = _load_funcionarios()
    funcionario = _find_funcionario_by_usuario(funcionarios, usuario_limpo)

    if not funcionario:
        return None

    if not bool(funcionario.get("ativo", True)):
        return None

    if not _verify_password(senha_informada, funcionario.get("senha_hash") or ""):
        return None

    funcionario["ultimo_login_em"] = _now_iso()
    _save_funcionarios(funcionarios)

    tipo = _safe_lower(funcionario.get("tipo"), "plantonista")
    permissao = _safe_lower(funcionario.get("permissao"), "operador")

    return {
        "username": funcionario.get("usuario"),
        "nome": funcionario.get("nome"),
        "perfil": FUNCIONARIO_PERMISSOES.get(permissao, "Acesso interno"),
        "tipo": tipo,
        "permissao": permissao,
        "funcionario_id": funcionario.get("id"),
        "is_admin": permissao == "admin",
    }


def _interno_login_redirect(next_url: str = "/interno/dashboard") -> RedirectResponse:
    return RedirectResponse(url=f"/interno/login?next={urllib_parse.quote(next_url)}", status_code=303)


def _cookie_secure(request: Request) -> bool:
    forwarded_proto = (request.headers.get("x-forwarded-proto") or "").lower().strip()
    if forwarded_proto == "https":
        return True
    return request.url.scheme == "https"


def _require_interno_user_html(request: Request, next_url: str) -> dict | RedirectResponse:
    user = _interno_user_from_request(request)
    if not user:
        return _interno_login_redirect(next_url)
    return user


def _require_interno_user_api(request: Request) -> dict | JSONResponse:
    user = _interno_user_from_request(request)
    if not user:
        return JSONResponse(status_code=401, content={"ok": False, "detail": "Não autenticado."})
    return user


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
# ROTAS INTERNAS SEG - PÁGINAS
# ============================================================
@app.get("/interno", response_class=HTMLResponse)
async def interno_root(request: Request):
    user = _interno_user_from_request(request)
    if user:
        return RedirectResponse(url="/interno/dashboard", status_code=303)
    return _interno_login_redirect("/interno/dashboard")


@app.get("/interno/login", response_class=HTMLResponse)
async def interno_login_page(request: Request, next: str = Query("/interno/dashboard")):
    user = _interno_user_from_request(request)
    if user:
        return RedirectResponse(url=next or "/interno/dashboard", status_code=303)

    return templates.TemplateResponse(
        "interno-login.html",
        {
            "request": request,
            "erro": "",
            "next": next or "/interno/dashboard",
        },
    )


@app.post("/interno/login", response_class=HTMLResponse)
async def interno_login_submit(
    request: Request,
    usuario: str = Form(...),
    senha: str = Form(...),
    next: str = Form("/interno/dashboard"),
):
    usuario_limpo = _normalizar_usuario_login(usuario)
    user_data = _validar_login_interno(usuario_limpo, senha or "")

    if not user_data:
        return templates.TemplateResponse(
            "interno-login.html",
            {
                "request": request,
                "erro": "Usuário ou senha inválidos, ou funcionário inativo.",
                "next": next or "/interno/dashboard",
                "usuario": usuario_limpo,
            },
            status_code=401,
        )

    destino = next or "/interno/dashboard"
    if not destino.startswith("/interno"):
        destino = "/interno/dashboard"

    response = RedirectResponse(url=destino, status_code=303)
    response.set_cookie(
        key=INTERNO_COOKIE_NAME,
        value=_create_interno_session(user_data),
        max_age=INTERNO_SESSION_TTL_SECONDS,
        httponly=True,
        secure=_cookie_secure(request),
        samesite="lax",
        path="/",
    )
    return response


@app.post("/interno/logout")
async def interno_logout():
    response = RedirectResponse(url="/interno/login", status_code=303)
    response.delete_cookie(INTERNO_COOKIE_NAME, path="/")
    return response


@app.get("/interno/dashboard", response_class=HTMLResponse)
async def interno_dashboard(request: Request):
    user_or_redirect = _require_interno_user_html(request, "/interno/dashboard")
    if isinstance(user_or_redirect, RedirectResponse):
        return user_or_redirect

    return templates.TemplateResponse(
        "interno-dashboard.html",
        {
            "request": request,
            "user": user_or_redirect,
            "funcionarios_resumo": _funcionarios_resumo(),
        },
    )


@app.get("/interno/funcionarios", response_class=HTMLResponse)
async def interno_funcionarios_page(request: Request):
    user_or_redirect = _require_interno_user_html(request, "/interno/funcionarios")
    if isinstance(user_or_redirect, RedirectResponse):
        return user_or_redirect

    return templates.TemplateResponse(
        "interno-funcionarios.html",
        {
            "request": request,
            "user": user_or_redirect,
            "tipos": FUNCIONARIO_TIPOS,
            "permissoes": FUNCIONARIO_PERMISSOES,
        },
    )


# ============================================================
# ROTAS INTERNAS SEG - API
# ============================================================
@app.get("/api/interno/me")
async def interno_me(request: Request):
    user_or_response = _require_interno_user_api(request)
    if isinstance(user_or_response, JSONResponse):
        return user_or_response
    return {"ok": True, "user": user_or_response}


@app.get("/api/interno/funcionarios")
async def api_interno_listar_funcionarios(request: Request):
    user_or_response = _require_interno_user_api(request)
    if isinstance(user_or_response, JSONResponse):
        return user_or_response

    funcionarios = [_funcionario_publico(f) for f in _load_funcionarios()]
    funcionarios.sort(key=lambda item: (not item.get("ativo"), item.get("nome", "").lower()))

    return {
        "ok": True,
        "funcionarios": funcionarios,
        "resumo": _funcionarios_resumo(),
    }


@app.post("/api/interno/funcionarios")
async def api_interno_criar_funcionario(request: Request):
    user_or_response = _require_interno_user_api(request)
    if isinstance(user_or_response, JSONResponse):
        return user_or_response

    try:
        payload = await request.json()
    except Exception:
        payload = {}

    dados, erro = _validar_payload_funcionario(payload, criando=True)
    if erro:
        return JSONResponse(status_code=400, content={"ok": False, "detail": erro})

    funcionarios = _load_funcionarios()

    if _find_funcionario_by_usuario(funcionarios, dados["usuario"]):
        return JSONResponse(status_code=409, content={"ok": False, "detail": "Já existe funcionário com esse usuário."})

    now = _now_iso()
    funcionario = {
        "id": _next_funcionario_id(funcionarios),
        "nome": dados["nome"],
        "telefone": dados["telefone"],
        "email": dados["email"],
        "cargo": dados["cargo"],
        "tipo": dados["tipo"],
        "usuario": dados["usuario"],
        "permissao": dados["permissao"],
        "ativo": dados["ativo"],
        "senha_hash": _hash_password(dados["senha"]),
        "criado_em": now,
        "atualizado_em": now,
        "ultimo_login_em": "",
        "criado_por": user_or_response.get("username"),
    }

    funcionarios.append(funcionario)
    _save_funcionarios(funcionarios)

    return JSONResponse(status_code=201, content={"ok": True, "funcionario": _funcionario_publico(funcionario)})


@app.put("/api/interno/funcionarios/{funcionario_id}")
async def api_interno_atualizar_funcionario(funcionario_id: int, request: Request):
    user_or_response = _require_interno_user_api(request)
    if isinstance(user_or_response, JSONResponse):
        return user_or_response

    try:
        payload = await request.json()
    except Exception:
        payload = {}

    dados, erro = _validar_payload_funcionario(payload, criando=False)
    if erro:
        return JSONResponse(status_code=400, content={"ok": False, "detail": erro})

    funcionarios = _load_funcionarios()
    funcionario = _find_funcionario_by_id(funcionarios, funcionario_id)

    if not funcionario:
        return JSONResponse(status_code=404, content={"ok": False, "detail": "Funcionário não encontrado."})

    existente = _find_funcionario_by_usuario(funcionarios, dados["usuario"])
    if existente and int(existente.get("id") or 0) != int(funcionario_id):
        return JSONResponse(status_code=409, content={"ok": False, "detail": "Já existe outro funcionário com esse usuário."})

    funcionario["nome"] = dados["nome"]
    funcionario["telefone"] = dados["telefone"]
    funcionario["email"] = dados["email"]
    funcionario["cargo"] = dados["cargo"]
    funcionario["tipo"] = dados["tipo"]
    funcionario["usuario"] = dados["usuario"]
    funcionario["permissao"] = dados["permissao"]
    funcionario["ativo"] = dados["ativo"]
    funcionario["atualizado_em"] = _now_iso()
    funcionario["atualizado_por"] = user_or_response.get("username")

    if dados["senha"]:
        funcionario["senha_hash"] = _hash_password(dados["senha"])

    _save_funcionarios(funcionarios)

    return {"ok": True, "funcionario": _funcionario_publico(funcionario)}


@app.post("/api/interno/funcionarios/{funcionario_id}/ativar")
async def api_interno_ativar_funcionario(funcionario_id: int, request: Request):
    user_or_response = _require_interno_user_api(request)
    if isinstance(user_or_response, JSONResponse):
        return user_or_response

    funcionarios = _load_funcionarios()
    funcionario = _find_funcionario_by_id(funcionarios, funcionario_id)

    if not funcionario:
        return JSONResponse(status_code=404, content={"ok": False, "detail": "Funcionário não encontrado."})

    funcionario["ativo"] = True
    funcionario["atualizado_em"] = _now_iso()
    funcionario["atualizado_por"] = user_or_response.get("username")
    _save_funcionarios(funcionarios)

    return {"ok": True, "funcionario": _funcionario_publico(funcionario)}


@app.post("/api/interno/funcionarios/{funcionario_id}/inativar")
async def api_interno_inativar_funcionario(funcionario_id: int, request: Request):
    user_or_response = _require_interno_user_api(request)
    if isinstance(user_or_response, JSONResponse):
        return user_or_response

    funcionarios = _load_funcionarios()
    funcionario = _find_funcionario_by_id(funcionarios, funcionario_id)

    if not funcionario:
        return JSONResponse(status_code=404, content={"ok": False, "detail": "Funcionário não encontrado."})

    funcionario["ativo"] = False
    funcionario["atualizado_em"] = _now_iso()
    funcionario["atualizado_por"] = user_or_response.get("username")
    _save_funcionarios(funcionarios)

    return {"ok": True, "funcionario": _funcionario_publico(funcionario)}


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
