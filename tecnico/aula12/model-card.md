# Model card — AgendeAkiAI

**Data deste documento:** 2026-10-16  
**Escopo:** prova de conceito local descrita neste repositório. O catálogo, a API, os clientes e os agendamentos da demonstração são simulados. Este documento não descreve uma implantação em produção.

## 1. Identificação

**Afirmação.** AgendeAkiAI é uma prova de conceito para descobrir e agendar serviços de beleza por texto. O grupo identificado no repositório é Emily Oliveira, Felipe Macena e Matheus Rodrigues. A versão da aplicação e a pessoa individual responsável por incidentes não estão identificadas; `2.0.0` é a versão do prompt remoto, não uma versão declarada do sistema.

**Evidência.** `README.md:L3-L7,L82-L86`; `src/prompts/agente-v1.txt:L1-L5`.

## 2. Finalidade

**Afirmação.** O agente consulta histórico e opções simulados, busca regras do corpus e pode preparar uma reserva. É destinado a apoiar a descoberta de serviços de beleza. Não deve ser usado para aconselhamento sobre alergias, atrasos, faltas ou assuntos fora desse escopo. Não é uma integração de produção.

**Evidência.** `docs/case.md:L5-L13,L39-L52,L97-L99`; `README.md:L5-L7`; `logs/05-fora-do-corpus.json` e `logs/09-fora-escopo.json`.

## 3. Autoridade

**Afirmação.** No modo padrão, o fluxo pode ler histórico, catálogo e regras locais. A única escrita de negócio prevista é criar uma reserva na API mock, depois de uma aprovação explícita; memória, checkpoint e logs também são gravados localmente. Não há evidência de credenciais de produção ou de integração com MCP.

| Limite | Ponto de aplicação e evidência | Situação |
|---|---|---|
| Escopo: busca de serviços de beleza e regras simuladas | Código reconhece o escopo e encerra pedidos externos: `src/grafo.py:L79-L85,L121-L126`; teste em `src/verificar.py:L45-L53`; execução `logs/09-fora-escopo.json`. | Aplicado no código para os casos verificados; classificador lexical tem limites conhecidos (`docs/case.md:L97-L99`). |
| Sem escrita antes da aprovação | O grafo pausa antes de `registrar_agendamento`: `src/grafo.py:L166-L195,L243-L247`; verificador rejeita escrita nos cenários sem aprovação: `src/verificar.py:L45-L49`; evidências: `logs/01-caso-simples.json`, `logs/10-aprovacao-expirada.json`. | Aplicado no código e exercitado nos logs. |
| Aprovar apenas opção apresentada/consultada | `src/grafo.py:L166-L189`; `logs/06-aprovacao-editada.json`. | Aplicado no código. |
| Credencial | O cliente usa `token-mock`; a API mock compara o mesmo token estático: `src/grafo.py:L270-L272`, `src/demo.py:L76-L79`, `src/mock_api.py:L160-L164`. | **LACUNA:** não há credencial individual ou privilégio limitado por operação/cliente; o token é somente do mock. |
| Limite de custo e tokens do modo Mistral | Teto local de US$ 0,01 e 4.000 tokens estimados; chamada com máximo de 400 tokens: `src/modelo.py:L17-L18,L29-L48`. | Aplicado no código local; não é limite de plataforma/provedor. |
| Limite de passos e tempo | Oito passos, recursão limitada e verificação de tempo no término: `src/grafo.py:L28-L32,L207-L224,L252-L262`. | Código limita passos/recursão; o teto de 30 s é verificado no nó terminal e não interrompe um nó em execução (`docs/arquitetura.md:L52`). |
| Falha de controle ou API | Falha de consulta termina sem confirmar: `src/tools.py:L57-L68`; verificação de ausência de escrita: `src/verificar.py:L45-L53`. | Aplicado para falhas observadas na API mock; recuperação diante de falhas de produção é **LACUNA**. |
| Suspender o agente | Não foi encontrado procedimento ou controle operacional para suspender o serviço. | **LACUNA:** definir responsável e mecanismo de suspensão. |
| Limites no prompt | O prompt instrui não inventar fatos e exige aprovação antes da escrita: `src/prompts/agente-v1.txt:L9-L16`. | Instrução de prompt não é controle independente; qualquer limite sustentado só pelo prompt é **LACUNA**. |

## 4. Ferramentas e integrações

**Afirmação.** `consultar_historico` e `buscar_opcoes` fazem GET na API HTTP mock; `buscar_regra` consulta o corpus Markdown local; `confirmar_agendamento` faz POST na API mock. Não há servidor MCP nesta implementação. A credencial é o token fixo de demonstração, sem escopo granular.

**Evidência.** `src/tools.py:L78-L106`; `src/recuperacao.py`; `src/mock_api.py:L88-L120,L160-L164`; `docs/arquitetura.md:L44-L48`; `docs/case.md:L55-L60,L86-L89`.

## 5. Modelo e provedor

**Afirmação.** O modo padrão é determinístico/local e não chama modelo. O modo opcional chama Mistral Small `mistral-small-2603`, por cliente OpenAI compatível apontado por padrão a `https://api.mistral.ai/v1`. Região de processamento, retenção pelo provedor e uso dos dados para treinamento não estão registrados no repositório. A avaliação do modo remoto não foi executada.

**Evidência.** `docs/modelos.md:L3-L8,L20-L24`; `src/modelo.py:L39-L48`; `docs/prompts.md:L7-L9,L22-L27`.

## 6. Dados

**Afirmação.** A demonstração usa dados fictícios. O projeto proíbe inserir dados reais na POC, mas não documenta base legal para um eventual uso real. A definição da base legal aplicável deve ser feita pelo controlador para cada finalidade; o art. 7º da LGPD lista as hipóteses legais e não seleciona uma automaticamente para este sistema.

| Local/percurso | Dados e finalidade | Guarda e prazo comprovados | Base legal |
|---|---|---|---|
| Entrada e estado do fluxo | Texto livre, `cliente_id`, `conversa_id`; buscar serviço e retomar a conversa. | Estado em memória durante o fluxo; cópia pode persistir no checkpoint. | Dados da POC são fictícios. Para dados reais: **LACUNA**. |
| Catálogo/API mock | Nomes fictícios, identificador de cliente, preferências e histórico; filtrar opções e personalizar a resposta. | `dados/catalogo.json` no repositório; reservas em memória do servidor mock e perdidas ao reiniciá-lo. | Dados simulados. Para integração real: **LACUNA**. |
| Memória local | `cliente_id`, trecho de até 180 caracteres da mensagem, preferência declarada e horário; personalização entre execuções. | `dados/memoria.json`, ignorado pelo Git; sem expiração automática; remoção explícita por cliente. | Para dados reais: **LACUNA**. |
| Checkpoint SQLite | Estado da conversa e aprovação pendente, para retomar após interrupção. | `dados/checkpoints.sqlite`; fica até remoção explícita; sem criptografia de aplicação. | Para dados reais: **LACUNA**. |
| Logs JSON | Entrada, identificadores, saída, eventos de ferramentas/contexto, aprovação, hash do código e horário; evidência das demonstrações. | Arquivos em `logs/`; não há prazo automático documentado. Remoção disponível pelo comando de esquecimento. | Dados demonstrativos fictícios. Para logs reais: **LACUNA**. |
| Mistral opcional | O pedido remoto inclui texto do cliente, resposta já verificada, fontes e suficiência, além do prompt. | Retenção, região e eliminação pelo provedor: **LACUNA**. Usar somente dados fictícios até isso ser documentado. | Para envio de dados reais: **LACUNA**. |

**Evidência.** `src/contratos.py:L6-L16`; `dados/catalogo.json:L1-L19`; `src/grafo.py:L97-L107,L207-L218`; `src/memoria.py:L12-L24,L45-L61`; `docs/memoria.md:L5-L12,L22-L30`; `src/demo.py:L60-L72`; `src/modelo.py:L21-L48`; `docs/case.md:L80-L85`. Referência legal: [LGPD, art. 7º — Planalto](https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/L13709.htm).

**Minimização e retenção.** A POC não tem expiração automática para memória, checkpoint e logs. O trecho de entrada guardado na memória é limitado a 180 caracteres, mas não há política documentada para decidir se cada trecho é necessário. A remoção local é explícita; a retenção de qualquer dado enviado ao Mistral não está comprovada.

## 7. Avaliação

**Afirmação.** O verificador local confere dez logs, o contrato de saída, a ausência de escrita em cenários sem aprovação, a idempotência e a expiração. A recuperação lexical atingiu 10/10 perguntas no alvo em 2026-10-04. Não há resultados por fatia para qualidade com clientes reais, versão formal da suíte ou medida de concordância entre juiz e avaliadores humanos. A avaliação Mistral está pendente.

**Evidência.** `src/verificar.py:L12-L17,L28-L71`; `docs/case.md:L74-L78`; `docs/rag.md:L15-L32`; `dados/resultado-avaliacao-rag.json`; `docs/prompts.md:L22-L27`; `docs/medicao-baseline.md:L1-L4`.

## 8. Limites conhecidos

**Afirmação.** Busca de regras e filtros são lexicais e pequenos; não medem adequação estética. O agente recusa assuntos sem suporte, incluindo alergias, atraso e falta. A API e os dados são mocks; a disponibilidade pode mudar entre consulta e confirmação em uma integração real. A resposta Mistral, se habilitada, tem validação de formato, mas não garantia semântica.

**Evidência.** `docs/case.md:L97-L105`; `docs/rag.md:L34-L38`; `docs/modelos.md:L20-L24`; `logs/05-fora-do-corpus.json`.

## 9. Riscos aceitos

**Afirmação.** O projeto identifica como risco principal dados inconsistentes ou disponibilidade alterada entre busca e reserva; propõe revalidar no backend real e não confirmar em caso de falha. Não há registro nomeado de quem aceitou formalmente esse risco, nem de outros riscos aceitos.

**Evidência.** `docs/case.md:L103-L105`.

**LACUNA:** registrar responsável, decisão de aceitação, justificativa, mitigação e condição de revisão.

## 10. Supervisão humana

**Afirmação.** O cliente revisa serviço, profissional, horário e preço antes da escrita de negócio. Pode aprovar, rejeitar ou editar para outra opção já consultada. A aprovação expira em 15 minutos; uma decisão tardia termina sem agendamento. Não está documentado quem pode suspender o agente.

**Evidência.** `src/grafo.py:L28-L32,L166-L195`; `docs/humano.md:L3-L21`; `logs/06-aprovacao-editada.json`; `logs/10-aprovacao-expirada.json`; fluxo de retomada em `README.md:L45-L53`.

## 11. Registro e retenção

**Afirmação.** Os logs da demonstração guardam entrada, horário, revisão-base, hash do código, saída validada e eventos; os eventos podem conter dados retornados pelas ferramentas, decisão humana e consumo/erro do modelo. O checkpoint guarda estado para retomada. A retenção é até remoção manual, sem prazo definido; não há controle de acesso ou criptografia de aplicação documentados.

**Evidência.** `src/demo.py:L50-L72`; exemplo `logs/01-caso-simples.json`; `src/grafo.py:L35-L64`; `docs/humano.md:L19-L21`; `docs/memoria.md:L5-L12,L22-L30`.

## 12. Histórico de mudanças

**Afirmação.** Há identificação do prompt remoto como `2.0.0` e hash do prompt em execução, além de hash do código e revisão-base nos logs. O repositório não apresenta histórico de versões do sistema com descrição da mudança e pessoa que a aprovou.

**Evidência.** `src/prompts/agente-v1.txt:L1-L5`; `src/grafo.py:L97-L102`; `src/demo.py:L50-L64`; `docs/io.md:L17-L18`.

**LACUNA:** manter histórico de versão do sistema, mudanças relevantes, data e aprovador.

## Lacunas

| Lacuna | Correção proposta | Prioridade |
|---|---|---|
| Responsável individual, versão do sistema e aprovador de mudanças não identificados. | Nomear responsável, versionar a aplicação e registrar aprovações. | Alta |
| Credencial mock sem privilégio granular; identidade do cliente não é autenticada pela API demonstrativa. | Antes de produção, usar autenticação individual e autorização por cliente/operação. | Alta |
| Sem mecanismo/autoridade operacional para suspender o agente. | Definir responsável e procedimento testável de suspensão. | Alta |
| Base legal para dados reais não documentada. | Controlador deve definir e registrar hipótese do art. 7º por finalidade antes de uso real. | Alta |
| Região, retenção e uso para treino do provedor não comprovados. | Documentar configuração e termos aplicáveis; manter dados fictícios até essa verificação. | Alta |
| Prazo de retenção dos dados locais é indefinido, embora haja remoção manual. | Definir prazos por armazenamento e automatizar expiração quando necessário. | Alta |
| Acesso e proteção de checkpoint, memória e logs não documentados; SQLite sem criptografia de aplicação. | Definir controle de acesso e proteção dos arquivos antes de dados reais. | Alta |
| Avaliação Mistral, concordância humano/juiz, versão de suíte e resultados por fatia ausentes. | Executar avaliação rotulada, comparar com revisão humana e registrar versão e resultados. | Média |
| Aceitação formal dos riscos sem registro de decisão/responsável. | Registrar decisão, mitigação e condição de revisão. | Média |

## Conclusão para auditoria

Com o código e os registros da POC, é possível verificar que o fluxo demonstrado só chega à escrita depois da aprovação e que cenários rejeitados ou expirados não escrevem. Isso não prova autoridade, identidade, retenção ou segurança de uma implantação real; esses pontos permanecem lacunas até existirem controles e evidências de produção.
