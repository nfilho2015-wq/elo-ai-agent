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


META_VERIFY_TOKEN = os.getenv("META_VERIFY_TOKEN", "")
META_APP_ID = os.getenv("META_APP_ID", "1748103033006020")
META_APP_SECRET = os.getenv("META_APP_SECRET", "")
META_GRAPH_VERSION = os.getenv("META_GRAPH_VERSION", "v23.0")


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
    code: str
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

    url = (
        f"https://graph.facebook.com/"
        f"{META_GRAPH_VERSION}/oauth/access_token?{parametros}"
    )

    requisicao = urllib.request.Request(
        url,
        method="GET",
        headers={
            "Accept": "application/json",
            "User-Agent": "Elo-AI-Agent/1.0",
        },
    )

    try:
        with urllib.request.urlopen(
            requisicao,
            timeout=20
        ) as resposta:
            dados = json.loads(
                resposta.read().decode("utf-8")
            )

    except urllib.error.HTTPError as erro:
        corpo = erro.read().decode(
            "utf-8",
            errors="replace"
        )

        print(
            "Meta recusou a troca do código. "
            f"HTTP {erro.code}: {corpo}"
        )

        raise HTTPException(
            status_code=502,
            detail=(
                "A Meta recusou a troca do código de autorização. "
                "Verifique o App ID, App Secret e a configuração "
                "do Facebook Login for Business."
            ),
        )

    except Exception as erro:
        print(
            "Erro ao trocar código por token:",
            type(erro).__name__,
        )

        raise HTTPException(
            status_code=502,
            detail="Não foi possível comunicar com a Meta."
        )

    access_token = dados.get("access_token")

    if not access_token:
        print(
            "Resposta da Meta sem access_token. "
            f"Campos recebidos: {list(dados.keys())}"
        )

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

        let codigoAutorizacao = null;
        let dadosEmbeddedSignup = null;
        let callbackEnviado = false;


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

            callbackEnviado = false;
            codigoAutorizacao = null;
            dadosEmbeddedSignup = null;

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

                        codigoAutorizacao =
                            response.authResponse.code;

                        atualizarStatus(
                            "Autorização recebida. Aguardando dados do WhatsApp..."
                        );

                        tentarFinalizarCadastro();

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


        function tentarFinalizarCadastro() {

            if (callbackEnviado) {
                return;
            }

            if (!codigoAutorizacao) {
                return;
            }

            /*
             * Em alguns fluxos a Meta pode não enviar o evento FINISH.
             * Nesse caso ainda fazemos a troca segura do code.
             */
            if (!dadosEmbeddedSignup) {

                setTimeout(
                    function() {

                        if (
                            codigoAutorizacao &&
                            !callbackEnviado
                        ) {
                            processarCodigoAutorizacao(
                                codigoAutorizacao,
                                null
                            );
                        }

                    },
                    1800
                );

                return;
            }

            processarCodigoAutorizacao(
                codigoAutorizacao,
                dadosEmbeddedSignup
            );

        }


        async function processarCodigoAutorizacao(
            code,
            sessionData
        ) {

            if (callbackEnviado) {
                return;
            }

            callbackEnviado = true;

            atualizarStatus(
                "Autorização recebida. Validando com a Meta..."
            );

            try {

                const payload = {
                    code: code
                };

                if (sessionData) {

                    payload.waba_id =
                        sessionData.waba_id || null;

                    payload.phone_number_id =
                        sessionData.phone_number_id || null;

                    payload.business_id =
                        sessionData.business_id || null;
                }

                const retorno = await fetch(
                    '/coexistencia/callback',
                    {
                        method: 'POST',

                        headers: {
                            'Content-Type': 'application/json'
                        },

                        body: JSON.stringify(payload)
                    }
                );

                const dados = await retorno.json();

                console.log(
                    "Retorno backend:",
                    dados
                );

                if (retorno.ok) {

                    let mensagem =
                        dados.message ||
                        "Autorização validada com sucesso.";

                    if (
                        dados.waba_id ||
                        dados.phone_number_id
                    ) {

                        mensagem +=
                            " WABA: " +
                            (dados.waba_id || "não informado") +
                            " | Phone Number ID: " +
                            (dados.phone_number_id || "não informado");
                    }

                    atualizarStatus(mensagem);

                } else {

                    callbackEnviado = false;

                    atualizarStatus(
                        dados.detail ||
                        "Erro ao processar autorização."
                    );

                }

            } catch (erro) {

                callbackEnviado = false;

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

                        if (
                            data.event === "FINISH" &&
                            data.data
                        ) {

                            dadosEmbeddedSignup =
                                data.data;

                            console.log(
                                "Embedded Signup finalizado:",
                                {
                                    waba_id:
                                        data.data.waba_id,
                                    phone_number_id:
                                        data.data.phone_number_id,
                                    business_id:
                                        data.data.business_id
                                }
                            );

                            tentarFinalizarCadastro();

                        } else if (
                            data.event === "CANCEL"
                        ) {

                            atualizarStatus(
                                "Cadastro cancelado antes da conclusão."
                            );

                        } else if (
                            data.event === "ERROR"
                        ) {

                            atualizarStatus(
                                "A Meta informou um erro durante o cadastro."
                            );

                            console.log(
                                "Erro Embedded Signup:",
                                data.data
                            );

                        }

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

    # O App Secret permanece somente no Render.
    # O access token retornado pela Meta também não é enviado ao navegador.
    access_token = trocar_codigo_por_token(
        dados.code
    )

    print(
        "Código trocado por access token com sucesso."
    )

    if dados.waba_id:
        print(
            "WABA ID recebido:",
            dados.waba_id
        )

    if dados.phone_number_id:
        print(
            "Phone Number ID recebido:",
            dados.phone_number_id
        )

    if dados.business_id:
        print(
            "Business ID recebido:",
            dados.business_id
        )

    # Mantemos a variável somente durante esta requisição.
    # Ela será usada no próximo passo para concluir as chamadas
    # necessárias da Graph API sem expor o token no navegador.
    del access_token

    return {
        "status": "ok",
        "message": "Autorização validada pela Meta com sucesso.",
        "waba_id": dados.waba_id,
        "phone_number_id": dados.phone_number_id,
        "business_id": dados.business_id,
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
