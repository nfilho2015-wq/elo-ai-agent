import os

from dotenv import load_dotenv
load_dotenv(override=True)

from fastapi import FastAPI, Request, Query, HTTPException, Response
from pydantic import BaseModel

from .database import registrar_mensagem, salvar_conversa
from .agent import reply_to_customer
from .meta import send_whatsapp_text

META_VERIFY_TOKEN = os.getenv("META_VERIFY_TOKEN", "")

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
@app.get("/webhook")
async def verificar_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
):
    if hub_mode == "subscribe" and hub_verify_token == META_VERIFY_TOKEN:
        return Response(content=hub_challenge, media_type="text/plain")

    raise HTTPException(
        status_code=403,
        detail="Token de verificacao invalido"
    )


@app.post("/webhook")
async def receber_webhook(request: Request):
    payload = await request.json()

    try:
        entry = payload.get("entry", [])

        if not entry:
            return {"status": "ok"}

        changes = entry[0].get("changes", [])

        if not changes:
            return {"status": "ok"}

        value = changes[0].get("value", {})
        messages = value.get("messages", [])

        if not messages:
            return {"status": "ok"}

        message = messages[0]

        telefone = message.get("from")
        tipo = message.get("type")

        if tipo != "text":
            return {"status": "ok"}

        texto = message.get("text", {}).get("body", "")

        if not texto:
            return {"status": "ok"}

        resposta = reply_to_customer(texto)

        await send_whatsapp_text(
            telefone,
            resposta
        )

    except Exception as erro:
        print("Erro no webhook:", erro)

    return {"status": "ok"}