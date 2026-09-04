# Case — triagem de ocorrências de entrega

## 1. O case — indústria e problema

**Setor:** logística de última milha, no atendimento pós-venda de uma transportadora.

**Problema em uma frase:** reduzir o tempo de triagem de reclamações de entrega, coletando o contexto faltante, consultando o pedido e preparando um chamado para confirmação do cliente.

**Contexto atual:** mensagens chegam por chat, e-mail ou WhatsApp em linguagem livre — por exemplo, “meu pedido não chegou”. Um atendente lê a mensagem, localiza o número do pedido, pergunta o que falta, consulta o rastreio, compara o status com a reclamação e registra o chamado. No piloto didático, a operação é simulada pelos pedidos e chamados dos exercícios 2 e 3; em produção, as consultas seriam feitas na API da transportadora. O tempo atual ainda não foi cronometrado: antes da implementação, o grupo medirá dez atendimentos reais ou simulados, do recebimento da mensagem até o registro correto, e guardará os dez tempos e a mediana no repositório. Não será usado número estimado como linha de base.

**Regras do domínio:**

- O pedido só pode ser consultado depois que o cliente fornecer um identificador válido; pedido inexistente é devolvido como dado e exige nova pergunta.
- Atraso ocorre quando a previsão já venceu e o pedido ainda não foi entregue.
- Se o rastreio disser “entregue” e o cliente disser que não recebeu, o caso é uma divergência, não um atraso automaticamente.
- Se a previsão ainda não venceu, o agente informa a previsão e não abre chamado de atraso.
- Abrir chamado é uma escrita: o cliente vê categoria, urgência e ação proposta e precisa confirmar. O agente não altera endereço, reembolsa nem cancela pedido.
- Após a escrita, o sistema consulta o protocolo criado para confirmar o estado antes de encerrar; casos ambíguos ou sem dados suficientes vão para um humano.

**O que dá errado hoje:** o cliente frequentemente omite pedido, data e tentativa de entrega; há números que não são pedidos (CEP e número de casa), mais de um pedido na mesma mensagem e pedidos escritos com pontuação. O ponto mais crítico é a divergência entre a narrativa e o rastreio: classificar “não recebi” como atraso sem confrontar o status “entregue” registra o problema errado. Também há retrabalho quando o atendente abre o chamado antes de confirmar os dados ou não verifica se a gravação funcionou.

**Casos reais do setor:**

1. **DPD UK.** A transportadora implantou uma experiência conversacional em texto no aplicativo de rastreio para dúvidas de clientes; a empresa informa que ela tratava mais de 32% das consultas dos cerca de 3 milhões de usuários do app. A arquitetura provável é um **roteador + workflow com ferramentas**: perguntas padronizadas vão para fluxos/intents e as ocorrências são sinalizadas para suporte humano. A divulgação não informa a definição de “tratada”, a taxa de resolução correta, o custo nem quantas conversas abandonadas entram no indicador. Fonte: [DPD UK](fontes.md#caso-1--dpd-uk).

2. **Hermes Germany.** A empresa mantém uma plataforma Track & Trace que atende milhões de pedidos diários e integra consultas de clientes, chatbots e portais internos com APIs distintas. O número publicado é 25% de redução de custo de infraestrutura após a arquitetura serverless, não um indicador de qualidade do chatbot. A arquitetura provável do atendimento é um **workflow com ferramentas** (consulta de rastreio e transformação de dados), com chatbot como canal. A empresa não divulga contenção, acurácia da resposta, tempo de resolução ou custo por conversa. Fonte: [Hermes Germany](fontes.md#caso-2--hermes-germany).

3. **TetriXX.** A plataforma de logística usa Gemini, Vertex AI e Agent Development Kit para transformar dados de transporte e faturas em insights; divulga disponibilidade superior a 99,99% para um agente e que seus clientes podem economizar milhões por ano eliminando ineficiências. Pelo uso de fontes externas e dados não estruturados, o padrão provável é **agente com ferramentas/RAG**, sujeito a revisão humana para decisões operacionais. A divulgação não apresenta linha de base, método de cálculo da economia, taxa de erro ou autonomia efetiva. Fonte: [TetriXX](fontes.md#caso-3--tetrixx).

## 2. Os usuários, e como será a interação

| Perfil | O que ele quer | O que ele sabe | O que ele pode fazer |
| --- | --- | --- | --- |
| Cliente | Saber onde está o pedido e resolver a ocorrência sem repetir informações | A própria experiência, eventualmente o número do pedido | Descrever o problema, responder perguntas e confirmar ou recusar a abertura do chamado |
| Atendente humano | Receber só casos completos e excepcionais | Políticas de atendimento e exceções | Corrigir a classificação, abrir/editar chamados e decidir escalonamentos permitidos |
| Supervisor de atendimento | Consistência e controle da operação | SLA, métricas e alçadas | Revisar amostras, alterar regras e aprovar políticas; não é o agente quem altera regras |
| Sistema de rastreio | Devolver o estado registrado do pedido | Status, previsão e transportadora | Apenas consultar dados; nenhuma escrita é feita nele por este projeto |

**Usuário principal:** o cliente que precisa resolver uma ocorrência de entrega.

**Interação:** o cliente inicia um chat. O agente pede uma informação por vez, normalmente uma a três trocas, até obter número do pedido e contexto mínimo. Depois consulta o rastreio, explica a conclusão em linguagem simples e devolve: (a) a previsão, quando não há atraso; (b) uma proposta de chamado com categoria, urgência e ação; ou (c) encaminhamento ao atendente, quando há divergência ou dados insuficientes. A escrita só ocorre após um “sim” inequívoco. Se não puder resolver, o cliente recebe o motivo, as informações já coletadas e o encaminhamento, sem promessa de prazo inventada.

**Diálogo de exemplo:**

> **Cliente:** Meu pedido não chegou.
>
> **Agente:** Sinto muito pelo transtorno. Qual é o número do pedido?
>
> **Cliente:** Acho que é 48219. Ninguém veio aqui.
>
> **Agente:** Consultei o pedido 48219: ele está em transporte, com previsão de 02/09; hoje é 08/09. A previsão venceu há seis dias e não há tentativa de entrega informada. Posso abrir um chamado de **entrega atrasada**, urgência **alta**, para acionar a transportadora e solicitar nova previsão?
>
> **Cliente:** Sim.
>
> **Agente:** Chamado 2026-0842 confirmado para o pedido 48219. A transportadora será acionada; acompanhe pelo protocolo. Se precisar acrescentar informação, informe esse número ao atendimento.

**Informação que o sistema precisa descobrir:** o número correto do pedido, se houve tentativa de entrega e, principalmente, se a versão do cliente é coerente com o status e a data de previsão retornados pelo rastreio. Essa decisão não vem pronta em um formulário e depende do diálogo e dos dados consultados.

## 3. Os ganhos esperados

**Por que um agente, e não software comum:** a consulta de um pedido conhecido e a abertura confirmada de um chamado são workflows. O agente se justifica na parte anterior: interpreta relato livre, decide qual lacuna perguntar sem repetir o que já foi dito e confronta a narrativa com o rastreio para escolher entre informar, propor chamado ou escalar. A autonomia é limitada: regras determinísticas validam IDs, datas e permissões, e a ação irreversível fica atrás de confirmação.

| Eixo | Linha de base (medida) | Alvo | Ganho | Volume |
| --- | --- | --- | --- | --- |
| Tempo de triagem até proposta/encaminhamento | **A medir antes do piloto:** mediana de 10 atendimentos cronometrados, com planilha e transcritos versionados; não há valor medido ainda | Reduzir a mediana em pelo menos 40%, sem aumentar classificações incorretas | Minutos poupados por ocorrência = mediana atual − mediana do piloto | 10 casos no piloto; projeção para produção somente depois de medir a fila real |
| Erro e retrabalho | **A medir antes do piloto:** em 10 casos, contar chamados cuja categoria ou pedido precisou ser corrigido pelo atendente | 0 chamados de atraso para pedido ainda no prazo e 0 divergências “entregue/não recebido” classificadas como atraso | Correções evitadas / 10 casos | 10 casos no piloto, incluindo atraso, entregue/não recebido, prazo futuro e pedido inexistente |

Os alvos são hipóteses verificáveis, não resultados prometidos. O teste compara o mesmo conjunto de casos com o processo manual e com o agente; cada resultado é verificado pelo status do pedido, pelas regras acima e pela revisão do atendente.

**Ganho para o usuário:** menos repetição de informação, resposta inicial mais rápida e visibilidade sobre o que será registrado antes que o chamado exista.

**Tensão entre usuário e negócio, se houver:** conter mais conversas reduz carga, mas encerrar uma conversa rapidamente não equivale a resolvê-la. Por isso a métrica principal do piloto é tempo com classificação verificada, e não apenas “conversas sem humano”; o usuário pode recusar o chamado e sempre recebe encaminhamento para um atendente nos casos incertos.
