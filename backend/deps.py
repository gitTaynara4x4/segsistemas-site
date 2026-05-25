from urllib import parse as urllib_parse

from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from .config import MODULOS_INTERNOS
from .security import interno_user_from_request


def interno_login_redirect(next_url: str = "/interno/dashboard") -> RedirectResponse:
    return RedirectResponse(url=f"/interno/login?next={urllib_parse.quote(next_url)}", status_code=303)


def user_is_admin(user: dict | None) -> bool:
    if not user:
        return False
    return bool(user.get("is_admin")) or str(user.get("permissao") or "").lower() == "admin"


def user_can_access(user: dict | None, modulo: str) -> bool:
    if not user:
        return False

    modulo = str(modulo or "").strip().lower()
    if not modulo:
        return False

    if modulo not in MODULOS_INTERNOS:
        return False

    if user_is_admin(user):
        return True

    acessos = user.get("acessos") or []
    if not isinstance(acessos, (list, tuple, set)):
        return False

    return modulo in {str(item).strip().lower() for item in acessos}


def acesso_negado_html(modulo: str) -> HTMLResponse:
    item = MODULOS_INTERNOS.get(modulo) or {}
    label = item.get("label") or modulo
    html = f"""
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
      <meta charset="UTF-8">
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <meta name="robots" content="noindex,nofollow">
      <title>Sem permissão | SEG Sistemas</title>
      <style>
        body {{
          margin: 0;
          min-height: 100vh;
          display: grid;
          place-items: center;
          background: #eef1ed;
          font-family: Inter, Arial, sans-serif;
          color: #111;
        }}
        .card {{
          width: min(520px, calc(100% - 32px));
          background: #fff;
          border-radius: 28px;
          padding: 34px;
          box-shadow: 0 20px 45px rgba(0,0,0,.08);
          text-align: center;
        }}
        h1 {{ margin: 0 0 10px; font-size: 28px; letter-spacing: -.04em; }}
        p {{ margin: 0 0 22px; color: #666; line-height: 1.5; }}
        a {{
          display: inline-flex;
          align-items: center;
          justify-content: center;
          height: 44px;
          padding: 0 22px;
          border-radius: 999px;
          background: #111;
          color: #fff;
          text-decoration: none;
          font-weight: 700;
          font-size: 14px;
        }}
      </style>
    </head>
    <body>
      <main class="card">
        <h1>Sem permissão</h1>
        <p>Seu usuário não tem acesso ao módulo <strong>{label}</strong>. Peça para um administrador liberar esse acesso no cadastro de funcionários.</p>
        <a href="/interno/dashboard">Voltar ao dashboard</a>
      </main>
    </body>
    </html>
    """
    return HTMLResponse(status_code=403, content=html)


def require_interno_user_html(request: Request, next_url: str) -> dict | RedirectResponse:
    user = interno_user_from_request(request)
    if not user:
        return interno_login_redirect(next_url)
    return user


def require_interno_module_html(request: Request, next_url: str, modulo: str) -> dict | RedirectResponse | HTMLResponse:
    user_or_redirect = require_interno_user_html(request, next_url)
    if isinstance(user_or_redirect, RedirectResponse):
        return user_or_redirect

    if not user_can_access(user_or_redirect, modulo):
        return acesso_negado_html(modulo)

    return user_or_redirect


def require_interno_user_api(request: Request) -> dict | JSONResponse:
    user = interno_user_from_request(request)
    if not user:
        return JSONResponse(status_code=401, content={"ok": False, "detail": "Não autenticado."})
    return user


def require_interno_module_api(request: Request, modulo: str) -> dict | JSONResponse:
    user_or_response = require_interno_user_api(request)
    if isinstance(user_or_response, JSONResponse):
        return user_or_response

    if not user_can_access(user_or_response, modulo):
        item = MODULOS_INTERNOS.get(modulo) or {}
        label = item.get("label") or modulo
        return JSONResponse(
            status_code=403,
            content={"ok": False, "detail": f"Sem permissão para acessar {label}."},
        )

    return user_or_response
