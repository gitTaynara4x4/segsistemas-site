import os
import re
from dataclasses import dataclass
from urllib.parse import quote_plus
from zoneinfo import ZoneInfo


# ============================================================
# PATHS BASE
# ============================================================

CURRENT_FILE = os.path.abspath(__file__)
BACKEND_DIR = os.path.dirname(CURRENT_FILE)
BASE_DIR = os.path.dirname(BACKEND_DIR)

ENV_FILE = os.path.join(BASE_DIR, ".env")


# ============================================================
# CARREGAR .ENV AUTOMATICAMENTE
# ============================================================

def _load_env_file() -> None:
    """
    Carrega o arquivo .env da raiz do projeto, quando existir.

    Em produção, variáveis definidas no painel do EasyPanel/Docker têm prioridade.
    O .env só completa o que ainda não veio do ambiente. Isso evita um .env antigo
    dentro da imagem sobrescrever as credenciais corretas do serviço.
    """
    if not os.path.exists(ENV_FILE):
        print(f"[CONFIG] Arquivo .env não encontrado em: {ENV_FILE}")
        return

    try:
        with open(ENV_FILE, "r", encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.strip()

                if not line or line.startswith("#") or "=" not in line:
                    continue

                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip()

                if not key:
                    continue

                if len(value) >= 2:
                    if (value.startswith('"') and value.endswith('"')) or (
                        value.startswith("'") and value.endswith("'")
                    ):
                        value = value[1:-1]

                # Não derruba variável já definida no ambiente do container.
                os.environ.setdefault(key, value)

        print(f"[CONFIG] .env carregado com sucesso: {ENV_FILE}")

    except Exception as exc:
        print("[CONFIG] Falha ao carregar .env:", exc)


_load_env_file()


# ============================================================
# HELPERS ENV
# ============================================================

def _env_str(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


def _env_int(name: str, default: int) -> int:
    value = _env_str(name)

    if not value:
        return default

    try:
        return int(value)
    except Exception:
        return default


def _env_bool(name: str, default: bool = False) -> bool:
    value = _env_str(name)

    if not value:
        return default

    return value.lower() in {"1", "true", "yes", "sim", "on"}


# No EasyPanel, dentro do mesmo projeto/rede, o app deve falar com o Postgres
# pelo nome do serviço e pela porta interna 5432. Os nomes abaixo apareceram
# nos logs, mas não resolvem/conectam no container do site.
EASYPANEL_DB_SERVICE_HOST = "bd-segsistemas"
EASYPANEL_DB_SERVICE_PORT = "5432"
WRONG_DB_HOSTS_FOR_THIS_PROJECT = {
    "sites_bd-segsistemas",
    "9ywrah.easypanel.host",
}


def _auto_fix_db_hosts_enabled() -> bool:
    # Deixa ligado por padrão para evitar repetir os erros dos logs.
    return _env_bool("POSTGRES_AUTO_FIX_EASYPANEL_HOSTS", True)


def _normalize_postgres_host(host: str) -> str:
    host = (host or "").strip()

    if not _auto_fix_db_hosts_enabled():
        return host

    if host.lower() in WRONG_DB_HOSTS_FOR_THIS_PROJECT:
        print(
            f"[CONFIG] POSTGRES_HOST '{host}' corrigido automaticamente para "
            f"'{EASYPANEL_DB_SERVICE_HOST}'."
        )
        return EASYPANEL_DB_SERVICE_HOST

    return host


def _normalize_postgres_port(host: str, port: str) -> str:
    host = (host or "").strip().lower()
    port = (port or "").strip() or EASYPANEL_DB_SERVICE_PORT

    if _auto_fix_db_hosts_enabled() and host in WRONG_DB_HOSTS_FOR_THIS_PROJECT:
        print(
            f"[CONFIG] POSTGRES_PORT '{port}' corrigido automaticamente para "
            f"'{EASYPANEL_DB_SERVICE_PORT}'."
        )
        return EASYPANEL_DB_SERVICE_PORT

    return port


def _fix_database_url(raw_url: str) -> str:
    """
    Corrige URLs copiadas do EasyPanel/Postgres.

    Problemas comuns corrigidos:
    - postgres:// vira postgresql+psycopg2://, que o SQLAlchemy entende.
    - postgresql:// também é forçado para psycopg2.
    - senhas com @ sem escape viram %40, por exemplo Pc1234@@@@.
    - host externo/errado do EasyPanel vira bd-segsistemas:5432 neste projeto.
    """
    url = (raw_url or "").strip()
    if not url:
        return ""

    if url.startswith("postgres://"):
        scheme = "postgresql+psycopg2"
        rest = url[len("postgres://") :]
    elif url.startswith("postgresql://"):
        scheme = "postgresql+psycopg2"
        rest = url[len("postgresql://") :]
    elif url.startswith("postgresql+psycopg2://"):
        scheme = "postgresql+psycopg2"
        rest = url[len("postgresql+psycopg2://") :]
    else:
        return url

    # Se não tiver userinfo, só normaliza o driver.
    if "@" not in rest:
        return f"{scheme}://{rest}"

    # rsplit pega o último @ como separador real entre senha e host.
    # Isso permite senha como Pc1234@@@@ sem quebrar o host.
    userinfo, host_part = rest.rsplit("@", 1)

    if ":" not in userinfo:
        safe_userinfo = quote_plus(userinfo)
    else:
        user, password = userinfo.split(":", 1)
        safe_userinfo = f"{quote_plus(user)}:{quote_plus(password)}"

    # host_part vem como: host:porta/banco?sslmode=disable
    # Troca host externo/errado pelo nome interno do serviço do EasyPanel.
    if _auto_fix_db_hosts_enabled():
        match = re.match(r"([^/?#]*)(.*)", host_part)
        if match:
            authority = match.group(1)
            suffix = match.group(2)
            host_only = authority.split(":", 1)[0].strip().lower()

            if host_only in WRONG_DB_HOSTS_FOR_THIS_PROJECT:
                print(
                    f"[CONFIG] DATABASE_URL host '{host_only}' corrigido automaticamente para "
                    f"'{EASYPANEL_DB_SERVICE_HOST}:{EASYPANEL_DB_SERVICE_PORT}'."
                )
                host_part = f"{EASYPANEL_DB_SERVICE_HOST}:{EASYPANEL_DB_SERVICE_PORT}{suffix}"

    return f"{scheme}://{safe_userinfo}@{host_part}"


def _mask_database_url(url: str) -> str:
    if not url or "@" not in url or "://" not in url:
        return url

    scheme, rest = url.split("://", 1)
    userinfo, host_part = rest.rsplit("@", 1)

    if ":" in userinfo:
        user, _password = userinfo.split(":", 1)
        return f"{scheme}://{user}:***@{host_part}"

    return f"{scheme}://***@{host_part}"


# ============================================================
# SETTINGS
# ============================================================

@dataclass(frozen=True)
class Settings:
    app_title: str = "SEG SISTEMAS Site"
    timezone: ZoneInfo = ZoneInfo("America/Sao_Paulo")

    # Projeto
    current_file: str = CURRENT_FILE
    backend_dir: str = BACKEND_DIR
    base_dir: str = BASE_DIR
    frontend_dir: str = os.path.join(BASE_DIR, "frontend")
    templates_dir: str = os.path.join(BASE_DIR, "frontend", "templates")
    static_dir: str = os.path.join(BASE_DIR, "frontend", "static")
    interno_data_dir: str = os.path.join(BACKEND_DIR, "data")

    # API ValoraCRM / Área do Cliente
    valora_api_base: str = (
        _env_str("VALORA_API_BASE")
        or _env_str("AREA_CLIENTE_API_BASE")
        or "https://segsis.com.br"
    ).rstrip("/")

    # Sessão interna
    interno_cookie_name: str = "seg_interno_session"
    interno_session_ttl_seconds: int = _env_int("SEG_INTERNO_SESSION_TTL_SECONDS", 28800)

    # Admin raiz do painel interno.
    # Não existe mais admin/seg123 fixo no código.
    # Deve vir do .env ou das variáveis do EasyPanel.
    interno_user: str = _env_str("SEG_INTERNO_USER")
    interno_password: str = _env_str("SEG_INTERNO_PASSWORD")
    interno_secret: str = _env_str("SEG_INTERNO_SECRET") or _env_str("SECRET_KEY")

    # Banco PostgreSQL.
    _raw_postgres_host: str = _env_str("POSTGRES_HOST")
    postgres_host: str = _normalize_postgres_host(_env_str("POSTGRES_HOST"))
    postgres_port: str = _normalize_postgres_port(
        _env_str("POSTGRES_HOST"),
        _env_str("POSTGRES_PORT", EASYPANEL_DB_SERVICE_PORT),
    )
    postgres_user: str = _env_str("POSTGRES_USER")
    postgres_password: str = _env_str("POSTGRES_PASSWORD")
    postgres_db: str = _env_str("POSTGRES_DB")
    postgres_sslmode: str = _env_str("POSTGRES_SSLMODE", "disable")

    @property
    def database_url(self) -> str:
        direct_url = _env_str("DATABASE_URL") or _env_str("SQLALCHEMY_DATABASE_URL")

        if direct_url:
            fixed_url = _fix_database_url(direct_url)
            print(f"[CONFIG] DATABASE_URL final: {_mask_database_url(fixed_url)}")
            return fixed_url

        user = quote_plus(self.postgres_user)
        password = quote_plus(self.postgres_password)
        host = self.postgres_host
        port = self.postgres_port
        db = quote_plus(self.postgres_db)
        sslmode = quote_plus(self.postgres_sslmode)

        url = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db}?sslmode={sslmode}"
        print(f"[CONFIG] DATABASE_URL montada: {_mask_database_url(url)}")
        return url

    def validar_configuracao_obrigatoria(self) -> None:
        faltando = []

        if not self.interno_user:
            faltando.append("SEG_INTERNO_USER")

        if not self.interno_password:
            faltando.append("SEG_INTERNO_PASSWORD")

        if not self.interno_secret:
            faltando.append("SEG_INTERNO_SECRET ou SECRET_KEY")

        direct_url = _env_str("DATABASE_URL") or _env_str("SQLALCHEMY_DATABASE_URL")

        # Pode configurar o banco de duas formas:
        # 1) DATABASE_URL completo; ou
        # 2) POSTGRES_HOST/USER/PASSWORD/DB separados.
        if not direct_url:
            if not self.postgres_host:
                faltando.append("POSTGRES_HOST")

            if not self.postgres_user:
                faltando.append("POSTGRES_USER")

            if not self.postgres_password:
                faltando.append("POSTGRES_PASSWORD")

            if not self.postgres_db:
                faltando.append("POSTGRES_DB")

        if faltando:
            raise RuntimeError(
                "Configuração obrigatória ausente no .env/EasyPanel: "
                + ", ".join(faltando)
                + f". Arquivo .env esperado em: {ENV_FILE}, ou configure no painel do serviço."
            )


settings = Settings()
settings.validar_configuracao_obrigatoria()


# ============================================================
# CONSTANTES DO PAINEL INTERNO
# ============================================================

FUNCIONARIO_TIPOS = {
    "plantonista": "Plantonista",
    "tecnico": "Técnico",
    "administrativo": "Administrativo",
    "gerente": "Gerente",
}


FUNCIONARIO_PERMISSOES = {
    "operador": "Operador",
    "supervisor": "Supervisor",
    "admin": "Administrador",
}


MODULOS_INTERNOS = {
    "dashboard": {
        "label": "Dashboard",
        "descricao": "Ver a tela inicial com resumo da operação.",
        "icone": "fa-solid fa-table-cells-large",
    },
    "funcionarios": {
        "label": "Funcionários",
        "descricao": "Cadastrar, editar, ativar e inativar funcionários.",
        "icone": "fa-solid fa-users",
    },
    "ponto": {
        "label": "Ponto online",
        "descricao": "Bater entrada, pausa, retorno, saída e consultar registros de ponto.",
        "icone": "fa-regular fa-clock",
    },
    "plantao": {
        "label": "Plantão",
        "descricao": "Iniciar/finalizar plantão e acompanhar plantões do dia.",
        "icone": "fa-solid fa-wave-square",
    },
    "passagem": {
        "label": "Passagem de plantão",
        "descricao": "Registrar, visualizar e assumir passagens de plantão.",
        "icone": "fa-solid fa-database",
    },
    "ocorrencias": {
        "label": "Ocorrências",
        "descricao": "Criar, editar, resolver e reabrir ocorrências internas.",
        "icone": "fa-regular fa-clipboard",
    },
    "manual": {
        "label": "Manual interno",
        "descricao": "Acessar procedimentos e orientações internas.",
        "icone": "fa-regular fa-folder-open",
    },
}


OCORRENCIA_TIPOS = {
    "cliente": "Cliente com problema",
    "alarme": "Disparo / alarme",
    "falha_tecnica": "Falha técnica",
    "comunicacao": "Queda de comunicação",
    "reclamacao": "Reclamação",
    "visita": "Visita pendente",
    "administrativo": "Administrativo",
    "outro": "Outro",
}


OCORRENCIA_PRIORIDADES = {
    "baixa": "Baixa",
    "media": "Média",
    "alta": "Alta",
    "critica": "Crítica",
}


OCORRENCIA_STATUS = {
    "aberta": "Aberta",
    "em_andamento": "Em andamento",
    "resolvida": "Resolvida",
    "cancelada": "Cancelada",
}
