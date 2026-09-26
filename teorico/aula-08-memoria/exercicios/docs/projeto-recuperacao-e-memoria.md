# Projeto de recuperação e memória — AgendeAkiAI

> Rascunho simples do Exercício 8. As decisões abaixo usam como base o
> [projeto AgendeAkiAI](https://github.com/MatheusRodri/bot-agendeakiai).
> O projeto atual usa uma API mock, catálogo em JSON e estado em memória. O que
> estiver descrito como memória persistente ou RAG é proposta para a próxima
> versão, não algo que já está implementado.

## 1. Recuperação

### 1.1 As dez perguntas do case

Como o projeto ainda não possui as dez perguntas do Exercício 6, este é um
conjunto inicial de perguntas que um cliente ou a operação poderia fazer.

| ID | Pergunta | Formato da resposta | Recuperação escolhida |
|---|---|---|---|
| P1 | Qual é o histórico do cliente `cliente-001`? | registro | consulta estruturada pelo identificador |
| P2 | Qual é o preço e o horário da opção `opc-001`? | registro | regex para extrair o ID e consulta estruturada |
| P3 | Quais penteados existem no Centro por até R$ 150? | registro | consulta estruturada com filtros |
| P4 | Quais horários estão livres para maquiagem no sábado? | registro | consulta estruturada na agenda |
| P5 | Onde a política fala em “48 horas de antecedência”? | termo | busca textual exata |
| P6 | O que combina com um casamento no calor e com estilo clássico? | assunto | busca vetorial nas descrições dos serviços |
| P7 | Que maquiagem combina com uma formatura e acabamento natural? | assunto | busca vetorial nas descrições dos serviços |
| P8 | Quero um visual discreto e profissional para uma entrevista. O que você sugere? | assunto | busca vetorial nas descrições dos serviços |
| P9 | Qual profissional atende no salão que oferece a opção `opc-003`? | relação | `JOIN` entre opção, profissional e salão |
| P10 | Quais bairros têm mais opções abaixo de R$ 150? | agregação | consulta estruturada com `GROUP BY` |

Contagem:

| Formato | Quantidade |
|---|---:|
| registro | 4 |
| termo | 1 |
| assunto | 3 |
| relação | 1 |
| agregação | 1 |
| **total** | **10** |

Portanto, **3 das 10 perguntas realmente precisam de busca vetorial**. As
outras sete são respondidas por regex, consulta estruturada, busca textual ou
`JOIN`/agregação.

### 1.2 Decisões por forma de recuperação

#### Consulta estruturada — usa

Os dados de cliente, catálogo, preço, profissional e disponibilidade já têm
campos definidos. P1, P2, P3, P4, P9 e P10 devem ser respondidas pela API e,
no futuro, pelo banco de dados da plataforma.

IDs como `cliente-001` e `opc-001` podem ser extraídos com regex. Filtros
escritos de formas variadas, como “sem gastar mais de cento e cinquenta”, são
extraídos pelo modelo em uma saída estruturada e validados pelo código.

O modelo **não escreve SQL**. A aplicação possui consultas prontas e aceita
somente parâmetros validados, por exemplo `bairro`, `servico`, data e
`orcamento_max`.

#### Busca textual — usa

Ela será usada em regras e políticas quando a pergunta trouxer uma expressão
exata, como “48 horas”, nome de salão ou código de opção. Na POC, como o corpus
é pequeno, uma busca simples no texto já basta. Se as regras forem colocadas
no PostgreSQL, a opção inicial será `tsvector` com índice GIN, sem criar um
novo serviço de busca.

Busca textual e vetorial serão escolhidas por um roteador. Se uma pergunta
ambígua precisar das duas, os resultados serão unidos por **RRF (Reciprocal
Rank Fusion)**. Os escores de BM25 e cosseno não serão somados diretamente,
porque usam escalas diferentes.

#### Busca vetorial — usa, mas apenas em três perguntas

Ela serve para P6, P7 e P8, pois essas perguntas descrevem uma intenção sem
usar necessariamente os mesmos termos do catálogo. O índice conterá
descrições verificadas de serviços, estilos e ocasiões. Preço, bairro, data e
disponibilidade ficam como metadados e são filtrados de forma determinística.

As quatro cegueiras precisam de medição. Como este é um rascunho e ainda não
foi executado um modelo de embedding, não serão inventados valores de cosseno:

| Cegueira | Par de controle do domínio | Cosseno |
|---|---|---|
| negação | “A opção opc-001 está disponível” / “A opção opc-001 não está disponível” | a medir |
| número | “Cancelamento exige 48 horas” / “Cancelamento exige 24 horas” | a medir |
| entidade | “Consultar a opção opc-001” / “Consultar a opção opc-002” | a medir |
| tempo | “Às 14h a opção estava livre” / “Às 14h05 a opção estava ocupada” | a medir |
| controle sem relação | “O cliente prefere estilo clássico” / “A API mock está online” | a medir |

Mesmo antes da medição, esses campos não serão decididos pelo vetor. Negação é
validada pelo código; números e IDs são filtros; disponibilidade e políticas
vigentes são escolhidas pelo carimbo de tempo.

#### Grafo — não usa

Existe pergunta de relação, como P9, mas o caminho é conhecido e curto:
`opção -> profissional -> salão`. Um ou dois `JOINs` resolvem o caso. Um banco
de grafo aumentaria o custo de construção e exigiria manter as relações
sincronizadas sem trazer benefício nesta versão.

### 1.3 Tabela de decisão

| Forma | Usa? | Para quais perguntas | Custo declarado | Por quê |
|---|---|---|---|---|
| regex | usa | P1 e P2 | baixo | extrai IDs de formato fixo antes da consulta |
| consulta estruturada | usa | P1, P2, P3, P4, P9 e P10 | baixo a médio | os dados já possuem campos e filtros definidos |
| busca textual | usa | P5 e buscas por nomes/códigos | baixo | o corpus inicial é pequeno e contém termos exatos |
| busca vetorial | usa | P6, P7 e P8 | médio | encontra serviços por intenção, ocasião e estilo |
| grafo | não usa | nenhuma nesta versão | alto | a única relação é rasa e pode ser resolvida com `JOIN` |

A ordem do roteador será: regex, consulta estruturada, busca textual e, por
último, busca vetorial. Grafo não entra na primeira versão.

## 2. Memória do agente

### 2.1 Curto e longo prazo

| Item | Curto prazo | Longo prazo |
|---|---|---|
| o que é | estado da conversa e da execução atual | informação útil que continua disponível em outras execuções |
| conteúdo no AgendeAkiAI | mensagem atual, filtros extraídos, opções consultadas, confirmação, passos, resultados das ferramentas e orçamento | episódios resumidos, preferências confirmadas do cliente e regras do agente |
| persistido como | um checkpoint JSON por `execution_id` | índice vetorial, tabela chave-valor e prompt versionado |
| quando é lido | uma vez ao iniciar ou retomar a execução | quando a intenção atual indicar relevância, ou por chave de cliente |
| acesso | pelo `execution_id` | por similaridade para episódios e por chave para preferências |
| ciclo de vida | termina após a conclusão e o prazo curto de auditoria | acumula, mas segue regras de contradição, decaimento e remoção |

O projeto atual possui `AgentState`, mas ele não sobrevive ao fim do processo.
Na versão proposta, o checkpoint guarda:

- `execution_id`, `cliente_id`, mensagem original e horário;
- confirmação explícita recebida ou ainda pendente;
- filtros extraídos e IDs das opções apresentadas;
- trajetória das ferramentas, com argumentos, resultado e status;
- ID do agendamento, caso a escrita já tenha acontecido;
- passos e tokens gastos;
- versões do prompt, modelo e catálogo.

O checkpoint é salvo **depois** de cada resultado de ferramenta. Assim, uma
retomada não repete um agendamento já confirmado. Uma aprovação pode chegar
horas depois usando o mesmo `execution_id`, e uma execução defeituosa pode ser
reproduzida com as mesmas versões registradas.

### 2.2 Orçamento da janela

O limite inicial continua simples: **4.000 tokens por execução**, como já está
definido no projeto.

| Fonte | Teto |
|---|---:|
| system prompt e regras | 800 tokens |
| objetivo e pedido atual | 400 tokens |
| trajetória da execução | 900 tokens |
| trechos recuperados do RAG | 900 tokens |
| memória de longo prazo | 400 tokens |
| reserva para a resposta | 600 tokens |
| **total** | **4.000 tokens** |

Quando o limite estourar, serão descartados nesta ordem:

1. resultados brutos antigos de ferramentas, preservando apenas um resumo;
2. episódios de memória com menor relevância;
3. trechos de RAG repetidos ou com menor escore;
4. mensagens antigas já resumidas.

Nunca serão descartados o pedido atual, a confirmação do cliente, a opção
selecionada e o registro de que o agendamento já foi ou não realizado.

### 2.3 As três memórias

| Tipo | O que guarda no case | Estrutura | Como é recuperada |
|---|---|---|---|
| episódica | resumo de uma busca anterior, preferências usadas e resultado da recomendação | índice por similaridade, com `cliente_id` e data nos metadados | pelos episódios do mesmo cliente que forem similares ao pedido atual |
| semântica | preferência confirmada: estilo, bairro e período preferido | tabela chave-valor por `cliente_id` e nome da preferência | busca exata pela chave, sem embedding |
| procedural | regras como “pedido atual vence o histórico” e “não agendar sem confirmação” | texto versionado no system prompt | carregado no início de toda execução |

### 2.4 Escrita e o que não entra

A escrita será conservadora:

- o **código** grava no máximo um resumo episódico de até 500 caracteres por
  execução concluída;
- o código atualiza no máximo três preferências semânticas quando o cliente as
  corrige ou confirma explicitamente;
- o **agente não altera sozinho** a memória procedural;
- regras procedurais só entram após revisão humana e mudança de versão do
  prompt.

Não serão guardados na memória de longo prazo:

- credenciais, tokens, documentos pessoais ou dados de pagamento;
- mensagens externas não verificadas como se fossem fatos;
- resultados brutos de ferramentas que podem ser consultados novamente;
- disponibilidade de agenda como preferência permanente;
- preço calculado ou ranking que possa ser recalculado.

## 3. Como o agente esquece

### 3.1 Contradição

Exemplo do domínio:

- às 14h, `opc-001` estava disponível;
- às 14h05, depois de um agendamento, `opc-001` ficou indisponível.

Os dois fatos são válidos em instantes diferentes. Todo fato terá
`observed_at`. Na leitura, o código agrupa por `opcao_id` e escolhe
deterministicamente `max(observed_at)`. O modelo não decide qual é o mais novo.

O fato anterior não é apagado por contradição. Ele é ignorado na resposta e o
descarte fica registrado no log com a chave do fato, a versão escolhida e a
versão descartada.

### 3.2 Decaimento

Episódios de recomendação não confirmados expiram depois de **180 dias**. Esse
prazo é suficiente para preferências sazonais perderem força e impede que uma
busca antiga continue influenciando o cliente indefinidamente.

Ao atingir o corte, o episódio é removido do índice vetorial. Preferências
confirmadas não seguem esse corte automático: são substituídas por
contradição, removidas a pedido do titular ou revalidadas em uma nova conversa.
Agendamentos oficiais seguem a política de retenção do sistema transacional,
não a política da memória do agente.

### 3.3 Remoção solicitada pelo titular

O `cliente_id` pode aparecer em mais lugares do que nas três memórias. A
remoção deve cobrir:

1. tabela de memória semântica;
2. documentos, vetores e metadados da memória episódica;
3. prompt e histórico de versões da memória procedural, caso uma regra cite o
   cliente;
4. checkpoints das execuções;
5. logs e traces de chamadas de ferramentas;
6. cache de respostas e resultados recuperados;
7. documentos e índice do RAG, se algum texto mencionar o cliente;
8. backups, por meio de uma marca de exclusão reaplicada após restauração.

O procedimento será:

1. receber e autenticar a solicitação;
2. gerar uma lista das estruturas a limpar;
3. remover por `cliente_id` e também procurar o identificador no conteúdo;
4. apagar o vetor e o documento de origem, sem reconstruir todo o índice;
5. executar uma varredura independente em todas as estruturas;
6. concluir somente se a busca exata e a busca por metadados retornarem zero
   ocorrências.

O teste pode gravar o marcador `cliente-remocao-teste-001`, executar a remoção
e falhar caso o marcador ainda apareça em qualquer estrutura. O log da remoção
guarda apenas o ID da solicitação e o resultado da verificação, não o conteúdo
apagado.

### 3.4 Reprodutibilidade

O sistema não será totalmente reprodutível ao longo do tempo. A mesma pergunta
pode produzir outra recomendação depois que preferências, catálogo,
disponibilidade ou memórias mudarem. Para depuração, o checkpoint registra as
versões usadas. Para avaliação, será necessário fixar uma cópia da memória e
do catálogo ou medir separadamente a qualidade do modelo e a mudança da
memória.

## Resposta final do exercício

Das dez perguntas propostas, **três precisam de busca vetorial**. Quatro são
consultas de registros, uma é busca textual, uma é relação resolvida com
`JOIN` e uma é agregação resolvida com consulta estruturada.
