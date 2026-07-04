import os
import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock
import pytz

EST = pytz.timezone("America/New_York")

VALID_ENTRY = "## Visão Geral\ntest\n## Auditoria de Erros e Acertos\ntest\n## Lição do Dia\ntest"


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

    frozen_dt = MagicMock()
    frozen_dt.now.return_value = datetime(2026, 7, 4, 11, 30, tzinfo=EST)
    monkeypatch.setattr(journal_writer, "datetime", frozen_dt)

    with patch("journal_writer.genai.configure"):
        with patch("journal_writer.genai.GenerativeModel") as mock_model_cls:
            with patch("journal_writer.time.sleep"):
                instance = MagicMock()
                instance.generate_content.side_effect = Exception("quota")
                mock_model_cls.return_value = instance

                journal_writer.write_journal()

    draft = tmp_path / "journal_draft_2026-07-04.txt"
    assert draft.exists()
    assert "[ERRO:" in draft.read_text()


def test_write_journal_appends_valid_entry(tmp_path, monkeypatch):
    import journal_writer
    monkeypatch.setattr(journal_writer, "LOGS_DIR", str(tmp_path))
    journal_path = tmp_path / "journal.md"
    journal_path.write_text("# Diário\n")
    monkeypatch.setattr(journal_writer, "JOURNAL_PATH", str(journal_path))
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")

    frozen_dt = MagicMock()
    frozen_dt.now.return_value = datetime(2026, 7, 4, 11, 30, tzinfo=EST)
    monkeypatch.setattr(journal_writer, "datetime", frozen_dt)

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


def test_write_journal_reprompts_when_first_entry_invalid(tmp_path, monkeypatch):
    import journal_writer
    monkeypatch.setenv("GEMINI_API_KEY", "fake")
    monkeypatch.setattr(journal_writer, "JOURNAL_PATH", str(tmp_path / "journal.md"))

    frozen_dt = MagicMock()
    frozen_dt.now.return_value = datetime(2026, 7, 4, 11, 30, tzinfo=EST)
    monkeypatch.setattr(journal_writer, "datetime", frozen_dt)

    responses = iter(["sem seções obrigatórias aqui", VALID_ENTRY])

    def fake_retry(model, prompt):
        return next(responses)

    monkeypatch.setattr(journal_writer, "_call_with_retry", fake_retry)
    journal_writer.write_journal()
    assert VALID_ENTRY in (tmp_path / "journal.md").read_text()


def test_write_journal_saves_draft_when_reprompt_also_invalid(tmp_path, monkeypatch):
    import journal_writer
    monkeypatch.setenv("GEMINI_API_KEY", "fake")
    monkeypatch.setattr(journal_writer, "LOGS_DIR", str(tmp_path))

    frozen_dt = MagicMock()
    frozen_dt.now.return_value = datetime(2026, 7, 4, 11, 30, tzinfo=EST)
    monkeypatch.setattr(journal_writer, "datetime", frozen_dt)

    invalid = "sem seções válidas"
    monkeypatch.setattr(journal_writer, "_call_with_retry", lambda *a: invalid)
    monkeypatch.setattr(journal_writer, "JOURNAL_PATH", str(tmp_path / "journal.md"))
    journal_writer.write_journal()
    drafts = list(tmp_path.glob("journal_draft_*.txt"))
    assert len(drafts) == 1
