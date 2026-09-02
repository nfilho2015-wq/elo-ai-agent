import os
import json
import urllib.parse
import urllib.request
import urllib.error

from dotenv import load_dotenv
load_dotenv(override=True)

from fastapi import FastAPI, Request, Query, HTTPException, Response
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .database import registrar_mensagem, salvar_conversa, get_conversation_history
from .agent import reply_to_customer
from .meta import send_whatsapp_text

# ✅ TODAS AS VARIÁVEIS VÊM DO AMBIENTE (Render/.env) - NUNCA DO CÓDIGO
META_VERIFY_TOKEN = os.getenv("META_VERIFY_TOKEN", "EloVerifyToken2026")
META_APP_ID = os.getenv("META_APP_ID")
META_APP_SECRET = os.getenv("META_APP_SECRET")
META_CONFIG_ID = os.getenv("META_CONFIG_ID")
META_GRAPH_VERSION = os.getenv("META_GRAPH_VERSION", "v23.0")
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
WABA_ID = os.getenv("WABA_ID")
META_ACCESS_TOKEN = os.getenv("META_ACCESS_TOKEN")

# ✅ URL do callback (deve ser exatamente a mesma cadastrada no Facebook)
REDIRECT_URI = "https://elo-ai-agent.onrender.com/coexistencia"

app = FastAPI(
    title="Elo AI Agent",
    version="0.4.0"
)

# ✅ Habilita CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class MensagemTeste(BaseModel):
    telefone: str
    mensagem: str
    nome: str | None = None
    canal: str = "whatsapp"


class CoexistenciaCallback(BaseModel):
    code: str | None = None
    access_token: str | None = None
    waba_id: str | None = None
    phone_number_id: str | None = None
    business_id: str | None = None


def trocar_codigo_por_token(code: str) -> str:
    """Troca o código do Facebook por um access token no servidor."""
    if not META_APP_SECRET or not META_APP_ID:
        raise HTTPException(status_code=500, detail="Credenciais da Meta não configuradas.")

    parametros = urllib.parse.urlencode({
        "client_id": META_APP_ID,
        "client_secret": META_APP_SECRET,
        "code": code,
        "redirect_uri": REDIRECT_URI,
    })

    url = f"https://graph.facebook.com/{META_GRAPH_VERSION}/oauth/access_token?{parametros}"
    requisicao = urllib.request.Request(url, method="GET", headers={"Accept": "application/json"})

    try:
        with urllib.request.urlopen(requisicao, timeout=20) as resposta:
            dados = json.loads(resposta.read().decode("utf-8"))
    except urllib.error.HTTPError as erro:
        corpo = erro.read().decode("utf-8", errors="replace")
        print(f"Meta recusou a troca do código. HTTP {erro.code}: {corpo}")
        raise HTTPException(status_code=502, detail="A Meta recusou a troca do código.")
    except Exception as erro:
        print("Erro ao trocar código por token:", type(erro).__name__)
        raise HTTPException(status_code=502, detail="Não foi possível comunicar com a Meta.")

    access_token = dados.get("access_token")
    if not access_token:
        raise HTTPException(status_code=502, detail="A Meta não retornou um token.")
    return access_token


@app.get("/")
def home():
    return {"status": "online", "brand": "Elo Ambientes Planejados"}


@app.get("/privacidade", response_class=HTMLResponse)
def privacidade():
    return """
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head><meta charset="UTF-8"><title>Política de Privacidade</title></head>
    <body style="font-family:Arial; max-width:800px; margin:40px auto; padding:20px; line-height:1.6;">
        <h1 style="color:#250366;">Política de Privacidade</h1>
        <p><strong>Elo Ambientes Planejados</strong></p>
        <h2>1. Informações Coletadas</h2>
        <p>Coletamos número de telefone, nome e mensagens enviadas.</p>
        <h2>2. Uso das Informações</h2>
        <p>Utilizamos para responder solicitações e melhorar o atendimento.</p>
        <h2>3. Compartilhamento</h2>
        <p>Não compartilhamos dados com terceiros.</p>
        <h2>4. Contato</h2>
        <p>Email: contato@elo.ae</p>
    </body>
    </html>
    """


@app.get("/exclusao-dados", response_class=HTMLResponse)
def exclusao_dados():
    return """
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head><meta charset="UTF-8"><title>Exclusão de Dados</title></head>
    <body style="font-family:Arial; max-width:800px; margin:40px auto; padding:20px; line-height:1.6;">
        <h1 style="color:#250366;">Exclusão de Dados do Usuário</h1>
        <p>Para solicitar a exclusão, envie um e-mail para <strong>contato@elo.ae</strong>.</p>
    </body>
    </html>
    """


@app.get("/coexistencia", response_class=HTMLResponse)
def coexistencia():
    return f"""
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><title>Elo - WhatsApp Coexistência</title></head>
<body style="font-family:Arial; max-width:700px; margin:60px auto; text-align:center;">
    <h2>Elo Ambientes Planejados</h2>
    <p>Vincular WhatsApp Business com a Elo IA</p>
    <button onclick="verificarSDK()" style="background:#25D366; color:white; border:none; padding:15px 25px; font-size:17px; border-radius:8px; cursor:pointer;">Conectar WhatsApp Business</button>
    <p id="status" style="margin-top:20px;"></p>
    <script>
        const APP_ID = '{META_APP_ID}';
        const CONFIG_ID = '{META_CONFIG_ID}';
        let codigoAutorizacao = null;
        let dadosEmbeddedSignup = null;
        let callbackEnviado = false;

        window.fbAsyncInit = function() {{
            FB.init({{ appId: APP_ID, autoLogAppEvents: true, xfbml: true, version: 'v23.0' }});
        }};

        (function(d, s, id) {{
            var js, fjs = d.getElementsByTagName(s)[0];
            if (d.getElementById(id)) return;
            js = d.createElement(s); js.id = id;
            js.src = "https://connect.facebook.net/pt_BR/sdk.js";
            js.async = true; js.defer = true; js.crossOrigin = "anonymous";
            fjs.parentNode.insertBefore(js, fjs);
        }}(document, 'script', 'facebook-jssdk'));

        function verificarSDK() {{
            if (typeof FB === 'undefined') {{ setTimeout(verificarSDK, 500); return; }}
            launchWhatsAppSignup();
        }}

        function launchWhatsAppSignup() {{
            callbackEnviado = false;
            FB.login(function(response) {{
                if (response.authResponse && response.authResponse.code) {{
                    codigoAutorizacao = response.authResponse.code;
                    tentarFinalizarCadastro();
                }}
            }}, {{ config_id: CONFIG_ID, response_type: 'code', override_default_response_type: true }});
        }}

        function tentarFinalizarCadastro() {{
            if (callbackEnviado) return;
            if (!codigoAutorizacao || !dadosEmbeddedSignup) return;
            processarAutorizacao(codigoAutorizacao, dadosEmbeddedSignup);
        }}

        async function processarAutorizacao(code, sessionData) {{
            if (callbackEnviado) return;
            callbackEnviado = true;
            try {{
                const payload = {{ code, waba_id: sessionData.waba_id, phone_number_id: sessionData.phone_number_id, business_id: sessionData.business_id }};
                const retorno = await fetch('/coexistencia/callback', {{ method: 'POST', headers: {{ 'Content-Type': 'application/json' }}, body: JSON.stringify(payload) }});
                const dados = await retorno.json();
                document.getElementById("status").innerText = dados.message || "Autorização validada!";
            }} catch (erro) {{
                document.getElementById("status").innerText = "Erro ao validar. Tente novamente.";
            }}
        }}

        window.addEventListener('message', function(event) {{
            if (event.origin !== "https://www.facebook.com") return;
            const data = typeof event.data === "string" ? JSON.parse(event.data) : event.data;
            if (data && data.type === "WA_EMBEDDED_SIGNUP" && data.event === "FINISH" && data.data) {{
                dadosEmbeddedSignup = data.data;
                tentarFinalizarCadastro();
            }}
        }});
    </script>
</body>
</html>
"""


@app.post("/coexistencia/callback")
async def coexistencia_callback(dados: CoexistenciaCallback):
    if not dados.code and not dados.access_token:
        raise HTTPException(status_code=400, detail="Nenhuma autorização recebida.")

    access_token = None
    if dados.code:
        access_token = trocar_codigo_por_token(dados.code)
    elif dados.access_token:
        access_token = dados.access_token

    if not access_token:
        raise HTTPException(status_code=400, detail="Não foi possível obter token.")

    return {"status": "ok", "message": "Autorização validada com sucesso!", "waba_id": dados.waba_id}


@app.post("/teste/mensagem")
def teste_mensagem(dados: MensagemTeste):
    registro = registrar_mensagem(telefone=dados.telefone, mensagem=dados.mensagem, canal=dados.canal, nome=dados.nome, external_id=dados.telefone)
    resposta = reply_to_customer(dados.mensagem)
    salvar_conversa(lead_id=registro["lead_id"], canal=dados.canal, remetente="ia", mensagem=resposta)
    return {"cliente_id": registro["cliente_id"], "lead_id": registro["lead_id"], "mensagem_cliente": dados.mensagem, "resposta_ia": resposta}


@app.get("/webhook")
async def verificar_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
):
    if hub_mode == "subscribe" and hub_verify_token == META_VERIFY_TOKEN:
        return Response(content=hub_challenge, media_type="text/plain")
    raise HTTPException(status_code=403, detail="Token de verificação inválido")


@app.post("/webhook")
async def receber_webhook(request: Request):
    payload = await request.json()
    try:
        entry = payload.get("entry", [])
        if not entry: return {"status": "ok"}
        changes = entry[0].get("changes", [])
        if not changes: return {"status": "ok"}
        value = changes[0].get("value", {})
        messages = value.get("messages", [])
        if not messages: return {"status": "ok"}

        message = messages[0]
        telefone = message.get("from")
        tipo = message.get("type")
        if tipo != "text": return {"status": "ok"}
        texto = message.get("text", {}).get("body", "")
        if not texto: return {"status": "ok"}

        # ✅ Registra a mensagem no banco e obtém o lead_id
        registro = registrar_mensagem(telefone=telefone, mensagem=texto, canal="whatsapp", external_id=telefone)
        
        # ✅ Busca o histórico real do banco
        history = get_conversation_history(registro["lead_id"])
        
        # ✅ Chama a IA com histórico
        resposta = reply_to_customer(texto, history=history)

        # ✅ Salva a resposta da IA
        salvar_conversa(lead_id=registro["lead_id"], canal="whatsapp", remetente="ia", mensagem=resposta)
        
        # ✅ Envia a resposta de volta ao cliente
        await send_whatsapp_text(telefone, resposta)
    except Exception as erro:
        print("❌ Erro no webhook:", erro)
    return {"status": "ok"}