"""Fork: profile delete stops that profile's plugin host (its cwd locks the profile dir on Windows)."""
from __future__ import annotations

from hermes_cli import plugins


class _Host:
    def __init__(self) -> None:
        self.stopped = False

    def shutdown(self) -> None:
        self.stopped = True


class _Manager:
    def __init__(self) -> None:
        self._plugins: dict = {}
        self._plugin_host_instance = _Host()
        self.unloaded = False

    def unload(self) -> bool:
        self.unloaded = True
        return True


def test_release_stops_only_the_deleted_profiles_host(tmp_path, monkeypatch):
    doomed_home = (tmp_path / "profiles" / "doomed").resolve()
    kept_home = (tmp_path / "profiles" / "kept").resolve()
    doomed, kept = _Manager(), _Manager()
    monkeypatch.setattr(plugins, "_plugin_managers_by_home", {doomed_home: doomed, kept_home: kept})
    monkeypatch.setattr(plugins, "_plugin_manager", doomed)

    assert plugins.release_plugin_manager_for_home(tmp_path / "profiles" / "doomed") is True

    assert doomed._plugin_host_instance.stopped and doomed.unloaded
    assert doomed_home not in plugins._plugin_managers_by_home
    assert plugins._plugin_manager is None
    assert not kept._plugin_host_instance.stopped and not kept.unloaded
    assert plugins._plugin_managers_by_home == {kept_home: kept}
    assert plugins.release_plugin_manager_for_home(doomed_home) is False
