import base64
import hashlib
import hmac
import json
import os
import time

from fastapi import Request

from .config import MODULOS_INTERNOS, settings
from .utils import safe_lower


def b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")


def b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode((value + padding).encode("utf-8"))


def hash_password(password: str) -> str:
    senha = password or ""
    iterations = 160_000
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", senha.encode("utf-8"), salt, iterations)
    return "pbkdf2_sha256${}${}${}".format(
        iterations,
        b64url_encode(salt),
        b64url_encode(digest),
    )


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algo, iter_str, salt_b64, digest_b64 = (stored_hash or "").split("$", 3)
        if algo != "pbkdf2_sha256":
            return False

        iterations = int(iter_str)
        salt = b64url_decode(salt_b64)
        expected = b64url_decode(digest_b64)
        got = hashlib.pbkdf2_hmac("sha256", (password or "").encode("utf-8"), salt, iterations)
        return hmac.compare_digest(got, expected)
    except Exception:
        return False


def normalizar_usuario_login(usuario: str | None) -> str:
    return safe_lower(usuario).replace(" ", "")


def sign_session_payload(payload_b64: str) -> str:
    return hmac.new(
        settings.interno_secret.encode("utf-8"),
        payload_b64.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def create_interno_session(user_data: dict) -> str:
    now = int(time.time())
    payload = {
        "sub": user_data.get("username") or user_data.get("usuario") or settings.interno_user,
        "nome": user_data.get("nome") or user_data.get("username") or settings.interno_user,
        "perfil": user_data.get("perfil") or "Acesso interno",
        "tipo": user_data.get("tipo") or "admin",
        "permissao": user_data.get("permissao") or "admin",
        "funcionario_id": user_data.get("funcionario_id"),
        "is_admin": bool(user_data.get("is_admin")),
        "acessos": user_data.get("acessos") or list(MODULOS_INTERNOS.keys()) if bool(user_data.get("is_admin")) else user_data.get("acessos") or [],
        "iat": now,
        "exp": now + settings.interno_session_ttl_seconds,
    }
    payload_b64 = b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = sign_session_payload(payload_b64)
    return f"{payload_b64}.{signature}"


def read_interno_session(request: Request) -> dict | None:
    token = request.cookies.get(settings.interno_cookie_name)
    if not token or "." not in token:
        return None

    try:
        payload_b64, signature = token.split(".", 1)
        expected = sign_session_payload(payload_b64)

        if not hmac.compare_digest(signature, expected):
            return None

        payload = json.loads(b64url_decode(payload_b64).decode("utf-8"))
        exp = int(payload.get("exp") or 0)

        if exp < int(time.time()):
            return None

        username = str(payload.get("sub") or "").strip()
        if not username:
            return None

        return payload

    except Exception:
        return None


def interno_user_from_request(request: Request) -> dict | None:
    payload = read_interno_session(request)
    if not payload:
        return None

    username = payload.get("sub") or settings.interno_user
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
        "acessos": payload.get("acessos") or (list(MODULOS_INTERNOS.keys()) if bool(payload.get("is_admin")) else []),
    }


def cookie_secure(request: Request) -> bool:
    forwarded_proto = (request.headers.get("x-forwarded-proto") or "").lower().strip()
    if forwarded_proto == "https":
        return True
    return request.url.scheme == "https"
