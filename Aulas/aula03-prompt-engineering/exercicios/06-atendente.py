"""Exercício 3 — um atendente que pergunta, pensa e age.

Uso:
    python 06-atendente.py             # conversa pelo terminal
    python 06-atendente.py --demo 1    # reproduz um dos quatro cenários

Requer as mesmas variáveis dos exemplos da aula: OPENAI_API_KEY,
LLM_BASE_URL (opcional) e LLM_MODELO (opcional).
"""

import argparse
import json
import os
import time
from datetime import date
from pathlib import Path

from dotenv import load_dotenv
from openai import APIStatusError, OpenAI, RateLimitError

load_dotenv()

client = OpenAI(
    base_url=os.environ.get("LLM_BASE_URL", "https://api.mistral.ai/v1"),
    api_key=os.environ.get("OPENAI_API_KEY"),
)

PASTA = Path(__file__).parent
PROMPTS = PASTA / "prompts"
HOJE = date(2026, 9, 8)
MAX_TURNOS_COLETA = 8
MAX_PASSOS = 12
MAX_TENTATIVAS_API = 4

PEDIDOS = {
    "48219": {"situacao": "em transporte", "previsao": "2026-09-02",
              "transportadora": "RápidoLog", "cliente": "Ana Souza"},
    "77310": {"situacao": "entregue", "previsao": "2026-08-19",
              "transportadora": "RápidoLog", "cliente": "Bruno Lima"},
    "90455": {"situacao": "aguardando coleta", "previsao": "2026-09-15",
              "transportadora": "TransBrasil", "cliente": "Ana Souza"},
    "31002": {"situacao": "em transporte", "previsao": "2026-09-11",
              "transportadora": "TransBrasil", "cliente": "Célia Rocha"},
}
CHAMADOS = {}
CATEGORIAS = ["entrega_atrasada", "endereco_errado", "produto_avariado",
              "duvida", "elogio"]
CONTADORES = {"modelo": 0, "ferramentas": 0}

# A unidade versionada é prompt × modelo × parâmetros, não só o texto.
COLETA = {
    "versao": 1, "prompt": "coleta-v1",
    "modelo": os.environ.get("LLM_MODELO", "mistral-small-latest"),
    # Conversa: alguma variação torna o atendimento menos robótico.
    "parametros": {"temperature": 0.6, "max_tokens": 180},
}
RACIOCINIO = {
    "versao": 1, "prompt": "raciocinio-v1",
    "modelo": os.environ.get("LLM_MODELO", "mistral-small-latest"),
    # Decisão baseada em dados: variação é defeito. Há espaço para o CoT.
    "parametros": {"temperature": 0, "max_tokens": 600},
}
REDACAO = {
    "versao": 1, "prompt": "redacao-v1",
    "modelo": os.environ.get("LLM_MODELO", "mistral-small-latest"),
    # Texto para pessoa: uma pequena variação é aceitável.
    "parametros": {"temperature": 0.5, "max_tokens": 180},
}


def carregar_prompt(nome: str, **variaveis: object) -> str:
    return (PROMPTS / f"{nome}.md").read_text(encoding="utf-8").format(**variaveis)


def chamar_modelo(config: dict, mensagens: list[dict]):
    """Chama a API, detecta truncamento e aplica backoff para 429."""
    for tentativa in range(MAX_TENTATIVAS_API):
        try:
            CONTADORES["modelo"] += 1
            resposta = client.chat.completions.create(
                model=config["modelo"], messages=mensagens, **config["parametros"]
            )
            escolha = resposta.choices[0]
            if escolha.finish_reason == "length":
                raise RuntimeError("resposta truncada (finish_reason='length')")
            return (escolha.message.content or "").strip()
        except RateLimitError:
            if tentativa == MAX_TENTATIVAS_API - 1:
                raise
            espera = 2 ** tentativa
            print(f"[429: aguardando {espera}s antes de tentar novamente]")
            time.sleep(espera)
        except APIStatusError:
            raise
    raise RuntimeError("não foi possível obter resposta do modelo")


# ----------------------------- ferramentas: o modelo não executa estas funções
def consultar_pedido(numero: str) -> dict:
    """Consulta o pedido; erros retornam como dados para manter o diálogo vivo."""
    CONTADORES["ferramentas"] += 1
    if not isinstance(numero, str) or not numero.isdigit() or len(numero) != 5:
        return {"erro": "número de pedido inválido", "dica": "use cinco dígitos"}
    pedido = PEDIDOS.get(numero)
    if pedido is None:
        return {"erro": f"pedido {numero} não encontrado",
                "dica": "peça ao cliente para conferir o número de cinco dígitos"}
    return {"numero": numero, **pedido}


def abrir_chamado(pedido: str, categoria: str, urgencia: str,
                  descricao: str, acao_sugerida: str) -> dict:
    """Ferramenta de escrita. Só deve ser chamada após confirmação explícita."""
    CONTADORES["ferramentas"] += 1
    if pedido not in PEDIDOS:
        return {"erro": "não é possível abrir chamado para pedido inexistente"}
    if categoria not in CATEGORIAS:
        return {"erro": f"categoria inválida: {categoria}"}
    if urgencia not in {"baixa", "media", "alta"}:
        return {"erro": f"urgência inválida: {urgencia}"}
    if not descricao.strip() or not acao_sugerida.strip():
        return {"erro": "descrição e ação sugerida são obrigatórias"}
    protocolo = f"{HOJE.year}-{len(CHAMADOS) + 842:04d}"
    CHAMADOS[protocolo] = {
        "protocolo": protocolo, "pedido": pedido, "categoria": categoria,
        "urgencia": urgencia, "descricao": descricao,
        "acao_sugerida": acao_sugerida,
    }
    return {"protocolo": protocolo}


def consultar_chamado(protocolo: str) -> dict:
    """Lê de volta uma escrita; não assume que criar equivale a persistir."""
    CONTADORES["ferramentas"] += 1
    chamado = CHAMADOS.get(protocolo)
    return chamado or {"erro": f"chamado {protocolo} não encontrado"}


# As descrições também são prompt: dizem ao modelo o que fazer e, sobretudo,
# o que NÃO fazer. O formato é o mesmo aceito em chat.completions.tools.
DECLARACOES_FERRAMENTAS = [
    {"type": "function", "function": {
        "name": "consultar_pedido",
        "description": "Consulta situação, previsão e transportadora de um pedido. "
                       "Use somente quando houver um número informado pelo cliente. "
                       "Não use para dúvidas gerais e nunca invente um número.",
        "parameters": {"type": "object", "properties": {
            "numero": {"type": "string", "description": "Número com cinco dígitos."}},
            "required": ["numero"], "additionalProperties": False},
    }},
    {"type": "function", "function": {
        "name": "abrir_chamado",
        "description": "Registra um chamado. Use apenas após diagnóstico e confirmação "
                       "explícita do cliente; nunca a use antes, pois altera o sistema.",
        "parameters": {"type": "object", "properties": {
            "pedido": {"type": "string"}, "categoria": {"type": "string", "enum": CATEGORIAS},
            "urgencia": {"type": "string", "enum": ["baixa", "media", "alta"]},
            "descricao": {"type": "string"}, "acao_sugerida": {"type": "string"}},
            "required": ["pedido", "categoria", "urgencia", "descricao", "acao_sugerida"],
            "additionalProperties": False},
    }},
    {"type": "function", "function": {
        "name": "consultar_chamado",
        "description": "Lê um chamado já criado para confirmar sua persistência. Use após "
                       "abrir_chamado; não use como substituto de uma abertura.",
        "parameters": {"type": "object", "properties": {"protocolo": {"type": "string"}},
                       "required": ["protocolo"], "additionalProperties": False},
    }},
]


def executar_ferramenta(nome: str, argumentos: dict) -> dict:
    """A fronteira de segurança: nomes e argumentos inválidos viram dados."""
    ferramentas = {
        "consultar_pedido": consultar_pedido,
        "abrir_chamado": abrir_chamado,
        "consultar_chamado": consultar_chamado,
    }
    funcao = ferramentas.get(nome)
    if funcao is None:
        return {"erro": f"ferramenta desconhecida: {nome}"}
    if not isinstance(argumentos, dict):
        return {"erro": "argumentos inválidos: esperado objeto JSON"}
    try:
        return funcao(**argumentos)
    except TypeError as erro:
        return {"erro": f"argumentos inválidos: {erro}"}


def imprimir_carimbo() -> None:
    print("=== ATENDIMENTO ===")
    for nome, config in (("coleta", COLETA), ("raciocinio", RACIOCINIO),
                         ("redacao", REDACAO)):
        parametros = config["parametros"]
        print(f"  {nome:<11} v{config['versao']}  prompt={config['prompt']:<16} "
              f"modelo={config['modelo']}  temp={parametros['temperature']}")


def json_do_modelo(texto: str, contexto: str) -> dict:
    try:
        inicio, fim = texto.find("{"), texto.rfind("}")
        if inicio < 0 or fim < inicio:
            raise ValueError("objeto JSON ausente")
        return json.loads(texto[inicio:fim + 1])
    except (json.JSONDecodeError, ValueError) as erro:
        raise RuntimeError(f"{contexto} não devolveu JSON válido: {erro}") from erro


def coletar(entrada, responder) -> tuple[list[dict], str]:
    """Conversa até o modelo declarar dados suficientes; não usa contador fixo."""
    historico = [{"role": "user", "content": entrada}]
    for _ in range(MAX_TURNOS_COLETA):
        prompt = carregar_prompt("coleta-v1", hoje=HOJE.isoformat())
        texto = chamar_modelo(COLETA, [{"role": "system", "content": prompt}, *historico])
        decisao = json_do_modelo(texto, "coleta")
        if decisao.get("pronto") is True:
            numero = str(decisao.get("numero_pedido", ""))
            if numero:
                return historico, numero
        pergunta = decisao.get("resposta")
        if not isinstance(pergunta, str) or not pergunta.strip():
            raise RuntimeError("coleta não forneceu pergunta")
        print(f"Bot: {pergunta}")
        resposta = responder("Cliente: ")
        historico.extend([
            {"role": "assistant", "content": pergunta},
            {"role": "user", "content": resposta},
        ])
    raise RuntimeError(f"coleta excedeu o teto de {MAX_TURNOS_COLETA} turnos")


def diagnosticar(historico: list[dict], pedido: dict) -> dict:
    # CoT entra somente aqui: comparar datas e versões dos fatos é uma tarefa
    # com etapas; na coleta só deixaria a conversa prolixa.
    prompt = carregar_prompt(
        "raciocinio-v1", hoje=HOJE.isoformat(), pedido=json.dumps(pedido, ensure_ascii=False),
        conversa=json.dumps(historico, ensure_ascii=False), categorias=", ".join(CATEGORIAS),
    )
    texto = chamar_modelo(RACIOCINIO, [{"role": "user", "content": prompt}])
    diagnostico = json_do_modelo(texto, "raciocínio")
    obrigatorios = {"categoria", "urgencia", "acao_sugerida", "descricao", "abrir_chamado"}
    if not obrigatorios <= diagnostico.keys():
        raise RuntimeError("conclusão do raciocínio incompleta")
    if diagnostico["categoria"] not in CATEGORIAS:
        raise RuntimeError("categoria fora do contrato")
    print("--- raciocínio ---")
    print(diagnostico.get("raciocinio", "(raciocínio não informado)"))
    print(f"Categoria: {diagnostico['categoria']}. Urgência: {diagnostico['urgencia']}.")
    print(f"Ação: {diagnostico['acao_sugerida']}")
    return diagnostico


def redigir(historico: list[dict], pedido: dict, diagnostico: dict, chamado: dict | None) -> str:
    prompt = carregar_prompt(
        "redacao-v1", conversa=json.dumps(historico, ensure_ascii=False),
        pedido=json.dumps(pedido, ensure_ascii=False),
        diagnostico=json.dumps(diagnostico, ensure_ascii=False),
        chamado=json.dumps(chamado, ensure_ascii=False),
    )
    return chamar_modelo(REDACAO, [{"role": "user", "content": prompt}])


def atender(entrada: str, responder=input) -> None:
    imprimir_carimbo()
    print(f"Cliente: {entrada}")
    passos = 0
    historico, numero = coletar(entrada, responder)
    passos += 1

    # Thought -> Action -> Observation: o programa executa a decisão do fluxo.
    print(f"[ACTION] consultar_pedido({numero!r})")
    pedido = executar_ferramenta("consultar_pedido", {"numero": numero})
    print(f"[OBSERVATION] {json.dumps(pedido, ensure_ascii=False)}")
    passos += 1
    while "erro" in pedido:
        if passos >= MAX_PASSOS:
            raise RuntimeError("agente excedeu o teto de passos")
        print("Bot: Não localizei esse pedido. Qual é o número correto?")
        nova_entrada = responder("Cliente: ")
        historico, numero = coletar(nova_entrada, responder)
        print(f"[ACTION] consultar_pedido({numero!r})")
        pedido = executar_ferramenta("consultar_pedido", {"numero": numero})
        print(f"[OBSERVATION] {json.dumps(pedido, ensure_ascii=False)}")
        passos += 1

    diagnostico = diagnosticar(historico, pedido)
    passos += 1
    chamado = None
    if diagnostico["abrir_chamado"]:
        print("Bot: Posso abrir um chamado com categoria "
              f"{diagnostico['categoria']}, urgência {diagnostico['urgencia']} e ação "
              f"\"{diagnostico['acao_sugerida']}\"? (sim/não)")
        confirmacao = responder("Cliente: ").strip().lower()
        if confirmacao in {"sim", "s", "confirmo", "pode"}:
            print("[ACTION] abrir_chamado(...) [escrita confirmada]")
            abertura = executar_ferramenta("abrir_chamado", {
                "pedido": numero, "categoria": diagnostico["categoria"],
                "urgencia": diagnostico["urgencia"], "descricao": diagnostico["descricao"],
                "acao_sugerida": diagnostico["acao_sugerida"],
            })
            print(f"[OBSERVATION] {json.dumps(abertura, ensure_ascii=False)}")
            if "erro" not in abertura:
                print(f"[ACTION] consultar_chamado({abertura['protocolo']!r})")
                chamado = executar_ferramenta(
                    "consultar_chamado", {"protocolo": abertura["protocolo"]}
                )
                print(f"[OBSERVATION] {json.dumps(chamado, ensure_ascii=False)}")
        else:
            diagnostico["acao_sugerida"] = "Nenhum chamado foi aberto, a pedido do cliente."
    print(f"Bot: {redigir(historico, pedido, diagnostico, chamado)}")
    print(f"[métricas] {CONTADORES['modelo']} chamadas ao modelo; "
          f"{CONTADORES['ferramentas']} chamadas a ferramentas")


DEMOS = {
    "1": ["meu pedido não chegou", "48219", "não, ninguém apareceu", "sim"],
    "2": ["o 77310 nunca chegou aqui", "não recebi nenhuma tentativa", "sim"],
    "3": ["cadê meu pedido 90455?", "não",],
    "4": ["o 99999 sumiu", "48219", "não, ninguém apareceu", "sim"],
}


def responder_demo(respostas: list[str]):
    def responder(rotulo: str) -> str:
        if not respostas:
            raise RuntimeError("o roteiro de demonstração acabou")
        resposta = respostas.pop(0)
        print(f"{rotulo}{resposta}")
        return resposta
    return responder


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo", choices=DEMOS, help="roda um dos quatro roteiros da entrega")
    args = parser.parse_args()
    try:
        if args.demo:
            roteiro = DEMOS[args.demo].copy()
            atender(roteiro.pop(0), responder_demo(roteiro))
        else:
            atender(input("Cliente: "))
    except Exception as erro:  # demonstração de falhas tratadas no terminal
        print(f"[ERRO TRATADO] {type(erro).__name__}: {erro}")
