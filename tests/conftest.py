import pytest


@pytest.fixture(autouse=True)
def _isolate_local_config(tmp_path_factory, monkeypatch):
    """Testy nie moga zalezec od lokalnej konfiguracji maszyny (local_config.json ze sciezka do
    prawdziwych paczek BDL) ani od BOROWIK_BDL_DIR -- inaczej zaladowalyby 45 tys. wydzielen."""
    monkeypatch.setattr("pipeline.local_config.LOCAL_CONFIG_PATH", tmp_path_factory.getbasetemp() / "brak_local_config.json")
    monkeypatch.delenv("BOROWIK_BDL_DIR", raising=False)
