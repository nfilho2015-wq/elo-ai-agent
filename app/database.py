import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

load_dotenv(override=True)

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL não encontrada no arquivo .env")

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True
)

SessionLocal = sessionmaker(bind=engine)

# ✅ CRIAÇÃO AUTOMÁTICA DAS TABELAS
def init_db():
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS public.clientes (
                id SERIAL PRIMARY KEY,
                nome TEXT,
                telefone TEXT UNIQUE,
                created_at TIMESTAMP DEFAULT NOW()
            );
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS public.leads (
                id SERIAL PRIMARY KEY,
                cliente_id INTEGER REFERENCES public.clientes(id),
                canal TEXT,
                external_id TEXT,
                status TEXT DEFAULT 'novo',
                created_at TIMESTAMP DEFAULT NOW()
            );
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS public.conversas (
                id SERIAL PRIMARY KEY,
                lead_id INTEGER REFERENCES public.leads(id),
                canal TEXT,
                remetente TEXT,
                mensagem TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            );
        """))

init_db()


def buscar_cliente_por_telefone(telefone):
    with engine.connect() as conn:
        return conn.execute(
            text("""
                SELECT *
                FROM public.clientes
                WHERE telefone = :telefone
                LIMIT 1
            """),
            {"telefone": telefone}
        ).mappings().first()


def criar_cliente(telefone, nome=None):
    with engine.begin() as conn:
        return conn.execute(
            text("""
                INSERT INTO public.clientes
                    (nome, telefone)
                VALUES
                    (:nome, :telefone)
                RETURNING id
            """),
            {
                "nome": nome,
                "telefone": telefone
            }
        ).scalar_one()


def buscar_ou_criar_cliente(telefone, nome=None):
    cliente = buscar_cliente_por_telefone(telefone)

    if cliente:
        return cliente["id"]

    return criar_cliente(telefone, nome)


def buscar_lead_ativo(cliente_id, canal):
    with engine.connect() as conn:
        return conn.execute(
            text("""
                SELECT *
                FROM public.leads
                WHERE cliente_id = :cliente_id
                  AND canal = :canal
                  AND status NOT IN ('vendido', 'perdido')
                ORDER BY id DESC
                LIMIT 1
            """),
            {
                "cliente_id": cliente_id,
                "canal": canal
            }
        ).mappings().first()


def criar_lead(cliente_id, canal, external_id=None):
    with engine.begin() as conn:
        return conn.execute(
            text("""
                INSERT INTO public.leads
                    (cliente_id, canal, external_id, status)
                VALUES
                    (:cliente_id, :canal, :external_id, 'novo')
                RETURNING id
            """),
            {
                "cliente_id": cliente_id,
                "canal": canal,
                "external_id": external_id
            }
        ).scalar_one()


def buscar_ou_criar_lead(cliente_id, canal, external_id=None):
    lead = buscar_lead_ativo(cliente_id, canal)

    if lead:
        return lead["id"]

    return criar_lead(cliente_id, canal, external_id)


def salvar_conversa(lead_id, canal, remetente, mensagem):
    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO public.conversas
                    (lead_id, canal, remetente, mensagem)
                VALUES
                    (:lead_id, :canal, :remetente, :mensagem)
            """),
            {
                "lead_id": lead_id,
                "canal": canal,
                "remetente": remetente,
                "mensagem": mensagem
            }
        )


# ✅ NOVA FUNÇÃO: Buscar histórico para a IA
def get_conversation_history(lead_id: int, limit: int = 10) -> list[dict]:
    with engine.connect() as conn:
        rows = conn.execute(
            text("""
                SELECT remetente, mensagem
                FROM public.conversas
                WHERE lead_id = :lead_id
                ORDER BY id DESC
                LIMIT :limit
            """),
            {"lead_id": lead_id, "limit": limit}
        ).mappings().all()

    historico = []
    for row in reversed(rows):
        historico.append({
            "role": "user" if row["remetente"] == "cliente" else "assistant",
            "content": row["mensagem"]
        })
    return historico


def registrar_mensagem(
    telefone,
    mensagem,
    canal="whatsapp",
    nome=None,
    external_id=None
):
    cliente_id = buscar_ou_criar_cliente(
        telefone=telefone,
        nome=nome
    )

    lead_id = buscar_ou_criar_lead(
        cliente_id=cliente_id,
        canal=canal,
        external_id=external_id
    )

    salvar_conversa(
        lead_id=lead_id,
        canal=canal,
        remetente="cliente",
        mensagem=mensagem
    )

    return {
        "cliente_id": cliente_id,
        "lead_id": lead_id
    }


# ✅ FUNÇÃO: Enviar e-mail para consultor (Outlook)
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def enviar_notificacao_consultor(lead_id: int, nome: str | None, ambiente: str, telefone: str):
    """Envia um e-mail para o consultor quando um lead for qualificado."""
    
    # 👇 PREENCHA COM OS DADOS DO OUTLOOK
    email_consultor = "elo_ambienteplanejados@hotmail.com"  # 👈 COLOQUE O SEU E-MAIL AQUI
    email_senha = "5hphyxciiyftkqntp"  # 👈 COLOQUE A SENHA DE APP AQUI (sem espaços)
    
    # Se você não tiver um email configurado, esta função pode retornar sem enviar
    if not email_consultor or not email_senha:
        return

    mensagem_html = f"""
    <h2>Novo Lead Qualificado - Elo Ambientes Planejados</h2>
    <p><strong>Nome:</strong> {nome or "Não informado"}</p>
    <p><strong>Ambiente:</strong> {ambiente}</p>
    <p><strong>Telefone:</strong> {telefone}</p>
    <p><strong>Origem:</strong> WhatsApp</p>
    <p><strong>Status:</strong> Aguardando atendimento humano</p>
    """

    try:
        msg = MIMEMultipart()
        msg["From"] = email_consultor
        msg["To"] = email_consultor
        msg["Subject"] = f"🔔 Novo Lead: {nome or 'Cliente'} - {ambiente}"
        msg.attach(MIMEText(mensagem_html, "html"))

        # ✅ SMTP DO OUTLOOK/HOTMAIL
        with smtplib.SMTP("smtp.office365.com", 587) as server:
            server.starttls()
            server.login(email_consultor, email_senha)
            server.sendmail(email_consultor, email_consultor, msg.as_string())
            print(f"✅ E-mail enviado para o consultor (Lead {lead_id})")
    except Exception as erro:
        print(f"❌ Erro ao enviar e-mail: {type(erro).__name__}: {erro}")