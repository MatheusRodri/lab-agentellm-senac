# Exercício 11 — Suíte do AgendeAkiAI

Pacote de avaliação ligado ao case AgendeAkiAI (`/home/matheus/projects/bot-agendeakiai`). O case usa catálogo, regras, API e clientes simulados; portanto, os casos observados são de desenvolvimento, não de produção.

## Conteúdo

- `dataset-v1.0.0.json`: 20 casos distribuídos em quatro classes, com origem, entrada, esperado e motivo de inclusão.
- `rubrica-v1.0.0.md`: propriedade textual avaliada pelo juiz, critério binário e exemplos.
- `avaliacao.py`: avaliação determinística de saída, trajetória e resultado, seguida do cálculo de fatias e da decisão da suíte.
- `juiz.py`: juiz estruturado usando o cliente de modelo da Aula 11.
- `rotulos-humanos.json`: estrutura para registrar os 30 rótulos manuais exigidos.
- `relatorio.md`: justificativas, regra de promoção prévia e campos para preencher com resultados reais.

## O que falta executar

O repositório do case ainda não tem duas versões avaliadas nos 20 casos nem 30 saídas rotuladas por pessoas. Por isso este pacote não inventa concordância, dispersão, métricas A/B ou decisão de promoção. Os casos sintéticos foram revisados por Codex contra `docs/case.md`, `docs/io.md`, `src/grafo.py`, `src/mock_api.py` e `dados/catalogo.json`; a equipe deve fazer a validação final dos casos antes de usar os números na entrega.

O modo padrão do AgendeAkiAI é determinístico (`MODO=mock`). A comparação A/B com efeito em respostas requer o modo Mistral, alterando somente a frase de prompt descrita no relatório. Resultado e trajetória continuam sendo medidos pelo código, sem depender do juiz.

## Uso das métricas

O `avaliacao.py` importa um JSON de resultados com a forma descrita em `relatorio.md`. Cada caso deve ter duas execuções em cada bloco (`A1`, `A2` e `B`); A1 e A2 são blocos separados para estimar o ruído. Inclua os snapshots do estado da API mock antes e depois de cada execução, a saída validada e os eventos do grafo.

Cada item de resultado deve seguir este formato (repita cada `id` duas vezes por bloco):

```json
{
  "id": "AG-001",
  "classe": "agendamento_aprovacao",
  "saida_validada": {"resultado": "...", "fontes": [], "suficiente": true},
  "trace": [{"tipo": "ferramenta", "ferramenta": "buscar_opcoes", "resultado": {"opcoes": []}}],
  "estado_antes": {"agendamentos": []},
  "estado_depois": {"agendamentos": []},
  "repeticao_idempotente": {"segunda_chamada": {"ja_existia": true}}
}
```

O campo `repeticao_idempotente` só é obrigatório nos casos que testam repetição. Os snapshots precisam vir da mesma instância isolada do mock durante uma execução, para capturar alterações reais de estado.

Para o juiz, copie 30 respostas representativas para `rotulos-humanos.json`, preencha `humano` e `nota_humana` após revisão manual, e execute `juiz.py` no ambiente configurado com `LLM_PROVEDOR`, chave ou servidor local e `LLM_MODELO_JUIZ`. A concordância não é calculada antes dos rótulos humanos e das respostas do juiz existirem.
