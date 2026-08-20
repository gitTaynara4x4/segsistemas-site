import asyncio
import json
import socket
import time
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from fastapi import APIRouter, Depends, Request as FastAPIRequest
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..deps import require_interno_user_api
from ..utils import now_local

router = APIRouter(prefix="/api/interno/status-sistemas", tags=["Interno - Status dos Sistemas"])


def _http_check(url: str, timeout: float = 4.0) -> tuple[str, str, float]:
    started = time.perf_counter()
    try:
        req = Request(url, headers={"User-Agent": "SEG-Interno-Health/1.0"}, method="GET")
        with urlopen(req, timeout=timeout) as response:
            code = int(getattr(response, "status", response.getcode()))
            latency = round((time.perf_counter() - started) * 1000, 1)
            if 200 <= code < 400:
                return "online", f"HTTP {code}", latency
            return "offline", f"HTTP {code}", latency
    except Exception as exc:
        latency = round((time.perf_counter() - started) * 1000, 1)
        detail = str(exc).splitlines()[0][:120] if str(exc) else "Sem resposta"
        return "offline", detail, latency


def _tcp_check(target: str, timeout: float = 3.0) -> tuple[str, str, float]:
    started = time.perf_counter()
    try:
        parsed = urlsplit(target)
        host = parsed.hostname
        port = parsed.port
        if not host or not port:
            raise ValueError("Destino TCP inválido")
        with socket.create_connection((host, port), timeout=timeout):
            latency = round((time.perf_counter() - started) * 1000, 1)
            return "online", f"TCP {host}:{port}", latency
    except Exception as exc:
        latency = round((time.perf_counter() - started) * 1000, 1)
        detail = str(exc).splitlines()[0][:120] if str(exc) else "Sem resposta"
        return "offline", detail, latency


def _configured_services() -> list[dict]:
    services: list[dict] = []
    if settings.status_sentor_url:
        services.append({"key": "sentor", "label": "Sentor", "target": settings.status_sentor_url})
    else:
        services.append({"key": "sentor", "label": "Sentor", "target": ""})

    if settings.status_active_net_url:
        services.append({"key": "active-net", "label": "Active Net", "target": settings.status_active_net_url})
    else:
        services.append({"key": "active-net", "label": "Active Net", "target": ""})

    raw = settings.status_services.strip()
    if raw:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                for index, item in enumerate(parsed):
                    if isinstance(item, dict):
                        label = str(item.get("label") or item.get("nome") or f"Serviço {index + 1}").strip()
                        target = str(item.get("url") or item.get("target") or "").strip()
                    elif isinstance(item, (list, tuple)) and len(item) >= 2:
                        label, target = str(item[0]).strip(), str(item[1]).strip()
                    else:
                        continue
                    if target:
                        services.append({"key": f"outro-{index + 1}", "label": label, "target": target})
        except Exception:
            # Também aceita formato simples: Nome|URL,Nome2|tcp://host:porta
            for index, chunk in enumerate(raw.split(",")):
                if "|" not in chunk:
                    continue
                label, target = [part.strip() for part in chunk.split("|", 1)]
                if label and target:
                    services.append({"key": f"outro-{index + 1}", "label": label, "target": target})

    # O Valora já é uma integração configurada no projeto; entra como serviço adicional
    # somente quando nenhum serviço extra foi configurado manualmente.
    if len(services) == 2 and settings.valora_api_base:
        services.append({"key": "valora", "label": "Valora CRM", "target": settings.valora_api_base})

    return services


def _status_payload(key: str, label: str, status: str, detail: str, latency_ms: float | None, kind: str) -> dict:
    labels = {
        "online": "Online",
        "offline": "Offline",
        "nao_configurado": "Não configurado",
    }
    return {
        "key": key,
        "label": label,
        "status": status,
        "status_label": labels.get(status, status.title()),
        "detail": detail,
        "latency_ms": latency_ms,
        "kind": kind,
    }


def _check_external(item: dict) -> dict:
    target = item["target"]
    if not target:
        return _status_payload(item["key"], item["label"], "nao_configurado", "Configure a URL de monitoramento no .env.", None, "http")

    if target.lower().startswith("tcp://"):
        status, detail, latency = _tcp_check(target)
        return _status_payload(item["key"], item["label"], status, detail, latency, "tcp")

    status, detail, latency = _http_check(target)
    return _status_payload(item["key"], item["label"], status, detail, latency, "http")


@router.get("")
async def status_sistemas(request: FastAPIRequest, db: Session = Depends(get_db)):
    user = require_interno_user_api(request)
    if isinstance(user, JSONResponse):
        return user

    def check_db() -> dict:
        started = time.perf_counter()
        try:
            # A Session do SQLAlchemy pertence a esta requisição e não deve ser
            # transferida para outra thread. O SELECT é mínimo e rápido.
            db.execute(text("SELECT 1")).scalar()
            latency = round((time.perf_counter() - started) * 1000, 1)
            return _status_payload("banco", "Banco de dados", "online", "PostgreSQL respondeu normalmente.", latency, "database")
        except Exception as exc:
            latency = round((time.perf_counter() - started) * 1000, 1)
            detail = str(exc).splitlines()[0][:120] if str(exc) else "Sem resposta"
            return _status_payload("banco", "Banco de dados", "offline", detail, latency, "database")

    external_items = _configured_services()
    external_results = await asyncio.gather(*[asyncio.to_thread(_check_external, item) for item in external_items])
    db_result = check_db()

    results = []
    # Mantém a ordem operacional: Sentor, Active Net, banco e demais serviços.
    results.extend(external_results[:2])
    results.append(db_result)
    results.extend(external_results[2:])

    online = sum(1 for item in results if item["status"] == "online")
    offline = sum(1 for item in results if item["status"] == "offline")
    not_configured = sum(1 for item in results if item["status"] == "nao_configurado")

    return {
        "ok": True,
        "atualizado_em": now_local().isoformat(timespec="seconds"),
        "sistemas": results,
        "resumo": {"online": online, "offline": offline, "nao_configurado": not_configured, "total": len(results)},
    }
