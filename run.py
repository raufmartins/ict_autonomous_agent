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
