import os
import httpx

META_ACCESS_TOKEN = os.getenv("META_ACCESS_TOKEN", "")
WA_PHONE_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
WA_VERSION = os.getenv("WHATSAPP_API_VERSION", "v23.0")

IG_TOKEN = os.getenv("INSTAGRAM_PAGE_ACCESS_TOKEN", META_ACCESS_TOKEN)
IG_VERSION = os.getenv("INSTAGRAM_API_VERSION", "v23.0")

async def send_whatsapp_text(to: str, text: str):
    url = f"https://graph.facebook.com/{WA_VERSION}/{WA_PHONE_ID}/messages"
    headers = {"Authorization": f"Bearer {META_ACCESS_TOKEN}"}
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": text}
    }
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(url, headers=headers, json=payload)
        r.raise_for_status()
        return r.json()

async def send_instagram_text(recipient_id: str, text: str):
    # O endpoint/identificador exato depende da configuração do app Meta.
    # Ajuste conforme o produto Instagram Messaging habilitado no seu app.
    url = f"https://graph.facebook.com/{IG_VERSION}/me/messages"
    params = {"access_token": IG_TOKEN}
    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": text}
    }
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(url, params=params, json=payload)
        r.raise_for_status()
        return r.json()
