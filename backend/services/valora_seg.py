from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any, Dict, Optional
from urllib import parse as urllib_parse
from urllib import request as urllib_request
from urllib.error import HTTPError, URLError

from ..config import settings


@dataclass
class ValoraSegError(Exception):
    status_code: int
    detail: str
    upstream_status: Optional[int] = None

    def __str__(self) -> str:
        return self.detail


def _make_url(path: str, query_params: Optional[Dict[str, Any]] = None) -> str:
    clean_path = "/" + str(path or "").lstrip("/")
    url = settings.valora_seg_api_base + clean_path

    if query_params:
        clean_query = {
            key: value
            for key, value in query_params.items()
            if value is not None and str(value).strip() != ""
        }
        if clean_query:
            url += "?" + urllib_parse.urlencode(clean_query)

    return url


def _decode_json(raw: bytes) -> Dict[str, Any]:
    text = raw.decode("utf-8", errors="replace") if raw else ""
    try:
        data = json.loads(text) if text else {}
    except Exception as exc:
        raise ValoraSegError(
            status_code=502,
            detail="O Valora respondeu em um formato inválido.",
        ) from exc

    if not isinstance(data, dict):
        raise ValoraSegError(
            status_code=502,
            detail="O Valora respondeu em um formato inesperado.",
        )

    return data


def _configured_api_key() -> str:
    key = str(settings.valora_seg_api_key or "").strip()
    if len(key) < 32:
        raise ValoraSegError(
            status_code=503,
            detail="A integração privada com o Valora ainda não está configurada na SEG.",
        )
    return key


def _request_sync(
    method: str,
    path: str,
    *,
    query_params: Optional[Dict[str, Any]] = None,
    payload: Optional[Dict[str, Any]] = None,
    private: bool = False,
    extra_headers: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    url = _make_url(path, query_params=query_params)
    headers = {
        "Accept": "application/json",
        "User-Agent": "SEG-Sistemas/Valora-Integration",
        "Cache-Control": "no-cache",
    }

    if private:
        headers["X-SEG-API-Key"] = _configured_api_key()

    for key, value in (extra_headers or {}).items():
        clean_key = str(key or "").strip()
        clean_value = str(value or "").strip()
        if clean_key and clean_value:
            headers[clean_key] = clean_value

    body = None
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib_request.Request(
        url=url,
        data=body,
        headers=headers,
        method=method.upper(),
    )

    timeout = max(2, min(int(settings.valora_seg_timeout_seconds or 10), 30))

    try:
        with urllib_request.urlopen(req, timeout=timeout) as resp:
            return _decode_json(resp.read())

    except HTTPError as exc:
        try:
            data = _decode_json(exc.read())
            upstream_detail = str(data.get("detail") or "").strip()
        except Exception:
            upstream_detail = ""

        if exc.code in {401, 403}:
            detail = "A SEG não conseguiu autenticar na integração privada do Valora."
        elif exc.code == 404:
            detail = upstream_detail or "Registro não encontrado no Valora."
        elif exc.code == 409:
            detail = upstream_detail or "A operação não pode ser concluída no estado atual."
        elif exc.code == 410:
            detail = upstream_detail or "Este link não está mais disponível."
        elif exc.code == 422:
            detail = upstream_detail or "Dados inválidos enviados para o Valora."
        elif exc.code == 503:
            detail = "A integração SEG ainda não está configurada no Valora."
        else:
            detail = upstream_detail or "O Valora não conseguiu concluir a consulta solicitada."

        raise ValoraSegError(
            status_code=exc.code if exc.code in {401, 403, 404, 409, 410, 422, 503} else 502,
            detail=detail,
            upstream_status=exc.code,
        ) from exc

    except URLError as exc:
        reason = str(getattr(exc, "reason", "") or "").lower()
        is_timeout = "timed out" in reason or "timeout" in reason
        raise ValoraSegError(
            status_code=504 if is_timeout else 502,
            detail=(
                "O Valora demorou além do limite para responder."
                if is_timeout
                else "A SEG não conseguiu se conectar ao Valora neste momento."
            ),
        ) from exc

    except TimeoutError as exc:
        raise ValoraSegError(
            status_code=504,
            detail="O Valora demorou além do limite para responder.",
        ) from exc

    except ValoraSegError:
        raise

    except Exception as exc:
        raise ValoraSegError(
            status_code=502,
            detail="Falha inesperada ao consultar o Valora.",
        ) from exc


async def _request(
    method: str,
    path: str,
    *,
    query_params: Optional[Dict[str, Any]] = None,
    payload: Optional[Dict[str, Any]] = None,
    private: bool = False,
    extra_headers: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    return await asyncio.to_thread(
        _request_sync,
        method,
        path,
        query_params=query_params,
        payload=payload,
        private=private,
        extra_headers=extra_headers,
    )


async def validar_sessao_portal(session_token: str) -> Dict[str, Any]:
    token = str(session_token or "").strip()
    if not token:
        raise ValoraSegError(status_code=422, detail="Sessão da Área do Cliente não informada.")

    return await _request(
        "GET",
        "/api/area-cliente-publica/dados",
        query_params={"session_token": token},
        private=False,
    )


async def obter_cliente_por_id(cliente_id: int) -> Dict[str, Any]:
    try:
        normalized_id = int(cliente_id)
    except Exception as exc:
        raise ValoraSegError(status_code=422, detail="Cliente inválido.") from exc

    if normalized_id <= 0:
        raise ValoraSegError(status_code=422, detail="Cliente inválido.")

    return await _request(
        "GET",
        f"/api/integracoes/seg/clientes/{normalized_id}",
        private=True,
    )


async def obter_cliente_por_codigo(codigo: str) -> Dict[str, Any]:
    normalized = str(codigo or "").strip()
    if not normalized:
        raise ValoraSegError(status_code=422, detail="Código do cliente não informado.")

    safe_codigo = urllib_parse.quote(normalized, safe="")
    return await _request(
        "GET",
        f"/api/integracoes/seg/clientes/codigo/{safe_codigo}",
        private=True,
    )


async def localizar_cliente_portal(identificador: str) -> Dict[str, Any]:
    normalized = str(identificador or "").strip()
    if not normalized:
        raise ValoraSegError(status_code=422, detail="Informe o código do cliente, Conta Monit24hs, CPF ou CNPJ.")

    return await _request(
        "POST",
        "/api/integracoes/seg/autenticacao/localizar",
        payload={"identificador": normalized},
        private=True,
    )


async def validar_primeiro_acesso_portal(identificador: str, verificacao: str) -> Dict[str, Any]:
    normalized_identifier = str(identificador or "").strip()
    normalized_check = str(verificacao or "").strip()
    if not normalized_identifier or not normalized_check:
        raise ValoraSegError(status_code=422, detail="Informe os dados necessários para validar o primeiro acesso.")

    return await _request(
        "POST",
        "/api/integracoes/seg/autenticacao/validar-primeiro-acesso",
        payload={
            "identificador": normalized_identifier,
            "verificacao": normalized_check,
        },
        private=True,
    )


async def verificar_integracao() -> Dict[str, Any]:
    return await _request(
        "GET",
        "/api/integracoes/seg/health",
        private=True,
    )



def _request_bytes_sync(method: str, path: str, *, query_params: Optional[Dict[str, Any]] = None, private: bool = False) -> tuple[bytes, str, Dict[str, str]]:
    url = _make_url(path, query_params=query_params)
    headers = {"Accept": "application/pdf", "User-Agent": "SEG-Sistemas/Valora-Integration", "Cache-Control": "no-cache"}
    if private:
        headers["X-SEG-API-Key"] = _configured_api_key()
    req = urllib_request.Request(url=url, headers=headers, method=method.upper())
    timeout = max(2, min(int(settings.valora_seg_timeout_seconds or 10), 30))
    try:
        with urllib_request.urlopen(req, timeout=timeout) as resp:
            return resp.read(), str(resp.headers.get("Content-Type") or "application/octet-stream"), dict(resp.headers.items())
    except HTTPError as exc:
        try:
            data = _decode_json(exc.read())
            detail = str(data.get("detail") or "")
        except Exception:
            detail = ""
        raise ValoraSegError(status_code=exc.code if exc.code in {401,403,404,409,422,503} else 502, detail=detail or "Não foi possível obter o documento no Valora.", upstream_status=exc.code) from exc
    except URLError as exc:
        raise ValoraSegError(status_code=502, detail="A SEG não conseguiu se conectar ao Valora neste momento.") from exc


async def obter_contratos_cliente(cliente_id: int) -> Dict[str, Any]:
    return await _request("GET", f"/api/integracoes/seg/clientes/{int(cliente_id)}/contratos", private=True)


async def marcar_contrato_visualizado(cliente_id: int, orcamento_id: int) -> Dict[str, Any]:
    return await _request("POST", f"/api/integracoes/seg/clientes/{int(cliente_id)}/contratos/{int(orcamento_id)}/visualizado", payload={}, private=True)


async def assinar_contrato_cliente(cliente_id: int, orcamento_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
    return await _request("POST", f"/api/integracoes/seg/clientes/{int(cliente_id)}/contratos/{int(orcamento_id)}/assinar", payload=payload, private=True)


async def obter_contrato_pdf(cliente_id: int, orcamento_id: int, *, assinado: bool = False) -> tuple[bytes, str, Dict[str, str]]:
    return await asyncio.to_thread(
        _request_bytes_sync,
        "GET",
        f"/api/integracoes/seg/clientes/{int(cliente_id)}/contratos/{int(orcamento_id)}/pdf",
        query_params={"assinado": "true" if assinado else "false"},
        private=True,
    )


async def emitir_boleto_cliente(cliente_id: int, lancamento_id: int) -> Dict[str, Any]:
    return await _request(
        "POST",
        f"/api/integracoes/seg/clientes/{int(cliente_id)}/financeiro/{int(lancamento_id)}/boleto/emitir",
        payload={},
        private=True,
    )


async def atualizar_boleto_cliente(cliente_id: int, lancamento_id: int) -> Dict[str, Any]:
    return await _request(
        "POST",
        f"/api/integracoes/seg/clientes/{int(cliente_id)}/financeiro/{int(lancamento_id)}/boleto/atualizar",
        payload={},
        private=True,
    )


# ---------------------------------------------------------------------------
# Proposta pública SEG -> API privada Valora
# ---------------------------------------------------------------------------
def _proposal_headers(client_ip: str = "", user_agent: str = "") -> Dict[str, str]:
    headers: Dict[str, str] = {}
    if str(client_ip or "").strip():
        headers["X-SEG-Client-IP"] = str(client_ip).strip()[:64]
    if str(user_agent or "").strip():
        headers["X-SEG-Client-User-Agent"] = str(user_agent).strip()[:500]
    return headers


async def obter_proposta_cliente(token: str, *, client_ip: str = "", user_agent: str = "") -> Dict[str, Any]:
    safe_token = urllib_parse.quote(str(token or "").strip(), safe="")
    if not safe_token:
        raise ValoraSegError(status_code=422, detail="Link da proposta incompleto.")
    return await _request(
        "GET",
        f"/api/integracoes/seg/propostas/{safe_token}",
        private=True,
        extra_headers=_proposal_headers(client_ip, user_agent),
    )


async def aprovar_proposta_cliente(token: str, *, client_ip: str = "", user_agent: str = "") -> Dict[str, Any]:
    safe_token = urllib_parse.quote(str(token or "").strip(), safe="")
    return await _request(
        "POST",
        f"/api/integracoes/seg/propostas/{safe_token}/aprovar",
        payload={"aceite": True},
        private=True,
        extra_headers=_proposal_headers(client_ip, user_agent),
    )


async def solicitar_alteracao_proposta_cliente(token: str, mensagem: str, *, client_ip: str = "", user_agent: str = "") -> Dict[str, Any]:
    safe_token = urllib_parse.quote(str(token or "").strip(), safe="")
    return await _request(
        "POST",
        f"/api/integracoes/seg/propostas/{safe_token}/solicitar-alteracao",
        payload={"mensagem": str(mensagem or "").strip()},
        private=True,
        extra_headers=_proposal_headers(client_ip, user_agent),
    )


async def obter_cadastro_contrato_proposta(token: str, *, client_ip: str = "", user_agent: str = "") -> Dict[str, Any]:
    safe_token = urllib_parse.quote(str(token or "").strip(), safe="")
    return await _request(
        "GET",
        f"/api/integracoes/seg/propostas/{safe_token}/cadastro-contrato",
        private=True,
        extra_headers=_proposal_headers(client_ip, user_agent),
    )


async def concluir_cadastro_contrato_proposta(token: str, payload: Dict[str, Any], *, client_ip: str = "", user_agent: str = "") -> Dict[str, Any]:
    safe_token = urllib_parse.quote(str(token or "").strip(), safe="")
    return await _request(
        "POST",
        f"/api/integracoes/seg/propostas/{safe_token}/cadastro-contrato",
        payload=payload,
        private=True,
        extra_headers=_proposal_headers(client_ip, user_agent),
    )
