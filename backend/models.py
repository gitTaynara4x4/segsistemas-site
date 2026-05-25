from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import relationship

from .database import Base


class InternoFuncionario(Base):
    __tablename__ = "interno_funcionarios"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(160), nullable=False, default="")
    telefone = Column(String(40), nullable=False, default="")
    email = Column(String(180), nullable=False, default="")
    cargo = Column(String(120), nullable=False, default="")
    tipo = Column(String(40), nullable=False, default="plantonista")
    usuario = Column(String(80), nullable=False, unique=True, index=True)
    permissao = Column(String(40), nullable=False, default="operador")
    acessos = Column(JSON, nullable=True)
    ativo = Column(Boolean, nullable=False, default=True)
    senha_hash = Column(Text, nullable=False, default="")
    criado_em = Column(DateTime(timezone=True), nullable=True)
    atualizado_em = Column(DateTime(timezone=True), nullable=True)
    ultimo_login_em = Column(DateTime(timezone=True), nullable=True)
    criado_por = Column(String(80), nullable=False, default="")
    atualizado_por = Column(String(80), nullable=False, default="")


class InternoPlantao(Base):
    __tablename__ = "interno_plantoes"

    id = Column(Integer, primary_key=True, index=True)
    status = Column(String(30), nullable=False, default="aberto", index=True)
    data_plantao = Column(Date, nullable=False, index=True)
    funcionario_id = Column(Integer, nullable=True, index=True)
    funcionario_nome = Column(String(160), nullable=False, default="")
    usuario = Column(String(80), nullable=False, default="", index=True)
    tipo = Column(String(40), nullable=False, default="")
    permissao = Column(String(40), nullable=False, default="")
    iniciado_em = Column(DateTime(timezone=True), nullable=True)
    finalizado_em = Column(DateTime(timezone=True), nullable=True)
    observacao_inicio = Column(Text, nullable=False, default="")
    observacao_fim = Column(Text, nullable=False, default="")
    confirmacao_inicio = Column(Boolean, nullable=False, default=True)
    confirmacao_fim = Column(Boolean, nullable=False, default=False)
    ip_inicio = Column(String(80), nullable=False, default="")
    ip_fim = Column(String(80), nullable=False, default="")
    duracao_segundos = Column(Integer, nullable=False, default=0)
    criado_em = Column(DateTime(timezone=True), nullable=True)
    atualizado_em = Column(DateTime(timezone=True), nullable=True)
    finalizado_por = Column(String(80), nullable=False, default="")


class InternoPassagem(Base):
    __tablename__ = "interno_passagens"

    id = Column(Integer, primary_key=True, index=True)
    status = Column(String(30), nullable=False, default="pendente", index=True)
    data_plantao = Column(Date, nullable=False, index=True)
    passado_por_id = Column(Integer, nullable=True, index=True)
    passado_por_nome = Column(String(160), nullable=False, default="")
    passado_por_usuario = Column(String(80), nullable=False, default="")
    passado_em = Column(DateTime(timezone=True), nullable=True)
    recebido_por_id = Column(Integer, nullable=True, index=True)
    recebido_por_nome = Column(String(160), nullable=False, default="")
    recebido_por_usuario = Column(String(80), nullable=False, default="")
    recebido_em = Column(DateTime(timezone=True), nullable=True)
    pendencias = Column(Text, nullable=False, default="")
    clientes_observacao = Column(Text, nullable=False, default="")
    falhas_sistema = Column(Text, nullable=False, default="")
    ocorrencias_importantes = Column(Text, nullable=False, default="")
    recado_proximo = Column(Text, nullable=False, default="")
    confirmacao_passagem = Column(Boolean, nullable=False, default=True)
    confirmacao_recebimento = Column(Boolean, nullable=False, default=False)
    ip_passagem = Column(String(80), nullable=False, default="")
    ip_recebimento = Column(String(80), nullable=False, default="")
    criado_em = Column(DateTime(timezone=True), nullable=True)
    atualizado_em = Column(DateTime(timezone=True), nullable=True)


class InternoOcorrencia(Base):
    __tablename__ = "interno_ocorrencias"

    id = Column(Integer, primary_key=True, index=True)
    status = Column(String(30), nullable=False, default="aberta", index=True)
    tipo = Column(String(60), nullable=False, default="outro", index=True)
    prioridade = Column(String(30), nullable=False, default="media", index=True)
    data_ocorrencia = Column(Date, nullable=False, index=True)
    titulo = Column(String(220), nullable=False, default="")
    cliente_nome = Column(String(180), nullable=False, default="")
    local = Column(String(180), nullable=False, default="")
    descricao = Column(Text, nullable=False, default="")
    providencia = Column(Text, nullable=False, default="")
    responsavel = Column(String(160), nullable=False, default="")
    criado_por_id = Column(Integer, nullable=True)
    criado_por_nome = Column(String(160), nullable=False, default="")
    criado_por_usuario = Column(String(80), nullable=False, default="")
    criado_em = Column(DateTime(timezone=True), nullable=True)
    atualizado_em = Column(DateTime(timezone=True), nullable=True)
    atualizado_por = Column(String(80), nullable=False, default="")
    resolvido_por_id = Column(Integer, nullable=True)
    resolvido_por_nome = Column(String(160), nullable=False, default="")
    resolvido_por_usuario = Column(String(80), nullable=False, default="")
    resolvido_em = Column(DateTime(timezone=True), nullable=True)
    solucao = Column(Text, nullable=False, default="")
    ip_criacao = Column(String(80), nullable=False, default="")
    ip_atualizacao = Column(String(80), nullable=False, default="")


class InternoPonto(Base):
    __tablename__ = "interno_pontos"

    id = Column(Integer, primary_key=True, index=True)
    status = Column(String(30), nullable=False, default="aberto", index=True)
    data_ponto = Column(Date, nullable=False, index=True)
    funcionario_id = Column(Integer, nullable=True, index=True)
    funcionario_nome = Column(String(160), nullable=False, default="")
    usuario = Column(String(80), nullable=False, default="", index=True)
    tipo = Column(String(40), nullable=False, default="")
    permissao = Column(String(40), nullable=False, default="")
    entrada_em = Column(DateTime(timezone=True), nullable=True)
    saida_em = Column(DateTime(timezone=True), nullable=True)
    observacao_entrada = Column(Text, nullable=False, default="")
    observacao_saida = Column(Text, nullable=False, default="")
    ip_entrada = Column(String(80), nullable=False, default="")
    ip_saida = Column(String(80), nullable=False, default="")
    duracao_total_segundos = Column(Integer, nullable=False, default=0)
    duracao_pausas_segundos = Column(Integer, nullable=False, default=0)
    duracao_liquida_segundos = Column(Integer, nullable=False, default=0)
    criado_em = Column(DateTime(timezone=True), nullable=True)
    atualizado_em = Column(DateTime(timezone=True), nullable=True)
    atualizado_por = Column(String(80), nullable=False, default="")

    pausas = relationship(
        "InternoPontoPausa",
        back_populates="ponto",
        cascade="all, delete-orphan",
        order_by="InternoPontoPausa.id",
    )


class InternoPontoPausa(Base):
    __tablename__ = "interno_ponto_pausas"

    id = Column(Integer, primary_key=True, index=True)
    ponto_id = Column(Integer, ForeignKey("interno_pontos.id", ondelete="CASCADE"), nullable=False, index=True)
    inicio_em = Column(DateTime(timezone=True), nullable=True)
    fim_em = Column(DateTime(timezone=True), nullable=True)
    duracao_segundos = Column(Integer, nullable=False, default=0)
    observacao_inicio = Column(Text, nullable=False, default="")
    observacao_fim = Column(Text, nullable=False, default="")
    ip_inicio = Column(String(80), nullable=False, default="")
    ip_fim = Column(String(80), nullable=False, default="")

    ponto = relationship("InternoPonto", back_populates="pausas")
