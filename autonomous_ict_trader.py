"""
Autonomous ICT Trader — Gemini Multi-Agent Auditor.

Uses google-generativeai with automatic function calling.
Each signal that passes decision_engine filters is evaluated here
by Gemini working through 3 phases (playbooks) before approving execution.
"""
import asyncio
import logging
import os
from datetime import datetime

try:
    import google.generativeai as genai
    _GENAI_AVAILABLE = True
except ImportError:
    genai = None
    _GENAI_AVAILABLE = False

from decision_engine import _check_red_folder, get_current_session
from state_manager import record_trade, get_recent_trades
from asset_params import get_asset_params
from rag_store import query_similar_wins

logger = logging.getLogger("ict_trader")

_PLAYBOOKS_DIR = os.path.join(os.path.dirname(__file__), "docs", "playbooks")
_MODEL = "gemini-2.5-flash"


# ── Knowledge Base Tools ──────────────────────────────────────────────────────

def _read_file(filename: str) -> str:
    try:
        with open(os.path.join(_PLAYBOOKS_DIR, filename)) as f:
            return f.read()
    except Exception as e:
        return f"Arquivo não encontrado: {e}"


def read_phase1_knowledge() -> str:
    """Lê as instruções da Fase 1: Mapeamento de Liquidez de Tempo."""
    return _read_file("ict_fase1_playbook.md")


def read_phase2_knowledge() -> str:
    """Lê as regras de ouro da Fase 2: Gatilho Cirúrgico."""
    return _read_file("ict_fase2_playbook.md")


def read_phase3_knowledge() -> str:
    """Lê os parâmetros da Fase 3: Gestão de Risco e Price Waiting."""
    return _read_file("ict_fase3_playbook.md")


def read_journal_status() -> str:
    """Lê o Diário de Operações para contexto do desempenho diário."""
    return _read_file("ict_trading_journal.md")


def get_economic_calendar_status() -> str:
    """Verifica Red Folders via Forex Factory na janela atual de ±30 min."""
    if _check_red_folder():
        return "BLOQUEIO: Red Folder detectado na janela atual. Operação proibida."
    return "Calendário limpo. Sem eventos de alto impacto na janela de ±30 min."


def execute_limit_order(action: str, limit_price: float, stop_loss: float) -> str:
    """
    Dispara uma ordem limite na corretora.
    Em produção: integra via MCP com MetaTrader ou API da corretora.
    """
    logger.info("ORDER action=%s limit=%.5f sl=%.5f", action, limit_price, stop_loss)
    return f"[PAPER] Ordem {action} limit={limit_price:.5f} SL={stop_loss:.5f} registrada."


def log_approved_trade(asset: str, action: str, fvg_entry: float,
                       stop_loss: float, justification: str) -> str:
    """
    Atualiza o trade no State Manager para OPEN com a justificativa da IA.
    Chame somente quando TODOS os critérios das 3 fases estiverem aprovados.
    """
    try:
        record_trade({
            "time": datetime.now().strftime("%H:%M"),
            "action": action,
            "asset": asset,
            "fvg_entry": fvg_entry,
            "sl_level": stop_loss,
            "justification": justification,
            "result": "OPEN",
            "r": 0.0,
        })
        return "Trade atualizado para OPEN no State Manager."
    except Exception as e:
        return f"Erro ao atualizar trade: {e}"


# ── Orchestrator ──────────────────────────────────────────────────────────────

_TOOLS = [
    read_phase1_knowledge,
    read_phase2_knowledge,
    read_phase3_knowledge,
    read_journal_status,
    get_economic_calendar_status,
    execute_limit_order,
    log_approved_trade,
]


def _build_prompt(payload: dict) -> str:
    asset = payload.get("asset", "UNKNOWN")
    params = get_asset_params(asset)
    session = get_current_session()
    daily_bias = payload.get("daily_bias", "NÃO INFORMADO")
    recent_trades = get_recent_trades(asset, limit=3)
    
    memory_str = "Sem registros recentes hoje."
    if recent_trades:
        memory_str = "\n".join([
            f"  - Trade às {t.get('time')} | Ação: {t.get('action')} | Resultado: {t.get('result')}" 
            for t in recent_trades
        ])

    target = payload.get("target_level")
    entry  = round((payload.get("fvg_top", 0) + payload.get("fvg_bottom", 0)) / 2, 8)
    sl     = payload.get("sl_level", 0)
    rr     = round(abs(target - entry) / abs(entry - sl), 2) if target and sl and entry != sl else "N/A"

    # RAG — 3 setups WIN mais similares da memória histórica
    similar = query_similar_wins(payload, n=3)
    if similar:
        rag_str = "\n".join([
            f"  [{i+1}] {t.get('asset')} {t.get('action')} | Zona: {t.get('zone_hit','')} | "
            f"Sessão: {t.get('session','')} | R: {t.get('r','')} | "
            f"Justificativa: {t.get('justification','')[:180]}"
            for i, t in enumerate(similar)
        ])
    else:
        rag_str = "  Banco de dados histórico ainda vazio. Primeiros trades WIN serão armazenados automaticamente."

    return f"""Você é o Auditor Autônomo ICT. Um sinal passou pelos filtros mecânicos e aguarda sua aprovação final.

SINAL DETECTADO:
  Ativo:        {asset}
  Ação:         {payload.get("action")}
  Zona:         {payload.get("zone_hit")}
  Sweep Level:  {payload.get("sweep_level")}
  FVG Topo:     {payload.get("fvg_top")}
  FVG Fundo:    {payload.get("fvg_bottom")}
  Entrada (mid):{entry}
  Stop Loss:    {sl}
  Alvo:         {target if target else "não informado"}
  R/R estimado: {rr}
  Timestamp:    {payload.get("timestamp")}

CONTEXTO DO MERCADO:
  Sessão de Negociação (Volume): {session}
  Viés Diário (Narrativa HTF): {daily_bias}

MEMÓRIA DE CURTO PRAZO (Últimos trades neste ativo hoje):
{memory_str}

CONTEXTO HISTÓRICO DE ALTA PROBABILIDADE (RAG — 3 setups WIN mais similares):
{rag_str}

PARÂMETROS MULTI-ATIVOS (Regras Específicas do Ativo {asset}):
  Tick Size: {params.get("tick_size")}
  Mínimo FVG Ticks: {params.get("min_fvg_ticks")}

PROTOCOLO DE AUDITORIA (execute em ordem, sem pular etapas):

FASE 1 — CONTEXTO MACRO
  1. Chame `read_phase1_knowledge` para carregar as regras de mapeamento.
  2. Chame `get_economic_calendar_status` para verificar Red Folders.
  3. Avalie se a sessão atual ({session}) é favorável segundo a Fase 1.
  → Se qualquer critério da Fase 1 reprovar: encerre com RECUSA e motivo.

FASE 2 — QUALIDADE DO GATILHO
  4. Chame `read_phase2_knowledge` para carregar as regras do gatilho cirúrgico.
  5. Avalie a qualidade do padrão: a zona {payload.get("zone_hit")} está alinhada com as
     regras de ouro? O FVG (topo={payload.get("fvg_top")}, fundo={payload.get("fvg_bottom")})
     tem tamanho adequado para o ativo {asset}?
  → Se a qualidade for insuficiente: encerre com RECUSA e motivo.

FASE 3 — GESTÃO DE RISCO
  6. Chame `read_phase3_knowledge` para carregar as regras de risco.
  7. Chame `read_journal_status` para verificar stops já tomados hoje.
  8. Valide se o limite diário de stops não foi atingido.
  → Se o limite foi atingido: encerre com RECUSA e motivo.

EXECUÇÃO (somente se todas as 3 fases aprovarem):
  9. Chame `log_approved_trade` com a justificativa resumida.
  10. Chame `execute_limit_order` com o preço de entrada no meio do FVG e o SL.

Ao final, apresente um RELATÓRIO estruturado com:
  - Decisão: APROVADO ou RECUSADO
  - Fase que bloqueou (se recusado)
  - Justificativa objetiva (máx. 5 linhas)
"""


def _run_evaluation(payload: dict) -> None:
    """Synchronous evaluation — runs inside asyncio.to_thread."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        logger.error("GEMINI_API_KEY não definida. Auditoria cancelada.")
        return

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        model_name=_MODEL,
        tools=_TOOLS,
        generation_config=genai.types.GenerationConfig(temperature=0),
    )

    import re as _re, time as _time

    prompt = _build_prompt(payload)
    chat = None
    for attempt in range(1, 4):
        chat = model.start_chat(enable_automatic_function_calling=True)
        try:
            chat.send_message(prompt)
            break
        except Exception as exc:
            err = str(exc)
            if "MALFORMED_FUNCTION_CALL" in err and attempt < 3:
                logger.warning("MALFORMED_FUNCTION_CALL — retentativa %d/3", attempt)
                chat = None
                continue
            if "429" in err:
                m = _re.search(r"seconds:\s*(\d+)", err)
                wait = int(m.group(1)) + 2 if m else 60
                if wait > 120:  # daily quota — não faz sentido aguardar
                    logger.warning("Quota diária Gemini atingida (%d req/dia). Auditoria adiada.", 20)
                    return
                logger.warning("Rate limit Gemini — aguardando %ds (tentativa %d/3)", wait, attempt)
                _time.sleep(wait)
                chat = None
                continue
            logger.error("Erro na auditoria Gemini: %s", exc)
            return

    if chat is None:
        logger.error("Auditoria falhou após retentativas.")
        return

    # Build full turn-by-turn transcript from chat history
    lines = [f"====== AUDITORIA IA | {payload.get('action')} {payload.get('asset')} ======"]
    for turn in chat.history:
        role = getattr(turn, "role", "?").upper()
        for part in getattr(turn, "parts", []):
            fn_call = getattr(part, "function_call", None)
            fn_resp = getattr(part, "function_response", None)
            text = getattr(part, "text", None)
            if fn_call:
                args = dict(fn_call.args) if fn_call.args else {}
                lines.append(f"  [{role}] → tool_call: {fn_call.name}({args})")
            elif fn_resp:
                resp_val = dict(fn_resp.response) if fn_resp.response else {}
                snippet = str(resp_val.get("result", resp_val))[:300]
                lines.append(f"  [{role}] ← tool_result: {fn_resp.name} | {snippet}")
            elif text and text.strip():
                lines.append(f"  [{role}] {text.strip()}")
    lines.append("========================================")
    logger.info("\n".join(lines))


async def evaluate_and_execute_signal(payload: dict) -> None:
    if not _GENAI_AVAILABLE:
        logger.error("google-generativeai não instalado. Execute: pip install google-generativeai")
        return
    logger.info(
        "Iniciando auditoria IA | %s %s zona=%s",
        payload.get("action"), payload.get("asset"), payload.get("zone_hit"),
    )
    await asyncio.to_thread(_run_evaluation, payload)


# ── Standalone test ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    dummy = {
        "asset": "BTC", "action": "BUY", "zone_hit": "zone1_low",
        "sweep_level": 64000.0, "fvg_top": 64200.0, "fvg_bottom": 64050.0,
        "sl_level": 63980.0, "timestamp": datetime.now().isoformat(),
    }
    asyncio.run(evaluate_and_execute_signal(dummy))
