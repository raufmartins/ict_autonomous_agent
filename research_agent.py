import os
import sys
import json
import asyncio
from datetime import datetime
import pytz

try:
    from anthropic import AsyncAnthropic
except ImportError:
    AsyncAnthropic = None

EST = pytz.timezone("America/New_York")

async def conduct_daily_research():
    if AsyncAnthropic is None:
        print("SDK da Anthropic não instalado. Pesquisa (Claude) ignorada.")
        return

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERRO: ANTHROPIC_API_KEY não definida. O Claude não poderá ser acionado.")
        return

    print(f"[{datetime.now(EST).strftime('%H:%M:%S')}] Iniciando Cientista de Dados (Claude)...")
    
    # 1. Load state
    state_file = os.path.join(os.path.dirname(__file__), "state.json")
    try:
        with open(state_file, "r") as f:
            state = json.load(f)
    except Exception as e:
        print(f"Erro ao ler state.json: {e}")
        return

    trades = state.get("trades_today", [])
    if not trades:
        print("Nenhum trade registrado hoje. Claude vai tirar uma folga.")
        return

    # 2. Load Phase 2 Playbook (Gatilho)
    playbook_file = os.path.join(os.path.dirname(__file__), "docs", "playbooks", "ict_fase2_playbook.md")
    try:
        with open(playbook_file, "r") as f:
            playbook_content = f.read()
    except Exception as e:
        playbook_content = f"Não foi possível ler o playbook: {e}"

    # 2.5 Load Asset Params (Multi-Ativos)
    asset_params_file = os.path.join(os.path.dirname(__file__), "asset_params.py")
    try:
        with open(asset_params_file, "r") as f:
            asset_params_content = f.read()
    except Exception as e:
        asset_params_content = f"Não foi possível ler os parâmetros de ativos: {e}"

    # 3. Create prompt
    prompt = f"""
    Você é o Head Trader Quantitativo do projeto ICT Autonomous Agent.
    A nossa arquitetura é Híbrida: O Gemini é o motor de execução (pilotando o mercado), e VOCÊ (Claude) é o motor de Pesquisa e Melhoria.
    
    Sua missão é ler o registro de trades do dia e o nosso manual de execução (Playbook) atual, e identificar oportunidades de melhoria na engenharia do nosso setup.
    
    ESTADO DO DIA (Trades Registrados):
    {json.dumps(state, indent=2)}

    PLAYBOOK DE EXECUÇÃO ATUAL (GATILHO - FASE 2):
    {playbook_content}

    CONFIGURAÇÕES MULTI-ATIVOS (Python - asset_params.py):
    {asset_params_content}

    TAREFA:
    1. Analise o que o Agente Executor (Gemini) fez hoje. Quantos "STOPs" e "WINs" tivemos? Verifique se há algum Ativo específico (ex: NQ, ETH) prejudicando a performance global.
    2. Se a performance estiver ruim, critique as regras do Playbook atual E os parâmetros do ativo no arquivo Python. Será que a janela de horário está errada? Será que o Mínimo FVG Ticks pro BTC está muito frouxo?
    3. Produza um breve relatório listando o que deve ser atualizado no Playbook de Execução OU no `asset_params.py` para que o Gemini performe melhor amanhã.
    4. Crie uma nova versão das regras que julgar falhas. Se o problema for métrico por ativo, forneça o novo código em Python para substituir a tabela `_ASSET_TABLE` em `asset_params.py`.
    """

    client = AsyncAnthropic(api_key=api_key)
    
    try:
        response = await client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=2048,
            temperature=0.4,
            system="Você é um quant researcher e cientista de dados focado em SMC / ICT Concepts.",
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        
        report = response.content[0].text
        
        log_dir = os.path.join(os.path.dirname(__file__), "logs")
        os.makedirs(log_dir, exist_ok=True)
        report_file = os.path.join(log_dir, f"claude_research_{datetime.now(EST).strftime('%Y-%m-%d')}.md")
        
        with open(report_file, "w") as f:
            f.write(report)
            
        print(f"[{datetime.now(EST).strftime('%H:%M:%S')}] Claude finalizou a análise! Relatório de Pesquisa gerado com sucesso em: {report_file}")
        
    except Exception as e:
        print(f"Erro ao consultar a API da Anthropic: {e}")

if __name__ == "__main__":
    asyncio.run(conduct_daily_research())
