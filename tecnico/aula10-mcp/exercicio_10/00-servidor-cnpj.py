# Exercício 10 — servidor MCP de CNPJ e CEP.
#
# Protocolo MCP: revisão 2025-11-25.
# SDK Python `mcp`: 1.27.0 (versão fixada em ../../requirements.txt).
#
# Inicie em um terminal próprio. O cliente conecta-se a este processo:
#     python 00-servidor-cnpj.py

import re

import requests
from mcp.server.fastmcp import FastMCP


BASE_URL = "https://brasilapi.com.br/api"
TIMEOUT_SEGUNDOS = 10
ENDERECO = "127.0.0.1"
PORTA = 8001

servidor = FastMCP("brasilapi-cnpj-cep")


def _normalizar_documento(valor: str, tamanho: int, rotulo: str) -> str | dict:
    """Retira pontuação permitida e devolve domínio inválido como conteúdo."""
    texto = str(valor).strip()
    if not re.fullmatch(r"[0-9.\-/\s]+", texto):
        return {
            "erro": f"{rotulo} contém caracteres inválidos",
            "recebido": valor,
            "formato_correto": f"{tamanho} dígitos; pontuação é opcional",
            "sugestao": "envie apenas os dígitos ou use a pontuação convencional",
        }

    digitos = re.sub(r"\D", "", texto)
    if len(digitos) != tamanho:
        return {
            "erro": f"{rotulo} deve ter exatamente {tamanho} dígitos",
            "recebido": valor,
            "formato_correto": f"{tamanho} dígitos; pontuação é opcional",
            "sugestao": f"corrija o {rotulo} e chame a ferramenta novamente",
        }
    return digitos


def _consultar(endpoint: str) -> requests.Response:
    """Timeout evita deixar chamadas externas prenderem o servidor."""
    resposta = requests.get(f"{BASE_URL}/{endpoint}", timeout=TIMEOUT_SEGUNDOS)
    # 4xx representa entrada inexistente/rejeitada (domínio); 5xx e falhas
    # de transporte são levantadas como exceções e viram falha MCP.
    if 400 <= resposta.status_code < 500 and resposta.status_code != 429:
        return resposta
    resposta.raise_for_status()
    return resposta


@servidor.tool()
def consultar_cnpj(cnpj: str) -> dict:
    """Consulta uma empresa pelo CNPJ e devolve identificação e endereço cadastral.

    cnpj: exatamente 14 dígitos; aceita pontuação convencional, como
    19.131.243/0001-97. A resposta mantém cnpj, razao_social e campos do
    endereço cadastral (cep, logradouro, numero, complemento, bairro,
    municipio, uf): identificam a empresa e fornecem o CEP para a consulta
    seguinte sem carregar sócios, CNAEs ou dados tributários irrelevantes.

    NÃO devolve coordenadas nem valida situação cadastral. Para endereço e
    coordenadas associados ao CEP, chame consultar_cep separadamente.
    """
    normalizado = _normalizar_documento(cnpj, 14, "CNPJ")
    if isinstance(normalizado, dict):
        return normalizado

    resposta = _consultar(f"cnpj/v1/{normalizado}")
    if resposta.status_code >= 400:
        return {
            "erro": "CNPJ não encontrado ou rejeitado pela BrasilAPI",
            "recebido": cnpj,
            "formato_correto": "14 dígitos; pontuação é opcional",
            "sugestao": "confira o número e tente novamente",
        }

    dados = resposta.json()
    # Mantemos só a identificação e o endereço cadastral, que fornece o CEP
    # usado pelo cliente na segunda consulta. Os demais campos não são usados.
    campos = ("cnpj", "razao_social", "cep", "logradouro", "numero",
              "complemento", "bairro", "municipio", "uf")
    return {campo: dados.get(campo) for campo in campos}


@servidor.tool()
def consultar_cep(cep: str) -> dict:
    """Consulta um CEP e devolve rua, bairro, cidade, UF e coordenadas se houver.

    cep: exatamente 8 dígitos; aceita pontuação convencional, como 01311-902.

    NÃO busca endereço por nome de rua e NÃO retorna dados de empresa; use
    consultar_cnpj para localizar o CEP cadastral de uma empresa.
    """
    normalizado = _normalizar_documento(cep, 8, "CEP")
    if isinstance(normalizado, dict):
        return normalizado

    resposta = _consultar(f"cep/v2/{normalizado}")
    if resposta.status_code >= 400:
        return {
            "erro": "CEP não encontrado ou rejeitado pela BrasilAPI",
            "recebido": cep,
            "formato_correto": "8 dígitos; pontuação é opcional",
            "sugestao": "confira o CEP e tente novamente",
        }

    dados = resposta.json()
    coordenadas = (dados.get("location") or {}).get("coordinates") or {}
    # Estes são os campos de endereço pedidos; latitude/longitude podem faltar.
    return {
        "cep": dados.get("cep"),
        "street": dados.get("street"),
        "neighborhood": dados.get("neighborhood"),
        "city": dados.get("city"),
        "state": dados.get("state"),
        "latitude": coordenadas.get("latitude"),
        "longitude": coordenadas.get("longitude"),
    }


if __name__ == "__main__":
    print(f"servidor brasilapi-cnpj-cep em http://{ENDERECO}:{PORTA}/mcp")
    servidor.run(transport="streamable-http", host=ENDERECO, port=PORTA)
