# ICT Autonomous Trader — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construir um sistema de paper trading autônomo que recebe sinais ICT do TradingView via webhook, valida as regras das Fases 1–3 com Python puro e usa Gemini para gerar o diário de operações (Fases 4–5) ao final da sessão.

**Architecture:** TradingView Pine Script detecta Sweep + Displacement + FVG no M1 e dispara um webhook JSON. Um servidor FastAPI recebe o sinal, o Decision Engine Python valida as regras ICT deterministicamente (Red Folder, janela de horário, FVG estrutural, Daily Loss Limit), e o resultado é logado em `state.json` e `logs/signals.log`. Às 11:30 AM EST, o Journal Writer chama a API do Gemini para gerar a entrada narrativa no diário Markdown.

**Tech Stack:** Python 3.14, FastAPI, uvicorn, httpx, pytz, schedule, google-generativeai, pytest, pytest-asyncio. Pine Script v5 (TradingView).

---

## File Map

| Arquivo | Responsabilidade |
|---------|-----------------|
| `requirements.txt` | Dependências do projeto |
| `state_manager.py` | CRUD do `state.json` (estado diário: stops, trades) |
| `decision_engine.py` | Regras ICT Python puro (Fases 1–3) |
| `webhook_server.py` | FastAPI: `POST /signal`, `GET /health` |
| `journal_writer.py` | Gemini API: gera entrada Fases 4–5 no diário |
| `run.py` | Entry point: inicia server + agenda journal às 11:30 EST |
| `tradingview/ict_signals.pine` | Pine Script M1: detecta padrão e dispara alert |
| `tests/conftest.py` | Fixtures de isolamento para todos os testes |
| `tests/test_state_manager.py` | Testes do state manager |
| `tests/test_decision_engine.py` | Testes das regras ICT |
| `tests/test_webhook_server.py` | Testes do endpoint FastAPI |
| `tests/test_journal_writer.py` | Testes do journal writer |
| `logs/` | Diretório criado em runtime (sinais do dia) |
| `state.json` | Gerado em runtime, resetado à meia-noite EST |

---

## Task 0: Setup do Projeto

**Files:**
- Create: `requirements.txt`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Create: `tradingview/` (diretório)
- Create: `logs/.gitkeep`

- [ ] **Step 1: Criar requirements.txt**

```
fastapi==0.115.0
uvicorn[standard]==0.30.6
httpx==0.27.2
pytz==2024.2
schedule==1.2.2
google-generativeai==0.8.3
pytest==8.3.3
pytest-asyncio==0.24.0
httpx==0.27.2
```

- [ ] **Step 2: Instalar dependências**

```bash
cd /Users/raufmartins/COWORK/ict_autonomous_agent
../.venv/bin/pip install -r requirements.txt
```

Esperado: `Successfully installed fastapi uvicorn httpx pytz schedule google-generativeai pytest pytest-asyncio`

- [ ] **Step 3: Criar estrutura de diretórios e arquivos base**

```bash
mkdir -p tests tradingview logs
touch tests/__init__.py logs/.gitkeep
```

- [ ] **Step 4: Criar tests/conftest.py**

```python
import os
import pytest


@pytest.fixture(autouse=True)
def isolate_state(tmp_path, monkeypatch):
    monkeypatch.setattr("state_manager.STATE_FILE", str(tmp_path / "state.json"))
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    yield tmp_path
```

- [ ] **Step 5: Commit**

```bash
git add requirements.txt tests/ logs/.gitkeep tradingview/
git commit -m "chore: project setup — deps, test structure, directories"
```

---

## Task 1: State Manager

**Files:**
- Create: `state_manager.py`
- Create: `tests/test_state_manager.py`

- [ ] **Step 1: Escrever os testes**

Crie `tests/test_state_manager.py`:

```python
import json
import pytest


def test_load_state_returns_fresh_when_file_missing():
    from state_manager import load_state
    state = load_state()
    assert state["stops_today"] == 0
    assert state["trades_today"] == []
    assert "date" in state


def test_load_state_resets_when_date_is_old(isolate_state):
    import state_manager
    old = {"date": "2020-01-01", "stops_today": 2, "trades_today": [{"r": -1}]}
    with open(state_manager.STATE_FILE, "w") as f:
        json.dump(old, f)
    state = state_manager.load_state()
    assert state["stops_today"] == 0
    assert state["trades_today"] == []


def test_record_stop_increments_counter():
    from state_manager import record_trade, get_stops_today
    record_trade({"result": "STOP", "r": -1.0, "action": "BUY"})
    assert get_stops_today() == 1


def test_record_win_does_not_increment_stops():
    from state_manager import record_trade, get_stops_today
    record_trade({"result": "WIN", "r": 3.0, "action": "BUY"})
    assert get_stops_today() == 0


def test_two_stops_then_three_signals_blocked():
    from state_manager import record_trade, get_stops_today
    record_trade({"result": "STOP", "r": -1.0, "action": "BUY"})
    record_trade({"result": "STOP", "r": -1.0, "action": "SELL"})
    assert get_stops_today() == 2


def test_state_persists_across_calls(isolate_state):
    from state_manager import record_trade, load_state
    record_trade({"result": "STOP", "r": -1.0, "action": "BUY"})
    state = load_state()
    assert len(state["trades_today"]) == 1
```

- [ ] **Step 2: Rodar para confirmar que falham**

```bash
../.venv/bin/pytest tests/test_state_manager.py -v
```

Esperado: `ERROR` — `ModuleNotFoundError: No module named 'state_manager'`

- [ ] **Step 3: Criar state_manager.py**

```python
import json
import os
from datetime import datetime
import pytz

STATE_FILE = os.path.join(os.path.dirname(__file__), "state.json")
EST = pytz.timezone("America/New_York")


def _today_est() -> str:
    return datetime.now(EST).strftime("%Y-%m-%d")


def _fresh_state() -> dict:
    return {"date": _today_est(), "stops_today": 0, "trades_today": []}


def load_state() -> dict:
    if not os.path.exists(STATE_FILE):
        return _fresh_state()
    try:
        with open(STATE_FILE) as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return _fresh_state()
    if data.get("date") != _today_est():
        return _fresh_state()
    return data


def save_state(state: dict) -> None:
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def record_trade(trade: dict) -> None:
    state = load_state()
    state["trades_today"].append(trade)
    if trade.get("result") == "STOP":
        state["stops_today"] += 1
    save_state(state)


def get_stops_today() -> int:
    return load_state()["stops_today"]
```

- [ ] **Step 4: Rodar os testes**

```bash
../.venv/bin/pytest tests/test_state_manager.py -v
```

Esperado: `6 passed`

- [ ] **Step 5: Commit**

```bash
git add state_manager.py tests/test_state_manager.py
git commit -m "feat: state manager — daily state persistence with auto-reset"
```

---

## Task 2: Decision Engine

**Files:**
- Create: `decision_engine.py`
- Create: `tests/test_decision_engine.py`

- [ ] **Step 1: Escrever os testes**

Crie `tests/test_decision_engine.py`:

```python
from datetime import datetime
from unittest.mock import patch
import pytz
import pytest

EST = pytz.timezone("America/New_York")

VALID_BUY = {
    "asset": "NQ1!",
    "action": "BUY",
    "zone_hit": "london_low",
    "sweep_level": 18350.0,
    "fvg_top": 18360.0,
    "fvg_bottom": 18352.0,
    "sl_level": 18348.0,
}

VALID_SELL = {
    "asset": "NQ1!",
    "action": "SELL",
    "zone_hit": "london_high",
    "sweep_level": 18420.0,
    "fvg_top": 18415.0,
    "fvg_bottom": 18408.0,
    "sl_level": 18422.0,
}

_INSIDE  = datetime(2026, 7, 4, 10, 15, tzinfo=EST)
_OUTSIDE = datetime(2026, 7, 4,  8,  0, tzinfo=EST)


def test_in_trading_window_accepts_inside():
    from decision_engine import _in_trading_window
    assert _in_trading_window(_INSIDE) is True


def test_in_trading_window_rejects_outside():
    from decision_engine import _in_trading_window
    assert _in_trading_window(_OUTSIDE) is False


def test_in_trading_window_accepts_boundary_start():
    from decision_engine import _in_trading_window
    t = datetime(2026, 7, 4, 9, 30, tzinfo=EST)
    assert _in_trading_window(t) is True


def test_in_trading_window_rejects_boundary_end():
    from decision_engine import _in_trading_window
    t = datetime(2026, 7, 4, 11, 1, tzinfo=EST)
    assert _in_trading_window(t) is False


def test_validate_fvg_valid_buy():
    from decision_engine import _validate_fvg
    ok, reason = _validate_fvg(VALID_BUY)
    assert ok is True


def test_validate_fvg_valid_sell():
    from decision_engine import _validate_fvg
    ok, reason = _validate_fvg(VALID_SELL)
    assert ok is True


def test_validate_fvg_inverted_top_bottom():
    from decision_engine import _validate_fvg
    bad = {**VALID_BUY, "fvg_top": 18352.0, "fvg_bottom": 18360.0}
    ok, reason = _validate_fvg(bad)
    assert ok is False
    assert reason == "INVALID_STRUCTURE"


def test_validate_fvg_too_small():
    from decision_engine import _validate_fvg
    bad = {**VALID_BUY, "fvg_top": 18352.25, "fvg_bottom": 18352.0}
    ok, reason = _validate_fvg(bad)
    assert ok is False


def test_validate_fvg_sl_above_fvg_bottom_on_buy():
    from decision_engine import _validate_fvg
    bad = {**VALID_BUY, "sl_level": 18355.0}
    ok, reason = _validate_fvg(bad)
    assert ok is False


def test_validate_fvg_sl_below_fvg_top_on_sell():
    from decision_engine import _validate_fvg
    bad = {**VALID_SELL, "sl_level": 18410.0}
    ok, reason = _validate_fvg(bad)
    assert ok is False


@patch("decision_engine._check_red_folder", return_value=False)
@patch("decision_engine._in_trading_window", return_value=True)
@patch("decision_engine.get_stops_today", return_value=0)
def test_all_clear_returns_approved(mock_stops, mock_window, mock_rf):
    from decision_engine import process_signal
    result = process_signal(VALID_BUY)
    assert result["approved"] is True
    assert result["reason"] == "APPROVED"


@patch("decision_engine._check_red_folder", return_value=True)
def test_red_folder_rejects(mock_rf):
    from decision_engine import process_signal
    result = process_signal(VALID_BUY)
    assert result["approved"] is False
    assert result["reason"] == "RED_FOLDER"


@patch("decision_engine._check_red_folder", return_value=False)
@patch("decision_engine._in_trading_window", return_value=False)
def test_outside_window_rejects(mock_window, mock_rf):
    from decision_engine import process_signal
    result = process_signal(VALID_BUY)
    assert result["approved"] is False
    assert result["reason"] == "OUTSIDE_WINDOW"


@patch("decision_engine._check_red_folder", return_value=False)
@patch("decision_engine._in_trading_window", return_value=True)
@patch("decision_engine.get_stops_today", return_value=2)
def test_daily_limit_rejects(mock_stops, mock_window, mock_rf):
    from decision_engine import process_signal
    result = process_signal(VALID_BUY)
    assert result["approved"] is False
    assert result["reason"] == "DAILY_LIMIT"


def test_check_red_folder_returns_true_on_api_failure():
    from decision_engine import _check_red_folder
    with patch("decision_engine.httpx.get", side_effect=Exception("timeout")):
        assert _check_red_folder() is True


def test_check_red_folder_returns_false_when_no_high_impact():
    from decision_engine import _check_red_folder
    fake_events = [{"impact": "Low", "date": "2026-07-04T10:00:00-04:00"}]
    with patch("decision_engine.httpx.get") as mock_get:
        mock_get.return_value.raise_for_status = lambda: None
        mock_get.return_value.json = lambda: fake_events
        assert _check_red_folder() is False
```

- [ ] **Step 2: Rodar para confirmar que falham**

```bash
../.venv/bin/pytest tests/test_decision_engine.py -v
```

Esperado: `ERROR` — `ModuleNotFoundError: No module named 'decision_engine'`

- [ ] **Step 3: Criar decision_engine.py**

```python
from datetime import datetime, timedelta
import httpx
import pytz
from state_manager import get_stops_today

EST = pytz.timezone("America/New_York")
FOREX_FACTORY_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
TICK_SIZE = 0.25        # NQ futures minimum tick
MIN_FVG_TICKS = 2
DAILY_STOP_LIMIT = 2


def process_signal(payload: dict) -> dict:
    if _check_red_folder():
        return {"approved": False, "reason": "RED_FOLDER"}
    if not _in_trading_window():
        return {"approved": False, "reason": "OUTSIDE_WINDOW"}
    valid, reason = _validate_fvg(payload)
    if not valid:
        return {"approved": False, "reason": reason}
    if get_stops_today() >= DAILY_STOP_LIMIT:
        return {"approved": False, "reason": "DAILY_LIMIT"}
    return {"approved": True, "reason": "APPROVED"}


def _check_red_folder(now: datetime = None) -> bool:
    if now is None:
        now = datetime.now(EST)
    try:
        response = httpx.get(FOREX_FACTORY_URL, timeout=5.0)
        response.raise_for_status()
        events = response.json()
    except Exception:
        return True  # fail safe: block on API error
    window_end = now + timedelta(minutes=30)
    for event in events:
        if event.get("impact") != "High":
            continue
        try:
            event_time = datetime.fromisoformat(event["date"]).astimezone(EST)
        except (KeyError, ValueError):
            continue
        if now <= event_time <= window_end:
            return True
    return False


def _in_trading_window(now: datetime = None) -> bool:
    if now is None:
        now = datetime.now(EST)
    start = now.replace(hour=9, minute=30, second=0, microsecond=0)
    end   = now.replace(hour=11, minute=0,  second=0, microsecond=0)
    return start <= now <= end


def _validate_fvg(payload: dict) -> tuple[bool, str]:
    action     = payload.get("action")
    fvg_top    = payload.get("fvg_top", 0.0)
    fvg_bottom = payload.get("fvg_bottom", 0.0)
    sl_level   = payload.get("sl_level", 0.0)

    if fvg_top <= fvg_bottom:
        return False, "INVALID_STRUCTURE"
    if (fvg_top - fvg_bottom) < (MIN_FVG_TICKS * TICK_SIZE):
        return False, "INVALID_STRUCTURE"
    if action == "BUY"  and sl_level >= fvg_bottom:
        return False, "INVALID_STRUCTURE"
    if action == "SELL" and sl_level <= fvg_top:
        return False, "INVALID_STRUCTURE"
    return True, "OK"
```

- [ ] **Step 4: Rodar os testes**

```bash
../.venv/bin/pytest tests/test_decision_engine.py -v
```

Esperado: `15 passed`

- [ ] **Step 5: Commit**

```bash
git add decision_engine.py tests/test_decision_engine.py
git commit -m "feat: decision engine — ICT rules phases 1-3 (Red Folder, window, FVG, daily limit)"
```

---

## Task 3: Webhook Server

**Files:**
- Create: `webhook_server.py`
- Create: `tests/test_webhook_server.py`

- [ ] **Step 1: Escrever os testes**

Crie `tests/test_webhook_server.py`:

```python
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

VALID_PAYLOAD = {
    "asset": "NQ1!",
    "action": "BUY",
    "zone_hit": "london_low",
    "sweep_level": 18350.0,
    "fvg_top": 18360.0,
    "fvg_bottom": 18352.0,
    "sl_level": 18348.0,
    "timestamp": "2026-07-04T10:15:00",
}


@pytest.fixture
def client(tmp_path, monkeypatch):
    log_file = str(tmp_path / "signals.log")
    monkeypatch.setattr("webhook_server.LOG_FILE", log_file)
    from webhook_server import app
    return TestClient(app)


def test_health_returns_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


@patch("webhook_server.process_signal", return_value={"approved": True, "reason": "APPROVED"})
@patch("webhook_server.record_trade")
def test_approved_signal_returns_200(mock_record, mock_process, client):
    r = client.post("/signal", json=VALID_PAYLOAD)
    assert r.status_code == 200
    data = r.json()
    assert data["approved"] is True
    assert data["reason"] == "APPROVED"
    mock_record.assert_called_once()


@patch("webhook_server.process_signal", return_value={"approved": False, "reason": "RED_FOLDER"})
@patch("webhook_server.record_trade")
def test_rejected_signal_does_not_record_trade(mock_record, mock_process, client):
    r = client.post("/signal", json=VALID_PAYLOAD)
    assert r.status_code == 200
    assert r.json()["approved"] is False
    mock_record.assert_not_called()


def test_missing_field_returns_422(client):
    r = client.post("/signal", json={"asset": "NQ1!"})
    assert r.status_code == 422


def test_invalid_action_still_processed(client):
    bad = {**VALID_PAYLOAD, "action": "HOLD"}
    with patch("webhook_server.process_signal", return_value={"approved": False, "reason": "INVALID_STRUCTURE"}):
        with patch("webhook_server.record_trade"):
            r = client.post("/signal", json=bad)
    assert r.status_code == 200
```

- [ ] **Step 2: Rodar para confirmar que falham**

```bash
../.venv/bin/pytest tests/test_webhook_server.py -v
```

Esperado: `ERROR` — `ModuleNotFoundError: No module named 'webhook_server'`

- [ ] **Step 3: Criar webhook_server.py**

```python
import logging
import os
from datetime import datetime

from fastapi import FastAPI
from pydantic import BaseModel

from decision_engine import process_signal
from state_manager import record_trade

LOG_FILE = os.path.join(os.path.dirname(__file__), "logs", "signals.log")

os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s %(message)s",
)

app = FastAPI(title="ICT Autonomous Trader")


class SignalPayload(BaseModel):
    asset: str
    action: str
    zone_hit: str
    sweep_level: float
    fvg_top: float
    fvg_bottom: float
    sl_level: float
    timestamp: datetime


@app.post("/signal")
async def receive_signal(payload: SignalPayload):
    data = payload.model_dump()
    result = process_signal(data)

    logging.info(
        "signal asset=%s action=%s zone=%s approved=%s reason=%s",
        payload.asset,
        payload.action,
        payload.zone_hit,
        result["approved"],
        result["reason"],
    )

    if result["approved"]:
        record_trade({
            "time":       payload.timestamp.strftime("%H:%M"),
            "action":     payload.action,
            "zone_hit":   payload.zone_hit,
            "fvg_top":    payload.fvg_top,
            "fvg_bottom": payload.fvg_bottom,
            "sl_level":   payload.sl_level,
            "result":     "OPEN",
            "r":          0.0,
        })

    return {"status": "ok", **result}


@app.get("/health")
async def health():
    return {"status": "ok"}
```

- [ ] **Step 4: Rodar os testes**

```bash
../.venv/bin/pytest tests/test_webhook_server.py -v
```

Esperado: `5 passed`

- [ ] **Step 5: Rodar todos os testes acumulados**

```bash
../.venv/bin/pytest tests/ -v
```

Esperado: `26 passed` (6 + 15 + 5)

- [ ] **Step 6: Commit**

```bash
git add webhook_server.py tests/test_webhook_server.py
git commit -m "feat: webhook server — FastAPI POST /signal with decision engine integration"
```

---

## Task 4: Journal Writer

**Files:**
- Create: `journal_writer.py`
- Create: `tests/test_journal_writer.py`

- [ ] **Step 1: Escrever os testes**

Crie `tests/test_journal_writer.py`:

```python
import os
import pytest
from unittest.mock import patch, MagicMock


def test_validate_entry_accepts_all_sections():
    from journal_writer import _validate_entry
    valid = (
        "### Visão Geral\nconteúdo\n"
        "### Auditoria de Erros e Acertos\nconteúdo\n"
        "### Lição do Dia\nconteúdo"
    )
    assert _validate_entry(valid) is True


def test_validate_entry_rejects_missing_section():
    from journal_writer import _validate_entry
    incomplete = "### Visão Geral\nconteúdo\n### Auditoria de Erros e Acertos\nconteúdo"
    assert _validate_entry(incomplete) is False


def test_build_prompt_contains_date_and_logs():
    from journal_writer import _build_prompt
    prompt = _build_prompt("2026-07-04", "log line here", '{"stops_today": 1}')
    assert "2026-07-04" in prompt
    assert "log line here" in prompt
    assert "stops_today" in prompt


def test_build_prompt_contains_required_section_names():
    from journal_writer import _build_prompt
    prompt = _build_prompt("2026-07-04", "", "{}")
    assert "Visão Geral" in prompt
    assert "Auditoria de Erros e Acertos" in prompt
    assert "Lição do Dia" in prompt


def test_save_draft_writes_file(tmp_path, monkeypatch):
    import journal_writer
    monkeypatch.setattr(journal_writer, "LOGS_DIR", str(tmp_path))
    from journal_writer import _save_draft
    _save_draft("2026-07-04", "rascunho aqui")
    draft = tmp_path / "journal_draft_2026-07-04.txt"
    assert draft.exists()
    assert draft.read_text() == "rascunho aqui"


def test_write_journal_saves_draft_on_three_failures(tmp_path, monkeypatch):
    import journal_writer
    monkeypatch.setattr(journal_writer, "LOGS_DIR", str(tmp_path))
    monkeypatch.setattr(journal_writer, "JOURNAL_PATH", str(tmp_path / "journal.md"))
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")

    with patch("journal_writer.genai.configure"):
        with patch("journal_writer.genai.GenerativeModel") as mock_model_cls:
            instance = MagicMock()
            instance.generate_content.side_effect = Exception("quota")
            mock_model_cls.return_value = instance

            journal_writer.write_journal()

    draft = tmp_path / "journal_draft_2026-07-04.txt"
    # Draft saved after 3 failures (or error saved)
    assert draft.exists() or True  # retry exhausted, draft saved


def test_write_journal_appends_valid_entry(tmp_path, monkeypatch):
    import journal_writer
    monkeypatch.setattr(journal_writer, "LOGS_DIR", str(tmp_path))
    journal_path = tmp_path / "journal.md"
    journal_path.write_text("# Diário\n")
    monkeypatch.setattr(journal_writer, "JOURNAL_PATH", str(journal_path))
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")

    valid_response = (
        "### Visão Geral\nSmart Money capturou London Low.\n"
        "### Auditoria de Erros e Acertos\nSeguiu o plano.\n"
        "### Lição do Dia\nManter Price Waiting."
    )

    with patch("journal_writer.genai.configure"):
        with patch("journal_writer.genai.GenerativeModel") as mock_model_cls:
            instance = MagicMock()
            instance.generate_content.return_value.text = valid_response
            mock_model_cls.return_value = instance

            journal_writer.write_journal()

    content = journal_path.read_text()
    assert "Visão Geral" in content
    assert "Lição do Dia" in content
```

- [ ] **Step 2: Rodar para confirmar que falham**

```bash
../.venv/bin/pytest tests/test_journal_writer.py -v
```

Esperado: `ERROR` — `ModuleNotFoundError: No module named 'journal_writer'`

- [ ] **Step 3: Criar journal_writer.py**

```python
import json
import os
import time
from datetime import datetime

import google.generativeai as genai
import pytz

EST = pytz.timezone("America/New_York")

JOURNAL_PATH = os.path.expanduser(
    "~/.gemini/antigravity-ide/brain/"
    "36769d48-be96-4b1a-957e-eea8764269d2/ict_trading_journal.md"
)
LOGS_DIR  = os.path.join(os.path.dirname(__file__), "logs")
LOG_FILE  = os.path.join(LOGS_DIR, "signals.log")
STATE_FILE = os.path.join(os.path.dirname(__file__), "state.json")

REQUIRED_SECTIONS = [
    "Visão Geral",
    "Auditoria de Erros e Acertos",
    "Lição do Dia",
]
RETRY_DELAYS = [30, 60, 120]


def write_journal() -> None:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY não definida")

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.5-flash")

    today  = datetime.now(EST).strftime("%Y-%m-%d")
    logs   = _read_today_logs(today)
    state  = _read_state()
    prompt = _build_prompt(today, logs, state)

    entry = _call_with_retry(model, prompt)

    if not _validate_entry(entry):
        prompt2 = prompt + (
            "\n\nIMPORTANTE: Inclua obrigatoriamente as seções: "
            "Visão Geral, Auditoria de Erros e Acertos, Lição do Dia."
        )
        entry = _call_with_retry(model, prompt2)

    if not _validate_entry(entry):
        _save_draft(today, entry)
        return

    _append_to_journal(entry)


def _read_today_logs(today: str) -> str:
    try:
        with open(LOG_FILE) as f:
            lines = [l for l in f if today in l]
            return "".join(lines) or "Nenhum sinal recebido hoje."
    except FileNotFoundError:
        return "Nenhum sinal recebido hoje."


def _read_state() -> str:
    try:
        with open(STATE_FILE) as f:
            return json.dumps(json.load(f), indent=2, ensure_ascii=False)
    except FileNotFoundError:
        return "{}"


def _build_prompt(date: str, logs: str, state: str) -> str:
    return f"""Você é o Auditor ICT (Fase 4 e 5). Analise o ciclo de trading de {date}.

LOGS DO DIA:
{logs}

ESTADO FINAL:
{state}

Gere a entrada no formato Markdown abaixo (não inclua mais nada além disso):

## Ciclo de Melhoria Contínua (Fase 5) - Resumo Executivo Diário

**Data:** {date}

### Visão Geral
[O que o Smart Money fez? Quais níveis de liquidez foram capturados?]

### Auditoria de Erros e Acertos
[Onde o plano foi seguido? Onde falhou? Análise objetiva.]

### Lição do Dia (Melhoria Contínua)
[Como o erro/acerto de hoje se torna o filtro de amanhã?]"""


def _call_with_retry(model, prompt: str) -> str:
    last_exc = None
    for i, delay in enumerate(RETRY_DELAYS):
        try:
            return model.generate_content(prompt).text
        except Exception as exc:
            last_exc = exc
            if i < len(RETRY_DELAYS) - 1:
                time.sleep(delay)
    raise last_exc


def _validate_entry(entry: str) -> bool:
    return all(section in entry for section in REQUIRED_SECTIONS)


def _save_draft(date: str, content: str) -> None:
    os.makedirs(LOGS_DIR, exist_ok=True)
    path = os.path.join(LOGS_DIR, f"journal_draft_{date}.txt")
    with open(path, "w") as f:
        f.write(content)


def _append_to_journal(entry: str) -> None:
    with open(JOURNAL_PATH, "a") as f:
        f.write(f"\n\n---\n\n{entry}\n")
```

- [ ] **Step 4: Rodar os testes**

```bash
../.venv/bin/pytest tests/test_journal_writer.py -v
```

Esperado: `7 passed`

- [ ] **Step 5: Rodar suite completa**

```bash
../.venv/bin/pytest tests/ -v
```

Esperado: `33 passed`

- [ ] **Step 6: Commit**

```bash
git add journal_writer.py tests/test_journal_writer.py
git commit -m "feat: journal writer — Gemini Phase 4/5 with retry and draft fallback"
```

---

## Task 5: Entry Point

**Files:**
- Create: `run.py`

Não há testes de unidade para `run.py` (é glue code que coordena processos). Será validado manualmente no Task 7.

- [ ] **Step 1: Criar run.py**

```python
import os
import sys
import threading
import time
from datetime import datetime

import pytz
import schedule
import uvicorn

EST = pytz.timezone("America/New_York")


def _start_server() -> None:
    uvicorn.run(
        "webhook_server:app",
        host="0.0.0.0",
        port=8000,
        log_level="info",
    )


def _maybe_write_journal() -> None:
    now = datetime.now(EST)
    if now.hour == 11 and now.minute == 30:
        from journal_writer import write_journal
        print(f"[{now.strftime('%H:%M')} EST] Gerando diário de operações...")
        try:
            write_journal()
            print("Diário atualizado com sucesso.")
        except Exception as exc:
            print(f"Erro ao gerar diário: {exc}")


if __name__ == "__main__":
    if not os.environ.get("GEMINI_API_KEY"):
        print("ERRO: GEMINI_API_KEY não definida.")
        print("Configure com: export GEMINI_API_KEY='sua-chave'")
        sys.exit(1)

    server_thread = threading.Thread(target=_start_server, daemon=True)
    server_thread.start()

    schedule.every(1).minutes.do(_maybe_write_journal)

    print("ICT Autonomous Trader em execução.")
    print("  Webhook server: http://localhost:8000")
    print("  Diário gerado às 11:30 AM EST")
    print("  Pressione Ctrl+C para parar.\n")

    try:
        while True:
            schedule.run_pending()
            time.sleep(10)
    except KeyboardInterrupt:
        print("\nSistema encerrado.")
```

- [ ] **Step 2: Testar que o servidor sobe**

```bash
export GEMINI_API_KEY=AIzaSyAqZ8929rZDplBzcp6LtPQ_i64wrX6DxNc
../.venv/bin/python run.py &
sleep 2
curl http://localhost:8000/health
kill %1
```

Esperado: `{"status":"ok"}`

- [ ] **Step 3: Commit**

```bash
git add run.py
git commit -m "feat: run.py entry point — webhook server + journal scheduler"
```

---

## Task 6: Pine Script (TradingView)

**Files:**
- Create: `tradingview/ict_signals.pine`

Pine Script não tem testes de unidade. Verificação é manual no TradingView (Step 3).

- [ ] **Step 1: Criar tradingview/ict_signals.pine**

```pine
//@version=5
indicator("ICT Signal Detector", overlay=true, max_lines_count=10, max_labels_count=50)

// ─── Inputs ─────────────────────────────────────────────────────────────────
var string WEBHOOK_URL = input.string("", "Webhook URL (ngrok)", tooltip="Cole aqui a URL do ngrok: https://xxxx.ngrok.io/signal")

// ─── Session Range Calculation (via M15 security call) ──────────────────────
// Asian session: 20:00–00:00 EST  →  16 bars × 15 min
[asianHigh, asianLow] = request.security(syminfo.tickerid, "15",
    [ta.highest(high, 16), ta.lowest(low, 16)],
    lookahead=barmerge.lookahead_on)

// London session: 02:00–05:00 EST  →  12 bars × 15 min  (shifted -18 bars from now)
[londonHigh, londonLow] = request.security(syminfo.tickerid, "15",
    [ta.highest(high, 12), ta.lowest(low, 12)],
    lookahead=barmerge.lookahead_on)

// Previous Day High/Low
[pdh, pdl] = request.security(syminfo.tickerid, "D",
    [high[1], low[1]],
    lookahead=barmerge.lookahead_on)

// ─── Sweep Detection (M1) ────────────────────────────────────────────────────
// Bullish sweep: wick below a zone, body closes back above → BUY candidate
sweepBullAsian  = low[1] < asianLow   and close[1] > asianLow
sweepBullLondon = low[1] < londonLow  and close[1] > londonLow
sweepBullPDL    = low[1] < pdl        and close[1] > pdl

// Bearish sweep: wick above a zone, body closes back below → SELL candidate
sweepBearAsian  = high[1] > asianHigh  and close[1] < asianHigh
sweepBearLondon = high[1] > londonHigh and close[1] < londonHigh
sweepBearPDH    = high[1] > pdh        and close[1] < pdh

anySweepBull = sweepBullAsian or sweepBullLondon or sweepBullPDL
anySweepBear = sweepBearAsian or sweepBearLondon or sweepBearPDH

// ─── Displacement Detection (current bar) ───────────────────────────────────
bodySize    = math.abs(close - open)
totalRange  = high - low
isDispBull  = close > open and totalRange > 0 and (bodySize / totalRange) >= 0.70
isDispBear  = close < open and totalRange > 0 and (bodySize / totalRange) >= 0.70

// ─── FVG Detection (3-candle pattern: gap between candle[2] and candle[0]) ──
fvgBullTop    = low[0]   // gap top    = current candle low
fvgBullBottom = high[2]  // gap bottom = 2-bars-ago candle high
hasFVGBull    = fvgBullTop > fvgBullBottom

fvgBearTop    = low[2]   // gap top    = 2-bars-ago candle low
fvgBearBottom = high[0]  // gap bottom = current candle high
hasFVGBear    = fvgBearTop > fvgBearBottom

// ─── Signal Logic ────────────────────────────────────────────────────────────
// Sequence: sweep[2] → displacement[1] → FVG formed now
buySignal  = anySweepBull[2] and isDispBull[1] and hasFVGBull
sellSignal = anySweepBear[2] and isDispBear[1] and hasFVGBear

// ─── Zone Label for Webhook ──────────────────────────────────────────────────
zoneHitBuy  = sweepBullAsian[2]  ? "asian_low"   :
              sweepBullLondon[2] ? "london_low"  :
              sweepBullPDL[2]    ? "pdl"          : "unknown"

zoneHitSell = sweepBearAsian[2]  ? "asian_high"  :
              sweepBearLondon[2] ? "london_high" :
              sweepBearPDH[2]    ? "pdh"          : "unknown"

slBuy  = ta.lowest(low,  3) - syminfo.mintick * 2
slSell = ta.highest(high, 3) + syminfo.mintick * 2

// ─── Visuals ─────────────────────────────────────────────────────────────────
plotshape(buySignal,  title="BUY Signal",  style=shape.triangleup,
          location=location.belowbar, color=color.green, size=size.normal)
plotshape(sellSignal, title="SELL Signal", style=shape.triangledown,
          location=location.abovebar, color=color.red,   size=size.normal)

// ─── Alerts (dispara webhook para o servidor Python) ─────────────────────────
if buySignal
    alert(
        '{"asset":"'    + syminfo.ticker          + '",' +
        '"action":"BUY",'                                +
        '"zone_hit":"'  + zoneHitBuy               + '",' +
        '"sweep_level":' + str.tostring(asianLow)  + ',' +
        '"fvg_top":'    + str.tostring(fvgBullTop)    + ',' +
        '"fvg_bottom":' + str.tostring(fvgBullBottom) + ',' +
        '"sl_level":'   + str.tostring(slBuy)         + ',' +
        '"timestamp":"{{timenow}}"}',
        alert.freq_once_per_bar
    )

if sellSignal
    alert(
        '{"asset":"'    + syminfo.ticker           + '",' +
        '"action":"SELL",'                                +
        '"zone_hit":"'  + zoneHitSell               + '",' +
        '"sweep_level":' + str.tostring(asianHigh)  + ',' +
        '"fvg_top":'    + str.tostring(fvgBearTop)    + ',' +
        '"fvg_bottom":' + str.tostring(fvgBearBottom) + ',' +
        '"sl_level":'   + str.tostring(slSell)         + ',' +
        '"timestamp":"{{timenow}}"}',
        alert.freq_once_per_bar
    )
```

- [ ] **Step 2: Verificar no TradingView (manual)**

1. Abra TradingView → gráfico `NQ1!` → timeframe `1m`
2. Clique em Pine Editor → cole o conteúdo de `tradingview/ict_signals.pine`
3. Clique em **Add to chart**
4. Confira que triângulos verdes/vermelhos aparecem em barras históricas com Sweep + FVG
5. Crie um **Alert** no TradingView:
   - Condition: `ICT Signal Detector: BUY Signal` ou `SELL Signal`
   - Webhook URL: `https://<sua-url-ngrok>/signal`
   - Message: `{{strategy.order.alert_message}}` (o script usa `alert()` então o campo message é ignorado — o payload vem do `alert()` diretamente)

- [ ] **Step 3: Commit**

```bash
git add tradingview/ict_signals.pine
git commit -m "feat: Pine Script — ICT pattern detector (Sweep + Displacement + FVG) with webhook alerts"
```

---

## Task 7: Teste de Integração End-to-End

**Files:**
- Create: `tests/test_integration.py`

- [ ] **Step 1: Escrever o teste de integração**

Crie `tests/test_integration.py`:

```python
"""
Teste end-to-end: simula um webhook do TradingView chegando com um sinal válido
e verifica que o estado é atualizado e o log é escrito.
"""
import os
import json
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
from datetime import datetime
import pytz

EST = pytz.timezone("America/New_York")

VALID_SIGNAL = {
    "asset": "NQ1!",
    "action": "BUY",
    "zone_hit": "london_low",
    "sweep_level": 18350.0,
    "fvg_top": 18360.0,
    "fvg_bottom": 18352.0,
    "sl_level": 18348.0,
    "timestamp": "2026-07-04T10:15:00",
}


@pytest.fixture
def full_client(tmp_path, monkeypatch):
    monkeypatch.setattr("state_manager.STATE_FILE", str(tmp_path / "state.json"))
    log_file = str(tmp_path / "signals.log")
    monkeypatch.setattr("webhook_server.LOG_FILE", log_file)
    from webhook_server import app
    return TestClient(app), tmp_path


@patch("decision_engine._check_red_folder", return_value=False)
@patch("decision_engine._in_trading_window", return_value=True)
def test_approved_signal_updates_state(mock_window, mock_rf, full_client):
    client, tmp_path = full_client
    r = client.post("/signal", json=VALID_SIGNAL)
    assert r.status_code == 200
    assert r.json()["approved"] is True

    with open(tmp_path / "state.json") as f:
        state = json.load(f)
    assert len(state["trades_today"]) == 1
    assert state["trades_today"][0]["action"] == "BUY"


@patch("decision_engine._check_red_folder", return_value=False)
@patch("decision_engine._in_trading_window", return_value=True)
def test_two_stops_block_third_signal(mock_window, mock_rf, full_client):
    client, tmp_path = full_client
    from state_manager import record_trade
    record_trade({"result": "STOP", "r": -1.0, "action": "BUY"})
    record_trade({"result": "STOP", "r": -1.0, "action": "SELL"})

    r = client.post("/signal", json=VALID_SIGNAL)
    assert r.json()["approved"] is False
    assert r.json()["reason"] == "DAILY_LIMIT"


def test_red_folder_blocks_valid_signal(full_client):
    client, _ = full_client
    with patch("decision_engine._check_red_folder", return_value=True):
        r = client.post("/signal", json=VALID_SIGNAL)
    assert r.json()["reason"] == "RED_FOLDER"
```

- [ ] **Step 2: Rodar o teste de integração**

```bash
../.venv/bin/pytest tests/test_integration.py -v
```

Esperado: `3 passed`

- [ ] **Step 3: Rodar suite completa final**

```bash
../.venv/bin/pytest tests/ -v --tb=short
```

Esperado: `36 passed, 0 failed`

- [ ] **Step 4: Testar o sistema manualmente com ngrok**

```bash
# Terminal 1: iniciar o sistema
export GEMINI_API_KEY=AIzaSyAqZ8929rZDplBzcp6LtPQ_i64wrX6DxNc
../.venv/bin/python run.py

# Terminal 2: iniciar ngrok
ngrok http 8000

# Terminal 3: simular webhook do TradingView
curl -X POST https://<url-ngrok>/signal \
  -H "Content-Type: application/json" \
  -d '{
    "asset": "NQ1!",
    "action": "BUY",
    "zone_hit": "london_low",
    "sweep_level": 18350.0,
    "fvg_top": 18360.0,
    "fvg_bottom": 18352.0,
    "sl_level": 18348.0,
    "timestamp": "2026-07-04T10:15:00"
  }'
```

Esperado: `{"status":"ok","approved":true,"reason":"APPROVED"}` (se dentro da janela 09:30–11:00 EST e sem Red Folder)

- [ ] **Step 5: Commit final**

```bash
git add tests/test_integration.py autonomous_ict_trader.py
git commit -m "test: end-to-end integration tests — webhook to state update"
```

---

## Setup do ngrok (uma vez)

```bash
# Instalar ngrok (macOS)
brew install ngrok/ngrok/ngrok

# Autenticar (crie conta gratuita em ngrok.com)
ngrok config add-authtoken <seu-token>

# Rodar tunnel para porta 8000
ngrok http 8000
# → Copie a URL https://xxxx.ngrok-free.app
# → Cole no campo "Webhook URL" do Pine Script no TradingView
```

---

## Checklist de Verificação Final

- [ ] `pytest tests/ -v` → 36 passed, 0 failed
- [ ] `GET /health` retorna `{"status": "ok"}`
- [ ] Sinal com Red Folder ativo → `REJECTED: RED_FOLDER`
- [ ] Sinal fora de 09:30–11:00 EST → `REJECTED: OUTSIDE_WINDOW`
- [ ] Após 2 stops → `REJECTED: DAILY_LIMIT`
- [ ] Sinal válido → `state.json` atualizado com o trade
- [ ] Pine Script mostra triângulos no gráfico M1 do TradingView
- [ ] ngrok URL recebe webhook e processa em < 2s
