# Exercício 14 — Os dez riscos no AgendeAkiAI

**Data:** 23/10/2026. **Case:** AgendeAkiAI, o mesmo dos exercícios 11 e 12.

## Escopo e evidências

Análise estática do repositório [`bot-agendeakiai`](../../../../bot-agendeakiai), revisão `bf3cdd3b0c54893efdace23c08948d2dfc2a72ba`, sem alterações locais no momento da leitura. Os endereços `src/arquivo.py:linha` abaixo são relativos a esse repositório. Cenários são hipóteses de ataque fundamentadas no código, não resultados de ataques executados.

O fluxo padrão é local, determinístico e usa clientes, catálogo e reservas fictícios. O modelo opcional atual é **Gemini**, chamado somente na finalização, sem ferramentas. A análise anterior da aula 12 citava Mistral; esta resposta usa o código atual (`src/grafo.py:211`, `src/modelo.py:53`).

O adaptador `--backend agendeaki` autentica o cliente e consulta o backend, mas desabilita reserva, memória local e checkpoint (`src/main.py:50`, `src/agendeaki_api.py:109`). Os cenários de escrita e memória desta resposta pertencem ao **backend mock**. Não há evidência aqui de implantação em produção, subagentes, MCP ou execução de código gerado pelo modelo.

**Como ler as mitigações:** “existente” descreve código inspecionado; “proposta” descreve uma mudança ainda não implementada. Nota de impacto mede o dano do cenário antes da mitigação proposta, não sua probabilidade. Reservas do mock recebem nota 3 porque a interface da POC não oferece desfazer a escrita; são efeitos simulados, sem pagamento ou reserva real. Reiniciar o mock limpa seu estado, mas não é uma operação de cancelamento do produto.

## Canais de entrada não confiável

| Canal | Onde entra | O que pode influenciar |
|---|---|---|
| Texto, `cliente_id` e `conversa_id` fornecidos à CLI | `src/main.py:75`, `src/grafo.py:100`, `src/grafo.py:262` | Filtros, identidade simulada, seleção de checkpoint e pedido enviado ao redator opcional. Campo não vazio não comprova identidade. |
| Regras Markdown do corpus | `src/recuperacao.py:36`, `src/grafo.py:115` | Resposta sobre regras; o último trecho selecionado compõe a resposta-base e pode chegar ao Gemini. Alterar o corpus exige acesso de escrita local ou à sua atualização. |
| Retornos HTTP de histórico, catálogo e reserva | `src/tools.py:42`, `src/grafo.py:106`, `src/grafo.py:129`, `src/grafo.py:203` | Ordenação, opções exibidas, aprovação e mensagem de resultado. |
| Memória e estado persistente | `src/memoria.py:31`, `src/grafo.py:62`, `src/grafo.py:263` | Preferência usada em outra execução e retomada de aprovação. Episódios livres não são enviados diretamente ao redator. |
| Saída do Gemini | `src/modelo.py:64`, `src/grafo.py:215` | Texto final entregue ao cliente. O schema valida a estrutura, sem provar fidelidade aos fatos. |

Descrições de ferramentas MCP e mensagens de agentes subordinados não são canais presentes neste case.

## Os dez riscos

### ASI01 — Sequestro de objetivo do agente

| Campo | Resposta |
|---|---|
| **Existe no case?** | sim — no redator Gemini opcional; o modo determinístico não interpreta instruções com LLM. |
| **Onde** | Pedido e resposta-base reunidos em `src/modelo.py:36`; chamada sem ferramentas em `src/modelo.py:53`; texto retornado substitui o resultado em `src/grafo.py:215`. |
| **Cenário de ataque** | Um usuário da POC inclui no pedido de penteado uma instrução para o redator declarar que a reserva está confirmada, mesmo que o fluxo tenha apenas listado opções. A instrução chega ao Gemini no campo `pedido`; se obedecida, a resposta afirma uma escrita que não aconteceu. |
| **Impacto** | **1** — no cenário com dados fictícios, o dano é uma resposta enganosa restrita à execução, corrigível por consulta ao estado; nenhuma ferramenta é chamada pelo modelo. |
| **Mitigação** | **Existente: menor privilégio**, redator sem ferramentas e escrita decidida antes da geração (`src/grafo.py:199`, `src/grafo.py:211`). **Proposta: minimização de contexto**, retirar o pedido livre depois da extração dos filtros, em `src/modelo.py:36`; usar template em código para estado da reserva. **Custo:** perde parte da adaptação da redação ao texto original. A inexatidão textual residual é aceita em ASI09, nos limites declarados adiante. |

### ASI02 — Uso indevido e exploração de ferramenta

| Campo | Resposta |
|---|---|
| **Existe no case?** | sim — ferramenta de escrita do backend mock. |
| **Onde** | `confirmar_agendamento`, `src/tools.py:94`; endpoint de escrita em `src/mock_api.py:115`; portão do grafo em `src/grafo.py:174`. |
| **Cenário de ataque** | Um processo local com o token público de demonstração envia diretamente ao endpoint mock um POST com uma opção válida e um cliente fictício, sem passar pela aprovação do grafo. O endpoint verifica token, cliente e opção, mas não exige prova de aprovação daquela operação. |
| **Impacto** | **3** — cria reserva simulada sem autorização do cliente; a interface da POC não oferece cancelamento dessa escrita. |
| **Mitigação** | **Existente: confirmação humana inescapável por prompt** no percurso do grafo, com prazo e edição restrita às opções consultadas (`src/grafo.py:177`, `src/grafo.py:187`). **Proposta: menor privilégio por ferramenta e argumento** no endpoint: separar leitura/escrita e exigir autorização de uso único, emitida após aprovação, vinculada a cliente, opção, horário, preço e prazo. Não confiar apenas no chamador. **Custo:** um POST genérico deixa de poder criar reservas sem o fluxo de autorização. |

### ASI03 — Abuso de identidade e privilégio

| Campo | Resposta |
|---|---|
| **Existe no case?** | sim — identidade e retomada não autenticadas no modo mock. |
| **Onde** | Cabeçalho `X-Mock-Cliente-Id` em `src/tools.py:38`; token compartilhado em `src/mock_api.py:160`; retomada por `conversa_id` em `src/grafo.py:262`. |
| **Cenário de ataque** | Um usuário com acesso à CLI local informa o identificador de outro cliente fictício e o `conversa_id` de uma aprovação pendente. Ao executar a retomada com “aprovar”, o grafo carrega o estado daquela conversa sem comparar o titular com uma identidade autenticada e pode registrar a reserva em nome da vítima simulada. |
| **Impacto** | **3** — aprovação indevida de reserva simulada em nome de outro cliente; a POC não dispõe de operação de desfazer. A nota não pressupõe dados pessoais reais no catálogo fictício. |
| **Mitigação** | **Proposta: credencial delegada e menor privilégio**, obter cliente de sessão autenticada, autorizar acesso ao par cliente/conversa antes de `Command(resume=...)` e retirar do usuário a escolha livre da identidade. Separar cache de grafo por sessão/credencial: hoje sua chave contém somente tipo e URL (`src/grafo.py:258`). **Existente no adaptador real:** cliente vem do login (`src/main.py:62`), escrita é desabilitada e não há checkpoint persistente (`src/agendeaki_api.py:109`). Isso não corrige a fronteira mock. |

### ASI04 — Cadeia de suprimentos agêntica

| Campo | Resposta |
|---|---|
| **Existe no case?** | sim — dependências Python e atualização do corpus; não depende de haver MCP. |
| **Onde** | Dependências fixadas em `requirements.txt:16`, `requirements.txt:24`; imports do runtime em `src/grafo.py:18`, `src/modelo.py:11`; corpus lido em `src/recuperacao.py:36`. |
| **Cenário de ataque** | Um atacante compromete o artefato de uma dependência distribuída pelo índice ou espelho usado na instalação. Na próxima instalação, o pacote é carregado pelo processo do agente e pode alterar as respostas ou ler arquivos e credenciais acessíveis ao processo. Este cenário pressupõe comprometimento da distribuição; não é atribuído a um pacote específico. |
| **Impacto** | **3** — comprometimento do runtime comum pode alcançar todos os usuários que executem essa instalação; a nota não depende de inventar um vazamento já ocorrido. |
| **Mitigação** | **Existente: versão fixada** com `==` em `requirements.txt`; isso não verifica integridade. **Proposta:** dependências transitivas com hashes conferidos na instalação, fonte de pacotes controlada, revisão de atualizações e execução com **menor privilégio**, sem acesso a arquivos desnecessários. Versionar e aprovar alterações do corpus antes da recuperação. **Custo:** atualizações exigem revisão e regeneração dos hashes. Não há `Dockerfile` no case inspecionado para citar como controle. |

### ASI05 — Execução inesperada de código

| Campo | Resposta |
|---|---|
| **Existe no case?** | **não aplicável** |
| **Onde** | |
| **Cenário de ataque** | |
| **Impacto** | |
| **Mitigação** | |

### ASI06 — Envenenamento de memória e de contexto

| Campo | Resposta |
|---|---|
| **Existe no case?** | sim — preferências persistentes e corpus local do backend mock. |
| **Onde** | Gravação de preferência em `src/memoria.py:45`; recuperação por cliente em `src/memoria.py:31`; preferência altera ordenação em `src/grafo.py:131`; corpus vigente em `src/recuperacao.py:38`. |
| **Cenário de ataque** | Um usuário local escolhe o `cliente_id` fictício de outra pessoa e envia “prefiro moderno”. Ao finalizar, o sistema salva essa preferência. Na próxima busca da vítima sem estilo explícito, a preferência contaminada muda a ordem das opções; o atacante não precisa estar presente nessa execução. |
| **Impacto** | **2** — alteração reversível alcança outro usuário e persiste entre execuções; pode ser removida ou substituída. Não há dado pessoal real neste cenário. |
| **Mitigação** | **Existente: minimização de contexto**, só o estilo estruturado influencia a ordenação; episódios livres não são passados ao Gemini. O estilo atual prevalece (`src/grafo.py:134`), e há remoção explícita (`src/memoria.py:64`). **Proposta: menor privilégio e controle de origem**, permitir gravação somente pelo titular autenticado, registrar proveniência, prazo de retenção e confirmação para alteração de preferência durável. Proteger escrita/atualização dos documentos do corpus. **Custo:** preferência não é aprendida silenciosamente em qualquer mensagem. |

### ASI07 — Comunicação insegura entre agentes

| Campo | Resposta |
|---|---|
| **Existe no case?** | **não aplicável** |
| **Onde** | |
| **Cenário de ataque** | |
| **Impacto** | |
| **Mitigação** | |

ASI05 não se aplica porque nenhum texto gerado é executado como programa, shell ou SQL; subprocessos da demonstração usam comandos definidos pelo desenvolvedor. ASI07 não se aplica porque não há subagente, delegação ou handoff: nós do LangGraph e um redator final não constituem comunicação entre agentes autônomos. **ASI08 se aplica**, pois há ferramentas sujeitas a falha no meio do fluxo.

### ASI08 — Falhas em cascata

| Campo | Resposta |
|---|---|
| **Existe no case?** | sim — resultado HTTP da escrita e comunicação posterior ao cliente. |
| **Onde** | Escrita em `src/mock_api.py:75`; resposta enviada depois em `src/mock_api.py:148`; timeout convertido em erro em `src/tools.py:57`; mensagem de falha em `src/grafo.py:206`. |
| **Cenário de ataque** | Um processo local capaz de interferir na API mock atrasa a resposta do POST depois de a reserva ser gravada. O cliente HTTP estoura o timeout; o grafo informa “nenhum agendamento foi registrado”, embora a reserva já exista. Confiando nisso, o cliente pode buscar outro horário e aprovar uma segunda reserva. |
| **Impacto** | **3** — uma falha de comunicação se propaga para informação falsa e pode produzir outra escrita sem operação de desfazer na POC. |
| **Mitigação** | **Existente: timeout e idempotência**, chave estável por cliente/opção/horário (`src/grafo.py:201`), deduplicação no mock (`src/mock_api.py:50`) e consulta que falha não abre aprovação (`src/grafo.py:138`). **Proposta: contenção da falha**, classificar timeout após POST como “resultado desconhecido”, consultar o resultado pela mesma chave e bloquear nova reserva até reconciliação ou revisão humana. Persistir a chave e o resultado de forma transacional antes de integrar escrita real. **Custo:** indisponibilidade pode deixar a confirmação pendente em vez de oferecer repetição imediata. |

### ASI09 — Exploração da confiança humano-agente

| Campo | Resposta |
|---|---|
| **Existe no case?** | sim — confiança na resposta textual opcional. |
| **Onde** | Resposta de regra em `src/grafo.py:119`; validação estrutural em `src/modelo.py:65`; substituição do texto final em `src/grafo.py:215`. |
| **Cenário de ataque** | Um usuário da demonstração inclui no pedido sobre cancelamento uma instrução para o Gemini anunciar reembolso integral e imediato. Se a redação obedecer, uma pessoa que leia a resposta pode confiar nessa política inexistente. O schema aceita uma string bem formada mesmo que contradiga a resposta-base. |
| **Impacto** | **1** — neste cenário de demonstração, a orientação pode ser corrigida na mesma execução, sem pagamento, envio ou registro de parecer; usa somente dados e políticas fictícios. Uso por clientes reais exigiria nova avaliação. |
| **Mitigação** | **Existente: confirmação humana montada pelo código**, com campos reais da opção e prazo, antes da escrita (`src/grafo.py:168`); o Gemini é chamado depois desse portão. Isso limita o efeito operacional, mas **não valida a veracidade da redação**. A ausência de um verificador semântico automático ou de revisão humana obrigatória de cada resposta é o **risco aceito** abaixo. **Alternativa para reavaliação:** templates para regras e resultado, sem reescrita desses fatos pelo modelo; custo de perder flexibilidade de linguagem. |

### ASI10 — Agentes desgovernados

| Campo | Resposta |
|---|---|
| **Existe no case?** | sim — falta de contenção agregada de execuções; não há auto-replicação nem delegação dinâmica. |
| **Onde** | Limites locais em `src/grafo.py:30`, `src/grafo.py:263` e `src/modelo.py:46`; tempo conferido apenas ao finalizar em `src/grafo.py:225`. |
| **Cenário de ataque** | Um usuário com acesso à execução local dispara repetidamente pedidos curtos no modo Gemini. Cada execução pode respeitar seu limite individual e ainda consumir a cota da credencial compartilhada, até impedir novas chamadas de modelo para todos que a utilizam. O workflow continua disponível no modo determinístico, mas o redator remoto fica indisponível. |
| **Impacto** | **3** — o esgotamento da cota pode alcançar todos os usuários da mesma credencial; não significa comprometimento de todos os usuários do provedor. |
| **Mitigação** | **Existente: teto de gasto por chamada**, pré-estimativa de tokens, limite de passos/recursão e fallback à resposta-base quando a chamada falha (`src/grafo.py:217`). Esses controles não são orçamento global nem interrupção imediata: a chamada remota admite 120 s (`src/modelo.py:49`). **Proposta:** orçamento cumulativo e rate limit por identidade, limite de concorrência, deadline aplicado antes de cada chamada e mecanismo para desligar o redator remoto, com responsável operacional definido. **Custo:** rejeitar ou responder por template quando a cota/tempo acabar. |

## Risco aceito — ASI09: redação semanticamente incorreta na demonstração

**Decisão deste exercício:** aceitar, no modo Gemini opcional da POC com dados fictícios, a possibilidade de o texto final contrariar a resposta-base. Não adicionar agora um segundo LLM verificador nem revisão humana obrigatória de cada resposta. Esta é uma decisão proposta para a entrega acadêmica; não representa aprovação formal de uma implantação real.

- **Por que foi aceito:** experimentar a clareza e a flexibilidade da redação é a finalidade desse modo opcional. Revisar toda resposta manualmente impede testar a interação imediata; um segundo modelo acrescenta custo e não prova correção semântica. O requisito atual é experimentar a redação em ambiente controlado.
- **O que o limita hoje:** uso local com dados fictícios; modo determinístico como padrão; modelo sem ferramentas; fluxo de escrita anterior à geração; aprovação montada em código; fontes e suficiência da saída pública preservadas pelo fluxo (`src/grafo.py:270`). Esses controles não impedem que a string `resultado` minta.
- **O que não será mitigado agora:** inexatidão semântica residual da string gerada. A minimização proposta em ASI01 reduz um vetor de injeção, mas não garante fidelidade factual e não substitui esta aceitação explícita.
- **Evento de reavaliação:** primeiro uso com clientes ou dados reais; habilitação do Gemini junto ao backend real; uma resposta falsa observada em avaliação; ou proposta de deixar o modelo interpretar aprovações/chamar ferramentas. Reavaliar **antes** da ampliação de escopo. Até decidir novos controles, manter a redação determinística nesse uso.
- **Responsabilidade:** decisão acadêmica documentada para revisão pelo grupo Emily Oliveira, Felipe Macena e Matheus Rodrigues. O responsável individual por incidentes e a aprovação operacional ainda precisam ser definidos; não se presume aceite dos integrantes.

## Priorização e resposta à questão final

| Prioridade | Riscos de maior impacto | Medida no ponto certo |
|---|---|---|
| 1 — autoridade da escrita | **ASI02 e ASI03 (3)** | Exigir aprovação vinculada à operação no endpoint e identidade autenticada na retomada; a validação no grafo sozinha não protege chamadas diretas. |
| 2 — consistência após escrita | **ASI08 (3)** | Reconciliar resultado desconhecido pela chave idempotente; impedir que um timeout seja apresentado como certeza de ausência de reserva. |
| 3 — alcance compartilhado | **ASI04 e ASI10 (3)** | Conferir integridade de dependências e limitar privilégios do processo; aplicar orçamento agregado e desligamento do redator. |
| 4 — persistência e texto | **ASI06 (2), ASI01 e ASI09 (1)** | Autorizar gravação de preferências, controlar origem do corpus e minimizar contexto; aceitar provisoriamente a inexatidão textual residual somente na demonstração. |

ASI05 e ASI07 são não aplicáveis por ausência da capacidade correspondente. Nenhuma mitigação proposta nesta análise foi implementada no case por esta entrega. Em especial, um comando defensivo no prompt não substitui autorização, aprovação nem validação em código.

## Referências da disciplina

- [Enunciado do exercício 14](../../../teorico/aula-14-mlops-seguranca/exercicios/enunciado.md).
- [Nota 01 — O mapa e a injeção](../../../teorico/aula-14-mlops-seguranca/notas-de-aula/01-o-mapa-e-a-injecao.md), catálogo e canais.
- [Nota 02 — Defesa por arquitetura](../../../teorico/aula-14-mlops-seguranca/notas-de-aula/02-defesa-por-arquitetura.md), padrões, custos e controles.
- [Case AgendeAkiAI](../../../../bot-agendeakiai/docs/case.md) e [arquitetura](../../../../bot-agendeakiai/docs/arquitetura.md), conferidos contra a revisão de código indicada no início.
