from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..deps import require_interno_module_api, user_is_admin
from ..models import InternoDocumento
from ..utils import now_utc, safe_lower, safe_str
from ..services.auditoria import registrar_auditoria

router = APIRouter(prefix="/api/interno/documentos", tags=["Interno - Documentos"])

UPLOAD_DIR = Path(settings.static_dir) / "uploads" / "documentos"
MAX_PDF_BYTES = 15 * 1024 * 1024
TIPOS = {
    "procedimento": "Procedimento",
    "manual": "Manual",
    "pdf": "PDF",
    "contato": "Contato útil",
}
CATEGORIAS_PADRAO = [
    "Operação",
    "Monitoramento",
    "Técnico",
    "Administrativo",
    "Contatos úteis",
]


def _parse_bool(value: str | None, default: bool = True) -> bool:
    if value is None:
        return default
    return safe_lower(value) not in {"0", "false", "nao", "não", "off"}


def _publico(item: InternoDocumento) -> dict:
    return {
        "id": item.id,
        "titulo": item.titulo or "",
        "descricao": item.descricao or "",
        "conteudo": item.conteudo or "",
        "categoria": item.categoria or "Geral",
        "tipo": item.tipo or "procedimento",
        "tipo_label": TIPOS.get(item.tipo or "", item.tipo or "Documento"),
        "arquivo_nome": item.arquivo_nome or "",
        "arquivo_url": item.arquivo_url or "",
        "contato_nome": item.contato_nome or "",
        "telefone": item.telefone or "",
        "email": item.email or "",
        "observacao": item.observacao or "",
        "ativo": bool(item.ativo),
        "criado_por_nome": item.criado_por_nome or "",
        "criado_em": item.criado_em.isoformat() if item.criado_em else None,
        "atualizado_em": item.atualizado_em.isoformat() if item.atualizado_em else None,
    }


def _validar_tipo(tipo: str) -> str | None:
    tipo = safe_lower(tipo)
    return tipo if tipo in TIPOS else None


def _nome_arquivo_seguro(nome: str) -> str:
    nome = Path(nome or "documento.pdf").name
    return " ".join(nome.split())[:180] or "documento.pdf"


@router.get("")
async def listar_documentos(
    request: Request,
    busca: str = "",
    categoria: str = "",
    tipo: str = "",
    db: Session = Depends(get_db),
):
    user_or_response = require_interno_module_api(request, "documentos")
    if isinstance(user_or_response, JSONResponse):
        return user_or_response

    query = db.query(InternoDocumento).filter(InternoDocumento.ativo.is_(True))
    categoria_norm = safe_str(categoria)
    tipo_norm = safe_lower(tipo)
    busca_norm = safe_str(busca)

    if categoria_norm and categoria_norm.lower() != "todos":
        query = query.filter(InternoDocumento.categoria == categoria_norm)
    if tipo_norm and tipo_norm != "todos":
        query = query.filter(InternoDocumento.tipo == tipo_norm)
    if busca_norm:
        termo = f"%{busca_norm}%"
        query = query.filter(
            or_(
                InternoDocumento.titulo.ilike(termo),
                InternoDocumento.descricao.ilike(termo),
                InternoDocumento.conteudo.ilike(termo),
                InternoDocumento.categoria.ilike(termo),
                InternoDocumento.contato_nome.ilike(termo),
                InternoDocumento.telefone.ilike(termo),
                InternoDocumento.email.ilike(termo),
            )
        )

    itens = query.order_by(InternoDocumento.categoria.asc(), InternoDocumento.titulo.asc()).limit(300).all()
    categorias = [item[0] for item in db.query(InternoDocumento.categoria).filter(InternoDocumento.ativo.is_(True)).distinct().order_by(InternoDocumento.categoria.asc()).all() if item[0]]
    for categoria_padrao in CATEGORIAS_PADRAO:
        if categoria_padrao not in categorias:
            categorias.append(categoria_padrao)

    return {
        "ok": True,
        "documentos": [_publico(item) for item in itens],
        "categorias": categorias,
        "tipos": TIPOS,
        "pode_gerenciar": user_is_admin(user_or_response),
    }


@router.post("")
async def criar_documento(
    request: Request,
    titulo: str = Form(""),
    descricao: str = Form(""),
    conteudo: str = Form(""),
    categoria: str = Form("Geral"),
    tipo: str = Form("procedimento"),
    contato_nome: str = Form(""),
    telefone: str = Form(""),
    email: str = Form(""),
    observacao: str = Form(""),
    ativo: str = Form("true"),
    arquivo: UploadFile | None = File(None),
    db: Session = Depends(get_db),
):
    user_or_response = require_interno_module_api(request, "documentos")
    if isinstance(user_or_response, JSONResponse):
        return user_or_response
    if not user_is_admin(user_or_response):
        return JSONResponse(status_code=403, content={"ok": False, "detail": "Somente a administração pode publicar documentos."})

    titulo = safe_str(titulo)
    categoria = safe_str(categoria) or "Geral"
    tipo_norm = _validar_tipo(tipo)
    if not titulo:
        return JSONResponse(status_code=400, content={"ok": False, "detail": "Informe o título."})
    if not tipo_norm:
        return JSONResponse(status_code=400, content={"ok": False, "detail": "Tipo de documento inválido."})

    if tipo_norm == "pdf":
        if not arquivo or not arquivo.filename:
            return JSONResponse(status_code=400, content={"ok": False, "detail": "Selecione um arquivo PDF."})
        extensao = Path(arquivo.filename).suffix.lower()
        if extensao != ".pdf":
            return JSONResponse(status_code=400, content={"ok": False, "detail": "Somente arquivos PDF são aceitos."})
        conteudo_arquivo = await arquivo.read()
        if not conteudo_arquivo.startswith(b"%PDF-"):
            return JSONResponse(status_code=400, content={"ok": False, "detail": "O arquivo enviado não é um PDF válido."})
        if len(conteudo_arquivo) > MAX_PDF_BYTES:
            return JSONResponse(status_code=400, content={"ok": False, "detail": "O PDF deve ter no máximo 15 MB."})
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        nome_original = _nome_arquivo_seguro(arquivo.filename)
        nome_salvo = f"{uuid4().hex}.pdf"
        destino = UPLOAD_DIR / nome_salvo
        destino.write_bytes(conteudo_arquivo)
        arquivo_nome = nome_original
        arquivo_url = f"/static/uploads/documentos/{nome_salvo}"
    else:
        arquivo_nome = ""
        arquivo_url = ""

    if tipo_norm == "contato" and not (contato_nome or telefone or email):
        return JSONResponse(status_code=400, content={"ok": False, "detail": "Informe pelo menos nome, telefone ou e-mail do contato."})

    now = now_utc()
    item = InternoDocumento(
        titulo=titulo,
        descricao=safe_str(descricao),
        conteudo=safe_str(conteudo),
        categoria=categoria,
        tipo=tipo_norm,
        arquivo_nome=arquivo_nome,
        arquivo_url=arquivo_url,
        contato_nome=safe_str(contato_nome),
        telefone=safe_str(telefone),
        email=safe_str(email),
        observacao=safe_str(observacao),
        ativo=_parse_bool(ativo),
        criado_por_id=user_or_response.get("funcionario_id"),
        criado_por_nome=user_or_response.get("nome") or user_or_response.get("username") or "Administração",
        criado_por_usuario=user_or_response.get("username") or "",
        criado_em=now,
        atualizado_em=now,
        atualizado_por=user_or_response.get("username") or "",
    )
    db.add(item)
    db.flush()
    registrar_auditoria(db, user_or_response, request, modulo="documentos", entidade="documento", entidade_id=item.id, acao="CRIAR", descricao=f"Publicou o documento: {item.titulo}.")
    db.commit()
    db.refresh(item)
    return JSONResponse(status_code=201, content={"ok": True, "documento": _publico(item)})


@router.put("/{documento_id}")
async def atualizar_documento(
    documento_id: int,
    request: Request,
    titulo: str = Form(""),
    descricao: str = Form(""),
    conteudo: str = Form(""),
    categoria: str = Form("Geral"),
    tipo: str = Form("procedimento"),
    contato_nome: str = Form(""),
    telefone: str = Form(""),
    email: str = Form(""),
    observacao: str = Form(""),
    ativo: str = Form("true"),
    arquivo: UploadFile | None = File(None),
    db: Session = Depends(get_db),
):
    user_or_response = require_interno_module_api(request, "documentos")
    if isinstance(user_or_response, JSONResponse):
        return user_or_response
    if not user_is_admin(user_or_response):
        return JSONResponse(status_code=403, content={"ok": False, "detail": "Somente a administração pode editar documentos."})

    item = db.query(InternoDocumento).filter(InternoDocumento.id == documento_id).first()
    if not item:
        return JSONResponse(status_code=404, content={"ok": False, "detail": "Documento não encontrado."})

    tipo_norm = _validar_tipo(tipo)
    titulo = safe_str(titulo)
    if not titulo or not tipo_norm:
        return JSONResponse(status_code=400, content={"ok": False, "detail": "Informe título e tipo válidos."})
    if tipo_norm == "pdf" and not arquivo and not item.arquivo_url:
        return JSONResponse(status_code=400, content={"ok": False, "detail": "Selecione um arquivo PDF."})
    if tipo_norm == "contato" and not (contato_nome or telefone or email):
        return JSONResponse(status_code=400, content={"ok": False, "detail": "Informe pelo menos nome, telefone ou e-mail do contato."})

    if tipo_norm == "pdf" and arquivo and arquivo.filename:
        extensao = Path(arquivo.filename).suffix.lower()
        if extensao != ".pdf":
            return JSONResponse(status_code=400, content={"ok": False, "detail": "Somente arquivos PDF são aceitos."})
        conteudo_arquivo = await arquivo.read()
        if not conteudo_arquivo.startswith(b"%PDF-"):
            return JSONResponse(status_code=400, content={"ok": False, "detail": "O arquivo enviado não é um PDF válido."})
        if len(conteudo_arquivo) > MAX_PDF_BYTES:
            return JSONResponse(status_code=400, content={"ok": False, "detail": "O PDF deve ter no máximo 15 MB."})
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        nome_salvo = f"{uuid4().hex}.pdf"
        (UPLOAD_DIR / nome_salvo).write_bytes(conteudo_arquivo)
        if item.arquivo_url:
            antigo = Path(settings.static_dir) / item.arquivo_url.replace("/static/", "").lstrip("/")
            if antigo.exists():
                antigo.unlink(missing_ok=True)
        item.arquivo_nome = _nome_arquivo_seguro(arquivo.filename)
        item.arquivo_url = f"/static/uploads/documentos/{nome_salvo}"
    elif tipo_norm != "pdf":
        if item.arquivo_url:
            antigo = Path(settings.static_dir) / item.arquivo_url.replace("/static/", "").lstrip("/")
            if antigo.exists():
                antigo.unlink(missing_ok=True)
        item.arquivo_nome = ""
        item.arquivo_url = ""

    item.titulo = titulo
    item.descricao = safe_str(descricao)
    item.conteudo = safe_str(conteudo)
    item.categoria = safe_str(categoria) or "Geral"
    item.tipo = tipo_norm
    item.contato_nome = safe_str(contato_nome)
    item.telefone = safe_str(telefone)
    item.email = safe_str(email)
    item.observacao = safe_str(observacao)
    item.ativo = _parse_bool(ativo)
    item.atualizado_em = now_utc()
    item.atualizado_por = user_or_response.get("username") or ""
    registrar_auditoria(db, user_or_response, request, modulo="documentos", entidade="documento", entidade_id=item.id, acao="ALTERAR", descricao=f"Alterou o documento: {item.titulo}.")

    db.commit()
    db.refresh(item)
    return {"ok": True, "documento": _publico(item)}


@router.delete("/{documento_id}")
async def excluir_documento(documento_id: int, request: Request, db: Session = Depends(get_db)):
    user_or_response = require_interno_module_api(request, "documentos")
    if isinstance(user_or_response, JSONResponse):
        return user_or_response
    if not user_is_admin(user_or_response):
        return JSONResponse(status_code=403, content={"ok": False, "detail": "Somente a administração pode excluir documentos."})

    item = db.query(InternoDocumento).filter(InternoDocumento.id == documento_id).first()
    if not item:
        return JSONResponse(status_code=404, content={"ok": False, "detail": "Documento não encontrado."})

    if item.arquivo_url:
        caminho = Path(settings.static_dir) / item.arquivo_url.replace("/static/", "").lstrip("/")
        if caminho.exists():
            caminho.unlink(missing_ok=True)

    titulo_auditoria = item.titulo
    item_id_auditoria = item.id
    registrar_auditoria(db, user_or_response, request, modulo="documentos", entidade="documento", entidade_id=item_id_auditoria, acao="ENCERRAR", descricao=f"Excluiu o documento: {titulo_auditoria}.")
    db.delete(item)
    db.commit()
    return {"ok": True}
