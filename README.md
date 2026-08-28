# Elo Ambientes Planejados — Agente IA

Projeto inicial em Python/FastAPI para centralizar:
- WhatsApp Cloud API
- Instagram Messaging
- OpenAI
- Cadastro de leads em banco SQL

## 1. Instalação

```bash
python -m venv .venv
```

Windows:
```bash
.venv\Scripts\activate
```

Linux/macOS:
```bash
source .venv/bin/activate
```

```bash
pip install -r requirements.txt
```

Copie `.env.example` para `.env` e preencha as credenciais.

## 2. Rodar

```bash
uvicorn app.main:app --reload --port 8000
```

Abra:
- http://localhost:8000/
- http://localhost:8000/docs

## 3. Webhook

Na Meta, configure uma URL pública apontando para:

`https://SEU-DOMINIO.com/webhook`

Para desenvolvimento local, publique a porta 8000 com um túnel HTTPS.

## 4. Fluxo do agente

O agente pergunta progressivamente:
1. nome
2. cidade/bairro
3. ambiente desejado
4. se possui medidas
5. estilo/preferência
6. faixa de investimento
7. prazo
8. convite para enviar fotos
9. encaminhamento para vendedor quando qualificado

## Observação

As permissões, versões de Graph API e requisitos de revisão podem mudar.
Antes de produção, valide a configuração atual no painel Meta for Developers.
