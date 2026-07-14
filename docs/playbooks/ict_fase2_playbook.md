# Master Trader IA: Estudo Completo da Fase 2 (Gatilhos de Entrada)

> [!IMPORTANT]
> **A Regra da Paciência:** A Fase 1 (M15) diz *ONDE* o mercado vai agir. A Fase 2 (M1) diz *QUANDO* você vai entrar. Apenas puxe o gatilho se a sequência exata de eventos desta fase acontecer. Sem adivinhações, apenas reação.

Este é o seu manual de execução cirúrgica. É aqui que o seu gerenciamento de risco e sua precisão são postos à prova.

---

## 1. A Regra da Primeira Vela (O Ringue de Batalha)

No ICT, o período de abertura da sessão (especialmente em Nova York) é conhecido pelo *Judas Swing* (movimento falso projetado para capturar a liquidez dos traders impacientes).

* **Horário Crítico:** 09:30 AM às 10:00 AM (EST).
* **O Procedimento:** Sente nas mãos. Deixe a primeira vela de 30 minutos se formar completamente.
* **A Marcação:** Assim que bater 10:00 AM, marque uma linha horizontal na **Máxima** e na **Mínima** dessa primeira vela de 30 minutos.
* **A Lógica:** Este é o verdadeiro "ringue" do dia. O volume que entra às 09:30 AM geralmente define os extremos dessa faixa inicial. O verdadeiro deslocamento institucional (IPDA) tenderá a ocorrer após a varredura (Sweep) de um desses extremos, coincidindo com as zonas mapeadas na Fase 1.

---

## 2. A Confirmação no Gráfico de 1 Minuto (M1)

O preço acabou de atingir uma de suas zonas da Fase 1 (Ex: Mínima de Londres ou a Mínima da Primeira Vela de 30m). Agora você vai para o **Gráfico de 1 Minuto (M1)** com o dedo no gatilho.

Você SÓ clica em Comprar ou Vender se a seguinte sequência mecânica de 3 passos ocorrer:

### Passo 1: O Sweep (Varredura de Liquidez)
O preço deve cruzar a linha da sua zona de liquidez e, idealmente, formar um pavio no M1 (rejeição). Se ele fechar com o corpo muito além da linha sem demonstrar fraqueza, continue esperando. Nós queremos ver a captura.

### Passo 2: O Displacement (Deslocamento Enérgico)
Imediatamente após a varredura, o Smart Money deve entrar com agressividade. O preço deve reverter em direção à faixa interna com velas institucionais.
* **Característica:** Velas com corpos longos e pouco pavio. Isso indica urgência.

### Passo 3: O Gatilho (FVG ou CSD)
Esse deslocamento obrigatoriamente precisa deixar uma "pegada":
* **FVG (Fair Value Gap):** O deslocamento deixa um espaço em branco (ineficiência) entre a sombra da vela 1 e a sombra da vela 3. Esse espaço é onde o algoritmo voltará para rebalancear o preço.
* **CSD (Change in State of Delivery):** O corpo da vela forte que promove o deslocamento engolfa (fecha além) dos corpos das velas anteriores que estavam indo em direção ao Sweep. É a mudança no fluxo de ordens.
* **A Execução:** Posicione uma Ordem Limite (Limit Order) de entrada no início do FVG.
* **O Stop Loss:** Obrigatório. Coloque o Stop Loss exatamente 1 ou 2 ticks abaixo do fundo (ou topo) absoluto gerado pelo Sweep. Nunca opere sem ele.

---

## 3. A Reação de Inversão ("O Flip")

O trader profissional não tem ego. Se o mercado invalidar a sua narrativa, você muda junto com ele de forma robótica.

> [!WARNING]
> **O Inverted FVG (A falha da Narrativa)**
> Você montou sua posição num FVG do M1 esperando a reversão. Porém, o mercado ignora a sua entrada e passa reto com o corpo de uma vela fechando *completamente do outro lado* do seu FVG, gerando um Stop Loss.

* **O que isso significa?** A sua zona de suporte/resistência institucional falhou. A narrativa do mercado não era reverter ali; a varredura não foi suficiente ou havia um alvo maior à frente.
* **A Reação (Flip):** O FVG falho agora se transforma em um **Inverted FVG**. Ele muda de polaridade (de suporte vira resistência, ou vice-versa). 
* **Ação:** Treine-se para agir rapidamente. Assim que o preço testar novamente o nível desse FVG invalidado (Inverted FVG), inverta sua mão. Entre na direção do rompimento buscando a próxima piscina de liquidez que você mapeou na Fase 1.

> [!TIP]
> **Resumo da Fase 2:** Aguarde a primeira vela de 30m. Assista a varredura da liquidez. Espere o deslocamento enérgico. Entre no FVG deixado para trás. Se o FVG falhar miseravelmente, o Inverted FVG é a sua nova entrada para recuperação rápida e sem ego.

---

## CRITÉRIOS DE DECISÃO — FASE 2 (para uso da IA Auditora)

A IA avalia a qualidade do gatilho detectado pelo poller. O sinal já passou pela validação mecânica (sweep + displacement ≥70% + FVG detectado no código), mas aqui avaliamos a qualidade contextual.

### Critério 1 — Confirmação do Sweep com Fechamento de Retorno (OBRIGATÓRIO)
- O detector de sinais já valida isso no código: `low[2] < zone_low and close[2] > zone_low`.
- A IA confirma: o sweep_level informado é plausível como zona de liquidez (não é um nível aleatório)?
- Se `sweep_level == 0.0` → **FAIL. RECUSADO.**

### Critério 2 — Tamanho do FVG é Significativo (OBRIGATÓRIO)
- Calcule: `fvg_size = fvg_top - fvg_bottom`
- Referências mínimas por ativo (valores absolutos em USD):
  | Ativo | FVG mínimo aceitável |
  |-------|---------------------|
  | BTC   | $50                 |
  | ETH   | $5                  |
  | SOL   | $0.30               |
  | XRP   | $0.003              |
  | BNB   | $0.50               |
- Se `fvg_size` for menor que o mínimo do ativo → **FAIL. RECUSADO** (FVG insignificante, risco de slippage consumir a entrada).

### Critério 3 — Stop Loss Posicionado Corretamente (OBRIGATÓRIO)
- Para BUY: `sl_level` deve estar **abaixo** de `fvg_bottom`. Qualquer SL acima ou igual ao fundo do FVG invalida o padrão.
- Para SELL: `sl_level` deve estar **acima** de `fvg_top`.
- Se posicionado incorretamente → **FAIL. RECUSADO.**

### Critério 4 — Risco/Retorno Mínimo (OBRIGATÓRIO)
- Estime o alvo primário como a próxima zona de liquidez oposta (nível da sessão anterior).
- O trade só vale se o R potencial for **≥ 2R** (distância ao alvo ≥ 2× a distância ao SL).
- Se não houver espaço livre suficiente para 2R → **FAIL. RECUSADO.**

### Critério 5 — Alinhamento BUY/SELL com Direção do Displacement (OBRIGATÓRIO)
- BUY: o displacement deve ser bullish (velas de alta com corpo ≥ 70% do range). O código já verifica isso, mas a IA confirma a coerência do payload.
- SELL: displacement deve ser bearish.
- Se `action=BUY` mas `fvg_top < fvg_bottom` → **FAIL** (estrutura invertida).

### Decisão Final Fase 2
| Critérios 1–5 | Decisão |
|---|---|
| Todos PASS | ✅ APROVADO — avançar para Fase 3 |
| Qualquer FAIL | ❌ RECUSADO — registrar qual critério falhou |
