# Master Trader IA: Estudo Completo da Fase 3 (Gestão de Risco e Condução)

> [!IMPORTANT]
> **A Regra da Sobrevivência:** O mercado é randômico no curto prazo e as perdas são garantidas estatisticamente. O único fator sob seu controle absoluto é quanto você perde e como você conduz o que ganha. A Fase 3 separa os jogadores de cassino dos operadores institucionais.

---

## 1. Risco Dinâmico e o Limite de Sobrevivência (Daily Loss Limit)

Um erro comum é tentar "recuperar" o dia após seguidos Stop Losses (o temido Revenge Trading). Isso corrói contas. Vamos programar um bloqueio mecânico no seu cérebro.

* **Regra Absoluta:** O seu Limite de Sobrevivência (Daily Loss Limit) é de **2 (dois) Stop Losses por dia**.
* **Como funciona:** Se você perder a primeira operação e a segunda operação em seguida, a sua sessão acabou. Feche o gráfico imediatamente.
* **O Risco por Trade:** Cada operação não deve expor mais do que 0.5% a 1% da sua margem. Tomar dois stops significará um drawdown de 1% a 2% no dia, algo perfeitamente reversível com a tática da condução.

> [!CAUTION]
> A emoção gritará: "Só mais um trade para eu empatar e zerar o dia!". Esta é a voz do varejo sendo liquidado. O algoritmo quer o seu desespero. Cumpra a regra de 2 stops ou você perderá o direito de ser treinado por mim.

---

## 2. A Tática do "Price Waiting" (Condução Assimétrica)

A maioria dos traders corta seus lucros precocemente por puro medo de o preço voltar ao ponto de entrada. Eles saem fixamente com 2R (duas vezes o risco), enquanto o algoritmo entrega deslocamentos que renderiam 8R, 10R ou 15R.

O objetivo do nosso modelo não é acertar todas, mas sim ter **matemática assimétrica** (quando erra, erra 1; quando acerta, acerta 5+).

### Como executar o Price Waiting de forma mecânica:

1. **Abandone o Take Profit Fixo de Fechamento Total:** Você pode fazer realizações parciais, mas a posição principal nunca deve ter um limite fechado tão curto na fase de aceleração.
2. **O Gatilho de Proteção Inicial:** Quando o preço aterrissar no primeiro nível óbvio de liquidez (exemplo: se você comprou na Mínima Asiática e o preço chegou ao Break Even/Meio do Range), você arrasta o Stop Loss para o 0x0 (ponto de entrada) para anular o risco.
3. **Trailing Stop nos Swings (M1):** 
   * Se você estiver **comprado** e o mercado estiver subindo com força, a cada vez que ele fizer um recuo e deixar um fundo claro (Swing Low) e continuar subindo, você arrastará o seu Stop Loss para ficar *exatamente um tick abaixo desse novo Swing Low*.
   * Se você estiver **vendido** e o mercado estiver caindo, a cada repique para cima que deixe um topo claro (Swing High) e continue caindo, você arrastará o seu Stop Loss para ficar *um tick acima desse novo Swing High*.
4. **Deixe o Mercado Tirar Você:** Não clique no botão "Fechar Ordem" por medo do retorno ("Vai que volta"). Deixe o preço acionar o seu trailing stop sozinho. Em dias em que a liquidez macro for buscada (ex: fechar um gap semanal inteiro), o "Price Waiting" vai transformar uma operação comum num trade de 8R a 12R.

> [!TIP]
> **Resumo da Fase 3:** Arrisque matematicamente. Imponha o limite inflexível de 2 perdas diárias. Quando engatar um trade bom, use os Swing Highs/Lows do gráfico M1 para seguir o preço. Deixe o algoritmo (IPDA) trabalhar a seu favor; ele vai esticar a corda. Você só recolhe a corda solta (o seu stop).

---

## CRITÉRIOS DE DECISÃO — FASE 3 (para uso da IA Auditora)

Esta é a última barreira antes da execução. Avalia o estado operacional do dia.

### Critério 1 — Limite Diário de Stops (OBRIGATÓRIO)

- Chame `read_journal_status()` para verificar o diário do dia.
- Conte os trades com `result == "STOP"` ou `r < 0` no dia atual.
- Se `stops_hoje >= 2` → **FAIL imediato. RECUSADO. Sessão encerrada.**
- Se `stops_hoje == 1` → PASS com ALERTA: este é o último trade permitido no dia.
- Se `stops_hoje == 0` → PASS.

### Critério 2 — Não Há Trade PENDING_AI ou OPEN no Mesmo Ativo (OBRIGATÓRIO)

- Verificar no journal se já existe um trade aberto (`result == "OPEN"` ou `result == "PENDING_AI"`) para o mesmo ativo do payload.
- Se sim → **FAIL. RECUSADO.** Não duplicar exposição no mesmo ativo.
- Se não → PASS.

### Critério 3 — Risco Total do Portfólio (RECOMENDADO)

- Contar quantos trades estão simultaneamente em `result == "OPEN"` ou `"PENDING_AI"` em todos os ativos.
- Se já houver 3 ou mais posições abertas → **FAIL RECOMENDADO** (risco de correlação entre cripto).
- Se houver 2 posições → PASS com RESSALVA.
- Se houver 0 ou 1 → PASS.

### Critério 4 — Horário Não é de Alta Volatilidade Não Estrutural (RECOMENDADO)

- Evitar entradas nos primeiros 5 minutos após abertura de sessão (08:00–08:05 EST para Londres, 09:30–09:35 EST para NY) quando o Judas Swing ainda está se formando.
- Se o timestamp do sinal cair nessas janelas → PASS com RESSALVA (aguardar confirmação adicional).

### Instrução de Execução (somente se Critérios 1 e 2 forem PASS)

Se todos os critérios obrigatórios passarem, a IA deve:

1. Calcular o preço de entrada: meio do FVG = `(fvg_top + fvg_bottom) / 2`
2. Chamar `log_approved_trade(asset, action, entry_price, sl_level, justificativa_resumida)`
3. Chamar `execute_limit_order(action, entry_price, sl_level)`
4. Retornar relatório com decisão APROVADO e os 3 critérios de cada fase.

### Decisão Final Fase 3

| Critério 1 | Critério 2 | Critério 3 | Decisão |
|---|---|---|---|
| PASS | PASS | PASS | ✅ APROVADO — executar |
| PASS | PASS | FAIL | ⚠️ APROVADO COM RESSALVA — executar, registrar alerta |
| FAIL | qualquer | qualquer | ❌ RECUSADO — sessão encerrada |
| qualquer | FAIL | qualquer | ❌ RECUSADO — posição duplicada |
