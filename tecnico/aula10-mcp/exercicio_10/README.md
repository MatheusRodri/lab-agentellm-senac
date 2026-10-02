# Exercício 10 — MCP de CNPJ e CEP

O servidor publica as ferramentas `consultar_cnpj` e `consultar_cep` por
Streamable HTTP. O cliente usa `ClientSession`, lista o contrato disponível e
encadeia a consulta de CEP com o CEP encontrado no cadastro da empresa.

Na raiz do repositório, instale as dependências de `tecnico/requirements.txt`.
Abra dois terminais na pasta `tecnico/aula10-mcp/exercicio_10/`:

```bash
python 00-servidor-cnpj.py
python cliente_cnpj.py 19.131.243/0001-97
```

O servidor escuta em `127.0.0.1:8001/mcp`, sem autenticação e apenas na
interface local. Para outro endereço, configure `MCP_CNPJ_URL` no processo do
cliente. As chamadas à BrasilAPI têm timeout de 10 segundos.
