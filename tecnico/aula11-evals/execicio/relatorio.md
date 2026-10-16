# Aula 11 — A suíte do AgendeAkiAI

**Data da regra prévia:** 2026-10-09. A regra abaixo foi registrada antes de qualquer comparação A/B desta entrega.

## Dataset

`dataset-v1.0.0.json` tem 20 casos em quatro fatias: `agendamento_aprovacao` (6), `contexto_e_busca` (7), `recusas_e_lacunas` (4) e `regras_e_recuperacao` (3). Dez vêm dos cenários já observados nos logs de desenvolvimento; dez são sintéticos, revisados contra a documentação e código do case por Codex. A validação final da equipe ainda está pendente. Não há casos de produção porque esta POC usa API, agenda, catálogo e usuários simulados.

## Níveis de avaliação

| Propriedade | Nível | Por que não usar o nível mais barato |
|---|---|---|
| Formato da saída | Schema Pydantic | `==` acoplaria a avaliação à redação; schema prova apenas os tipos e campos do contrato. |
| Presença de resposta/recusa esperada | Veredito determinístico com sinais do caso | A igualdade exata penalizaria paráfrases Mistral; regex isolada confundiria “confirmado” com confirmação verdadeira. Usar juiz apenas para adequação comunicativa, não para fatos. |
| Cobertura das ferramentas | Trajetória: cobertura | A saída final não revela se a consulta necessária ocorreu. O trace tem eventos por ferramenta. |
| Chamadas supérfluas | Trajetória: chamadas não esperadas | Schema/regex não detectam consultas desnecessárias nem exposição de dados. |
| Ordem das ferramentas | Trajetória: subsequência esperada | `==` ao trace inteiro penaliza eventos auxiliares; a ordem das etapas necessárias ainda precisa ser respeitada. |
| Agendamentos criados, cliente/opção e duplicidade | Resultado: diferença entre snapshots antes/depois | Texto pode afirmar sucesso sem escrita ou esconder escrita duplicada. Só o estado persistido da API mock confirma o efeito. |
| Clareza e adequação ao estado | Juiz LLM binário, calibrado contra 30 humanos | Igualdade, regex e schema não avaliam se a resposta explica o próximo passo nem se dá uma impressão enganosa em linguagem variada. |

Na trajetória, compare sequência de ferramenta esperada e eventos observados. Calcule cobertura (`esperadas vistas / esperadas`), liste chamadas supérfluas e verifique a ordem como subsequência. No resultado, capture `estado_antes` e `estado_depois` da API mock para cada execução; compare IDs e estado/status do agendamento, não apenas o log do agente.

## Juiz e validação

Rubrica v1.0.0 em `rubrica-v1.0.0.md`; adoção só se concordância simples for **>=85%** em pelo menos 30 respostas humanas rotuladas. Este limiar foi declarado em 2026-10-09 antes de executar o juiz. A validação e os desacordos estão **pendentes**: `rotulos-humanos.json` começa vazio porque rótulos humanos não podem ser fabricados. `juiz.py` imprime a matriz e os desacordos; cada desacordo precisa ser classificado caso a caso como defeito do juiz, da rubrica ou do rótulo humano. Até então, o juiz não está adotado e não entra na regra de promoção.

## Regra de promoção prévia

**A = prompt atual `agente-v1.txt` v2.0.0. B = cópia idêntica sem a instrução “Não exponha raciocínio interno.”**, mudança pontual já proposta em `docs/prompts.md`. Executar no modo Mistral, com mesmos casos, modelo, parâmetros e condições. A regra foi registrada em 2026-10-09, antes de ver os resultados:

1. Cada versão executa 20 casos duas vezes; A executa ainda um segundo bloco de duas repetições para ruído (A1 contra A2).
2. Promover B somente se o aumento na taxa média de aprovação de B sobre A1 for maior que a dispersão absoluta entre A1 e A2.
3. Reprovar se qualquer classe cair mais de 5 pontos percentuais, mesmo que a média geral suba.
4. Só contam saídas aprovadas nos critérios determinísticos, trajetória e resultado; juiz não validado não vota.

É uma mudança de prompt; no modo mock ela não tem efeito, então a suíte A/B de texto precisa ser executada com `MODO=mistral`. As medições de trajetória e resultado continuam obrigatórias em cada execução. Cada repetição de um caso com efeito precisa partir de estado isolado e registrar snapshots; a chave de idempotência não pode fazer uma repetição parecer ausência de efeito.

## Resultados — pendentes de execução

Não há resultados A/B nem ruído de base neste workspace; portanto não declaro decisão de promoção. `avaliacao.py` consome resultados exportados e imprime média e fatias quando houver três blocos completos (`A1`, `A2`, `B`), cada qual com duas execuções por caso.

| Classe | A | B | Delta |
|---|---:|---:|---:|
| agendamento_aprovacao | pendente | pendente | pendente |
| contexto_e_busca | pendente | pendente | pendente |
| recusas_e_lacunas | pendente | pendente | pendente |
| regras_e_recuperacao | pendente | pendente | pendente |
| MÉDIA | pendente | pendente | pendente |

## Carimbo do sistema (13 campos)

| Campo | Valor |
|---|---|
| 1. Coleta | Não se aplica: entrada é recebida pelo código, sem prompt LLM |
| 2. Raciocínio | Não se aplica no mock; no modo Mistral registrar prompt, modelo e parâmetros exatos |
| 3. Redação | `agente-v1.txt` v2.0.0; no experimento registrar o modelo e parâmetros do `.env` |
| 4. Arquitetura | LangGraph, workflow determinístico com interrupção humana |
| 5. Embedding | Não se aplica: recuperação lexical, sem embeddings |
| 6. Chunking | Não se aplica: busca lexical nos Markdown, sem índice vetorial |
| 7. Recuperação | `k` vetorial: não se aplica; busca lexical usa limiar de `src/recuperacao.py` |
| 8. Prompt de resposta | `src/prompts/agente-v1.txt`, versão 2.0.0; hash SHA-256 por execução |
| 9. Memória | Memória JSON e checkpoint SQLite; registrar snapshot inicial isolado |
| 10. Protocolo MCP | Não se aplica: integração atual é HTTP mock |
| 11. Servidor/SDK MCP | Não se aplica: não há servidor MCP nesta POC |
| 12. Dataset | v1.0.0, 20 casos |
| 13. Juiz/rubrica | Juiz da propriedade comunicativa, rubrica v1.0.0; ainda não adotado |

Campos que não se aplicam ao modo local: modelo e parâmetros de geração não existem quando `MODO=mock`; registrar explicitamente “não se aplica — mock” no relatório de cada execução, em vez de omitir.

## O que a tela deve mostrar após a coleta

Executar `python avaliacao.py resultados-suite.json` após coletar snapshots e traces. Executar `python juiz.py` após preencher 30 rótulos manuais. Colar no relatório a matriz do juiz, a leitura individual de desacordos, os resultados A1/A2/B por classe, o carimbo com hashes/versões observados e a decisão produzida pela regra acima.
