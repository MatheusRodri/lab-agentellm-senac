Você analisa um problema de entrega usando somente os fatos abaixo. Hoje é
{hoje}. Compare a previsão com hoje, confronte o relato do cliente com a
situação do sistema e raciocine passo a passo. Se o sistema disser "entregue"
e o cliente negar recebimento, chame isso de divergência, não de atraso.

Pedido: {pedido}
Conversa: {conversa}
Categorias permitidas: {categorias}

Responda somente JSON. O campo "raciocinio" deve explicar as comparações; a
conclusão deve conter categoria, urgencia (baixa/media/alta), descricao,
acao_sugerida específica e abrir_chamado (boolean). Só abra chamado para uma
ocorrência que exija atuação. Previsão futura não é atraso.

Formato:
{{"raciocinio":"...", "categoria":"duvida", "urgencia":"baixa",
  "descricao":"...", "acao_sugerida":"...", "abrir_chamado":false}}
