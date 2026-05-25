from datetime import datetime, timezone
from typing import Any

from fastapi import Request

from .config import settings


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def now_local() -> datetime:
    return datetime.now(settings.timezone)


def today_local_iso() -> str:
    return now_local().date().isoformat()


def safe_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip()


def safe_lower(value: Any, default: str = "") -> str:
    return safe_str(value, default).lower()


def read_json_body_safe(payload: Any) -> dict:
    return payload if isinstance(payload, dict) else {}


def client_ip(request: Request) -> str:
    forwarded = safe_str(request.headers.get("x-forwarded-for"))
    if forwarded:
        return forwarded.split(",")[0].strip()

    real_ip = safe_str(request.headers.get("x-real-ip"))
    if real_ip:
        return real_ip

    if request.client:
        return request.client.host or ""
    return ""


def parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None

    try:
        raw = str(value).strip()
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        dt = datetime.fromisoformat(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def dt_to_iso(value: datetime | None) -> str:
    if not value:
        return ""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def duracao_segundos(inicio_iso: str | None, fim_iso: str | None = None) -> int:
    inicio = parse_iso_datetime(inicio_iso)
    fim = parse_iso_datetime(fim_iso or now_iso())

    if not inicio or not fim:
        return 0

    try:
        segundos = int((fim - inicio).total_seconds())
        return max(segundos, 0)
    except Exception:
        return 0


def duracao_label(segundos: int) -> str:
    segundos = max(int(segundos or 0), 0)
    horas = segundos // 3600
    minutos = (segundos % 3600) // 60

    if horas <= 0 and minutos <= 0:
        return "menos de 1 min"

    if horas <= 0:
        return f"{minutos} min"

    return f"{horas}h {minutos:02d}min"


def parse_bool(value: Any) -> bool:
    if isinstance(value, str):
        return value.lower().strip() in {"true", "1", "sim", "ok", "confirmo"}
    return bool(value)
