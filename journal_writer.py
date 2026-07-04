import json
import os
import time
from datetime import datetime

import google.generativeai as genai
import pytz

EST = pytz.timezone("America/New_York")

_DEFAULT_JOURNAL = os.path.expanduser(
    "~/.gemini/antigravity-ide/brain/"
    "36769d48-be96-4b1a-957e-eea8764269d2/ict_trading_journal.md"
)
JOURNAL_PATH = os.environ.get("ICT_JOURNAL_PATH", _DEFAULT_JOURNAL)
LOGS_DIR  = os.path.join(os.path.dirname(__file__), "logs")
LOG_FILE  = os.path.join(LOGS_DIR, "signals.log")
STATE_FILE = os.path.join(os.path.dirname(__file__), "state.json")

REQUIRED_SECTIONS = [
    "Visão Geral",
    "Auditoria de Erros e Acertos",
    "Lição do Dia",
]
RETRY_DELAYS = [30, 60]


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

    try:
        entry = _call_with_retry(model, prompt)
    except Exception as exc:
        _save_draft(today, f"[ERRO: {exc}]")
        return

    if not _validate_entry(entry):
        prompt2 = prompt + (
            "\n\nIMPORTANTE: Inclua obrigatoriamente as seções: "
            "Visão Geral, Auditoria de Erros e Acertos, Lição do Dia."
        )
        try:
            entry = _call_with_retry(model, prompt2)
        except Exception as exc:
            _save_draft(today, f"[ERRO na re-tentativa: {exc}]\n\n{entry}")
            return

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
    if not os.path.exists(STATE_FILE):
        return "{}"
    try:
        with open(STATE_FILE) as f:
            return json.dumps(json.load(f), ensure_ascii=False, indent=2)
    except (json.JSONDecodeError, IOError):
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
    os.makedirs(os.path.dirname(JOURNAL_PATH), exist_ok=True)
    with open(JOURNAL_PATH, "a") as f:
        f.write(f"\n\n---\n\n{entry}\n")
