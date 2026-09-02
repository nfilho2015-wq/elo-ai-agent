import os
import httpx

# ✅ Lembre-se de preencher essas variáveis no Render!
META_ACCESS_TOKEN = os.getenv("META_ACCESS_TOKEN")
WA_PHONE_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
WA_VERSION = os.getenv("WHATSAPP_API_VERSION", "v23.0")

async def send_whatsapp_text(to: str, text: str):
    # ✅ Proteção contra envio sem token
    if not META_ACCESS_TOKEN or not WA_PHONE_ID:
        print("❌ ERRO: META_ACCESS_TOKEN ou WHATSAPP_PHONE_NUMBER_ID não configurados.")
        return {"error": "missing_credentials"}
        
    url = f"https://graph.facebook.com/{WA_VERSION}/{WA_PHONE_ID}/messages"
    headers = {"Authorization": f"Bearer {META_ACCESS_TOKEN}"}
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": text}
    }
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(url, headers=headers, json=payload)
        if r.status_code != 200:
            print(f"❌ Erro ao enviar WhatsApp: {r.text}")
        r.raise_for_status()
        return r.json()