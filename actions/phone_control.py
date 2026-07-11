import os
import sys
import zipfile
import urllib.request
import subprocess
import urllib.parse
from pathlib import Path

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
BIN_DIR = BASE_DIR / "bin"
ADB_PATH = BIN_DIR / "adb.exe"

ADB_DOWNLOAD_URL = "https://dl.google.com/android/repository/platform-tools-latest-windows.zip"

def ensure_adb() -> bool:
    """Ensures adb.exe and its DLL dependencies are present. Downloads if necessary."""
    if ADB_PATH.exists():
        return True

    print("[phone_control] ADB not found. Downloading Android platform-tools...")
    BIN_DIR.mkdir(parents=True, exist_ok=True)
    zip_path = BIN_DIR / "platform-tools.zip"

    try:
        # Download platform-tools
        urllib.request.urlretrieve(ADB_DOWNLOAD_URL, zip_path)
        print("[phone_control] Download complete. Extracting ADB components...")

        # Extract only the necessary files
        needed_files = {"platform-tools/adb.exe", "platform-tools/AdbWinApi.dll", "platform-tools/AdbWinUsbApi.dll"}
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            for file_info in zip_ref.infolist():
                if file_info.filename in needed_files:
                    # Rename during extraction to put them directly in bin/
                    dest_name = Path(file_info.filename).name
                    dest_file_path = BIN_DIR / dest_name
                    with zip_ref.open(file_info) as source, open(dest_file_path, "wb") as target:
                        target.write(source.read())

        # Cleanup zip file
        if zip_path.exists():
            zip_path.unlink()

        print("[phone_control] ADB setup successfully.")
        return True
    except Exception as e:
        print(f"[phone_control] Failed to download/install ADB: {e}")
        # Clean up any partial files
        if zip_path.exists():
            zip_path.unlink()
        return False

def run_adb(args: list[str]) -> tuple[str, str, int]:
    """Runs a command with the local adb binary."""
    if not ensure_adb():
        return "", "ADB binary could not be loaded.", -1

    cmd = [str(ADB_PATH)] + args
    try:
        # Hide console window on Windows to keep it silent and clean
        startupinfo = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE

        process = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=15,
            startupinfo=startupinfo
        )
        return process.stdout, process.stderr, process.returncode
    except subprocess.TimeoutExpired:
        return "", "ADB command timed out.", -2
    except Exception as e:
        return "", f"Failed to run ADB: {str(e)}", -3

def check_connection() -> str:
    """Checks the status of connected Android devices."""
    stdout, stderr, code = run_adb(["devices"])
    if code != 0:
        return f"Error checking devices: {stderr}"
    
    lines = stdout.strip().split("\n")
    devices = [line.strip() for line in lines[1:] if line.strip()]
    
    if not devices:
        return "No devices connected. Please connect your phone via USB and enable USB Debugging."
    
    status_str = []
    for d in devices:
        parts = d.split()
        if len(parts) >= 2:
            serial, state = parts[0], parts[1]
            if state == "unauthorized":
                status_str.append(f"Device found ({serial}) but is UNAUTHORIZED. Please accept the prompt on your phone screen.")
            elif state == "device":
                status_str.append(f"Phone successfully connected (Serial: {serial}). ready to accept commands.")
            else:
                status_str.append(f"Device ({serial}) is in state: {state}.")
        else:
            status_str.append(f"Unknown device listing: {d}")
            
    return "\n".join(status_str)

def dial_call(number: str) -> str:
    """Dials a phone number directly on the device."""
    clean_num = "".join(c for c in number if c.isdigit() or c == "+")
    if not clean_num:
        return "Invalid phone number provided."
        
    stdout, stderr, code = run_adb(["shell", "am", "start", "-a", "android.intent.action.CALL", "-d", f"tel:{clean_num}"])
    if code != 0:
        # Fallback to dialer if CALL permission is not granted to ADB shell
        stdout, stderr, code = run_adb(["shell", "am", "start", "-a", "android.intent.action.DIAL", "-d", f"tel:{clean_num}"])
        if code != 0:
            return f"Failed to start call: {stderr or stdout}"
        return f"Opened dialer with number: {number}"
    return f"Calling {number} on your phone."

def open_url(url: str) -> str:
    """Opens a URL in the default browser of the Android phone."""
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "https://" + url
    stdout, stderr, code = run_adb(["shell", "am", "start", "-a", "android.intent.action.VIEW", "-d", url])
    if code != 0:
        return f"Failed to open URL on phone: {stderr or stdout}"
    return f"Opened {url} on your phone's browser."

def send_whatsapp(number: str, message: str) -> str:
    """Opens a WhatsApp chat with the specified number and populates the message."""
    # Ensure phone number includes country code without + or spaces
    clean_num = "".join(c for c in number if c.isdigit())
    if not clean_num:
        return "Invalid phone number for WhatsApp."
    
    # URL encode the message text
    encoded_msg = urllib.parse.quote(message)
    whatsapp_url = f"https://api.whatsapp.com/send?phone={clean_num}&text={encoded_msg}"
    
    stdout, stderr, code = run_adb(["shell", "am", "start", "-a", "android.intent.action.VIEW", "-d", whatsapp_url])
    if code != 0:
        return f"Failed to open WhatsApp: {stderr or stdout}"
        
    # Wait 1.5 seconds for WhatsApp to load, then simulate ENTER key to send it if possible
    # We can run this asynchronously or just let it focus. Focusing is safer, but let's try a press key enter helper.
    # We will send a keyevent 66 (ENTER) after a short delay
    import time
    def _send_enter():
        time.sleep(2.5)
        # Press enter to submit the pre-populated text
        run_adb(["shell", "input", "keyevent", "66"])
        
    import threading
    threading.Thread(target=_send_enter, daemon=True).start()
    
    return f"Opening WhatsApp chat with {number} and pre-filling your message."

def press_key(key_name: str) -> str:
    """Simulates pressing a physical/virtual key on the phone."""
    key_map = {
        "home": 3,
        "back": 4,
        "power": 26,
        "volume_up": 24,
        "volume_down": 25,
        "enter": 66,
        "tab": 61,
        "space": 62,
        "delete": 67,
    }
    
    key_code = key_map.get(key_name.lower().strip())
    if not key_code:
        try:
            key_code = int(key_name)
        except ValueError:
            return f"Unknown key name: {key_name}."
            
    stdout, stderr, code = run_adb(["shell", "input", "keyevent", str(key_code)])
    if code != 0:
        return f"Failed to press key {key_name}: {stderr or stdout}"
    return f"Pressed {key_name} key on phone."

def type_text(text: str) -> str:
    """Types text on the phone screen."""
    # Replace spaces with %s for ADB input command Compatibility
    formatted_text = text.replace(" ", "%s")
    stdout, stderr, code = run_adb(["shell", "input", "text", formatted_text])
    if code != 0:
        return f"Failed to type text: {stderr or stdout}"
    return f"Typed message on phone screen."

def tap(x: int, y: int) -> str:
    """Taps on the screen at (x, y) coordinates."""
    stdout, stderr, code = run_adb(["shell", "input", "tap", str(x), str(y)])
    if code != 0:
        return f"Failed to tap at ({x}, {y}): {stderr or stdout}"
    return f"Tapped screen at coordinate ({x}, {y})."

def connect_wireless(ip: str, port: str = "5555") -> str:
    """Connects to an Android device over Wi-Fi (wireless debugging)."""
    address = f"{ip.strip()}:{port.strip()}"
    stdout, stderr, code = run_adb(["connect", address])
    if code != 0:
        return f"Failed to connect wirelessly: {stderr or stdout}"
    return stdout.strip()

def pair_wireless(ip: str, port: str, pairing_code: str) -> str:
    """Pairs with an Android device over Wi-Fi using a pairing code (Android 11+)."""
    address = f"{ip.strip()}:{port.strip()}"
    stdout, stderr, code = run_adb(["pair", address, pairing_code.strip()])
    if code != 0:
        return f"Failed to pair wirelessly: {stderr or stdout}"
    return stdout.strip()

def phone_control(parameters=None, player=None) -> str:
    """Main router function for phone_control tool."""
    params = parameters or {}
    action = params.get("action", "").lower().strip()
    
    if player:
        player.write_log(f"[phone_control] {action}")
        
    if action == "check_connection":
        return check_connection()
    elif action == "connect_wireless":
        ip = params.get("url", "") # We can reuse url or pass as text
        port = params.get("key", "5555") # We can reuse key parameter for port
        if not ip:
            return "IP address (provided in 'url' or 'text') is required to connect wirelessly."
        return connect_wireless(ip, port)
    elif action == "pair_wireless":
        ip = params.get("url", "")
        port = params.get("key", "")
        pairing_code = params.get("text", "")
        if not ip or not port or not pairing_code:
            return "IP, Port, and Pairing Code are all required to pair wirelessly."
        return pair_wireless(ip, port, pairing_code)
    elif action == "dial_call":
        number = params.get("number", "")
        if not number:
            return "No phone number provided."
        return dial_call(number)
    elif action == "open_url":
        url = params.get("url", "")
        if not url:
            return "No URL provided."
        return open_url(url)
    elif action == "send_whatsapp":
        number = params.get("number", "")
        text = params.get("text", "")
        if not number or not text:
            return "Phone number and text are both required to send a WhatsApp message."
        return send_whatsapp(number, text)
    elif action == "press_key":
        key = params.get("key", "")
        if not key:
            return "No key name provided."
        return press_key(key)
    elif action == "type_text":
        text = params.get("text", "")
        if not text:
            return "No text provided to type."
        return type_text(text)
    elif action == "tap":
        x = params.get("x")
        y = params.get("y")
        if x is None or y is None:
            return "Coordinates x and y must be provided for a tap action."
        try:
            return tap(int(x), int(y))
        except ValueError:
            return "Coordinates x and y must be integers."
    else:
        return f"Unknown action: {action}. Supported: check_connection, connect_wireless, pair_wireless, dial_call, open_url, send_whatsapp, press_key, type_text, tap"

