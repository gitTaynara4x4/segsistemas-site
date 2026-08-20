from sqlalchemy.orm import Session

from ..models import InternoAuditoria
from ..utils import client_ip, now_utc


def registrar_auditoria(
    db: Session,
    user: dict,
    request,
    *,
    modulo: str,
    entidade: str,
    acao: str,
    descricao: str,
    entidade_id: int | None = None,
    dados: dict | None = None,
) -> InternoAuditoria:
    registro = InternoAuditoria(
        modulo=str(modulo or "interno")[:60],
        entidade=str(entidade or "")[:80],
        entidade_id=entidade_id,
        acao=str(acao or "OUTRO")[:30].upper(),
        descricao=str(descricao or "")[:500],
        usuario_id=user.get("funcionario_id"),
        usuario_nome=str(user.get("nome") or user.get("username") or "")[:160],
        usuario=str(user.get("username") or "")[:80],
        ip=client_ip(request),
        criado_em=now_utc(),
        dados=dados or {},
    )
    db.add(registro)
    return registro
