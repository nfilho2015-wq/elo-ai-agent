import os
import json
import urllib.parse
import urllib.request
import urllib.error

from dotenv import load_dotenv
load_dotenv(override=True)

from fastapi import FastAPI, Request, Query, HTTPException, Response
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from .database import registrar_mensagem, salvar_conversa
from .agent import reply_to_customer
from .meta import send_whatsapp_text


# ✅ IDs REAIS DA ELO AMBIENTES PLANEJADOS
META_VERIFY_TOKEN = os.getenv("META_VERIFY_TOKEN", "EloVerifyToken2026")
META_APP_ID = os.getenv("META_APP_ID", "1748103033006020")
META_APP_SECRET = os.getenv("META_APP_SECRET", "7c95bd1c86c4f5e4f296cfb9acb040c2")
META_CONFIG_ID = os.getenv("META_CONFIG_ID", "1414583593977374")
META_GRAPH_VERSION = os.getenv("META_GRAPH_VERSION", "v23.0")
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "1265952296607671")
WABA_ID = os.getenv("WABA_ID", "1971509998688303")


app = FastAPI(
    title="Elo AI Agent",
    version="0.3.0"
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
    """
    Troca o código temporário do Facebook Login for Business por um
    access token no SERVIDOR.
    O token nunca é devolvido ao navegador e nunca é gravado em log.
    """
    if not META_APP_SECRET:
        raise HTTPException(
            status_code=500,
            detail="META_APP_SECRET não está configurado no servidor."
        )

    parametros = urllib.parse.urlencode(
        {
            "client_id": META_APP_ID,
            "client_secret": META_APP_SECRET,
            "code": code,
            "redirect_uri": "https://elo-ai-agent.onrender.com/",
        }
    )

    url = f"https://graph.facebook.com/{META_GRAPH_VERSION}/oauth/access_token?{parametros}"

    requisicao = urllib.request.Request(
        url,
        method="GET",
        headers={
            "Accept": "application/json",
            "User-Agent": "Elo-AI-Agent/1.0",
        },
    )

    try:
        with urllib.request.urlopen(requisicao, timeout=20) as resposta:
            dados = json.loads(resposta.read().decode("utf-8"))
    except urllib.error.HTTPError as erro:
        corpo = erro.read().decode("utf-8", errors="replace")
        print(f"Meta recusou a troca do código. HTTP {erro.code}: {corpo}")
        raise HTTPException(
            status_code=502,
            detail="A Meta recusou a troca do código de autorização."
        )
    except Exception as erro:
        print("Erro ao trocar código por token:", type(erro).__name__)
        raise HTTPException(
            status_code=502,
            detail="Não foi possível comunicar com a Meta."
        )

    access_token = dados.get("access_token")
    if not access_token:
        print(f"Resposta da Meta sem access_token. Campos: {list(dados.keys())}")
        raise HTTPException(
            status_code=502,
            detail="A Meta não retornou um token de acesso."
        )

    return access_token


@app.get("/")
def home():
    return {
        "status": "online",
        "brand": "Elo Ambientes Planejados",
        "service": "IA + Supabase",
        "waba_id": WABA_ID,
        "phone_number_id": WHATSAPP_PHONE_NUMBER_ID
    }


@app.get("/privacidade")
def privacidade():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Política de Privacidade - Elo Ambientes Planejados</title>
        <style>
            body { font-family: Arial; max-width: 800px; margin: 40px auto; padding: 20px; line-height: 1.6; }
            h1 { color: #250366; }
            h2 { color: #250366; margin-top: 30px; }
            .container { background: #f9f9f9; padding: 30px; border-radius: 10px; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Política de Privacidade</h1>
            <p><strong>Elo Ambientes Planejados</strong></p>
            <p>Última atualização: 31 de agosto de 2026</p>
            
            <h2>1. Informações Coletadas</h2>
            <p>Coletamos as seguintes informações quando você interage com nosso assistente via WhatsApp:</p>
            <ul>
                <li>Número de telefone</li>
                <li>Nome (quando fornecido)</li>
                <li>Mensagens enviadas para o assistente</li>
            </ul>
            
            <h2>2. Uso das Informações</h2>
            <p>Utilizamos suas informações para:</p>
            <ul>
                <li>Responder suas perguntas e solicitações</li>
                <li>Melhorar nosso atendimento ao cliente</li>
                <li>Enviar informações sobre nossos produtos e serviços</li>
            </ul>
            
            <h2>3. Compartilhamento de Dados</h2>
            <p>Não compartilhamos seus dados pessoais com terceiros.</p>
            
            <h2>4. Armazenamento</h2>
            <p>Seus dados são armazenados em nosso banco de dados seguro (Supabase).</p>
            
            <h2>5. Seus Direitos</h2>
            <p>Você pode solicitar a exclusão de seus dados a qualquer momento.</p>
            
            <h2>6. Contato</h2>
            <p>Email: contato@elo.ae</p>
            <p>Telefone: +55 91 8141-0773</p>
        </div>
    </body>
    </html>
    """


@app.get("/coexistencia", response_class=HTMLResponse)
def coexistencia():
    return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Elo - WhatsApp Coexistência</title>
</head>

<body style="font-family:Arial; max-width:700px; margin:60px auto; text-align:center;">

    <h2>Elo Ambientes Planejados</h2>
    <p>Vincular WhatsApp Business com a Elo IA</p>

    <button
        onclick="verificarSDK()"
        style="background:#25D366; color:white; border:none; padding:15px 25px; font-size:17px; border-radius:8px; cursor:pointer;"
    >
        Conectar WhatsApp Business
    </button>

    <p id="status" style="margin-top:20px;"></p>

    <script>
        // ✅ IDs REAIS DA ELO
        const APP_ID = '{META_APP_ID}';
        const CONFIG_ID = '{META_CONFIG_ID}';
        const WABA_ID = '{WABA_ID}';
        const PHONE_NUMBER_ID = '{WHATSAPP_PHONE_NUMBER_ID}';

        let codigoAutorizacao = null;
        let accessTokenFacebook = null;
        let dadosEmbeddedSignup = null;
        let callbackEnviado = false;

        // ✅ INICIALIZAÇÃO DO FACEBOOK SDK
        window.fbAsyncInit = function() {{
            console.log("✅ Facebook SDK inicializado!");
            FB.init({{
                appId: APP_ID,
                autoLogAppEvents: true,
                xfbml: true,
                version: 'v23.0'
            }});
            console.log("✅ Facebook SDK configurado com App ID:", APP_ID);
        }};

        // ✅ CARREGAMENTO DO SDK COM ASYNC E DEFER
        (function(d, s, id) {{
            var js;
            var fjs = d.getElementsByTagName(s)[0];
            if (d.getElementById(id)) return;
            js = d.createElement(s);
            js.id = id;
            js.src = "https://connect.facebook.net/pt_BR/sdk.js";
            js.async = true;
            js.defer = true;
            js.crossOrigin = "anonymous";
            fjs.parentNode.insertBefore(js, fjs);
            console.log("✅ SDK carregando...");
        }}(document, 'script', 'facebook-jssdk'));

        // ✅ FUNÇÃO PARA VERIFICAR SE O SDK ESTÁ CARREGADO
        function verificarSDK() {{
            if (typeof FB === 'undefined') {{
                atualizarStatus("⏳ Carregando Facebook... Aguarde");
                console.log("⏳ SDK não carregado, tentando novamente em 500ms...");
                setTimeout(verificarSDK, 500);
                return;
            }}
            console.log("✅ SDK carregado com sucesso!");
            launchWhatsAppSignup();
        }}

        function atualizarStatus(texto) {{
            document.getElementById("status").innerText = texto;
        }}

        function launchWhatsAppSignup() {{
            callbackEnviado = false;
            codigoAutorizacao = null;
            accessTokenFacebook = null;
            dadosEmbeddedSignup = null;

            atualizarStatus("🔄 Abrindo autenticação do WhatsApp...");

            console.log("🚀 Iniciando FB.login com config_id:", CONFIG_ID);

            // ✅ AJUSTE: response_type = 'code' (correto para Embedded Signup)
            FB.login(
                function(response) {{
                    console.log("📱 Resposta Facebook (callback):", response);
                    
                    // ✅ CAPTURA O CÓDIGO DE AUTORIZAÇÃO
                    if (response.authResponse && response.authResponse.code) {{
                        codigoAutorizacao = response.authResponse.code;
                        console.log("✅ Código de autorização recebido:", codigoAutorizacao);
                        atualizarStatus("✅ Autorização recebida. Aguardando dados do WhatsApp...");
                        tentarFinalizarCadastro();
                    }} else if (response.status === 'connected') {{
                        atualizarStatus("✅ Facebook conectado. Aguardando dados do WhatsApp...");
                        console.log("✅ Status connected:", response.authResponse);
                    }} else {{
                        console.log("⏳ Aguardando evento do Embedded Signup...");
                        atualizarStatus("⏳ Aguardando autorização do WhatsApp...");
                    }}
                }},
                {{
                    config_id: CONFIG_ID,
                    response_type: 'code',  // ✅ CORRETO PARA EMBEDDED SIGNUP
                    override_default_response_type: true,
                    extras: {{
                        version: 'v4'
                    }}
                }}
            );
        }}

        function tentarFinalizarCadastro() {{
            if (callbackEnviado) return;
            
            // ✅ VERIFICA SE TEM O CÓDIGO DE AUTORIZAÇÃO
            if (!codigoAutorizacao && !accessTokenFacebook) {{
                atualizarStatus("⏳ Aguardando código de autorização...");
                return;
            }}
            
            if (!dadosEmbeddedSignup) {{
                atualizarStatus("⏳ Aguardando conclusão do Cadastro Incorporado...");
                return;
            }}
            
            if (!dadosEmbeddedSignup.waba_id || !dadosEmbeddedSignup.phone_number_id) {{
                atualizarStatus("⚠️ Cadastro concluído, mas a Meta não retornou WABA ID e Phone Number ID.");
                console.log("❌ Dados incompletos do Embedded Signup:", dadosEmbeddedSignup);
                return;
            }}
            
            console.log("✅ Dados completos, processando autorização...");
            processarAutorizacao(
                codigoAutorizacao,
                accessTokenFacebook,
                dadosEmbeddedSignup
            );
        }}

        async function processarAutorizacao(code, accessToken, sessionData) {{
            if (callbackEnviado) return;
            callbackEnviado = true;
            atualizarStatus("🔄 Validando com o servidor...");

            try {{
                const payload = {{}};
                
                // ✅ PRIORIZA O CÓDIGO (que é trocado no servidor)
                if (code) {{
                    payload.code = code;
                }} else if (accessToken) {{
                    payload.access_token = accessToken;
                }}
                
                if (sessionData) {{
                    payload.waba_id = sessionData.waba_id || null;
                    payload.phone_number_id = sessionData.phone_number_id || null;
                    payload.business_id = sessionData.business_id || null;
                }}

                console.log("📤 Enviando payload:", payload);

                const retorno = await fetch('/coexistencia/callback', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify(payload)
                }});

                const dados = await retorno.json();
                console.log("📥 Retorno backend:", dados);

                if (retorno.ok) {{
                    let mensagem = dados.message || "✅ Autorização validada com sucesso!";
                    if (dados.waba_id || dados.phone_number_id) {{
                        mensagem += " WABA: " + (dados.waba_id || "não informado") + 
                                   " | Phone Number ID: " + (dados.phone_number_id || "não informado");
                    }}
                    atualizarStatus("✅ " + mensagem);
                }} else {{
                    callbackEnviado = false;
                    atualizarStatus("❌ " + (dados.detail || "Erro ao processar autorização."));
                }}
            }} catch (erro) {{
                callbackEnviado = false;
                console.error("❌ Erro ao enviar autorização:", erro);
                atualizarStatus("❌ Erro ao enviar autorização para o servidor.");
            }}
        }}

        // ✅ LISTENER DO EMBEDDED SIGNUP
        window.addEventListener('message', function(event) {{
            if (event.origin !== "https://www.facebook.com") {{
                console.log("🌐 Evento ignorado - origem diferente:", event.origin);
                return;
            }}

            try {{
                const data = typeof event.data === "string" ? JSON.parse(event.data) : event.data;
                console.log("📩 Evento recebido do Facebook:", data);

                if (data && data.type === "WA_EMBEDDED_SIGNUP") {{
                    console.log("📌 Evento WA_EMBEDDED_SIGNUP detectado!");
                    
                    if (data.event === "FINISH" && data.data) {{
                        dadosEmbeddedSignup = {{
                            waba_id: data.data.waba_id || null,
                            phone_number_id: data.data.phone_number_id || null,
                            business_id: data.data.business_id || null,
                            access_token: data.data.access_token || null
                        }};

                        if (dadosEmbeddedSignup.access_token) {{
                            accessTokenFacebook = dadosEmbeddedSignup.access_token;
                            console.log("🔑 Access token recebido via Embedded Signup");
                        }}

                        console.log("✅ Embedded Signup finalizado:", dadosEmbeddedSignup);
                        atualizarStatus("✅ Cadastro concluído! Validando...");
                        tentarFinalizarCadastro();
                    }} else if (data.event === "CANCEL") {{
                        callbackEnviado = false;
                        atualizarStatus("❌ Cadastro cancelado.");
                        console.log("❌ Usuário cancelou o cadastro");
                    }} else if (data.event === "ERROR") {{
                        callbackEnviado = false;
                        atualizarStatus("❌ Erro no cadastro.");
                        console.log("❌ Erro Embedded Signup:", data.data);
                    }}
                }}
                
                // ✅ TAMBÉM CAPTURA EVENTOS DE AUTORIZAÇÃO SEPARADOS
                if (data && data.type === "FB_AUTHORIZATION" && data.data && data.data.code) {{
                    codigoAutorizacao = data.data.code;
                    console.log("✅ Código de autorização recebido via evento:", codigoAutorizacao);
                    tentarFinalizarCadastro();
                }}
                
            }} catch (erro) {{
                console.log("ℹ️ Evento não-JSON recebido:", event.data);
            }}
        }});

        console.log("🚀 Página carregada, aguardando interação do usuário...");
        console.log("📋 Config ID:", CONFIG_ID);
        console.log("📋 App ID:", APP_ID);
        console.log("📋 WABA ID:", WABA_ID);
        console.log("📋 Phone Number ID:", PHONE_NUMBER_ID);
    </script>

</body>
</html>
"""


@app.post("/coexistencia/callback")
async def coexistencia_callback(dados: CoexistenciaCallback):
    if not dados.code and not dados.access_token:
        raise HTTPException(
            status_code=400,
            detail="Nenhuma autorização foi recebida da Meta."
        )

    access_token = None

    if dados.code:
        print("📥 Código de autorização do Embedded Signup recebido.")
        access_token = trocar_codigo_por_token(dados.code)
        print("✅ Código trocado por access token com sucesso.")
    elif dados.access_token:
        print("📥 Access token recebido diretamente pelo Facebook Login.")
        access_token = dados.access_token

    if not access_token:
        raise HTTPException(
            status_code=400,
            detail="Não foi possível obter um token de acesso válido."
        )

    if dados.waba_id:
        print("✅ WABA ID recebido:", dados.waba_id)
    if dados.phone_number_id:
        print("✅ Phone Number ID recebido:", dados.phone_number_id)
    if dados.business_id:
        print("✅ Business ID recebido:", dados.business_id)

    return {
        "status": "ok",
        "message": "Autorização validada pela Meta com sucesso.",
        "waba_id": dados.waba_id,
        "phone_number_id": dados.phone_number_id,
        "business_id": dados.business_id,
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

    resposta = reply_to_customer(dados.mensagem)

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
    raise HTTPException(status_code=403, detail="Token de verificacao invalido")


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
        await send_whatsapp_text(telefone, resposta)

    except Exception as erro:
        print("❌ Erro no webhook:", erro)

    return {"status": "ok"}