import json
import subprocess
import sys
import time
from pathlib import Path

try:
    import pyautogui
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE    = 0.06
    _PYAUTOGUI = True
except ImportError:
    _PYAUTOGUI = False

try:
    import pyperclip
    _PYPERCLIP = True
except ImportError:
    _PYPERCLIP = False

try:
    import pygetwindow as gw
    _PYGETWINDOW = True
except ImportError:
    _PYGETWINDOW = False

def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent

def _get_os() -> str:
    try:
        cfg = json.loads(
            (_base_dir() / "config" / "api_keys.json").read_text(encoding="utf-8")
        )
        return cfg.get("os_system", "windows").lower()
    except Exception:
        return "windows"


def _require_pyautogui():
    if not _PYAUTOGUI:
        raise RuntimeError("PyAutoGUI not installed. Run: pip install pyautogui")


def _paste_text(text: str) -> None:
    _require_pyautogui()

    os_name = _get_os()
    paste_hotkey = ("command", "v") if os_name == "mac" else ("ctrl", "v")

    if _PYPERCLIP:
        pyperclip.copy(text)
        time.sleep(0.15)
        pyautogui.hotkey(*paste_hotkey)
        time.sleep(0.1)
    else:
        pyautogui.write(text, interval=0.03)


def _clear_and_paste(text: str) -> None:
    _require_pyautogui()
    os_name = _get_os()
    select_all = ("command", "a") if os_name == "mac" else ("ctrl", "a")
    pyautogui.hotkey(*select_all)
    time.sleep(0.15)
    pyautogui.press("backspace")   # backspace is more reliable than delete in search/input fields
    time.sleep(0.15)
    _paste_text(text)

def _focus_window_by_title(title_keyword: str) -> bool:
    """Bring a window to the foreground by matching a keyword in its title.
    Returns True if a matching window was found and focused."""
    if _PYGETWINDOW:
        try:
            wins = gw.getWindowsWithTitle(title_keyword)
            if wins:
                w = wins[0]
                w.restore()
                time.sleep(0.3)
                w.activate()
                time.sleep(0.5)
                return True
        except Exception as e:
            print(f"[SendMessage] pygetwindow focus failed: {e}")
    # Fallback: use PowerShell AppActivate
    try:
        script = f'(New-Object -ComObject WScript.Shell).AppActivate("{title_keyword}")'
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True, timeout=3,
        )
        time.sleep(0.6)
        return True
    except Exception:
        return False


def _open_app(app_name: str) -> bool:
    _require_pyautogui()
    os_name = _get_os()

    try:
        if os_name == "windows":
            # First try to activate an already-running window
            if _PYGETWINDOW:
                try:
                    wins = gw.getWindowsWithTitle(app_name)
                    if wins:
                        w = wins[0]
                        w.restore()
                        time.sleep(0.3)
                        w.activate()
                        time.sleep(0.8)
                        print(f"[SendMessage] ✅ Focused existing window: {app_name}")
                        return True
                except Exception:
                    pass

            # Not running — launch via Start Menu
            pyautogui.press("win")
            time.sleep(0.6)
            _paste_text(app_name)
            time.sleep(0.8)
            pyautogui.press("enter")
            time.sleep(3.5)   # wait for app to launch

            # After launch, bring the window to the foreground
            _focus_window_by_title(app_name)
            return True

        elif os_name == "mac":
            result = subprocess.run(
                ["open", "-a", app_name],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode != 0:
                result = subprocess.run(
                    ["open", "-a", f"{app_name}.app"],
                    capture_output=True, text=True, timeout=10,
                )
            time.sleep(2.5)
            return result.returncode == 0

        else: 
            launched = False
            for launcher in [
                ["gtk-launch", app_name.lower()],
                [app_name.lower()],
            ]:
                try:
                    subprocess.Popen(
                        launcher,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    launched = True
                    break
                except FileNotFoundError:
                    continue
            time.sleep(2.5)
            return launched

    except Exception as e:
        print(f"[SendMessage] ⚠️ Could not open {app_name}: {e}")
        return False


def _open_browser_url(url: str) -> bool:
    import webbrowser
    try:
        webbrowser.open(url)
        time.sleep(4.0) 
        return True
    except Exception as e:
        print(f"[SendMessage] ⚠️ Could not open browser: {e}")
        return False

def _search_in_app(query: str) -> None:
    """Generic in-app search using Ctrl+F (for non-WhatsApp apps)."""
    _require_pyautogui()
    os_name = _get_os()
    search_hotkey = ("command", "f") if os_name == "mac" else ("ctrl", "f")

    pyautogui.hotkey(*search_hotkey)
    time.sleep(0.5)
    _clear_and_paste(query)
    time.sleep(1.0)

def _desktop_send(app_name: str, receiver: str, message: str) -> str:
    if not _open_app(app_name):
        return f"Could not open {app_name}."

    time.sleep(1.0)
    _search_in_app(receiver)
    pyautogui.press("enter")
    time.sleep(0.8)

    _paste_text(message)
    time.sleep(0.2)
    pyautogui.press("enter")
    time.sleep(0.3)
    return f"Message sent to {receiver} via {app_name}."


def _send_whatsapp(receiver: str, message: str) -> str:
    """Send a WhatsApp message via WhatsApp Desktop (Windows).

    Strategy:
    1. Open / bring WhatsApp to foreground.
    2. Press Escape to ensure we are on the main chat-list view (not inside a chat).
    3. Press Ctrl+F — when on the main view this focuses the SIDEBAR search bar.
    4. Clear any old text, then type the contact name.
    5. Press Down + Enter to open the first matching chat.
    6. Click the message input bar at the bottom and send.
    """
    _require_pyautogui()

    # ── Step 1: Open / focus WhatsApp ────────────────────────────────────────
    win = None
    if _PYGETWINDOW:
        try:
            wins = gw.getWindowsWithTitle("WhatsApp")
            if wins:
                win = wins[0]
                win.restore()
                time.sleep(0.3)
                win.activate()
                time.sleep(0.8)
        except Exception as e:
            print(f"[SendMessage] pygetwindow: {e}")

    if not win:
        # Window not found — launch it
        if not _open_app("WhatsApp"):
            return "Could not open WhatsApp."
        time.sleep(2.0)
        # Try to grab the window after launch
        if _PYGETWINDOW:
            try:
                wins = gw.getWindowsWithTitle("WhatsApp")
                if wins:
                    win = wins[0]
                    win.activate()
                    time.sleep(0.8)
            except Exception:
                pass

    time.sleep(1.0)   # let the window fully settle

    # ── Step 2: Press Escape to exit any open chat → back to chat list ───────
    # This ensures Ctrl+F targets the sidebar search, not in-chat search
    pyautogui.press("escape")
    time.sleep(0.5)
    pyautogui.press("escape")   # press twice to be safe
    time.sleep(0.5)

    # ── Step 3: Open sidebar search with Ctrl+F ──────────────────────────────
    pyautogui.hotkey("ctrl", "f")
    time.sleep(1.0)   # wait for the search bar to appear and get focus

    # ── Step 4: Clear old text and type the contact name ────────────────────
    pyautogui.hotkey("ctrl", "a")
    time.sleep(0.1)
    pyautogui.press("backspace")
    time.sleep(0.1)

    # Write the name letter-by-letter so WhatsApp can filter results as you type
    pyautogui.write(receiver, interval=0.07)
    print(f"[SendMessage] 🔍 Typed contact name: '{receiver}'")
    time.sleep(2.5)   # wait for search results to populate

    # ── Step 5: Navigate to the first result and open the chat ───────────────
    pyautogui.press("down")   # move focus to the first result
    time.sleep(0.5)
    pyautogui.press("enter")  # open the chat
    time.sleep(1.8)           # wait for the chat view to load

    # ── Step 6: Focus the message input bar and send the message ─────────────
    if win:
        # Click at 60% across (message area) and 93% down (bottom input bar)
        mx = win.left + int(win.width  * 0.60)
        my = win.top  + int(win.height * 0.93)
    else:
        screen_w, screen_h = pyautogui.size()
        mx = int(screen_w * 0.60)
        my = int(screen_h * 0.93)

    pyautogui.click(mx, my)
    time.sleep(0.5)

    _paste_text(message)
    time.sleep(0.3)
    pyautogui.press("enter")
    time.sleep(0.5)
    return f"Message sent to {receiver} via WhatsApp."

def _send_telegram(receiver: str, message: str) -> str:
    """Send Telegram message using Ctrl+K (quick switcher / contact search)."""
    _require_pyautogui()

    if not _open_app("Telegram"):
        return "Could not open Telegram."

    time.sleep(1.0)

    # Ctrl+K opens Telegram's quick-switch / contact search
    pyautogui.hotkey("ctrl", "k")
    time.sleep(0.8)
    _clear_and_paste(receiver)
    time.sleep(1.2)
    pyautogui.press("enter")
    time.sleep(0.8)

    _paste_text(message)
    time.sleep(0.2)
    pyautogui.press("enter")
    time.sleep(0.3)
    return f"Message sent to {receiver} via Telegram."


def _send_signal(receiver: str, message: str) -> str:
    return _desktop_send("Signal", receiver, message)


def _send_discord(receiver: str, message: str) -> str:
    return _desktop_send("Discord", receiver, message)


def _send_teams(receiver: str, message: str) -> str:
    """Send a message via Microsoft Teams using Ctrl+K (command box)."""
    _require_pyautogui()

    if not _open_app("Teams"):
        return "Could not open Microsoft Teams."

    time.sleep(2.0)

    # Ctrl+K opens Teams search/command box
    pyautogui.hotkey("ctrl", "k")
    time.sleep(0.8)
    _clear_and_paste(f"/chat {receiver}")
    time.sleep(1.2)
    pyautogui.press("enter")
    time.sleep(1.0)

    _paste_text(message)
    time.sleep(0.2)
    pyautogui.press("enter")
    time.sleep(0.3)
    return f"Message sent to {receiver} via Microsoft Teams."


def _send_instagram(receiver: str, message: str) -> str:
    _require_pyautogui()

    if not _open_browser_url("https://www.instagram.com/direct/new/"):
        return "Could not open Instagram in browser."

    _paste_text(receiver)
    time.sleep(1.5)

    pyautogui.press("down")
    time.sleep(0.3)
    pyautogui.press("enter")   
    time.sleep(0.4)

    for _ in range(4):
        pyautogui.press("tab")
        time.sleep(0.15)
    pyautogui.press("enter")
    time.sleep(2.0)

    _paste_text(message)
    time.sleep(0.2)
    pyautogui.press("enter")
    time.sleep(0.3)

    return f"Message sent to {receiver} via Instagram."


def _send_messenger(receiver: str, message: str) -> str:
    _require_pyautogui()

    if not _open_browser_url("https://www.messenger.com/"):
        return "Could not open Messenger in browser."


    _search_in_app(receiver)
    time.sleep(0.5)
    pyautogui.press("down")
    time.sleep(0.3)
    pyautogui.press("enter")
    time.sleep(1.0)

    _paste_text(message)
    time.sleep(0.2)
    pyautogui.press("enter")
    time.sleep(0.3)

    return f"Message sent to {receiver} via Messenger."

_PLATFORM_MAP = [
    ({"whatsapp", "wp", "wapp"},                   _send_whatsapp),
    ({"telegram", "tg"},                            _send_telegram),
    ({"instagram", "ig", "insta"},                  _send_instagram),
    ({"signal"},                                    _send_signal),
    ({"discord"},                                   _send_discord),
    ({"messenger", "facebook", "fb"},               _send_messenger),
    ({"teams", "microsoft teams", "msteams"},       _send_teams),
]


def _resolve_platform(platform_str: str):
    key = platform_str.lower().strip()
    for keywords, handler in _PLATFORM_MAP:
        if any(k in key for k in keywords):
            return handler
    return lambda r, m: _desktop_send(platform_str.strip().title(), r, m)


def send_message(
    parameters: dict,
    response=None,
    player=None,
    session_memory=None,
) -> str:
    params       = parameters or {}
    receiver     = params.get("receiver", "").strip()
    message_text = params.get("message_text", "").strip()
    platform     = params.get("platform", "whatsapp").strip()

    if not receiver:
        return "Please specify a recipient."
    if not message_text:
        return "Please specify the message content."
    if not _PYAUTOGUI:
        return "PyAutoGUI is not installed — cannot control the desktop."

    preview = message_text[:50] + ("…" if len(message_text) > 50 else "")
    print(f"[SendMessage] 📨 {platform} → {receiver}: {preview}")
    if player:
        player.write_log(f"[msg] {platform} → {receiver}")

    try:
        handler = _resolve_platform(platform)
        result  = handler(receiver, message_text)
    except Exception as e:
        result = f"Could not send message: {e}"

    print(f"[SendMessage] {'✅' if 'sent' in result.lower() else '❌'} {result}")
    if player:
        player.write_log(f"[msg] {result}")

    return result