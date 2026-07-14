# Master Trader IA: Estudo Completo da Fase 1

> [!IMPORTANT]
> **A Regra de Ouro do ICT:** O tempo precede o preço. O Interbank Price Delivery Algorithm (IPDA) programa suas entregas de preço baseadas em horários específicos, buscando a liquidez (ordens de Stop Loss) deixada nas sessões anteriores por traders de varejo.

Este playbook é o seu manual mecânico de preparação diária. Siga estas etapas rigorosamente antes de buscar qualquer entrada no gráfico.

---

## 1. Mapeamento de Tempo (Gráfico de 15 Minutos - M15)

O varejo opera tentando adivinhar a direção. O Smart Money opera caçando onde estão as poças de dinheiro (liquidez). Estas poças se formam acima e abaixo de consolidações formadas durante sessões de mercado específicas.

Todos os dias, desenhe linhas horizontais nestes níveis exatos. Ajuste o fuso horário do seu TradingView para **Nova York (EST)**.

### A. Sessão Asiática (Asian Range)
* **Horário de Formação:** 20:00 às 00:00 EST.
* **Característica:** Geralmente é uma consolidação estreita. O mercado interbancário está acumulando posições lentamente.
* **O que marcar no gráfico:**
  * **Asia High (Máxima Asiática):** Poça de *Buy Stops* (liquidez compradora).
  * **Asia Low (Mínima Asiática):** Poça de *Sell Stops* (liquidez vendedora).
* **Dinâmica Algorítmica:** O algoritmo adora expandir para fora dessa faixa durante a sessão de Londres ou Nova York para liquidar os traders que operam o rompimento asiático.

### B. Sessão de Londres (London Killzone)
* **Horário de Formação:** 02:00 às 05:00 EST.
* **Característica:** É aqui que frequentemente é criada a máxima ou a mínima verdadeira do dia. Londres tem volume massivo.
* **O que marcar no gráfico:**
  * **London High (Máxima de Londres):** Resistência algorítmica ou alvo de liquidez para Nova York.
  * **London Low (Mínima de Londres):** Suporte algorítmico ou alvo de liquidez para Nova York.

### C. Níveis Diários e Semanais Anteriores
A liquidez "macro" atrai o preço como um ímã.
* **PDH (Previous Daily High):** A máxima do dia anterior. Se for rompida de forma fraca (varredura), é um gatilho para reversão.
* **PDL (Previous Daily Low):** A mínima do dia anterior.
* **PWH / PWL (Previous Weekly High/Low):** Máximas e mínimas da semana anterior. Muito utilizadas para alvos de *swing trade* ou *day trades* de longa duração.

---

## 2. Filtro de Contexto (O Seu Escudo Contra a Manipulação)

Antes de traçar qualquer linha, você precisa saber quando o algoritmo vai injetar volatilidade extrema.
* **Onde olhar:** Forex Factory, Investing.com ou ferramentas similares.
* **O que procurar:** Notícias de Alto Impacto (Red Folders), como CPI (Inflação), NFP (Emprego) e FOMC (Taxa de Juros).

> [!WARNING]
> **A Regra do Isolamento de Volatilidade:**
> Se houver uma notícia *Red Folder* agendada para 08:30 AM ou 10:00 AM (horários comuns), você está TERMINANTEMENTE PROIBIDO de estar posicionado no mercado 15 minutos antes e 15 minutos depois do evento.
> *Por quê?* O Smart Money usa esses eventos para expandir agressivamente os spreads, causando slippage e stopando as duas pontas do varejo antes de seguir a verdadeira direção do dia. Deixe a poeira baixar.

---

## 3. Mapeamento de Cenários (A Mente Reativa, Sem Viés)

O maior erro do trader amador é o *Daily Bias* (Viés Diário) engessado. Entrar no dia pensando "hoje o dia é de alta e eu só vou comprar" é fatalidade algorítmica.

Nós usamos um **Mapeamento Lógico Condicional** (Se -> Então). Abaixo estão exemplos de como você deve narrar a sua manhã (Anota mental ou no diário):

### Cenário A (Reversão Clássica)
* **Condição:** "Se o preço durante a abertura de NY varrer a *Mínima de Londres* no M15..."
* **Reação M1:** "...eu descerei para o M1 aguardando um deslocamento violento de alta (Displacement + FVG). Meu alvo de lucro primário será a *Máxima Asiática*."

### Cenário B (Continuação após Manipulação)
* **Condição:** "Se o preço subir no início do dia e capturar a *Máxima do Dia Anterior (PDH)*, rejeitando imediatamente..."
* **Reação M1:** "...procurarei gatilhos de venda no M1. Meu alvo de lucro será a *Mínima de Londres* formada nas últimas horas."

### Cenário C (O "Flip" - Quebra de Narrativa)
* **Condição:** "Se eu comprar num FVG (M1) focado na *Mínima de Londres* e o mercado destruir o meu FVG formando um *Inverted FVG*..."
* **Reação:** "...a narrativa de reversão falhou. O mercado quer mais liquidez abaixo. Inverto a posição imediatamente buscando a próxima piscina, que é a *Mínima do Dia Anterior (PDL)*."

> [!TIP]
> **Resumo da Fase 1:** Você não está prevendo para onde o preço vai. Você está desenhando as "armadilhas" de liquidez no M15. Quando o preço cair nessas armadilhas, o algoritmo lhe dará o sinal de gatilho no M1 (Fase 2). Seu trabalho é apenas esperar o preço chegar nas suas linhas.

---

## CRITÉRIOS DE DECISÃO — FASE 1 (para uso da IA Auditora)

A IA deve avaliar cada critério abaixo e atribuir PASS ou FAIL. Se qualquer critério obrigatório receber FAIL, a decisão da Fase 1 é **RECUSADO** e a auditoria encerra aqui.

### Critério 1 — Red Folder (OBRIGATÓRIO)
- Chame `get_economic_calendar_status()`.
- Se retornar BLOQUEIO → **FAIL imediato. RECUSADO.**
- Se retornar "Calendário limpo" → PASS.

### Critério 2 — Sessão de Mercado (OBRIGATÓRIO)
- Avalie a sessão atual informada no payload.
- **PASS** para: `NOVA_YORK`, `NOVA_YORK_E_LONDRES (OVERLAP)`, `LONDRES`
- **FAIL** para: `ASIA (TOQUIO/SINGAPURA)` — a sessão asiática não gera deslocamentos confiáveis para cripto intraday; apenas consolida. Exceção: se `zone_hit` for `pdl` ou `pdh`, pode PASS pois são níveis macro independentes de sessão.
- **FAIL** para: `FECHADO`

### Critério 3 — Zona Atingida é Nível ICT Válido (OBRIGATÓRIO)
- A `zone_hit` do payload deve corresponder a um nível de liquidez reconhecido:
  - **BUY válidos:** `zone1_low`, `zone2_low`, `pdl`
  - **SELL válidos:** `zone1_high`, `zone2_high`, `pdh`
- Qualquer outro valor → **FAIL. RECUSADO.**

### Critério 4 — Coerência Direcional (RECOMENDADO)
- Se a ação for BUY: verificar se a sessão atual tem histórico de reversão bullish (Londres e abertura NY são ideais para varredura de mínimas).
- Se a ação for SELL: idem para máximas.
- Este critério é RECOMENDADO — um FAIL aqui reduz o score mas não bloqueia sozinho.

### Decisão Final Fase 1
| Critérios 1, 2, 3 | Critério 4 | Decisão |
|---|---|---|
| Todos PASS | PASS | ✅ APROVADO — avançar para Fase 2 |
| Todos PASS | FAIL | ⚠️ APROVADO COM RESSALVA — registrar no relatório |
| Qualquer FAIL | qualquer | ❌ RECUSADO |
