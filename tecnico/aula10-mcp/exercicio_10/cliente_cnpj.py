# Exercício 10 — cliente MCP que encadeia CNPJ e CEP.
#
# O cliente conhece o contrato MCP (nomes e campos das ferramentas), mas não
# conhece a BrasilAPI nem seus endpoints. Se o servidor trocar a fonte, este
# cliente não muda enquanto o contrato das ferramentas continuar igual.
#
# Uso, com 00-servidor-cnpj.py rodando em outro terminal:
#     python cliente_cnpj.py 19.131.243/0001-97
# URL alternativa: defina MCP_CNPJ_URL (por padrão http://127.0.0.1:8001/mcp).

import asyncio
import json
import os
import re
import sys

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


URL_SERVIDOR = os.environ.get("MCP_CNPJ_URL", "http://127.0.0.1:8001/mcp")


def digitos(valor: str) -> str:
    return re.sub(r"\D", "", valor)


def formatar_cnpj(valor: str) -> str:
    numeros = digitos(valor)
    if len(numeros) != 14:
        return valor
    return f"{numeros[:2]}.{numeros[2:5]}.{numeros[5:8]}/{numeros[8:12]}-{numeros[12:]}"


def formatar_cep(valor: str | None) -> str:
    numeros = digitos(valor or "")
    if len(numeros) != 8:
        return valor or "não disponível"
    return f"{numeros[:5]}-{numeros[5:]}"


def texto_retorno(resultado) -> dict:
    """Lê o texto MCP e falha explicitamente em erros de infraestrutura."""
    if resultado.isError:
        detalhes = "\n".join(
            bloco.text for bloco in resultado.content
            if getattr(bloco, "text", None)
        )
        raise RuntimeError(detalhes or "falha de infraestrutura na ferramenta")
    # Algumas versões do SDK também expõem o objeto em structuredContent;
    # usar esse campo evita depender de como a versão serializa o texto.
    estruturado = getattr(resultado, "structuredContent", None)
    if isinstance(estruturado, dict):
        return estruturado
    partes = [bloco.text for bloco in resultado.content
              if getattr(bloco, "text", None)]
    if not partes:
        raise RuntimeError("o servidor retornou uma resposta sem conteúdo textual")
    try:
        return json.loads("\n".join(partes))
    except json.JSONDecodeError as erro:
        raise RuntimeError("resposta MCP não está no JSON esperado") from erro


async def executar(cnpj: str) -> int:
    async with streamable_http_client(URL_SERVIDOR) as (leitura, escrita, _):
        async with ClientSession(leitura, escrita) as sessao:
            await sessao.initialize()
            lista = await sessao.list_tools()
            nomes = [ferramenta.name for ferramenta in lista.tools]
            faltantes = {"consultar_cnpj", "consultar_cep"} - set(nomes)
            if faltantes:
                raise RuntimeError(
                    "servidor MCP sem as ferramentas necessárias: "
                    + ", ".join(sorted(faltantes))
                )

            print(f"SERVIDOR: {sessao.server_info.name}   (ferramentas: {', '.join(nomes)})")
            print()
            print(f"CNPJ ............ {formatar_cnpj(cnpj)}")

            empresa = texto_retorno(await sessao.call_tool(
                "consultar_cnpj", arguments={"cnpj": cnpj}
            ))
            if empresa.get("erro"):
                print(f"ERRO ............ {empresa['erro']}")
                print(f"Formato correto . {empresa.get('formato_correto', '14 dígitos')}")
                print(f"Ação ............ {empresa.get('sugestao', 'corrija o CNPJ e tente novamente')}")
                return 1

            cep = empresa.get("cep")
            if not cep:
                print("ERRO ............ consulta do CNPJ não trouxe CEP para encadear a consulta")
                return 1

            # O encadeamento é responsabilidade do cliente. O endereço final
            # vem da consulta CEP; os campos de endereço do CNPJ não são usados.
            endereco = texto_retorno(await sessao.call_tool(
                "consultar_cep", arguments={"cep": cep}
            ))
            if endereco.get("erro"):
                print(f"Razão social .... {empresa.get('razao_social') or 'não disponível'}")
                print(f"CEP ............. {formatar_cep(cep)}")
                print(f"ERRO ............ {endereco['erro']}")
                print(f"Ação ............ {endereco.get('sugestao', 'confira o CEP')}")
                return 1

            rua = endereco.get("street") or "(rua não disponível)"
            bairro = endereco.get("neighborhood") or "(bairro não disponível)"
            cidade = endereco.get("city") or "(cidade não disponível)"
            uf = endereco.get("state") or "--"
            latitude, longitude = endereco.get("latitude"), endereco.get("longitude")
            coordenadas = (f"{latitude} / {longitude}"
                           if latitude is not None and longitude is not None
                           else "não disponível para este CEP")

            print(f"Razão social .... {empresa.get('razao_social') or 'não disponível'}")
            print(f"CEP ............. {formatar_cep(cep)}")
            print(f"Endereço ........ {rua} — {bairro}, {cidade}/{uf}")
            print(f"Lat / Long ...... {coordenadas}")
            return 0


def main() -> int:
    if len(sys.argv) != 2:
        print("Uso: python cliente_cnpj.py <CNPJ>", file=sys.stderr)
        return 2
    try:
        return asyncio.run(executar(sys.argv[1]))
    except Exception as erro:
        print(f"Falha ao consultar o servidor MCP: {erro}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())


# Saídas dos três casos pedidos (execute o servidor em outro terminal):
#
# 1) CNPJ válido com coordenadas
# $ python cliente_cnpj.py 19.131.243/0001-97
# SERVIDOR: brasilapi-cnpj-cep   (ferramentas: consultar_cnpj, consultar_cep)
#
# CNPJ ............ 19.131.243/0001-97
# Razão social .... OPEN KNOWLEDGE BRASIL
# CEP ............. 01311-902
# Endereço ........ Avenida Paulista 37 — Bela Vista, São Paulo/SP
# Lat / Long ...... -23.5475 / -46.63611
#
# 2) CNPJ com formato inválido
# $ python cliente_cnpj.py 123
# SERVIDOR: brasilapi-cnpj-cep   (ferramentas: consultar_cnpj, consultar_cep)
#
# CNPJ ............ 123
# ERRO ............ CNPJ deve ter exatamente 14 dígitos
# Formato correto . 14 dígitos; pontuação é opcional
# Ação ............ corrija o CNPJ e chame a ferramenta novamente
#
# 3) CNPJ com formato válido, mas inexistente
# $ python cliente_cnpj.py 00.000.000/0000-00
# SERVIDOR: brasilapi-cnpj-cep   (ferramentas: consultar_cnpj, consultar_cep)
#
# CNPJ ............ 00.000.000/0000-00
# ERRO ............ CNPJ não encontrado ou rejeitado pela BrasilAPI
# Formato correto . 14 dígitos; pontuação é opcional
# Ação ............ confira o número e tente novamente
