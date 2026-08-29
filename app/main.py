import os

from dotenv import load_dotenv
load_dotenv(override=True)

from fastapi import FastAPI, Request, Query, HTTPException, Response
from fastapi.responses import HTMLResponse
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


class CoexistenciaCallback(BaseModel):
    code: str


@app.get("/")
def home():
    return {
        "status": "online",
        "brand": "Elo Ambientes Planejados",
        "service": "IA + Supabase"
    }


@app.get("/coexistencia", response_class=HTMLResponse)
def coexistencia():
    return """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Elo - WhatsApp Coexistência</title>
</head>

<body style="font-family:Arial; max-width:700px; margin:60px auto; text-align:center;">

    <h2>Elo Ambientes Planejados</h2>

    <p>
        Vincular WhatsApp Business com a Elo IA
    </p>

    <button
        onclick="launchWhatsAppSignup()"
        style="
            background:#25D366;
            color:white;
            border:none;
            padding:15px 25px;
            font-size:17px;
            border-radius:8px;
            cursor:pointer;
        "
    >
        Conectar WhatsApp Business
    </button>

    <p id="status" style="margin-top:20px;"></p>

    <script>

        window.fbAsyncInit = function() {
            FB.init({
                appId: '1748103033006020',
                autoLogAppEvents: true,
                xfbml: true,
                version: 'v23.0'
            });
        };


        (function(d, s, id) {

            var js;
            var fjs = d.getElementsByTagName(s)[0];

            if (d.getElementById(id)) {
                return;
            }

            js = d.createElement(s);
            js.id = id;
            js.src = "https://connect.facebook.net/pt_BR/sdk.js";

            fjs.parentNode.insertBefore(js, fjs);

        }(document, 'script', 'facebook-jssdk'));


        function atualizarStatus(texto) {
            document.getElementById("status").innerText = texto;
        }


        function launchWhatsAppSignup() {

            atualizarStatus(
                "Abrindo autenticação do WhatsApp..."
            );

            FB.login(

                function(response) {

                    console.log(
                        "Resposta Facebook:",
                        response
                    );

                    if (
                        response.authResponse &&
                        response.authResponse.code
                    ) {

                        processarCodigoAutorizacao(
                            response.authResponse.code
                        );

                    } else {

                        atualizarStatus(
                            "O Facebook não retornou o código de autorização."
                        );

                        console.log(
                            "Login sem código:",
                            response
                        );

                    }

                },

                {
                    config_id: '912441148600105',
                    response_type: 'code',
                    override_default_response_type: true,

                    extras: {
                        setup: {},
                        featureType: 'whatsapp_business_app_onboarding',
                        sessionInfoVersion: '3'
                    }
                }

            );

        }


        async function processarCodigoAutorizacao(code) {

            atualizarStatus(
                "Autorização recebida. Processando..."
            );

            try {

                const retorno = await fetch(
                    '/coexistencia/callback',
                    {
                        method: 'POST',

                        headers: {
                            'Content-Type': 'application/json'
                        },

                        body: JSON.stringify({
                            code: code
                        })
                    }
                );

                const dados = await retorno.json();

                console.log(
                    "Retorno backend:",
                    dados
                );

                if (retorno.ok) {

                    atualizarStatus(
                        dados.message ||
                        "Autorização recebida com sucesso."
                    );

                } else {

                    atualizarStatus(
                        dados.detail ||
                        "Erro ao processar autorização."
                    );

                }

            } catch (erro) {

                console.error(
                    "Erro ao enviar código:",
                    erro
                );

                atualizarStatus(
                    "Erro ao enviar autorização para o servidor."
                );

            }

        }


        window.addEventListener(
            'message',
            function(event) {

                if (
                    event.origin !== "https://www.facebook.com"
                ) {
                    return;
                }

                try {

                    const data =
                        typeof event.data === "string"
                            ? JSON.parse(event.data)
                            : event.data;

                    console.log(
                        "Evento Embedded Signup:",
                        data
                    );

                    if (
                        data &&
                        data.type === "WA_EMBEDDED_SIGNUP"
                    ) {

                        console.log(
                            "WhatsApp Embedded Signup:",
                            data
                        );

                    }

                } catch (erro) {

                    console.log(
                        "Evento recebido:",
                        event.data
                    );

                }

            }
        );

    </script>

</body>
</html>
"""


@app.post("/coexistencia/callback")
async def coexistencia_callback(
    dados: CoexistenciaCallback
):

    if not dados.code:
        raise HTTPException(
            status_code=400,
            detail="Código de autorização não recebido."
        )

    print(
        "Código de autorização do Embedded Signup recebido."
    )

    return {
        "status": "ok",
        "message": "Autorização recebida pelo servidor da Elo."
    }


@app.post("/teste/mensagem")
def teste_mensagem(
    dados: MensagemTeste
):

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

    if (
        hub_mode == "subscribe"
        and hub_verify_token == META_VERIFY_TOKEN
    ):

        return Response(
            content=hub_challenge,
            media_type="text/plain"
        )

    raise HTTPException(
        status_code=403,
        detail="Token de verificacao invalido"
    )


@app.post("/webhook")
async def receber_webhook(
    request: Request
):

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

        texto = message.get(
            "text",
            {}
        ).get(
            "body",
            ""
        )

        if not texto:
            return {"status": "ok"}

        resposta = reply_to_customer(
            texto
        )

        await send_whatsapp_text(
            telefone,
            resposta
        )

    except Exception as erro:

        print(
            "Erro no webhook:",
            erro
        )

    return {
        "status": "ok"
    }