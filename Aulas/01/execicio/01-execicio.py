# Assistente que verifica disponibilidade de entrega

import json
import os
import requests
from datetime import datetime, date, timedelta
from dotenv import load_dotenv
from openai import OpenAI


# Carrega as variáveis do arquivo .env
load_dotenv()


# Cliente usando a API da Mistral
client = OpenAI(
    base_url="https://api.mistral.ai/v1",
    api_key=os.environ.get("OPENAI_API_KEY")
)


# --- Ferramenta ---
def verificar_entrega(cep, data_entrega):
    """Verifica se uma entrega pode ser realizada para o CEP e data informados."""

    # Remove caracteres do CEP
    cep = cep.replace("-", "").replace(".", "").strip()

    # Valida o CEP
    if not cep.isdigit() or len(cep) != 8:
        return {
            "pode_entregar": False,
            "motivo": "CEP inválido."
        }

    # Converte e valida a data
    try:
        data = datetime.strptime(data_entrega, "%d/%m/%Y").date()
    except ValueError:
        return {
            "pode_entregar": False,
            "motivo": "Data inválida. Use o formato DD/MM/AAAA."
        }

    hoje = date.today()

    # Não permite entrega hoje ou em datas passadas
    if data <= hoje:
        return {
            "pode_entregar": False,
            "motivo": "A data da entrega deve ser a partir de amanhã."
        }

    # Prazo máximo de 7 dias
    data_maxima = hoje + timedelta(days=7)

    if data > data_maxima:
        return {
            "pode_entregar": False,
            "motivo": "Só aceitamos entregas para os próximos 7 dias."
        }

    # Consulta os feriados na BrasilAPI
    try:
        url = f"https://brasilapi.com.br/api/feriados/v1/{data.year}"

        response = requests.get(url, timeout=10)
        response.raise_for_status()

        feriados = response.json()

    except requests.RequestException:
        return {
            "pode_entregar": False,
            "motivo": "Não foi possível consultar os feriados."
        }

    # Converte a data para o formato usado pela BrasilAPI
    data_formatada = data.strftime("%Y-%m-%d")

    # Verifica se a data escolhida é feriado
    for feriado in feriados:
        if feriado["date"] == data_formatada:
            return {
                "pode_entregar": False,
                "motivo": f"Não realizamos entregas no feriado: {feriado['name']}."
            }

    return {
        "pode_entregar": True,
        "motivo": "Entrega disponível para o CEP e data informados."
    }


# Mapeamento das ferramentas
FERRAMENTAS = {
    "verificar_entrega": verificar_entrega
}


# Ferramentas disponíveis para o modelo
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "verificar_entrega",
            "description": "Verifica se é possível realizar uma entrega para um CEP em uma determinada data.",
            "parameters": {
                "type": "object",
                "properties": {
                    "cep": {
                        "type": "string",
                        "description": "CEP onde será realizada a entrega."
                    },
                    "data_entrega": {
                        "type": "string",
                        "description": "Data desejada para entrega no formato DD/MM/AAAA."
                    }
                },
                "required": ["cep", "data_entrega"]
            }
        }
    }
]


messages = [
    {
        "role": "system",
        "content": (
            "Você é um assistente de entregas. "
            "Use a ferramenta verificar_entrega para verificar se uma entrega é possível. "
            "Nunca invente a disponibilidade. "
            "Responda de forma simples e objetiva em português."
        )
    }
]


# Dados do usuário
cep = input("Digite o CEP: ")
data_entrega = input("Digite a data de entrega (DD/MM/AAAA): ")

pergunta = f"Posso realizar uma entrega para o CEP {cep} no dia {data_entrega}?"

messages.append({
    "role": "user",
    "content": pergunta
})


# Envia a pergunta para o modelo
response = client.chat.completions.create(
    model="mistral-small-latest",
    messages=messages,
    tools=TOOLS
)

resposta = response.choices[0].message
messages.append(resposta)


# Caso o modelo queira usar a ferramenta
if resposta.tool_calls:

    for chamada in resposta.tool_calls:

        argumentos = json.loads(
            chamada.function.arguments or "{}"
        )

        resultado = FERRAMENTAS[
            chamada.function.name
        ](**argumentos)

        messages.append({
            "role": "tool",
            "tool_call_id": chamada.id,
            "content": json.dumps(
                resultado,
                ensure_ascii=False
            )
        })


    # Mistral gera a resposta final
    response = client.chat.completions.create(
        model="mistral-small-latest",
        messages=messages,
        tools=TOOLS
    )

    print()
    print(response.choices[0].message.content)

else:
    print()
    print(resposta.content)