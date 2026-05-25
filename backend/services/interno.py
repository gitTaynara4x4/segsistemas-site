from datetime import date, datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..config import (
    FUNCIONARIO_PERMISSOES,
    FUNCIONARIO_TIPOS,
    MODULOS_INTERNOS,
    OCORRENCIA_PRIORIDADES,
    OCORRENCIA_STATUS,
    OCORRENCIA_TIPOS,
)
from ..models import (
    InternoFuncionario,
    InternoOcorrencia,
    InternoPassagem,
    InternoPlantao,
    InternoPonto,
    InternoPontoPausa,
)
from ..utils import dt_to_iso, duracao_label, duracao_segundos, now_iso, safe_lower, safe_str, today_local_iso
from ..security import normalizar_usuario_login


def _date_from_iso(value: str | None) -> date:
    raw = safe_str(value) or today_local_iso()
    try:
        return date.fromisoformat(raw)
    except Exception:
        return date.fromisoformat(today_local_iso())


def _date_to_iso(value: date | None) -> str:
    return value.isoformat() if value else ""


def _parse_dt(value: str | None) -> datetime | None:
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



ACESSOS_PADRAO_OPERACAO = [
    "dashboard",
    "ponto",
    "plantao",
    "passagem",
    "ocorrencias",
    "manual",
]


def modulos_validos() -> list[str]:
    return list(MODULOS_INTERNOS.keys())


def normalizar_acessos(
    acessos_raw,
    permissao: str = "operador",
    usar_padrao_se_vazio: bool = True,
) -> list[str]:
    permissao_norm = safe_lower(permissao, "operador")
    todos = modulos_validos()

    if permissao_norm == "admin":
        return todos

    if acessos_raw is None:
        return ACESSOS_PADRAO_OPERACAO[:] if usar_padrao_se_vazio else []

    if isinstance(acessos_raw, str):
        raw = acessos_raw.strip()
        if not raw:
            itens = []
        else:
            try:
                import json

                parsed = json.loads(raw)
                itens = parsed if isinstance(parsed, list) else [raw]
            except Exception:
                itens = [item.strip() for item in raw.split(",")]
    elif isinstance(acessos_raw, (list, tuple, set)):
        itens = list(acessos_raw)
    else:
        itens = []

    permitidos = set(todos)
    normalizados: list[str] = []

    for item in itens:
        chave = safe_lower(item)
        if chave in permitidos and chave not in normalizados:
            normalizados.append(chave)

    if not normalizados and usar_padrao_se_vazio:
        return ACESSOS_PADRAO_OPERACAO[:]

    return normalizados


def acessos_labels(acessos: list[str]) -> list[str]:
    labels = []
    for chave in acessos:
        item = MODULOS_INTERNOS.get(chave) or {}
        labels.append(item.get("label") or chave)
    return labels


def funcionario_publico(funcionario: InternoFuncionario) -> dict:
    tipo = safe_lower(funcionario.tipo, "plantonista")
    permissao = safe_lower(funcionario.permissao, "operador")
    acessos = normalizar_acessos(funcionario.acessos, permissao, usar_padrao_se_vazio=True)

    return {
        "id": funcionario.id,
        "nome": funcionario.nome or "",
        "telefone": funcionario.telefone or "",
        "email": funcionario.email or "",
        "cargo": funcionario.cargo or "",
        "tipo": tipo,
        "tipo_label": FUNCIONARIO_TIPOS.get(tipo, tipo.title()),
        "usuario": funcionario.usuario or "",
        "permissao": permissao,
        "permissao_label": FUNCIONARIO_PERMISSOES.get(permissao, permissao.title()),
        "acessos": acessos,
        "acessos_labels": acessos_labels(acessos),
        "ativo": bool(funcionario.ativo),
        "criado_em": dt_to_iso(funcionario.criado_em),
        "atualizado_em": dt_to_iso(funcionario.atualizado_em),
        "ultimo_login_em": dt_to_iso(funcionario.ultimo_login_em),
        "tem_senha": bool(funcionario.senha_hash),
    }


def funcionarios_resumo(db: Session) -> dict:
    total = db.query(func.count(InternoFuncionario.id)).scalar() or 0
    ativos = db.query(func.count(InternoFuncionario.id)).filter(InternoFuncionario.ativo.is_(True)).scalar() or 0
    inativos = max(total - ativos, 0)
    plantonistas = (
        db.query(func.count(InternoFuncionario.id))
        .filter(InternoFuncionario.ativo.is_(True), InternoFuncionario.tipo == "plantonista")
        .scalar()
        or 0
    )
    return {"total": total, "ativos": ativos, "inativos": inativos, "plantonistas": plantonistas}


def validar_payload_funcionario(payload: dict, criando: bool = True) -> tuple[dict | None, str | None]:
    nome = safe_str(payload.get("nome"))
    usuario = normalizar_usuario_login(payload.get("usuario"))
    telefone = safe_str(payload.get("telefone"))
    email = safe_lower(payload.get("email"))
    cargo = safe_str(payload.get("cargo"))
    tipo = safe_lower(payload.get("tipo"), "plantonista")
    permissao = safe_lower(payload.get("permissao"), "operador")
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

    acessos = normalizar_acessos(
        payload.get("acessos"),
        permissao,
        usar_padrao_se_vazio=not ("acessos" in payload),
    )

    if permissao != "admin" and not acessos:
        return None, "Marque pelo menos uma tela que o funcionário pode acessar."

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
        "acessos": acessos,
        "ativo": ativo,
        "senha": senha,
    }, None


def find_funcionario_by_usuario_ou_email(db: Session, identificador: str) -> InternoFuncionario | None:
    identificador_norm = normalizar_usuario_login(identificador)
    if not identificador_norm:
        return None

    return (
        db.query(InternoFuncionario)
        .filter(
            (InternoFuncionario.usuario == identificador_norm)
            | (func.lower(InternoFuncionario.email) == identificador_norm)
        )
        .first()
    )


def find_funcionario_by_usuario(db: Session, usuario: str) -> InternoFuncionario | None:
    # Mantido por compatibilidade com outras partes do sistema.
    return find_funcionario_by_usuario_ou_email(db, usuario)


def usuario_match_registro(registro, user: dict) -> bool:
    funcionario_id_user = user.get("funcionario_id")
    funcionario_id_registro = getattr(registro, "funcionario_id", None)
    if funcionario_id_user is not None and funcionario_id_registro is not None:
        try:
            return int(funcionario_id_user) == int(funcionario_id_registro)
        except Exception:
            pass
    return normalizar_usuario_login(getattr(registro, "usuario", "")) == normalizar_usuario_login(user.get("username"))


def plantao_publico(plantao: InternoPlantao | None) -> dict | None:
    if not plantao:
        return None
    status = safe_lower(plantao.status, "aberto")
    iniciado_em = dt_to_iso(plantao.iniciado_em)
    finalizado_em = dt_to_iso(plantao.finalizado_em)
    if status == "finalizado":
        duracao = int(plantao.duracao_segundos or duracao_segundos(iniciado_em, finalizado_em))
    else:
        duracao = duracao_segundos(iniciado_em)
    return {
        "id": plantao.id,
        "status": status,
        "status_label": "Em andamento" if status == "aberto" else "Finalizado",
        "data_plantao": _date_to_iso(plantao.data_plantao),
        "funcionario_id": plantao.funcionario_id,
        "funcionario_nome": plantao.funcionario_nome or "",
        "usuario": plantao.usuario or "",
        "tipo": plantao.tipo or "",
        "permissao": plantao.permissao or "",
        "iniciado_em": iniciado_em,
        "finalizado_em": finalizado_em,
        "observacao_inicio": plantao.observacao_inicio or "",
        "observacao_fim": plantao.observacao_fim or "",
        "confirmacao_inicio": bool(plantao.confirmacao_inicio),
        "confirmacao_fim": bool(plantao.confirmacao_fim),
        "ip_inicio": plantao.ip_inicio or "",
        "ip_fim": plantao.ip_fim or "",
        "duracao_segundos": duracao,
        "duracao_label": duracao_label(duracao),
        "criado_em": dt_to_iso(plantao.criado_em),
        "atualizado_em": dt_to_iso(plantao.atualizado_em),
    }


def plantao_aberto_do_usuario(db: Session, user: dict) -> InternoPlantao | None:
    query = db.query(InternoPlantao).filter(InternoPlantao.status == "aberto")
    funcionario_id = user.get("funcionario_id")
    if funcionario_id is not None:
        return query.filter(InternoPlantao.funcionario_id == funcionario_id).order_by(InternoPlantao.id.desc()).first()
    return query.filter(InternoPlantao.usuario == normalizar_usuario_login(user.get("username"))).order_by(InternoPlantao.id.desc()).first()


def plantoes_do_dia(db: Session, data_plantao: str | None = None, limite: int | None = None) -> list[InternoPlantao]:
    dia = _date_from_iso(data_plantao)
    query = db.query(InternoPlantao).filter(InternoPlantao.data_plantao == dia).order_by(InternoPlantao.id.desc())
    if limite:
        query = query.limit(limite)
    return list(query.all())


def plantoes_resumo(db: Session) -> dict:
    hoje = plantoes_do_dia(db)
    abertos = [p for p in hoje if safe_lower(p.status, "aberto") == "aberto"]
    finalizados = [p for p in hoje if safe_lower(p.status, "aberto") == "finalizado"]
    return {
        "data": today_local_iso(),
        "total_hoje": len(hoje),
        "abertos": len(abertos),
        "finalizados": len(finalizados),
        "em_andamento": len(abertos),
    }


def validar_payload_passagem(payload: dict) -> tuple[dict | None, str | None]:
    pendencias = safe_str(payload.get("pendencias"))
    clientes_observacao = safe_str(payload.get("clientes_observacao"))
    falhas_sistema = safe_str(payload.get("falhas_sistema"))
    ocorrencias_importantes = safe_str(payload.get("ocorrencias_importantes"))
    recado_proximo = safe_str(payload.get("recado_proximo"))
    confirmacao = payload.get("confirmacao_passagem") if "confirmacao_passagem" in payload else payload.get("confirmacao")

    if isinstance(confirmacao, str):
        confirmacao = confirmacao.lower().strip() in {"true", "1", "sim", "ok", "confirmo"}
    else:
        confirmacao = bool(confirmacao)

    if not confirmacao:
        return None, "Confirme que as informações da passagem estão corretas."
    if not any([pendencias, clientes_observacao, falhas_sistema, ocorrencias_importantes, recado_proximo]):
        return None, "Informe pelo menos uma observação para registrar a passagem."

    return {
        "pendencias": pendencias,
        "clientes_observacao": clientes_observacao,
        "falhas_sistema": falhas_sistema,
        "ocorrencias_importantes": ocorrencias_importantes,
        "recado_proximo": recado_proximo,
    }, None


def passagem_publica(passagem: InternoPassagem | None) -> dict | None:
    if not passagem:
        return None
    status = safe_lower(passagem.status, "pendente")
    return {
        "id": passagem.id,
        "status": status,
        "status_label": "Recebida" if status == "recebida" else "Pendente",
        "data_plantao": _date_to_iso(passagem.data_plantao),
        "passado_por_id": passagem.passado_por_id,
        "passado_por_nome": passagem.passado_por_nome or "",
        "passado_por_usuario": passagem.passado_por_usuario or "",
        "passado_em": dt_to_iso(passagem.passado_em),
        "recebido_por_id": passagem.recebido_por_id,
        "recebido_por_nome": passagem.recebido_por_nome or "",
        "recebido_por_usuario": passagem.recebido_por_usuario or "",
        "recebido_em": dt_to_iso(passagem.recebido_em),
        "pendencias": passagem.pendencias or "",
        "clientes_observacao": passagem.clientes_observacao or "",
        "falhas_sistema": passagem.falhas_sistema or "",
        "ocorrencias_importantes": passagem.ocorrencias_importantes or "",
        "recado_proximo": passagem.recado_proximo or "",
        "confirmacao_passagem": bool(passagem.confirmacao_passagem),
        "confirmacao_recebimento": bool(passagem.confirmacao_recebimento),
        "ip_passagem": passagem.ip_passagem or "",
        "ip_recebimento": passagem.ip_recebimento or "",
        "criado_em": dt_to_iso(passagem.criado_em),
        "atualizado_em": dt_to_iso(passagem.atualizado_em),
    }


def passagens_do_dia(db: Session, data_plantao: str | None = None, limite: int | None = None) -> list[InternoPassagem]:
    dia = _date_from_iso(data_plantao)
    query = db.query(InternoPassagem).filter(InternoPassagem.data_plantao == dia).order_by(InternoPassagem.id.desc())
    if limite:
        query = query.limit(limite)
    return list(query.all())


def ultima_passagem_pendente(db: Session) -> InternoPassagem | None:
    return (
        db.query(InternoPassagem)
        .filter(InternoPassagem.status == "pendente")
        .order_by(InternoPassagem.id.desc())
        .first()
    )


def passagens_resumo(db: Session) -> dict:
    hoje = passagens_do_dia(db)
    pendentes = [p for p in hoje if safe_lower(p.status, "pendente") == "pendente"]
    recebidas = [p for p in hoje if safe_lower(p.status, "pendente") == "recebida"]
    pendentes_total = db.query(func.count(InternoPassagem.id)).filter(InternoPassagem.status == "pendente").scalar() or 0
    return {
        "data": today_local_iso(),
        "total_hoje": len(hoje),
        "pendentes_hoje": len(pendentes),
        "recebidas_hoje": len(recebidas),
        "pendentes_total": pendentes_total,
    }


def validar_payload_ocorrencia(payload: dict, editando: bool = False) -> tuple[dict | None, str | None]:
    titulo = safe_str(payload.get("titulo"))
    cliente_nome = safe_str(payload.get("cliente_nome"))
    local = safe_str(payload.get("local"))
    descricao = safe_str(payload.get("descricao"))
    providencia = safe_str(payload.get("providencia"))
    responsavel = safe_str(payload.get("responsavel"))
    tipo = safe_lower(payload.get("tipo"), "outro")
    prioridade = safe_lower(payload.get("prioridade"), "media")
    status = safe_lower(payload.get("status"), "aberta")

    if not titulo:
        return None, "Informe o título da ocorrência."
    if not descricao:
        return None, "Informe a descrição da ocorrência."
    if tipo not in OCORRENCIA_TIPOS:
        return None, "Tipo de ocorrência inválido."
    if prioridade not in OCORRENCIA_PRIORIDADES:
        return None, "Prioridade inválida."
    if status not in OCORRENCIA_STATUS:
        return None, "Status inválido."

    return {
        "titulo": titulo,
        "cliente_nome": cliente_nome,
        "local": local,
        "descricao": descricao,
        "providencia": providencia,
        "responsavel": responsavel,
        "tipo": tipo,
        "prioridade": prioridade,
        "status": status,
    }, None


def ocorrencia_publica(ocorrencia: InternoOcorrencia | None) -> dict | None:
    if not ocorrencia:
        return None
    status = safe_lower(ocorrencia.status, "aberta")
    tipo = safe_lower(ocorrencia.tipo, "outro")
    prioridade = safe_lower(ocorrencia.prioridade, "media")
    return {
        "id": ocorrencia.id,
        "status": status,
        "status_label": OCORRENCIA_STATUS.get(status, status.title()),
        "tipo": tipo,
        "tipo_label": OCORRENCIA_TIPOS.get(tipo, tipo.title()),
        "prioridade": prioridade,
        "prioridade_label": OCORRENCIA_PRIORIDADES.get(prioridade, prioridade.title()),
        "data_ocorrencia": _date_to_iso(ocorrencia.data_ocorrencia),
        "titulo": ocorrencia.titulo or "",
        "cliente_nome": ocorrencia.cliente_nome or "",
        "local": ocorrencia.local or "",
        "descricao": ocorrencia.descricao or "",
        "providencia": ocorrencia.providencia or "",
        "responsavel": ocorrencia.responsavel or "",
        "criado_por_id": ocorrencia.criado_por_id,
        "criado_por_nome": ocorrencia.criado_por_nome or "",
        "criado_por_usuario": ocorrencia.criado_por_usuario or "",
        "criado_em": dt_to_iso(ocorrencia.criado_em),
        "atualizado_em": dt_to_iso(ocorrencia.atualizado_em),
        "atualizado_por": ocorrencia.atualizado_por or "",
        "resolvido_por_id": ocorrencia.resolvido_por_id,
        "resolvido_por_nome": ocorrencia.resolvido_por_nome or "",
        "resolvido_por_usuario": ocorrencia.resolvido_por_usuario or "",
        "resolvido_em": dt_to_iso(ocorrencia.resolvido_em),
        "solucao": ocorrencia.solucao or "",
        "ip_criacao": ocorrencia.ip_criacao or "",
        "ip_atualizacao": ocorrencia.ip_atualizacao or "",
    }


def ocorrencias_do_dia(db: Session, data_ocorrencia: str | None = None) -> list[InternoOcorrencia]:
    dia = _date_from_iso(data_ocorrencia)
    return list(
        db.query(InternoOcorrencia)
        .filter(InternoOcorrencia.data_ocorrencia == dia)
        .order_by(InternoOcorrencia.id.desc())
        .all()
    )


def ocorrencias_abertas(db: Session) -> list[InternoOcorrencia]:
    return list(
        db.query(InternoOcorrencia)
        .filter(InternoOcorrencia.status.in_(["aberta", "em_andamento"]))
        .order_by(InternoOcorrencia.id.desc())
        .all()
    )


def ocorrencias_resumo(db: Session) -> dict:
    hoje = ocorrencias_do_dia(db)
    abertas = ocorrencias_abertas(db)
    criticas = [o for o in abertas if safe_lower(o.prioridade, "media") == "critica"]
    resolvidas_hoje = [o for o in hoje if safe_lower(o.status, "aberta") == "resolvida"]
    return {
        "data": today_local_iso(),
        "total_hoje": len(hoje),
        "abertas": len(abertas),
        "criticas": len(criticas),
        "resolvidas_hoje": len(resolvidas_hoje),
    }


def ponto_pausas_publicas(ponto: InternoPonto) -> list[dict]:
    pausas = []
    for pausa in ponto.pausas or []:
        pausas.append({
            "inicio_em": dt_to_iso(pausa.inicio_em),
            "fim_em": dt_to_iso(pausa.fim_em),
            "duracao_segundos": int(pausa.duracao_segundos or 0),
            "observacao_inicio": pausa.observacao_inicio or "",
            "observacao_fim": pausa.observacao_fim or "",
            "ip_inicio": pausa.ip_inicio or "",
            "ip_fim": pausa.ip_fim or "",
        })
    return pausas


def total_pausas_segundos(ponto: InternoPonto, incluir_pausa_aberta: bool = True) -> int:
    total = 0
    for pausa in ponto.pausas or []:
        inicio = dt_to_iso(pausa.inicio_em)
        fim = dt_to_iso(pausa.fim_em)
        if fim:
            total += duracao_segundos(inicio, fim)
        elif incluir_pausa_aberta:
            total += duracao_segundos(inicio)
    return max(int(total or 0), 0)


def ponto_duracoes(ponto: InternoPonto) -> dict:
    entrada_em = dt_to_iso(ponto.entrada_em)
    saida_em = dt_to_iso(ponto.saida_em)
    status = safe_lower(ponto.status, "aberto")

    total = duracao_segundos(entrada_em, saida_em or None) if entrada_em else 0
    pausas = total_pausas_segundos(ponto, incluir_pausa_aberta=status != "finalizado")
    liquido = max(total - pausas, 0)

    if status == "finalizado":
        total = int(ponto.duracao_total_segundos or total)
        pausas = int(ponto.duracao_pausas_segundos or pausas)
        liquido = int(ponto.duracao_liquida_segundos or max(total - pausas, 0))

    return {
        "duracao_total_segundos": max(total, 0),
        "duracao_pausas_segundos": max(pausas, 0),
        "duracao_liquida_segundos": max(liquido, 0),
        "duracao_total_label": duracao_label(total),
        "duracao_pausas_label": duracao_label(pausas),
        "duracao_liquida_label": duracao_label(liquido),
    }


def ponto_publico(ponto: InternoPonto | None) -> dict | None:
    if not ponto:
        return None
    status = safe_lower(ponto.status, "aberto")
    status_label_map = {"aberto": "Trabalhando", "pausado": "Em pausa", "finalizado": "Finalizado"}
    duracoes = ponto_duracoes(ponto)
    return {
        "id": ponto.id,
        "status": status,
        "status_label": status_label_map.get(status, status.title()),
        "data_ponto": _date_to_iso(ponto.data_ponto),
        "funcionario_id": ponto.funcionario_id,
        "funcionario_nome": ponto.funcionario_nome or "",
        "usuario": ponto.usuario or "",
        "tipo": ponto.tipo or "",
        "permissao": ponto.permissao or "",
        "entrada_em": dt_to_iso(ponto.entrada_em),
        "saida_em": dt_to_iso(ponto.saida_em),
        "observacao_entrada": ponto.observacao_entrada or "",
        "observacao_saida": ponto.observacao_saida or "",
        "pausas": ponto_pausas_publicas(ponto),
        "ip_entrada": ponto.ip_entrada or "",
        "ip_saida": ponto.ip_saida or "",
        "criado_em": dt_to_iso(ponto.criado_em),
        "atualizado_em": dt_to_iso(ponto.atualizado_em),
        **duracoes,
    }


def ponto_aberto_do_usuario(db: Session, user: dict) -> InternoPonto | None:
    query = db.query(InternoPonto).filter(InternoPonto.status.in_(["aberto", "pausado"]))
    funcionario_id = user.get("funcionario_id")
    if funcionario_id is not None:
        return query.filter(InternoPonto.funcionario_id == funcionario_id).order_by(InternoPonto.id.desc()).first()
    return query.filter(InternoPonto.usuario == normalizar_usuario_login(user.get("username"))).order_by(InternoPonto.id.desc()).first()


def pontos_do_dia(db: Session, data_ponto: str | None = None, limite: int | None = None) -> list[InternoPonto]:
    dia = _date_from_iso(data_ponto)
    query = db.query(InternoPonto).filter(InternoPonto.data_ponto == dia).order_by(InternoPonto.id.desc())
    if limite:
        query = query.limit(limite)
    return list(query.all())


def ultima_pausa_aberta(ponto: InternoPonto) -> InternoPontoPausa | None:
    for pausa in reversed(ponto.pausas or []):
        if pausa.inicio_em and not pausa.fim_em:
            return pausa
    return None


def pontos_resumo(db: Session) -> dict:
    hoje = pontos_do_dia(db)
    trabalhando = [p for p in hoje if safe_lower(p.status, "aberto") == "aberto"]
    em_pausa = [p for p in hoje if safe_lower(p.status, "aberto") == "pausado"]
    finalizados = [p for p in hoje if safe_lower(p.status, "aberto") == "finalizado"]
    total_liquido = sum(int(ponto_duracoes(p).get("duracao_liquida_segundos") or 0) for p in hoje)
    return {
        "data": today_local_iso(),
        "total_hoje": len(hoje),
        "trabalhando": len(trabalhando),
        "em_pausa": len(em_pausa),
        "finalizados": len(finalizados),
        "ativos_agora": len(trabalhando) + len(em_pausa),
        "horas_liquidas_segundos": total_liquido,
        "horas_liquidas_label": duracao_label(total_liquido),
    }
