import os

from banker_radar.config import load_dotenv_file


def test_load_dotenv_file_does_not_override_existing_env(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "TELEGRAM_BOT_TOKEN=from-file\n"
        "TELEGRAM_CHAT_ID=-1003903984676\n"
        "# ignored comment\n"
        "QUOTED_VALUE=\"hello world\"\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "from-env")
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    monkeypatch.delenv("QUOTED_VALUE", raising=False)

    loaded = load_dotenv_file(env_file)

    assert loaded == 2
    assert os.environ["TELEGRAM_BOT_TOKEN"] == "from-env"
    assert os.environ["TELEGRAM_CHAT_ID"] == "-1003903984676"
    assert os.environ["QUOTED_VALUE"] == "hello world"
