import os
import sys
import threading
import time
from datetime import datetime

import pytz
import schedule
import uvicorn

from journal_writer import write_journal
from poller import run_poll_loop

EST = pytz.timezone("America/New_York")


def _start_server() -> None:
    uvicorn.run(
        "webhook_server:app",
        host="0.0.0.0",
        port=8000,
        log_level="info",
    )


def _write_daily_journal() -> None:
    from datetime import datetime
    import pytz
    import asyncio
    from research_agent import conduct_daily_research

    EST = pytz.timezone("America/New_York")
    now = datetime.now(EST)
    print(f"[{now.strftime('%H:%M')} EST] Gerando diário de operações...")
    try:
        write_journal()
        print("Diário atualizado com sucesso.")
        
        # Dispara o Head Trader (Claude) para pesquisar e melhorar os manuais
        asyncio.run(conduct_daily_research())
    except Exception as exc:
        print(f"Erro na rotina de fechamento (Diário/Pesquisa): {exc}")


if __name__ == "__main__":
    if not os.environ.get("GEMINI_API_KEY"):
        print("ERRO: GEMINI_API_KEY não definida.")
        print("Configure com: export GEMINI_API_KEY='sua-chave'")
        sys.exit(1)

    server_thread = threading.Thread(target=_start_server, daemon=True)
    server_thread.start()

    poller_thread = threading.Thread(target=run_poll_loop, daemon=True, name="ict-poller")
    poller_thread.start()

    schedule.every().day.at("11:30").do(_write_daily_journal)

    print("ICT Autonomous Trader em execução.")
    print("  Webhook server: http://localhost:8000")
    print("  Poller Binance:  30 s — BTCUSDT ETHUSDT SOLUSDT XRPUSDT BNBUSDT")
    print("  Diário gerado às 11:30 AM EST")
    print("  Pressione Ctrl+C para parar.\n")

    try:
        while True:
            schedule.run_pending()
            if not server_thread.is_alive():
                print("ERRO: Servidor encerrado inesperadamente. Saindo...")
                sys.exit(1)
            time.sleep(10)
    except KeyboardInterrupt:
        print("\nSistema encerrado.")
