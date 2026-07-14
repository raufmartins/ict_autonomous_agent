"""
Data Annotator — Claude-powered fine-tuning dataset generator.

Reads state.json for all closed trades, uses Claude as annotator to:
  - Explain WHY each trade won or stopped out (ICT lens)
  - Generate the ideal Gemini audit conversation for that setup

Exports a .jsonl file in Vertex AI supervised fine-tuning format.
Run manually after accumulating enough closed trades:
    python3 data_annotator.py [--days N] [--output path/to/out.jsonl]
"""
import argparse
import json
import os
from datetime import datetime, timedelta

import pytz

try:
    import anthropic
    _ANTHROPIC_AVAILABLE = True
except ImportError:
    _ANTHROPIC_AVAILABLE = False
    print("ERRO: pip install anthropic")

EST = pytz.timezone("America/New_York")
_STATE_FILE = os.path.join(os.path.dirname(__file__), "state.json")
_DEFAULT_OUT = os.path.join(os.path.dirname(__file__), "data", "finetune_dataset.jsonl")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _load_closed_trades(days: int) -> list[dict]:
    if not os.path.exists(_STATE_FILE):
        return []
    with open(_STATE_FILE) as f:
        raw = json.load(f)

    # state.json may hold a single day (trades_today) or a weekly archive (trades)
    trades = raw.get("trades", raw.get("trades_today", []))
    cutoff = datetime.now(EST) - timedelta(days=days)

    closed = []
    for t in trades:
        if t.get("result") not in ("WIN", "STOP"):
            continue
        # best-effort date filter
        ts = t.get("timestamp") or t.get("time") or ""
        try:
            dt = datetime.fromisoformat(ts).replace(tzinfo=EST) if "T" in ts else None
            if dt and dt < cutoff:
                continue
        except ValueError:
            pass
        closed.append(t)
    return closed


def _build_annotation_prompt(trade: dict) -> str:
    return f"""Você é um especialista em ICT (Inner Circle Trader) e está revisando um trade executado por um sistema de IA.

TRADE:
  Ativo:          {trade.get('asset')}
  Ação:           {trade.get('action')}
  Zona:           {trade.get('zone_hit', trade.get('zone', 'N/A'))}
  Sessão:         {trade.get('session', 'N/A')}
  Entrada (mid):  {trade.get('fvg_entry', 'N/A')}
  Stop Loss:      {trade.get('sl_level', 'N/A')}
  Resultado:      {trade.get('result')}
  R múltiplo:     {trade.get('r', 0)}
  Justificativa da IA: {trade.get('justification', 'N/A')}

Sua tarefa:
1. Analise em 2-3 frases por que este trade resultou em {trade.get('result')}.
   - Se WIN: o que estava correto na estrutura ICT?
   - Se STOP: qual critério foi ignorado ou mal avaliado?
2. Gere a conversa IDEAL (exemplo perfeito de fine-tuning) entre o usuário e o auditor ICT.
   - Se WIN: mostre o raciocínio correto levando à aprovação APROVADO.
   - Se STOP: mostre como o auditor deveria ter RECUSADO e o motivo exato.

Responda SOMENTE com JSON válido, sem markdown, neste formato exato:
{{
  "analysis": "Análise do resultado em 2-3 frases",
  "ideal_user_prompt": "O prompt completo que deve ser enviado ao auditor ICT",
  "ideal_model_response": "A resposta ideal do auditor com decisão APROVADO ou RECUSADO e justificativa ICT"
}}"""


def _annotate(client, trade: dict) -> dict | None:
    try:
        resp = client.messages.create(
            model="claude-opus-4-7",
            max_tokens=1500,
            messages=[{"role": "user", "content": _build_annotation_prompt(trade)}],
        )
        text = resp.content[0].text.strip()
        start, end = text.find("{"), text.rfind("}") + 1
        return json.loads(text[start:end])
    except Exception as e:
        print(f"  [ERRO] {trade.get('asset')} {trade.get('action')}: {e}")
        return None


# ── Main ──────────────────────────────────────────────────────────────────────

def export_dataset(days: int = 7, output: str = _DEFAULT_OUT) -> None:
    if not _ANTHROPIC_AVAILABLE:
        return

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERRO: ANTHROPIC_API_KEY não definida.")
        return

    client = anthropic.Anthropic(api_key=api_key)
    trades = _load_closed_trades(days)

    if not trades:
        print(f"Nenhum trade fechado nos últimos {days} dias em {_STATE_FILE}.")
        return

    print(f"Anotando {len(trades)} trades com Claude opus-4-7 …")
    os.makedirs(os.path.dirname(output), exist_ok=True)

    count = 0
    with open(output, "w", encoding="utf-8") as out:
        for i, trade in enumerate(trades, 1):
            tag = f"{trade.get('asset')} {trade.get('action')} {trade.get('result')}"
            print(f"  [{i}/{len(trades)}] {tag} …", end=" ", flush=True)
            ann = _annotate(client, trade)
            if not ann:
                print("PULADO")
                continue
            # Vertex AI supervised fine-tuning format
            record = {
                "messages": [
                    {"role": "user",   "content": ann["ideal_user_prompt"]},
                    {"role": "model",  "content": ann["ideal_model_response"]},
                ],
                "_meta": {
                    "asset":   trade.get("asset"),
                    "result":  trade.get("result"),
                    "r":       trade.get("r"),
                    "analysis": ann["analysis"],
                },
            }
            out.write(json.dumps(record, ensure_ascii=False) + "\n")
            count += 1
            print("OK")

    print(f"\nDataset exportado → {output}  ({count} exemplos)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Gera dataset de fine-tuning a partir do state.json")
    parser.add_argument("--days",   type=int, default=7,             help="Janela de dias (padrão: 7)")
    parser.add_argument("--output", type=str, default=_DEFAULT_OUT,  help="Caminho do .jsonl de saída")
    args = parser.parse_args()
    export_dataset(days=args.days, output=args.output)
