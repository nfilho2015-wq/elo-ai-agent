import os

from dotenv import load_dotenv
load_dotenv(override=True)

from fastapi import FastAPI
from pydantic import BaseModel

from .database import registrar_mensagem, salvar_conversa
from .agent import reply_to_customer

app = FastAPI(
    title="Elo AI Agent",
    version="0.2.0"
)


class MensagemTeste(BaseModel):
    telefone: str
    mensagem: str
    nome: str | None = None
    canal: str = "whatsapp"


@app.get("/")
def home():
    return {
        "status": "online",
        "brand": "Elo Ambientes Planejados",
        "service": "IA + Supabase"
    }


@app.post("/teste/mensagem")
def teste_mensagem(dados: MensagemTeste):

    registro = registrar_mensagem(
        telefone=dados.telefone,
        mensagem=dados.mensagem,
        canal=dados.canal,
        nome=dados.nome,
        external_id=dados.telefone
    )

    resposta = reply_to_customer(
        dados.mensagem
    )

    salvar_conversa(
        lead_id=registro["lead_id"],
        canal=dados.canal,
        remetente="ia",
        mensagem=resposta
    )

    return {
        "cliente_id": registro["cliente_id"],
        "lead_id": registro["lead_id"],
        "mensagem_cliente": dados.mensagem,
        "resposta_ia": resposta
    }