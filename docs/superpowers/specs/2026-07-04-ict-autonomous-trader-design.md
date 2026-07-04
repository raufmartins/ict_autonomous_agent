# ICT Autonomous Trader — Design Spec
**Data:** 2026-07-04
**Status:** Aprovado pelo usuário

---

## Objetivo

Transformar o protocolo ICT manual (Fases 1–5) em um sistema autônomo de paper trading. O sistema detecta padrões ICT no TradingView, valida as regras via Python puro e usa Gemini exclusivamente para síntese do diário ao final da sessão.

---

## Arquitetura e Fluxo de Dados

```
TradingView (gráfico NQ M1)
  └─ Pine Script detecta: Sweep → Displacement → FVG
       └─ Webhook JSON → https://<ngrok-url>/signal
            └─ FastAPI Webhook Server  (webhook_server.py)
                 └─ Decision Engine Python  (decision_engine.py)
                      ├─ Fase 1: Red Folder? → Forex Factory JSON API
                      ├─ Fase 2: Sinal válido? → Sweep + FVG + horário
                      ├─ Fase 3: Daily Limit? → state.json (stops_today >= 2)
                      └─ Resultado: APPROVED | REJECTED + motivo → logs/signals.log

[Uma vez por dia às 11:30 AM EST]
Journal Writer  (journal_writer.py)
  └─ Lê logs/signals.log do dia
       └─ Gemini API (gemini-2.5-flash) gera narrativa Fase 4/5
            └─ Append → ict_trading_journal.md
```

**Princípio central:** regras ICT são código Python determinístico. Gemini entra apenas onde agrega valor real — síntese qualitativa do diário.

---

## Componentes

### 1. `tradingview/ict_signals.pine` — Detecção de Padrão

Pine Script rodando no gráfico M1 do TradingView.

**O que detecta (sequência obrigatória):**
1. **Sweep:** preço cruza uma zona de liquidez mapeada (Asian High/Low, London High/Low, PDH/PDL) e rejeita com pavio no M1
2. **Displacement:** vela de reversão com corpo ≥ 70% do range e pavio inferior ≤ 30%
3. **FVG:** gap entre sombra da vela 1 e sombra da vela 3 deixado pelo displacement

**Payload do alerta (JSON):**
```json
{
  "asset": "NQ1!",
  "action": "BUY",
  "zone_hit": "london_low",
  "sweep_level": 18350.00,
  "fvg_top": 18360.00,
  "fvg_bottom": 18352.00,
  "sl_level": 18348.00,
  "timestamp": "2026-07-04T10:15:00"
}
```

**Zonas monitoradas no M15 (calculadas pelo Pine Script):**
- Asian High / Asian Low (20:00–00:00 EST)
- London High / London Low (02:00–05:00 EST)
- PDH / PDL (Previous Day High/Low)

---

### 2. `webhook_server.py` — Receptor de Sinais

**Tecnologia:** FastAPI  
**Endpoint:** `POST /signal`

**Responsabilidades:**
- Recebe e valida estrutura do payload (retorna `422` se incompleto)
- Chama `decision_engine.process_signal()` de forma assíncrona
- Responde `200 OK` em < 2s (dentro do timeout do TradingView)
- Endpoint `GET /health` para monitoramento

---

### 3. `decision_engine.py` — Regras ICT em Python Puro

Três filtros em sequência. Qualquer `False` rejeita o sinal imediatamente.

| Fase | Filtro | Lógica |
|------|--------|--------|
| 1 | Red Folder | Consulta `https://nfs.faireconomy.media/ff_calendar_thisweek.json`. Se houver evento de alto impacto nos próximos 30 minutos → `REJECTED: RED_FOLDER` |
| 2 | Horário válido | Aceita apenas 09:30–11:00 EST. Fora disso → `REJECTED: OUTSIDE_WINDOW` |
| 2 | FVG estrutural | `fvg_top > fvg_bottom`, distância mínima de 2 ticks, `sl_level` abaixo de `fvg_bottom` (BUY) ou acima de `fvg_top` (SELL) → caso contrário `REJECTED: INVALID_STRUCTURE` |
| 3 | Daily Loss Limit | Lê `state.json`. Se `stops_today >= 2` → `REJECTED: DAILY_LIMIT` |

Se todos os filtros passam → `APPROVED` → registra trade simulado em `state.json` e `logs/signals.log`.

---

### 4. `state_manager.py` — Estado Diário

Arquivo `state.json`, resetado automaticamente à meia-noite EST:

```json
{
  "date": "2026-07-04",
  "stops_today": 1,
  "trades_today": [
    {
      "time": "10:15",
      "action": "BUY",
      "zone_hit": "london_low",
      "fvg_top": 18360.00,
      "fvg_bottom": 18352.00,
      "sl_level": 18348.00,
      "result": "STOP",
      "r": -1.0
    }
  ]
}
```

**Price Waiting simulado:** registra swing lows/highs recebidos por updates do TradingView para simular trailing stop.

---

### 5. `journal_writer.py` — Gemini (Fase 4/5)

Executado às 11:30 AM EST via `schedule`. Usa `google-generativeai` (chamada direta, sem Antigravity SDK).

**Modelo:** `gemini-2.5-flash`

**Fluxo:**
1. Lê `logs/signals.log` do dia
2. Lê `state.json` para resultado dos trades
3. Monta prompt com contexto do dia + playbooks Fase 4/5
4. Gemini gera entrada no formato exato do `ict_trading_journal.md`
5. Valida presença das seções: `Visão Geral`, `Auditoria de Erros e Acertos`, `Lição do Dia`
6. Se inválido → re-prompta uma vez
7. Append no `ict_trading_journal.md`

---

### 6. `run.py` — Entry Point

Inicia o servidor FastAPI e agenda o journal writer:

```python
# Inicia FastAPI em thread separada
# Agenda journal_writer às 11:30 AM EST via schedule
# Loop principal mantém o processo vivo
```

---

## Estrutura de Arquivos

```
ict_autonomous_agent/
├── run.py                          ← entry point
├── webhook_server.py               ← FastAPI, POST /signal
├── decision_engine.py              ← regras ICT Python puro
├── state_manager.py                ← state.json CRUD
├── journal_writer.py               ← Gemini Fase 4/5
├── autonomous_ict_trader.py        ← mantido (refatorado para usar decision_engine)
├── tradingview/
│   └── ict_signals.pine            ← Pine Script para TradingView
├── logs/
│   └── signals.log                 ← log de todos os sinais recebidos
├── state.json                      ← estado diário (gerado em runtime)
└── docs/
    └── superpowers/
        └── specs/
            └── 2026-07-04-ict-autonomous-trader-design.md
```

**Dependências Python a adicionar:**
```
fastapi
uvicorn
schedule
google-generativeai
httpx          ← para consultar Forex Factory
pytz           ← para timezone EST
```

---

## Error Handling

### Falhas de Infraestrutura

| Falha | Comportamento |
|-------|---------------|
| ngrok / webhook server offline | Sinal perdido — nenhuma ação. Correto: sem confirmação, sem operação. |
| `state.json` corrompido | Recria com `stops_today: 0`, loga warning. Erra para o lado conservador. |

### Falhas de Dados

| Falha | Comportamento |
|-------|---------------|
| Forex Factory API indisponível | **Assume Red Folder ativo** → `REJECTED`. Na dúvida, não opera. |
| Payload TradingView incompleto | FastAPI retorna `422`. Sinal descartado com motivo no log. |
| `sl_level` inválido | Decision Engine rejeita com `REJECTED: INVALID_STRUCTURE`. |

### Falhas do Gemini (Journal Writer)

| Falha | Comportamento |
|-------|---------------|
| Quota 429 | Retry com backoff: 30s → 60s → 120s. Após 3 falhas, salva rascunho em `logs/journal_draft_YYYY-MM-DD.txt`. |
| Resposta sem seções obrigatórias | Re-prompta uma vez. Se falhar novamente, salva rascunho. |
| API key inválida | Log crítico + exit. Diário não é time-critical. |

### Princípio Geral

> **Falha conservadora:** qualquer erro que impeça validação completa resulta em `REJECTED`. O sistema nunca aprova na dúvida.

---

## Fora de Escopo (Esta Versão)

- Execução real de ordens (broker API)
- Price Waiting automatizado em tempo real via stream de ticks
- Interface web / dashboard
- Múltiplos ativos simultaneamente
- Backtesting automatizado

---

## Critérios de Sucesso

1. TradingView webhook chega e é processado em < 2s
2. Sinal com Red Folder ativo é rejeitado corretamente
3. Após 2 stops no dia, todos os sinais subsequentes são rejeitados
4. Journal escrito pelo Gemini contém as 3 seções obrigatórias
5. `state.json` reseta automaticamente à meia-noite EST
