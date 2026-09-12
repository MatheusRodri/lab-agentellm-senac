# Arquitetura v1 — AgendeAki AI

> Versão inicial da arquitetura do agente de recomendação de penteados. As
> proporções e os tetos são estimativas para orientar o primeiro protótipo e
> serão revisados quando houver dados de uso.

## 1. Entrada

O usuário principal é a cliente que procura uma sugestão de penteado para uma
ocasião. Ela inicia a conversa por chat, por exemplo: “Vou a um casamento e
não sei como arrumar meu cabelo”.

As entradas são heterogêneas: estima-se que ~65% sejam pedidos de recomendação
de estilo, ~25% sejam dúvidas de agenda/disponibilidade e ~10% sejam suporte
ou assuntos fora do escopo. Há heterogeneidade suficiente para uma triagem;
sem ela, uma dúvida simples de agenda gastaria o mesmo agente usado para uma
recomendação que precisa de coleta e raciocínio.

## 2. System

**System prompt, em uma frase:** “Você é a assistente AgendeAki AI: ajuda a
cliente a encontrar opções de penteado e profissionais disponíveis, sem fazer
diagnóstico de saúde, prometer resultado visual ou confirmar um agendamento
sem o consentimento explícito da cliente.”

| Ferramenta | Faz | Tipo | Reversível? |
| --- | --- | --- | --- |
| `buscar_profissionais` | Consulta profissionais por cidade, estilo e faixa de preço. | Leitura | Sim |
| `consultar_disponibilidade` | Consulta horários de um profissional. | Leitura | Sim |
| `salvar_preferencia` | Salva o estilo de que a cliente gostou para uso futuro. | Escrita | Sim, a cliente pode alterar/remover. |
| `criar_solicitacao_agendamento` | Cria uma solicitação, ainda não uma reserva confirmada. | Escrita | Sim, até a confirmação da cliente/profissional. |

O estado precisa sobreviver entre passos: objetivo da cliente, ocasião, data,
cidade, comprimento/textura do cabelo quando informado, restrições de preço,
preferências, profissionais/horários já consultados, perguntas já feitas,
falhas de ferramenta e a trajetória de chamadas. A lista de mensagens é só a
forma de conversar com o modelo; não é o estado do sistema.

**Orçamento do agente de recomendação:** máximo de 6 passos, 10.000 tokens e
60 segundos por atendimento. O roteador tem uma chamada curta; o avaliador tem
no máximo 2 rodadas; a solicitação de agenda não é criada sem confirmação da
cliente. Os números são pequenos de propósito: a cliente está esperando no
chat e uma recomendação não justifica uma trajetória longa.

## 3. Fluxo de processamento

```text
1. ENTRADA        cliente escreve no chat                                  [—]
        ↓
2. TRIAGEM        identifica recomendação, agenda, suporte ou fora         [ROUTER, 1 chamada]
        recomendação -> 3     agenda -> 6     suporte/fora -> retorno/fila
        ↓
3. COLETA         pergunta somente o que falta para recomendar              [AGENTE, 6 passos / 10k tokens / 60 s]
        ↓
4. CONSULTA       busca profissionais e disponibilidade conforme critérios  [CÓDIGO + ferramentas de leitura]
        ↓
5. RECOMENDAÇÃO   compara opções, redige e confere restrições                [AVALIADOR-OTIMIZADOR, 2 rodadas]
        ↓
6. SOLICITAÇÃO    salva preferência ou cria pré-agendamento                  [ESCRITA REVERSÍVEL + confirmação]
        ↓
7. RETORNO        mostra opções, próximos passos ou encaminhamento          [—]
```

O sistema não usa um orquestrador-trabalhador nesta v1. A recomendação depende
de uma única cliente e de poucas consultas previsíveis; as subtarefas já são
conhecidas no fluxo. Um orquestrador acrescentaria autonomia e custo sem uma
decisão dinâmica que o justifique.

## 4. Contratos entre etapas

| Etapa | Entra | Sai |
| --- | --- | --- |
| 1. Entrada | Texto livre da cliente. | `{"texto": "Vou a um casamento"}` |
| 2. Triagem | Texto da cliente. | `{"rota":"recomendacao", "confianca":"alta", "dados_extraidos":{"ocasiao":"casamento"}}` |
| 3. Coleta | Rota e dados extraídos; não repete o texto bruto. | `{"objetivo":"penteado para casamento", "cidade":"...", "data":"...", "preferencias":[...], "faltando":[...]}` |
| 4. Consulta | Critérios estruturados da coleta. | `{"opcoes":[{"profissional_id":"...", "estilos":[...], "preco_inicial":0, "horarios":[...]}]}` |
| 5. Recomendação | Objetivo, preferências e opções consultadas. | `{"recomendacoes":[...], "justificativa":"...", "limites":"...", "pode_agendar":true}` |
| 6. Solicitação | Profissional/horário escolhidos e confirmação explícita. | `{"solicitacao_id":"...", "status":"aguardando_confirmacao"}` ou `{"acao":"nao_solicitada"}` |
| 7. Retorno | Resultado da recomendação ou solicitação. | Texto curto que a cliente lê. |

**Exemplo do que a cliente vê:** “Para o casamento, encontrei duas opções de
penteado compatíveis com o estilo que você descreveu. A profissional Ana tem
horário no sábado às 14h; quer que eu crie uma solicitação de agendamento?”

## 5. Decisões de arquitetura

| Padrão | Onde para | Por que ele é necessário | Por que o mais simples não basta |
| --- | --- | --- | --- |
| Router | Triagem | A entrada mistura recomendação, agenda e suporte; cada rota tem custo e regras diferentes. | Um único fluxo trataria dúvidas de agenda como se precisassem de análise de estilo. |
| Agente com estado | Coleta | A cliente raramente informa ocasião, data, cidade, preferência e restrições de uma vez; o agente decide a próxima pergunta e consulta. | Um workflow fixo repetiria perguntas já respondidas ou encerraria sem dados suficientes. |
| Avaliador-otimizador | Recomendação | Confere se a resposta respeita ocasião, preço, disponibilidade e não promete resultado. | Uma redação única pode parecer boa, mas omitir uma restrição ou recomendar horário inexistente. |
| Escrita com confirmação | Solicitação | A cliente deve controlar quando uma preferência ou solicitação é gravada. | Uma chamada automática transformaria uma sugestão em ação no sistema sem consentimento. |

## 6. Limites e encaminhamento humano

O agente não recomenda tratamentos para queda de cabelo, alergias ou outras
questões de saúde; nesses casos, informa o limite e sugere procurar um
profissional de saúde. Também encaminha para atendimento humano quando não
encontra profissional/horário, quando a cliente relata uma necessidade fora do
catálogo ou quando há conflito entre disponibilidade e preferência.

Nenhum agendamento é confirmado pelo modelo. O agente apenas cria uma
solicitação reversível depois de uma confirmação explícita como “sim, pode
solicitar esse horário”.
