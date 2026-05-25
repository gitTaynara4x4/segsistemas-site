"""
Migra os JSON antigos do painel interno para o PostgreSQL.

Como usar na raiz do projeto:
    python -m backend.scripts.migrar_json_para_banco

Antes, configure as variáveis do banco:
    POSTGRES_HOST=9ywrah.easypanel.host
    POSTGRES_PORT=7456
    POSTGRES_USER=postgress
    POSTGRES_PASSWORD=...
    POSTGRES_DB=postgres
"""

import json
import os
from datetime import date, datetime, timezone

from sqlalchemy import text

from backend.database import Base, SessionLocal, engine
from backend.models import (
    InternoFuncionario,
    InternoOcorrencia,
    InternoPassagem,
    InternoPlantao,
    InternoPonto,
    InternoPontoPausa,
)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")


def load_json(filename: str, key: str) -> list[dict]:
    path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(path):
        print(f"[IGNORADO] {filename} não encontrado em {path}")
        return []

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, dict):
        items = data.get(key) or []
    else:
        items = data
    return [item for item in items if isinstance(item, dict)]


def parse_dt(value):
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


def parse_date(value):
    if not value:
        return date.today()
    try:
        return date.fromisoformat(str(value).strip()[:10])
    except Exception:
        return date.today()


def migrate_funcionarios(db):
    items = load_json("interno_funcionarios.json", "funcionarios")
    count = 0
    for item in items:
        if not item.get("id"):
            continue
        obj = db.get(InternoFuncionario, int(item["id"]))
        if not obj:
            obj = InternoFuncionario(id=int(item["id"]))
            db.add(obj)
        obj.nome = item.get("nome") or ""
        obj.telefone = item.get("telefone") or ""
        obj.email = item.get("email") or ""
        obj.cargo = item.get("cargo") or ""
        obj.tipo = item.get("tipo") or "plantonista"
        obj.usuario = item.get("usuario") or ""
        obj.permissao = item.get("permissao") or "operador"
        obj.ativo = bool(item.get("ativo", True))
        obj.senha_hash = item.get("senha_hash") or ""
        obj.criado_em = parse_dt(item.get("criado_em"))
        obj.atualizado_em = parse_dt(item.get("atualizado_em"))
        obj.ultimo_login_em = parse_dt(item.get("ultimo_login_em"))
        obj.criado_por = item.get("criado_por") or ""
        obj.atualizado_por = item.get("atualizado_por") or ""
        count += 1
    print(f"[OK] Funcionários migrados/atualizados: {count}")


def migrate_plantoes(db):
    items = load_json("interno_plantoes.json", "plantoes")
    count = 0
    for item in items:
        if not item.get("id"):
            continue
        obj = db.get(InternoPlantao, int(item["id"]))
        if not obj:
            obj = InternoPlantao(id=int(item["id"]))
            db.add(obj)
        obj.status = item.get("status") or "aberto"
        obj.data_plantao = parse_date(item.get("data_plantao"))
        obj.funcionario_id = item.get("funcionario_id")
        obj.funcionario_nome = item.get("funcionario_nome") or ""
        obj.usuario = item.get("usuario") or ""
        obj.tipo = item.get("tipo") or ""
        obj.permissao = item.get("permissao") or ""
        obj.iniciado_em = parse_dt(item.get("iniciado_em"))
        obj.finalizado_em = parse_dt(item.get("finalizado_em"))
        obj.observacao_inicio = item.get("observacao_inicio") or ""
        obj.observacao_fim = item.get("observacao_fim") or ""
        obj.confirmacao_inicio = bool(item.get("confirmacao_inicio", True))
        obj.confirmacao_fim = bool(item.get("confirmacao_fim", False))
        obj.ip_inicio = item.get("ip_inicio") or ""
        obj.ip_fim = item.get("ip_fim") or ""
        obj.duracao_segundos = int(item.get("duracao_segundos") or 0)
        obj.criado_em = parse_dt(item.get("criado_em"))
        obj.atualizado_em = parse_dt(item.get("atualizado_em"))
        obj.finalizado_por = item.get("finalizado_por") or ""
        count += 1
    print(f"[OK] Plantões migrados/atualizados: {count}")


def migrate_passagens(db):
    items = load_json("interno_passagens.json", "passagens")
    count = 0
    for item in items:
        if not item.get("id"):
            continue
        obj = db.get(InternoPassagem, int(item["id"]))
        if not obj:
            obj = InternoPassagem(id=int(item["id"]))
            db.add(obj)
        obj.status = item.get("status") or "pendente"
        obj.data_plantao = parse_date(item.get("data_plantao"))
        obj.passado_por_id = item.get("passado_por_id")
        obj.passado_por_nome = item.get("passado_por_nome") or ""
        obj.passado_por_usuario = item.get("passado_por_usuario") or ""
        obj.passado_em = parse_dt(item.get("passado_em"))
        obj.recebido_por_id = item.get("recebido_por_id")
        obj.recebido_por_nome = item.get("recebido_por_nome") or ""
        obj.recebido_por_usuario = item.get("recebido_por_usuario") or ""
        obj.recebido_em = parse_dt(item.get("recebido_em"))
        obj.pendencias = item.get("pendencias") or ""
        obj.clientes_observacao = item.get("clientes_observacao") or ""
        obj.falhas_sistema = item.get("falhas_sistema") or ""
        obj.ocorrencias_importantes = item.get("ocorrencias_importantes") or ""
        obj.recado_proximo = item.get("recado_proximo") or ""
        obj.confirmacao_passagem = bool(item.get("confirmacao_passagem", True))
        obj.confirmacao_recebimento = bool(item.get("confirmacao_recebimento", False))
        obj.ip_passagem = item.get("ip_passagem") or ""
        obj.ip_recebimento = item.get("ip_recebimento") or ""
        obj.criado_em = parse_dt(item.get("criado_em"))
        obj.atualizado_em = parse_dt(item.get("atualizado_em"))
        count += 1
    print(f"[OK] Passagens migradas/atualizadas: {count}")


def migrate_ocorrencias(db):
    items = load_json("interno_ocorrencias.json", "ocorrencias")
    count = 0
    for item in items:
        if not item.get("id"):
            continue
        obj = db.get(InternoOcorrencia, int(item["id"]))
        if not obj:
            obj = InternoOcorrencia(id=int(item["id"]))
            db.add(obj)
        obj.status = item.get("status") or "aberta"
        obj.tipo = item.get("tipo") or "outro"
        obj.prioridade = item.get("prioridade") or "media"
        obj.data_ocorrencia = parse_date(item.get("data_ocorrencia"))
        obj.titulo = item.get("titulo") or ""
        obj.cliente_nome = item.get("cliente_nome") or ""
        obj.local = item.get("local") or ""
        obj.descricao = item.get("descricao") or ""
        obj.providencia = item.get("providencia") or ""
        obj.responsavel = item.get("responsavel") or ""
        obj.criado_por_id = item.get("criado_por_id")
        obj.criado_por_nome = item.get("criado_por_nome") or ""
        obj.criado_por_usuario = item.get("criado_por_usuario") or ""
        obj.criado_em = parse_dt(item.get("criado_em"))
        obj.atualizado_em = parse_dt(item.get("atualizado_em"))
        obj.atualizado_por = item.get("atualizado_por") or ""
        obj.resolvido_por_id = item.get("resolvido_por_id")
        obj.resolvido_por_nome = item.get("resolvido_por_nome") or ""
        obj.resolvido_por_usuario = item.get("resolvido_por_usuario") or ""
        obj.resolvido_em = parse_dt(item.get("resolvido_em"))
        obj.solucao = item.get("solucao") or ""
        obj.ip_criacao = item.get("ip_criacao") or ""
        obj.ip_atualizacao = item.get("ip_atualizacao") or ""
        count += 1
    print(f"[OK] Ocorrências migradas/atualizadas: {count}")


def migrate_pontos(db):
    items = load_json("interno_pontos.json", "pontos")
    count = 0
    for item in items:
        if not item.get("id"):
            continue
        obj = db.get(InternoPonto, int(item["id"]))
        if not obj:
            obj = InternoPonto(id=int(item["id"]))
            db.add(obj)
        obj.status = item.get("status") or "aberto"
        obj.data_ponto = parse_date(item.get("data_ponto"))
        obj.funcionario_id = item.get("funcionario_id")
        obj.funcionario_nome = item.get("funcionario_nome") or ""
        obj.usuario = item.get("usuario") or ""
        obj.tipo = item.get("tipo") or ""
        obj.permissao = item.get("permissao") or ""
        obj.entrada_em = parse_dt(item.get("entrada_em"))
        obj.saida_em = parse_dt(item.get("saida_em"))
        obj.observacao_entrada = item.get("observacao_entrada") or ""
        obj.observacao_saida = item.get("observacao_saida") or ""
        obj.ip_entrada = item.get("ip_entrada") or ""
        obj.ip_saida = item.get("ip_saida") or ""
        obj.duracao_total_segundos = int(item.get("duracao_total_segundos") or 0)
        obj.duracao_pausas_segundos = int(item.get("duracao_pausas_segundos") or 0)
        obj.duracao_liquida_segundos = int(item.get("duracao_liquida_segundos") or 0)
        obj.criado_em = parse_dt(item.get("criado_em"))
        obj.atualizado_em = parse_dt(item.get("atualizado_em"))
        obj.atualizado_por = item.get("atualizado_por") or ""
        db.flush()

        # Recria pausas do ponto.
        for antiga in list(obj.pausas):
            db.delete(antiga)
        db.flush()
        for pausa_item in item.get("pausas") or []:
            pausa = InternoPontoPausa(
                ponto_id=obj.id,
                inicio_em=parse_dt(pausa_item.get("inicio_em")),
                fim_em=parse_dt(pausa_item.get("fim_em")),
                duracao_segundos=int(pausa_item.get("duracao_segundos") or 0),
                observacao_inicio=pausa_item.get("observacao_inicio") or "",
                observacao_fim=pausa_item.get("observacao_fim") or "",
                ip_inicio=pausa_item.get("ip_inicio") or "",
                ip_fim=pausa_item.get("ip_fim") or "",
            )
            db.add(pausa)
        count += 1
    print(f"[OK] Pontos migrados/atualizados: {count}")


def reset_sequences(db):
    tabelas = [
        ("interno_funcionarios", "id"),
        ("interno_plantoes", "id"),
        ("interno_passagens", "id"),
        ("interno_ocorrencias", "id"),
        ("interno_pontos", "id"),
        ("interno_ponto_pausas", "id"),
    ]
    for tabela, coluna in tabelas:
        db.execute(text(f"SELECT setval(pg_get_serial_sequence('{tabela}', '{coluna}'), COALESCE((SELECT MAX({coluna}) FROM {tabela}), 1), true)"))
    print("[OK] Sequences ajustadas.")


def main():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        migrate_funcionarios(db)
        migrate_plantoes(db)
        migrate_passagens(db)
        migrate_ocorrencias(db)
        migrate_pontos(db)
        db.commit()
        reset_sequences(db)
        db.commit()
        print("[FINALIZADO] Migração concluída.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
