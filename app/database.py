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