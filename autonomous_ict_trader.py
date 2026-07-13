import asyncio
import os
import sys
from datetime import datetime

try:
    from google.antigravity import Agent, LocalAgentConfig, types
except ImportError:
    Agent = None
    LocalAgentConfig = None
    types = None

# Integração com Módulos Reais
from decision_engine import _check_red_folder, get_current_session
from state_manager import record_trade
from asset_params import get_asset_params

# =========================================================================
# Ferramentas Customizadas (Knowledge Base)
# Substitui a necessidade humana de injetar o playbook a cada sessão.
# =========================================================================

def get_playbook_path(filename: str) -> str:
    return os.path.join(os.path.dirname(__file__), "docs", "playbooks", filename)

def read_phase1_knowledge() -> str:
    """Lê as instruções mecânicas da Fase 1 (Mapeamento de Liquidez de Tempo)."""
    file_path = get_playbook_path("ict_fase1_playbook.md")
    try:
        with open(file_path, "r") as f:
            return f.read()
    except Exception as e:
        return f"Erro ao ler Fase 1: {e}"

def read_phase2_knowledge() -> str:
    """Lê as regras de ouro para o gatilho cirúrgico (Fase 2)."""
    file_path = get_playbook_path("ict_fase2_playbook.md")
    try:
        with open(file_path, "r") as f:
            return f.read()
    except Exception as e:
        return f"Erro ao ler Fase 2: {e}"

def read_phase3_knowledge() -> str:
    """Lê os parâmetros de limite diário e Price Waiting (Fase 3)."""
    file_path = get_playbook_path("ict_fase3_playbook.md")
    try:
        with open(file_path, "r") as f:
            return f.read()
    except Exception as e:
        return f"Erro ao ler Fase 3: {e}"

def read_journal_status() -> str:
    """Lê o Diário de Operações para auditar os resultados diários."""
    file_path = get_playbook_path("ict_trading_journal.md")
    try:
        with open(file_path, "r") as f:
            return f.read()
    except Exception as e:
        return f"Erro ao ler o Diário: {e}"

def log_trade(asset: str, action: str, price: float, result: str, r: float) -> str:
    """
    Registra a operação no banco de dados local do State Manager.
    (Versão conectada ao state_manager.py real)
    """
    trade = {
        "asset": asset,
        "action": action,
        "price": price,
        "result": result,
        "r": r,
        "timestamp": datetime.now().isoformat()
    }
    try:
        record_trade(trade)
        return "Operação logada no State Manager com sucesso pela IA de Auditoria."
    except Exception as e:
        return f"Erro ao registrar trade: {e}"

# =========================================================================
# Mock Tools (Mercado e Execução)
# Em produção, essas funções farão interface via MCP com MetaTrader ou APIs de Corretora.
# =========================================================================
def get_economic_calendar_status() -> str:
    """Verifica Red Folders (Fase 1) usando o Decision Engine real."""
    has_red_folder = _check_red_folder()
    if has_red_folder:
        return "ATENÇÃO: Red Folder detectado no Forex Factory na janela atual. Bloqueio de operações."
    return "Calendário limpo. Sem Red Folders na janela de +/- 30 min."

def get_market_data_m15() -> str:
    """Retorna os dados OHLC e as zonas de liquidez mapeadas (M15)."""
    return "Mínima de Londres mapeada em 18350.00. Máxima Asiática em 18420.00."

def execute_limit_order(action: str, limit_price: float, stop_loss: float) -> str:
    """Ferramenta do Phase 2 Agent para enviar a ordem à corretora sem mãos humanas."""
    return f"Ordem {action} limite disparada em {limit_price} com SL em {stop_loss}."


# =========================================================================
# Orquestração Principal do Sistema Multi-Agente
# =========================================================================
import logging
logger = logging.getLogger("ict_trader")

async def evaluate_and_execute_signal(payload: dict):
    if Agent is None:
        logger.error("SDK google.antigravity não encontrado. Pulando execução do Agente Autônomo.")
        return

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        logger.error("GEMINI_API_KEY não está definida. Impossível rodar Agente Autônomo.")
        return

    logger.info(f"Iniciando auditoria da IA para o sinal {payload.get('action')} em {payload.get('asset')}...")

    config = LocalAgentConfig(
        api_key=api_key,
        capabilities=types.CapabilitiesConfig(
            enable_subagents=True,
        ),
        tools=[
            read_phase1_knowledge,
            read_phase2_knowledge,
            read_phase3_knowledge,
            read_journal_status,
            log_trade,
            get_economic_calendar_status,
            get_market_data_m15,
            execute_limit_order
        ]
    )

    asset_name = payload.get("asset", "UNKNOWN")
    asset_parameters = get_asset_params(asset_name)
    current_session = get_current_session()

    system_prompt = f"""
    Você é a Mente Mestra (Orquestrador) do Sistema ICT Autônomo.
    Um sinal de operação acabou de passar pelos filtros mecânicos (código duro) e foi encaminhado para sua auditoria final.
    
    DADOS DO SINAL (Payload do Webhook):
    Ativo: {asset_name}
    Ação: {payload.get("action")}
    Zona atingida: {payload.get("zone_hit")}
    Nível de Sweep: {payload.get("sweep_level")}
    Topo do FVG: {payload.get("fvg_top")}
    Fundo do FVG: {payload.get("fvg_bottom")}
    Stop Loss: {payload.get("sl_level")}
    Timestamp: {payload.get("timestamp")}

    CONTEXTO DO MERCADO:
    Sessão de Negociação (Volume Dominante): {current_session}

    PARÂMETROS MULTI-ATIVOS (Regras Específicas do Ativo {asset_name}):
    Tick Size: {asset_parameters.get("tick_size")}
    Mínimo FVG Ticks: {asset_parameters.get("min_fvg_ticks")}

    Sua missão é coordenar o fluxo operacional sem intervenção humana:
    1. Acione um subagente (Phase 1) para ler o conhecimento da Fase 1 e o Calendário Econômico.
    2. Acione um subagente executor (Phase 2) para ler o conhecimento da Fase 2. Usando os níveis da Fase 1 e o Payload atual, avalie a qualidade deste gatilho.
    3. Acione o subagente gestor (Phase 3) para ler a Fase 3 e validar se estamos dentro dos parâmetros operacionais.
    4. Se TUDO estiver de acordo com as regras de ouro, você MESMO deve chamar a ferramenta `log_trade` atualizando o trade (com status OPEN) e a ferramenta `execute_limit_order`. Caso contrário, apenas registre a recusa no log.
    
    Traga-me a justificativa completa dessa auditoria.
    """

    try:
        async with Agent(config) as agent:
            response = await agent.chat(system_prompt)
            result = await response.text()
            logger.info("====== RELATÓRIO DA AUDITORIA DA IA ======\n%s\n=============================================", result)
    except Exception as e:
        logger.error(f"Erro ao executar Agente Autônomo: {e}")

if __name__ == "__main__":
    # Teste isolado simulando um webhook
    dummy_payload = {
        "asset": "NQ", "action": "BUY", "zone_hit": "LDN_LOW",
        "sweep_level": 18350.00, "fvg_top": 18360.00, "fvg_bottom": 18355.00,
        "sl_level": 18348.00, "timestamp": datetime.now().isoformat()
    }
    asyncio.run(evaluate_and_execute_signal(dummy_payload))
