"""Exercício 02 — do e-mail do cliente ao chamado aberto.

Execute a partir da raiz do projeto:
    source .venv/bin/activate
    python Aulas/aula02-modelos-e-parametros/exercicio/08-abertura-de-chamados.py
"""

import json
import os
import time
from collections import defaultdict

from dotenv import load_dotenv
from openai import OpenAI


load_dotenv()

client = OpenAI(
    base_url=os.environ.get("LLM_BASE_URL", "https://api.mistral.ai/v1"),
    api_key=os.environ.get("OPENAI_API_KEY"),
)

MODELO = os.environ.get("LLM_MODELO", "mistral-small-latest")
MAX_TENTATIVAS = 4

# Preços em US$ por 1 milhão de tokens. Consultado em 21/08/2026 em
# https://docs.mistral.ai/inference/pricing . Atualize junto com o modelo.
PRECOS = {
    "mistral-small-latest": {"entrada": 0.15, "saida": 0.60},
    "mistral-small-2603": {"entrada": 0.15, "saida": 0.60},
}

# --- ETAPA 1: ler e processar -------------------------------------------
# temperature 0       -> extração: variação aqui é DEFEITO (nota 02, §9).
# max_tokens 120      -> ponto de partida para o schema de três campos; o fim
#                        do programa mostra o maior completion_tokens do lote
#                        para dimensionar o próximo limite (nota 02, §8).
# response_format     -> JSON Schema com enum impede rótulo fora da lista
#                        (nota 02, §7.3). Meça completion_tokens ao executar.
# penalidades 0       -> penalizariam repetições que fazem parte do JSON
#                        (nota 03, §5), portanto não ajudam nesta tarefa.
EXTRACAO = {
    "temperature": 0,
    "max_tokens": 120,
    "frequency_penalty": 0,
    "presence_penalty": 0,
}

# --- ETAPA 2: redigir o chamado -----------------------------------------
# temperature 0.35    -> há espaço para fluência, mas consistência factual
#                        ainda é mais importante que criatividade (nota 02, §9).
# max_tokens 280      -> título, descrição e ação são maiores; o fim mostra o
#                        maior completion_tokens para validar este pior caso
#                        com as execuções reais (nota 02, §8).
# response_format     -> schema separa os três trechos para o código montar o
#                        chamado; formato não deve depender só do prompt (§7.3).
# penalidades 0       -> não são necessárias: instruções de concisão controlam
#                        repetição sem distorcer termos importantes (nota 03, §5).
REDACAO = {
    "temperature": 0.35,
    "max_tokens": 280,
    "frequency_penalty": 0,
    "presence_penalty": 0,
}

# A redação costuma custar mais: ela gera até 280 tokens e a tarifa de saída
# (US$/M tokens) é maior que a de entrada; a extração retorna só um JSON curto.

CATEGORIAS = [
    "entrega_atrasada",
    "endereco_errado",
    "produto_avariado",
    "duvida",
    "elogio",
]
URGENCIAS = ["baixa", "media", "alta"]
MENSAGENS = [
    ("Meu pedido 48219 era pra chegar terça e até hoje nada. Já são 5 dias!",
     "entrega_atrasada", "48219"),
    ("bom dia, o entregador deixou na rua de tras, numero 45. o meu é 145",
     "endereco_errado", None),
    ("A caixa do pedido 77310 chegou toda amassada e a tampa do liquidificador trincou",
     "produto_avariado", "77310"),
    ("vocês entregam no sábado?", "duvida", None),
    ("Só pra dizer que o rapaz da entrega foi super educado, obrigada!", "elogio", None),
    ("Pedido 90021 cancelado e recomprado como 90455, o 90455 não chegou",
     "entrega_atrasada", "90455"),
    ("PEDIDO 12 MIL 340 ENTREGUE NO CEP ERRADO, EU MORO NO 04567890 E FOI PRO 04567089",
     "endereco_errado", "12340"),
    ("Recebi o pedido n 55.102 com a tela rachada. Quero trocar.",
     "produto_avariado", "55102"),
]

SCHEMA_EXTRACAO = {
    "type": "object",
    "properties": {
        "categoria": {"type": "string", "enum": CATEGORIAS},
        "pedido": {"type": ["string", "null"], "pattern": "^[0-9]+$"},
        "urgencia": {"type": "string", "enum": URGENCIAS},
    },
    "required": ["categoria", "pedido", "urgencia"],
    "additionalProperties": False,
}

SCHEMA_REDACAO = {
    "type": "object",
    "properties": {
        "titulo": {"type": "string", "minLength": 1},
        "descricao": {"type": "string", "minLength": 1},
        "acao_sugerida": {"type": "string", "minLength": 1},
    },
    "required": ["titulo", "descricao", "acao_sugerida"],
    "additionalProperties": False,
}
CAMPOS = ["Categoria:", "Urgência:", "Pedido:", "Título:", "Descrição:", "Ação sugerida:"]


class RespostaTruncadaError(RuntimeError):
    """A API atingiu max_tokens: conteúdo parcial não pode virar chamado."""


def e_erro_429(erro):
    """Funciona tanto com RateLimitError quanto com clientes compatíveis."""
    return getattr(erro, "status_code", None) == 429


def chamar_api(mensagens, configuracao, response_format):
    """Chama a API com backoff somente para 429 e rejeita saída truncada."""
    for tentativa in range(MAX_TENTATIVAS):
        try:
            resposta = client.chat.completions.create(
                model=MODELO,
                messages=mensagens,
                response_format=response_format,
                **configuracao,
            )
            escolha = resposta.choices[0]
            if escolha.finish_reason == "length":
                raise RespostaTruncadaError(
                    "finish_reason='length': aumente max_tokens e refaça a chamada"
                )
            if escolha.finish_reason not in {"stop", None}:
                raise RuntimeError(f"finish_reason inesperado: {escolha.finish_reason!r}")
            conteudo = (escolha.message.content or "").strip()
            if not conteudo:
                raise RuntimeError("a API retornou conteúdo vazio")
            return conteudo, resposta.usage
        except Exception as erro:  # noqa: BLE001 - queremos continuar no lote
            if e_erro_429(erro) and tentativa < MAX_TENTATIVAS - 1:
                espera = 2 ** tentativa
                print(f"  429 recebido; nova tentativa em {espera}s "
                      f"({tentativa + 1}/{MAX_TENTATIVAS})")
                time.sleep(espera)
                continue
            raise
    raise RuntimeError("não deveria chegar aqui")


def carregar_json(conteudo, schema, nome_etapa):
    """Validação defensiva, mesmo quando o provedor aceita JSON Schema."""
    try:
        dados = json.loads(conteudo)
    except json.JSONDecodeError as erro:
        raise ValueError(f"{nome_etapa}: JSON inválido: {erro.msg}") from erro

    obrigatorios = schema["required"]
    if not isinstance(dados, dict) or set(dados) != set(obrigatorios):
        raise ValueError(f"{nome_etapa}: chaves inválidas: {dados!r}")
    return dados


def extrair(mensagem):
    prompt = f"""Classifique e extraia dados da mensagem de uma transportadora.

Categorias permitidas: {", ".join(CATEGORIAS)}.
Retorne apenas o objeto do schema.

Regras de desempate:
- Se houver mais de um pedido, use o pedido sobre o qual há reclamação.
- Se houver elogio e reclamação, classifique a reclamação.
- Número de casa, CEP e outros números não são pedido.
- Converta pedido por extenso ou com pontuação para uma string só de dígitos.
- urgencia é baixa, media ou alta conforme tom e problema relatados.

Mensagem do cliente:
{mensagem}"""
    conteudo, uso = chamar_api(
        [{"role": "user", "content": prompt}],
        EXTRACAO,
        {"type": "json_schema", "json_schema": {
            "name": "dados_chamado", "schema": SCHEMA_EXTRACAO, "strict": True,
        }},
    )
    dados = carregar_json(conteudo, SCHEMA_EXTRACAO, "extração")
    if dados["categoria"] not in CATEGORIAS or dados["urgencia"] not in URGENCIAS:
        raise ValueError(f"extração: valores fora do contrato: {dados!r}")
    if dados["pedido"] is not None and not dados["pedido"].isdigit():
        raise ValueError(f"extração: pedido inválido: {dados['pedido']!r}")
    return dados, uso


def redigir(mensagem, dados):
    prompt = f"""Escreva os três trechos de um chamado de atendimento.
Use exclusivamente os fatos da mensagem original e os dados classificados.
Não invente nome, endereço, data, tentativa de entrega ou qualquer outro fato.
Não inclua os rótulos "Título", "Descrição" ou "Ação sugerida" no texto.

Ação sugerida é obrigatória: comece com verbo e diga o destinatário claro,
além de uma providência específica para esta mensagem. Exemplos bons:
"Acionar a transportadora para rastrear o pedido 48219 e retornar ao cliente
com nova previsão" e "Encaminhar ao atendimento comercial a dúvida sobre
entregas aos sábados para que responda ao cliente". Não use ação genérica.
Se pedido for nulo, não invente um número.

Dados classificados:
{json.dumps(dados, ensure_ascii=False)}

Mensagem original:
{mensagem}"""
    conteudo, uso = chamar_api(
        [{"role": "user", "content": prompt}],
        REDACAO,
        {"type": "json_schema", "json_schema": {
            "name": "texto_chamado", "schema": SCHEMA_REDACAO, "strict": True,
        }},
    )
    texto = carregar_json(conteudo, SCHEMA_REDACAO, "redação")
    if not all(isinstance(texto[campo], str) and texto[campo].strip()
               for campo in SCHEMA_REDACAO["required"]):
        raise ValueError(f"redação: campo vazio: {texto!r}")
    return texto, uso


def montar_chamado(numero, dados, texto):
    pedido = dados["pedido"] or "não informado"
    chamado = f"""=== CHAMADO #{numero} ===
Categoria:  {dados['categoria']}
Urgência:   {dados['urgencia']}
Pedido:     {pedido}

Título: {texto['titulo'].strip()}

Descrição:
{texto['descricao'].strip()}

Ação sugerida: {texto['acao_sugerida'].strip()}"""
    faltando = [campo for campo in CAMPOS if campo not in chamado]
    if faltando:
        raise ValueError(f"chamado incompleto, faltam: {faltando}")
    return chamado


def tokens(uso, atributo):
    return int(getattr(uso, atributo, 0) or 0) if uso else 0


def custo(uso):
    preco = PRECOS.get(MODELO)
    if preco is None:
        return None
    return (tokens(uso, "prompt_tokens") * preco["entrada"]
            + tokens(uso, "completion_tokens") * preco["saida"]) / 1_000_000


def imprimir_custos(usos, concluidos):
    if not concluidos:
        print("\nSem chamados concluídos; não há custo médio para calcular.")
        return
    if MODELO not in PRECOS:
        print(f"\nPreço não configurado para {MODELO!r}; inclua-o em PRECOS.")
        return

    por_etapa = {etapa: sum(custo(uso) or 0 for uso in lista)
                 for etapa, lista in usos.items()}
    total = sum(por_etapa.values())
    print("\n--- CUSTOS (US$) ---")
    print(f"Extração:             ${por_etapa['extracao']:.8f}")
    print(f"Redação:              ${por_etapa['redacao']:.8f}")
    print(f"Médio por chamado:    ${total / concluidos:.8f}")
    print(f"Projeção (800/dia):   ${(total / concluidos) * 800:.6f}/dia")
    print("\n--- MEDIÇÃO PARA max_tokens ---")
    print("Maior completion_tokens — extração: "
          f"{max((tokens(uso, 'completion_tokens') for uso in usos['extracao']), default=0)}")
    print("Maior completion_tokens — redação:  "
          f"{max((tokens(uso, 'completion_tokens') for uso in usos['redacao']), default=0)}")


def main():
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("Defina OPENAI_API_KEY no arquivo .env antes de executar.")

    usos = defaultdict(list)
    chamados = 0
    falhas = 0
    acertos = 0

    for indice, (mensagem, categoria_esperada, pedido_esperado) in enumerate(MENSAGENS, 1):
        print(f"\n{'=' * 78}\nMensagem {indice}: {mensagem}")
        try:
            dados, uso_extracao = extrair(mensagem)
            usos["extracao"].append(uso_extracao)
            if (dados["categoria"], dados["pedido"]) == (categoria_esperada, pedido_esperado):
                acertos += 1

            texto, uso_redacao = redigir(mensagem, dados)
            usos["redacao"].append(uso_redacao)
            chamado = montar_chamado(f"2026-{indice:04d}", dados, texto)
            print(chamado)
            chamados += 1
        except Exception as erro:  # noqa: BLE001 - falha de uma mensagem não para o lote
            falhas += 1
            print(f"ERRO TRATADO na mensagem {indice}: {type(erro).__name__}: {erro}")

    print(f"\n{'=' * 78}")
    print(f"Etapa 1 — categoria e pedido corretos: {acertos}/8")
    print(f"Resultado: {chamados} mensagens viraram chamado; {falhas} falharam.")
    imprimir_custos(usos, chamados)


if __name__ == "__main__":
    main()
