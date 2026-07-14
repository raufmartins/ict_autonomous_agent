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
from state_manager import record_trade
from asset_params import get_asset_params

logger = logging.getLogger("ict_trader")

_PLAYBOOKS_DIR = os.path.join(os.path.dirname(__file__), "docs", "playbooks")
_MODEL = "gemini-1.5-pro"


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

    return f"""Você é o Auditor Autônomo ICT. Um sinal passou pelos filtros mecânicos e aguarda sua aprovação final.

SINAL DETECTADO:
  Ativo:        {asset}
  Ação:         {payload.get("action")}
  Zona:         {payload.get("zone_hit")}
  Sweep Level:  {payload.get("sweep_level")}
  FVG Topo:     {payload.get("fvg_top")}
  FVG Fundo:    {payload.get("fvg_bottom")}
  Stop Loss:    {payload.get("sl_level")}
  Timestamp:    {payload.get("timestamp")}
  Sessão:       {session}
  Tick Size:    {params.get("tick_size")}

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
    )
    chat = model.start_chat(enable_automatic_function_calling=True)

    try:
        response = chat.send_message(_build_prompt(payload))
        logger.info(
            "====== AUDITORIA IA | %s %s ======\n%s\n========================================",
            payload.get("action"), payload.get("asset"), response.text,
        )
    except Exception as e:
        logger.error("Erro na auditoria Gemini: %s", e)


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
