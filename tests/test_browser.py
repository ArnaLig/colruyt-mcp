"""Browser detection on Windows and Linux (no browser is launched)."""
import pytest

from colruyt_mcp import browser, config


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "HOME", tmp_path)
    monkeypatch.setattr(config, "BROWSER_FILE", tmp_path / "browser.json")
    monkeypatch.delenv("COLRUYT_MCP_BROWSER", raising=False)


def fake_windows(monkeypatch, existing: set[str]):
    monkeypatch.setenv("ProgramFiles", r"C:\PF")
    monkeypatch.setenv("ProgramFiles(x86)", r"C:\PF86")
    monkeypatch.setenv("LOCALAPPDATA", r"C:\LA")
    monkeypatch.setattr(browser.Path, "exists", lambda self: str(self) in existing)


def fake_linux(monkeypatch, commands: dict[str, str]):
    monkeypatch.setattr(browser.shutil, "which", lambda cmd: commands.get(cmd))
    monkeypatch.setattr(browser.Path, "exists", lambda self: self.as_posix() in commands.values())


def test_windows_prefers_edge_then_chrome(monkeypatch):
    fake_windows(monkeypatch, {r"C:\PF\Google\Chrome\Application\chrome.exe"})
    b = browser.find_browser(platform="win32")
    assert (b.family, b.path) == ("chrome", r"C:\PF\Google\Chrome\Application\chrome.exe")
    assert b.profile_dir == config.HOME / "chrome-profile"


def test_windows_per_user_chrome_install(monkeypatch):
    fake_windows(monkeypatch, {r"C:\LA\Google\Chrome\Application\chrome.exe"})
    assert browser.find_browser("chrome", platform="win32").path == r"C:\LA\Google\Chrome\Application\chrome.exe"


def test_linux_prefers_chrome_and_falls_back_to_chromium(monkeypatch):
    fake_linux(monkeypatch, {"google-chrome": "/usr/bin/google-chrome", "chromium": "/usr/bin/chromium"})
    assert browser.find_browser(platform="linux").family == "chrome"
    fake_linux(monkeypatch, {"chromium-browser": "/usr/bin/chromium-browser"})
    b = browser.find_browser(platform="linux")
    assert (b.family, b.path) == ("chromium", "/usr/bin/chromium-browser")


def test_explicit_path_and_env(monkeypatch):
    fake_linux(monkeypatch, {"x": "/opt/google/chrome/chrome"})
    monkeypatch.setenv("COLRUYT_MCP_BROWSER", "/opt/google/chrome/chrome")
    assert browser.find_browser(platform="linux").family == "chrome"


def test_saved_choice_is_reused(monkeypatch):
    fake_linux(monkeypatch, {"google-chrome": "/usr/bin/google-chrome", "microsoft-edge": "/usr/bin/microsoft-edge"})
    browser.remember(browser.Browser("edge", "/usr/bin/microsoft-edge"), "UA/1")
    assert browser.find_browser(platform="linux").family == "edge"
    assert browser.saved_user_agent() == "UA/1"


def test_missing_browser_message(monkeypatch):
    fake_linux(monkeypatch, {})
    with pytest.raises(RuntimeError, match="COLRUYT_MCP_BROWSER"):
        browser.find_browser(platform="linux")
