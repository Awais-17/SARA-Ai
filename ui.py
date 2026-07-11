from __future__ import annotations

import platform
if platform.system() == "Windows":
    import ctypes
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

import json
import math
import os
import platform
import random
import subprocess
import sys
import threading
import time
from pathlib import Path

import psutil

from PyQt6.QtCore import (
    QEasingCurve, QMimeData, QObject, QPointF, QRectF, QSize, Qt,
    QTimer, QUrl, pyqtSignal,
)
from PyQt6.QtGui import (
    QBrush, QColor, QDragEnterEvent, QDropEvent, QFont, QFontDatabase,
    QKeySequence, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap,
    QRadialGradient, QShortcut,
)
from PyQt6.QtWidgets import (
    QApplication, QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QMainWindow, QPushButton, QScrollArea, QSizePolicy, QTextEdit,
    QVBoxLayout, QWidget, QProgressBar,
)

def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent

BASE_DIR   = _base_dir()
CONFIG_DIR = BASE_DIR / "config"
API_FILE   = CONFIG_DIR / "api_keys.json"

_DEFAULT_W, _DEFAULT_H = 980, 700
_MIN_W,     _MIN_H     = 820, 580
_LEFT_W  = 154
_RIGHT_W = 340

_OS = platform.system()  # "Windows" | "Darwin" | "Linux"


class C:
    # Pink, Orange, and Blue Cyberpunk Hologram HUD Palette
    BG        = "#02040a" # Deep Obsidian Blue-Black
    PANEL     = "#090f1d" # Translucent Deep Slate Blue Panel Base
    PANEL2    = "#121a36" # Accent Slate Blue Panel Base
    BORDER    = "#1a254c" # Muted Holographic Blue Border
    BORDER_B  = "#00d4ff" # Glowing Electric Blue / Cyan
    BORDER_A  = "#ff007f" # Neon Pink / Magenta
    PRI       = "#00f0ff" # Vibrant Cyan / Blue
    PRI_DIM   = "#009bb3" # Muted Cyan
    PRI_GHO   = "#051c2d" # Ghost Cyan Glow
    ACC       = "#ff007f" # Neon Pink Accent
    ACC2      = "#ff6a00" # Neon Orange Accent
    GREEN     = "#00f0ff" # Vibrant Cyan / Blue (Listening)
    GREEN_D   = "#009bb3"
    RED       = "#ff0055" # Vibrant Ruby Red / Pink
    MUTED_C   = "#cc0066" # Muted Pink
    TEXT      = "#ffffff" # Ice White
    TEXT_DIM  = "#4e638c" # Muted Slate Blue
    TEXT_MED  = "#8ec5fc" # Mid Holographic Blue
    WHITE     = "#f2f7ff"
    DARK      = "#010205"
    BAR_BG    = "#060b18" # Empty bar/track background


def qcol(h: str, a: int = 255) -> QColor:
    c = QColor(h); c.setAlpha(a); return c

def _mono_font(size: int, weight=QFont.Weight.Normal) -> QFont:
    f = QFont()
    f.setFamilies(["Consolas", "Monaco", "Menlo", "Courier New", "monospace"])
    f.setPointSize(size)
    f.setWeight(weight)
    return f

def _sans_font(size: int, weight=QFont.Weight.Normal) -> QFont:
    f = QFont()
    f.setFamilies(["Segoe UI", "Inter", "Roboto", "Helvetica Neue", "Arial", "sans-serif"])
    f.setPointSize(size)
    f.setWeight(weight)
    return f

class _SysMetrics:
    def __init__(self):
        self.cpu  = 0.0
        self.mem  = 0.0
        self.net  = 0.0   
        self.gpu  = -1.0  
        self.tmp  = -1.0  
        self._lock = threading.Lock()
        self._last_net = psutil.net_io_counters()
        self._last_net_t = time.time()
        self._running = True
        t = threading.Thread(target=self._loop, daemon=True)
        t.start()

    def _loop(self):
        while self._running:
            try:
                self._update()
            except Exception:
                pass
            time.sleep(1.5)

    def _update(self):
        cpu = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory().percent

        nc  = psutil.net_io_counters()
        now = time.time()
        dt  = now - self._last_net_t
        if dt > 0:
            sent = (nc.bytes_sent - self._last_net.bytes_sent) / dt
            recv = (nc.bytes_recv - self._last_net.bytes_recv) / dt
            net  = (sent + recv) / (1024 * 1024)
        else:
            net = 0.0
        self._last_net   = nc
        self._last_net_t = now

        gpu = self._get_gpu()

        tmp = self._get_temp()

        with self._lock:
            self.cpu = cpu
            self.mem = mem
            self.net = net
            self.gpu = gpu
            self.tmp = tmp

    def _get_gpu(self) -> float:
        # NVIDIA
        try:
            r = subprocess.run(
                ["nvidia-smi", "--query-gpu=utilization.gpu",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=2
            )
            if r.returncode == 0:
                vals = [float(v.strip()) for v in r.stdout.strip().split("\n") if v.strip()]
                if vals:
                    return sum(vals) / len(vals)
        except Exception:
            pass

        # AMD (Linux)
        if _OS == "Linux":
            try:
                r = subprocess.run(
                    ["rocm-smi", "--showuse", "--csv"],
                    capture_output=True, text=True, timeout=2
                )
                if r.returncode == 0:
                    for line in r.stdout.strip().split("\n"):
                        parts = line.split(",")
                        if len(parts) >= 2:
                            try:
                                return float(parts[1].strip().replace("%", ""))
                            except ValueError:
                                pass
            except Exception:
                pass

            # Intel GPU (Linux)
            try:
                r = subprocess.run(
                    ["intel_gpu_top", "-J", "-s", "500"],
                    capture_output=True, text=True, timeout=1
                )
                if r.returncode == 0 and "Render/3D" in r.stdout:
                    import re
                    m = re.search(r'"busy":\s*([\d.]+)', r.stdout)
                    if m:
                        return float(m.group(1))
            except Exception:
                pass

        # macOS — powermetrics (GPU Engine)
        if _OS == "Darwin":
            try:
                r = subprocess.run(
                    ["sudo", "-n", "powermetrics", "-n", "1", "-i", "500",
                     "--samplers", "gpu_power"],
                    capture_output=True, text=True, timeout=2
                )
                if r.returncode == 0 and "GPU" in r.stdout:
                    import re
                    m = re.search(r'GPU\s+Active:\s+([\d.]+)%', r.stdout)
                    if m:
                        return float(m.group(1))
            except Exception:
                pass

        return -1.0

    def _get_temp(self) -> float:
        try:
            temps = psutil.sensors_temperatures()
            candidates = ["coretemp", "k10temp", "cpu_thermal", "acpitz",
                          "cpu-thermal", "zenpower", "it8688"]
            for name in candidates:
                if name in temps:
                    entries = temps[name]
                    if entries:
                        return entries[0].current
            for entries in temps.values():
                if entries:
                    return entries[0].current
        except Exception:
            pass
        if _OS == "Darwin":
            try:
                r = subprocess.run(
                    ["osx-cpu-temp"], capture_output=True, text=True, timeout=2
                )
                if r.returncode == 0:
                    import re
                    m = re.search(r"([\d.]+)", r.stdout)
                    if m:
                        return float(m.group(1))
            except Exception:
                pass

        if _OS == "Windows":
            try:
                r = subprocess.run(
                    ["powershell", "-Command",
                     "(Get-WmiObject MSAcpi_ThermalZoneTemperature -Namespace root/wmi).CurrentTemperature"],
                    capture_output=True, text=True, timeout=3
                )
                if r.returncode == 0 and r.stdout.strip():
                    raw = float(r.stdout.strip().split("\n")[0])
                    return (raw / 10.0) - 273.15
            except Exception:
                pass

        return -1.0

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "cpu": self.cpu,
                "mem": self.mem,
                "net": self.net,
                "gpu": self.gpu,
                "tmp": self.tmp,
            }


_metrics = _SysMetrics()

class HudCanvas(QWidget):
    def __init__(self, face_path: str, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)
        self.setMinimumSize(300, 300)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.setMouseTracking(True)
        self._hovered_btn = None
        self._btn_angles = [30, 90, 150, 210, 270, 330]
        self._btn_names = ["SYS", "CORE", "NET", "MEM", "VIS", "SEC"]

        self.muted    = False
        self.speaking = False
        self.state    = "INITIALISING"

        self._tick       = 0
        self._scale      = 1.0
        self._tgt_scale  = 1.0
        self._halo       = 60.0
        self._tgt_halo   = 60.0
        self._last_t     = time.time()
        self._scan       = 0.0
        self._scan2      = 180.0
        
        # Orbital speeds
        self._rings      = [0.0, 120.0, 240.0]
        self._pulses: list[float] = [0.0, 60.0, 120.0]
        self._blink      = True
        self._blink_tick = 0
        
        # Interactive particle constellation network
        self._particles: list[dict] = []
        for _ in range(54):
            self._particles.append({
                "x": random.uniform(20, 600),
                "y": random.uniform(20, 600),
                "vx": random.uniform(-0.6, 0.6),
                "vy": random.uniform(-0.6, 0.6),
                "r": random.uniform(1.2, 3.2),
                "alpha": random.randint(80, 210)
            })
        self._burst_particles: list[dict] = []
        self._mouse_pos = QPointF(-1000, -1000)
        
        self._face_px: QPixmap | None = None
        self._load_face(face_path)

        self._tmr = QTimer(self)
        self._tmr.timeout.connect(self._step)
        self._tmr.start(16)

    def _load_face(self, path: str):
        try:
            from PIL import Image, ImageDraw
            import io
            img = Image.open(path).convert("RGBA")
            sz  = min(img.size)
            img = img.resize((sz, sz), Image.LANCZOS)
            mk  = Image.new("L", (sz, sz), 0)
            ImageDraw.Draw(mk).ellipse((2, 2, sz - 2, sz - 2), fill=255)
            img.putalpha(mk)
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            px = QPixmap(); px.loadFromData(buf.getvalue())
            self._face_px = px
        except Exception:
            self._face_px = None

    def _step(self):
        self._tick += 1
        now = time.time()
        
        # Dynamic pulse scaling based on speech & mute status
        if now - self._last_t > (0.12 if self.speaking else 0.5):
            if self.speaking:
                self._tgt_scale = random.uniform(1.08, 1.16)
                self._tgt_halo  = random.uniform(160, 210)
            elif self.muted:
                self._tgt_scale = random.uniform(0.998, 1.002)
                self._tgt_halo  = random.uniform(15, 28)
            else:
                self._tgt_scale = random.uniform(1.002, 1.010)
                self._tgt_halo  = random.uniform(50, 72)
            self._last_t = now

        sp = 0.35 if self.speaking else 0.15
        self._scale += (self._tgt_scale - self._scale) * sp
        self._halo  += (self._tgt_halo  - self._halo)  * sp

        speeds = [1.5, -1.0, 2.2] if self.speaking else [0.6, -0.4, 1.0]
        for i, spd in enumerate(speeds):
            self._rings[i] = (self._rings[i] + spd) % 360

        self._scan  = (self._scan  + (3.5 if self.speaking else 1.5)) % 360
        self._scan2 = (self._scan2 + (-2.2 if self.speaking else -0.85)) % 360

        fw  = min(self.width(), self.height()) or 400
        lim = fw * 0.76
        pulse_spd = 4.5 if self.speaking else 2.2
        self._pulses = [r + pulse_spd for r in self._pulses if r + pulse_spd < lim]
        if len(self._pulses) < 3 and random.random() < (0.08 if self.speaking else 0.03):
            self._pulses.append(0.0)

        # Physics simulation for floating particle network
        W = self.width() or 400
        H = self.height() or 400
        cx, cy = W / 2, H / 2
        r_core = fw * 0.32
        
        mx, my = self._mouse_pos.x(), self._mouse_pos.y()
        
        for p in self._particles:
            p["x"] += p["vx"]
            p["y"] += p["vy"]
            
            # Bounce particles off boundaries
            if p["x"] < 12 or p["x"] > W - 12:
                p["vx"] *= -1
                p["x"] = max(12, min(W - 12, p["x"]))
            if p["y"] < 12 or p["y"] > H - 12:
                p["vy"] *= -1
                p["y"] = max(12, min(H - 12, p["y"]))
                
            # Slowly push away from the main central visualizer core
            dx = p["x"] - cx
            dy = p["y"] - cy
            dist = math.sqrt(dx*dx + dy*dy)
            if dist < r_core - 15:
                force = (r_core - 15 - dist) * 0.04
                p["vx"] += (dx / (dist + 0.1)) * force
                p["vy"] += (dy / (dist + 0.1)) * force
                
            # Mouse interaction (light gravity, heavy repulsion when too close)
            if mx > 0 and my > 0:
                mdx = mx - p["x"]
                mdy = my - p["y"]
                mdist = math.sqrt(mdx*mdx + mdy*mdy)
                if mdist < 130:
                    if mdist > 32:
                        # pulling force
                        p["vx"] += (mdx / mdist) * 0.14
                        p["vy"] += (mdy / mdist) * 0.14
                    else:
                        # push force
                        p["vx"] -= (mdx / (mdist + 0.1)) * 0.95
                        p["vy"] -= (mdy / (mdist + 0.1)) * 0.95
                        
            # Clamp particle velocity to prevent explosions
            v_limit = 2.8 if self.speaking else 1.3
            v_mag = math.sqrt(p["vx"]**2 + p["vy"]**2)
            if v_mag > v_limit:
                p["vx"] = (p["vx"] / v_mag) * v_limit
                p["vy"] = (p["vy"] / v_mag) * v_limit

        # Drifting thought bursts (emitted when speaking)
        if self.speaking and random.random() < 0.35:
            ang = random.uniform(0, 2 * math.pi)
            r_s = fw * 0.20
            self._burst_particles.append({
                "x": cx + math.cos(ang) * r_s,
                "y": cy + math.sin(ang) * r_s,
                "vx": math.cos(ang) * random.uniform(1.2, 3.2),
                "vy": math.sin(ang) * random.uniform(1.2, 3.2) - 0.5,
                "alpha": 255
            })
            
        self._burst_particles = [
            {
                "x": bp["x"] + bp["vx"],
                "y": bp["y"] + bp["vy"],
                "vx": bp["vx"] * 0.95,
                "vy": bp["vy"] * 0.95,
                "alpha": bp["alpha"] - 6
            }
            for bp in self._burst_particles if bp["alpha"] > 6
        ]

        self._blink_tick += 1
        if self._blink_tick >= 38:
            self._blink = not self._blink
            self._blink_tick = 0
        self.update()

    def mouseMoveEvent(self, e):
        self._mouse_pos = e.position()
        cx, cy = self.width() / 2, self.height() / 2
        fw = min(self.width(), self.height())
        r_btn = fw * 0.38
        
        self._hovered_btn = None
        pos = e.position()
        mx, my = pos.x(), pos.y()
        
        for idx, ang in enumerate(self._btn_angles):
            rad = math.radians(ang)
            bx = cx + r_btn * math.cos(rad)
            by = cy - r_btn * math.sin(rad)
            dist = math.sqrt((mx - bx)**2 + (my - by)**2)
            if dist <= 24:
                self._hovered_btn = idx
                break
        self.update()

    def leaveEvent(self, e):
        self._mouse_pos = QPointF(-1000, -1000)
        self._hovered_btn = None
        self.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            if self._hovered_btn is not None:
                name = self._btn_names[self._hovered_btn]
                parent = self.parent()
                while parent is not None:
                    if hasattr(parent, "_log_sig"):
                        break
                    parent = parent.parent()
                
                logs = {
                    "SYS": "SYS: Quantum Diagnostics operational. Uptime: verified. System status: NOMINAL.",
                    "CORE": "CORE: Neural core response delay: 0.14ms. Thought coherence: 99.8%.",
                    "NET": "NET: Establishing secure node channels. Bandwidth status: OPTIMIZED.",
                    "MEM": "MEM: Cache vectors compressed. Dynamic memory stack optimization completed.",
                    "VIS": "VIS: Activating visual frame capture logic. Display telemetry active.",
                    "SEC": "SEC: Quantum Firewall layer v8.5 active. Encrypted key exchange established."
                }
                
                if parent and hasattr(parent, "_log_sig"):
                    parent._log_sig.emit(logs.get(name, f"HUD: Sub-module {name} activated."))
                
                # Make HUD pulse strongly on press
                self._halo = 230.0
                self.update()
            else:
                super().mousePressEvent(e)
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        W, H = self.width(), self.height()
        cx, cy = W / 2.0, H / 2.0
        fw = min(W, H)

        # 1. Background Rich Holographic Gradient (Vibrant light leak in corners, dark center)
        bg_grad = QRadialGradient(cx, cy, max(W, H) * 0.75)
        bg_grad.setColorAt(0.0, QColor("#02040a")) # Deep Obsidian Blue-Black center
        bg_grad.setColorAt(0.65, QColor("#081226")) # Deep Slate Blue transition
        bg_grad.setColorAt(1.0, QColor("#000104")) # Fades to pitch black at outer edges
        p.fillRect(self.rect(), bg_grad)

        # 2. Tech Grid (Thin cyan-blue grid lines)
        grid_pen = QPen(qcol(C.PRI, 25), 0.5)
        p.setPen(grid_pen)
        grid_size = 28
        for x in range(0, W, grid_size):
            p.drawLine(x, 0, x, H)
        for y in range(0, H, grid_size):
            p.drawLine(0, y, W, y)
            
        # Draw central double axes lines (radar target style)
        p.setPen(QPen(qcol(C.PRI, 60), 0.8))
        p.drawLine(QPointF(cx, 0.0), QPointF(cx, float(H)))
        p.drawLine(QPointF(0.0, cy), QPointF(float(W), cy))

        # Faint circular coordinate grid in the center
        p.setPen(QPen(qcol(C.PRI, 35), 0.5))
        for r_factor in [0.04, 0.08, 0.12, 0.16]:
            r_circ = fw * r_factor
            p.drawEllipse(QRectF(cx - r_circ, cy - r_circ, r_circ * 2.0, r_circ * 2.0))
        
        # Radial crosshair sub-lines
        p.setPen(QPen(qcol(C.PRI, 25), 0.5))
        for deg in [30, 60, 120, 150, 210, 240, 300, 330]:
            rad = math.radians(deg)
            p.drawLine(
                QPointF(cx, cy),
                QPointF(cx + fw * 0.15 * math.cos(rad), cy - fw * 0.15 * math.sin(rad))
            )

        # 3. Layered Text Draw Helper (Double layer with offset shadow to match holographic screen look)
        def draw_layered_text(rect, flags, text, size=7, mono=False, glow_col=C.BORDER_A, main_col=C.TEXT_MED, offset=1):
            p.setFont(_mono_font(size) if mono else _sans_font(size, QFont.Weight.Bold))
            # Shadow glow layer
            p.setPen(QPen(qcol(glow_col, 110), 1.2))
            p.drawText(rect.translated(offset, offset), flags, text)
            # Main front layer
            p.setPen(QPen(qcol(main_col, 245), 1))
            p.drawText(rect, flags, text)

        # 4. Background Concentric Tech Wireframes (Faint thin cyan circles)
        p.setBrush(Qt.BrushStyle.NoBrush)
        for r_factor in [0.08, 0.12, 0.16, 0.20, 0.24, 0.31]:
            r_wire = fw * r_factor
            p.setPen(QPen(qcol(C.PRI, 20), 0.5))
            p.drawEllipse(QRectF(cx - r_wire, cy - r_wire, r_wire * 2.0, r_wire * 2.0))

        # Sonar pulses expanding outward (Neon Pink glow pulses)
        for r_pulse in self._pulses:
            if r_pulse > 0:
                opacity = int(140 * (1.0 - r_pulse / (fw * 0.76)))
                if opacity > 0:
                    p.setPen(QPen(qcol(C.ACC, opacity), 1.0))
                    p.drawEllipse(QRectF(cx - r_pulse, cy - r_pulse, r_pulse * 2.0, r_pulse * 2.0))

        # 5. Inner Ring 1: Thin solid neon pink circle immediately surrounding central logo
        r_inner1 = fw * 0.14
        p.setPen(QPen(qcol(C.BORDER_A, 160), 1.2))
        p.drawEllipse(QRectF(cx - r_inner1, cy - r_inner1, r_inner1 * 2.0, r_inner1 * 2.0))

        # 6. Inner Ring 2 (Segmented Pink, Orange, and Blue)
        r_inner2 = fw * 0.18
        
        # Left segment (135° to 225°) -> Neon Pink (C.BORDER_A)
        p.setPen(QPen(qcol(C.BORDER_A, 220), 4.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.FlatCap))
        p.drawArc(QRectF(cx - r_inner2, cy - r_inner2, r_inner2 * 2.0, r_inner2 * 2.0), 135 * 16, 90 * 16)

        # 4 glowing pink dots inside the pink segment
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(qcol(C.BORDER_A, 255)))
        for deg in [145, 165, 185, 205]:
            rad = math.radians(deg)
            dot_x = cx + r_inner2 * math.cos(rad)
            dot_y = cy - r_inner2 * math.sin(rad)
            p.drawEllipse(QRectF(dot_x - 2.5, dot_y - 2.5, 5.0, 5.0))

        # Top-Right segment (30° to 120°) -> Neon Orange (C.ACC2)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(qcol(C.ACC2, 220), 4.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.FlatCap))
        p.drawArc(QRectF(cx - r_inner2, cy - r_inner2, r_inner2 * 2.0, r_inner2 * 2.0), 30 * 16, 90 * 16)

        # 5 glowing orange status dots on the top-right orange segment
        p.setPen(Qt.PenStyle.NoPen)
        # Pulsing opacity for orange dots
        dot_alpha = int(175 + 80 * math.sin(self._tick * 0.12))
        p.setBrush(QBrush(qcol(C.ACC2, dot_alpha)))
        for deg in [45, 60, 75, 90, 105]:
            rad = math.radians(deg)
            dot_x = cx + r_inner2 * math.cos(rad)
            dot_y = cy - r_inner2 * math.sin(rad)
            p.drawEllipse(QRectF(dot_x - 2.5, dot_y - 2.5, 5.0, 5.0))

        # Bottom-Right segment (225° to 30° / i.e. 225° to 390°) -> Glowing Blue (C.BORDER_B)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(qcol(C.BORDER_B, 180), 1.5))
        p.drawArc(QRectF(cx - r_inner2, cy - r_inner2, r_inner2 * 2.0, r_inner2 * 2.0), 225 * 16, 165 * 16)

        # Radar Sweep Animation (trailing wedge sweeps clockwise)
        p.setBrush(Qt.BrushStyle.NoBrush)
        sweep_angle = self._scan
        sweep_rad = fw * 0.35
        for i in range(45):
            opacity = int(60 * (1.0 - i / 45.0))
            p.setPen(QPen(qcol(C.BORDER_B, opacity), 1.2)) # Blue radar sweep
            ang = sweep_angle - i
            rad_ang = math.radians(ang)
            p.drawLine(
                QPointF(cx, cy),
                QPointF(cx + sweep_rad * math.cos(rad_ang), cy - sweep_rad * math.sin(rad_ang))
            )

        # 7. Middle Ticks and Block Segments (Dynamic Animations)
        # Top Quadrant Ticks: 12 thin radial orange ticks pointing outwards
        # Animate tick length slightly to simulate high-tech resonance/data flow
        t_base_start = fw * 0.20
        t_base_end = fw * 0.22
        p.setPen(QPen(qcol(C.ACC2, 160), 1.0))
        for i in range(12):
            deg = 45 + (90.0 / 11.0) * i
            rad = math.radians(deg)
            pulse_len = 2.0 * math.sin(self._tick * 0.15 + i)
            t_start = t_base_start
            t_end = t_base_end + pulse_len
            p.drawLine(
                QPointF(cx + t_start * math.cos(rad), cy - t_start * math.sin(rad)),
                QPointF(cx + t_end * math.cos(rad), cy - t_end * math.sin(rad))
            )
            
        # Bottom Quadrant Ticks: 12 thin radial blue ticks pointing downwards (pulsing dynamically)
        p.setPen(QPen(qcol(C.BORDER_B, 160), 1.0))
        for i in range(12):
            deg = 225 + (90.0 / 11.0) * i
            rad = math.radians(deg)
            pulse_len = 2.0 * math.cos(self._tick * 0.15 + i)
            t_start = t_base_start
            t_end = t_base_end + pulse_len
            p.drawLine(
                QPointF(cx + t_start * math.cos(rad), cy - t_start * math.sin(rad)),
                QPointF(cx + t_end * math.cos(rad), cy - t_end * math.sin(rad))
            )

        # Segmented blocks at radius fw * 0.245 (Curved block segments counter-rotating!)
        p.setPen(QPen(qcol(C.BORDER_A, 180), 6.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.FlatCap))
        r_mid_block = fw * 0.245
        
        # Counter-rotation speed
        crot = -(self._tick * 0.08) % 360
        
        # Right Segmented Block (Pink): 5 sub-segments rotating counter-clockwise
        for i in range(5):
            start_ang = crot - 42 + i * 18
            p.drawArc(QRectF(cx - r_mid_block, cy - r_mid_block, r_mid_block * 2.0, r_mid_block * 2.0), int(start_ang * 16), 15 * 16)

        # Left Segmented Block (Blue): 4 sub-segments rotating counter-clockwise
        p.setPen(QPen(qcol(C.BORDER_B, 180), 6.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.FlatCap))
        for i in range(4):
            start_ang = crot + 138 + i * 23
            p.drawArc(QRectF(cx - r_mid_block, cy - r_mid_block, r_mid_block * 2.0, r_mid_block * 2.0), int(start_ang * 16), 19 * 16)

        # Rotating Compass Tick Ring (r = fw * 0.37)
        r_comp = fw * 0.37
        p.setPen(QPen(qcol(C.BORDER_B, 60), 0.8))
        p.drawEllipse(QRectF(cx - r_comp, cy - r_comp, r_comp * 2.0, r_comp * 2.0))
        rot_comp = (self._tick * 0.05) % 360 # Slow rotation
        for deg in range(0, 360, 6):
            ang = deg + rot_comp
            rad = math.radians(ang)
            is_major = (deg % 30 == 0)
            t_len = 6.0 if is_major else 3.0
            p.setPen(QPen(qcol(C.BORDER_B if is_major else C.BORDER, 150 if is_major else 70), 1.2 if is_major else 0.8))
            p.drawLine(
                QPointF(cx + r_comp * math.cos(rad), cy - r_comp * math.sin(rad)),
                QPointF(cx + (r_comp + t_len) * math.cos(rad), cy - (r_comp + t_len) * math.sin(rad))
            )

        # 8. Outer Ring (Thick Segmented Plates in Blue & Pink)
        r_outer = fw * 0.33
        thickness = int(fw * 0.04)
        p.setBrush(Qt.BrushStyle.NoBrush)
        
        # Draw outer thin borders for the thick ring (glowing cyan outline)
        p.setPen(QPen(qcol(C.PRI, 60), 0.8))
        p.drawEllipse(QRectF(cx - (r_outer + thickness/2.0 + 2.0), cy - (r_outer + thickness/2.0 + 2.0), (r_outer + thickness/2.0 + 2.0) * 2.0, (r_outer + thickness/2.0 + 2.0) * 2.0))
        p.drawEllipse(QRectF(cx - (r_outer - thickness/2.0 - 2.0), cy - (r_outer - thickness/2.0 - 2.0), (r_outer - thickness/2.0 - 2.0) * 2.0, (r_outer - thickness/2.0 - 2.0) * 2.0))

        # Continuous rotation speed (clockwise)
        rot = (self._tick * 0.12) % 360

        # Draw 4 major plates in glowing electric blue
        p.setPen(QPen(qcol(C.BORDER_B, 240), thickness, Qt.PenStyle.SolidLine, Qt.PenCapStyle.FlatCap))
        p.drawArc(QRectF(cx - r_outer, cy - r_outer, r_outer * 2.0, r_outer * 2.0), int((rot + 10) * 16), 70 * 16)
        p.drawArc(QRectF(cx - r_outer, cy - r_outer, r_outer * 2.0, r_outer * 2.0), int((rot + 280) * 16), 70 * 16)
        p.drawArc(QRectF(cx - r_outer, cy - r_outer, r_outer * 2.0, r_outer * 2.0), int((rot + 190) * 16), 70 * 16)
        p.drawArc(QRectF(cx - r_outer, cy - r_outer, r_outer * 2.0, r_outer * 2.0), int((rot + 100) * 16), 70 * 16)

        # Draw Top-Left Plate detail: 4 glowing pink dots rotating with the plate (~120° to 144°)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(qcol(C.BORDER_A, 255)))
        for i in range(4):
            deg = rot + 120 + i * 8.0
            rad = math.radians(deg)
            dot_x = cx + (r_outer + thickness/2.0 + 7.0) * math.cos(rad)
            dot_y = cy - (r_outer + thickness/2.0 + 7.0) * math.sin(rad)
            p.drawEllipse(QRectF(dot_x - 3.0, dot_y - 3.0, 6.0, 6.0))

        # 9. Inner Rotating Gear Outlines (Pink & Orange accents)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(qcol(C.BORDER_A, 120), 1.0))
        r_gear = fw * 0.29
        p.drawArc(QRectF(cx - r_gear, cy - r_gear, r_gear * 2.0, r_gear * 2.0), int((-rot + 30) * 16), 140 * 16)
        p.drawArc(QRectF(cx - r_gear, cy - r_gear, r_gear * 2.0, r_gear * 2.0), int((-rot + 210) * 16), 100 * 16)

        # 10. Central Soft Holographic Backlight Glow (Pulsing size)
        pulse_glow = fw * 0.15 + 4.0 * math.sin(self._tick * 0.08)
        center_glow = QRadialGradient(cx, cy, pulse_glow)
        center_glow.setColorAt(0.0, qcol(C.BORDER_A, 90)) # Pink glow center
        center_glow.setColorAt(0.5, qcol(C.BORDER_B, 30)) # Blue glow mid
        center_glow.setColorAt(1.0, qcol(C.BG, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(center_glow))
        p.drawEllipse(QRectF(cx - fw * 0.20, cy - fw * 0.20, fw * 0.40, fw * 0.40))

        # 11. Large Sci-Fi "S.A.R.A." Center Text & Logo Area Stack
        # Setup wide character spacing for S.A.R.A.
        # Pulsing text size when speaking
        text_scale = 1.0 + 0.04 * math.sin(self._tick * 0.2) if self.speaking else 1.0
        s_font = QFont("Segoe UI", int(fw * 0.052 * text_scale), QFont.Weight.Black)
        s_font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 5)
        p.setFont(s_font)

        # Glow layer (underneath offset in Neon Pink)
        p.setPen(QPen(qcol(C.BORDER_A, 150), 2))
        p.drawText(QRectF(cx - 150, cy - 20, 300, 45), Qt.AlignmentFlag.AlignCenter, "S.A.R.A.")

        # Bright front layer (White)
        p.setPen(QPen(qcol(C.WHITE, 255), 1))
        p.drawText(QRectF(cx - 150, cy - 19, 300, 45), Qt.AlignmentFlag.AlignCenter, "S.A.R.A.")

        # Foreground text labels inside central area:
        # SYSTEM ACTIVE above S.A.R.A. (Neon Orange)
        draw_layered_text(QRectF(cx - 100, cy - 35, 200, 14), Qt.AlignmentFlag.AlignCenter, "SYSTEM ACTIVE", size=7, glow_col=C.BORDER_A, main_col=C.ACC2)
        
        # NEURAL CORE below S.A.R.A. (Electric Blue)
        draw_layered_text(QRectF(cx - 100, cy + 26, 200, 14), Qt.AlignmentFlag.AlignCenter, "NEURAL CORE", size=7, glow_col=C.BORDER_A, main_col=C.BORDER_B)
        
        # /VOICE LINK STABLE/ below NEURAL CORE (Ice White)
        draw_layered_text(QRectF(cx - 100, cy + 42, 200, 14), Qt.AlignmentFlag.AlignCenter, "/VOICE LINK STABLE/", size=6, glow_col=C.BORDER_B, main_col=C.TEXT_MED)

        # Low-opacity telemetry stack above SYSTEM ACTIVE
        draw_layered_text(QRectF(cx - 100, cy - 64, 200, 11), Qt.AlignmentFlag.AlignCenter, "S.A.R.A. LAUNCH?", size=5, mono=True, main_col=qcol(C.TEXT_DIM, 75))
        draw_layered_text(QRectF(cx - 100, cy - 56, 200, 11), Qt.AlignmentFlag.AlignCenter, "/YES/ S.A.R.A. LAUNCH?", size=5, mono=True, main_col=qcol(C.TEXT_DIM, 75))
        draw_layered_text(QRectF(cx - 100, cy - 48, 200, 11), Qt.AlignmentFlag.AlignCenter, "S.A.R.A. LAUNCHING", size=5, mono=True, main_col=qcol(C.TEXT_DIM, 100))

        # 12. Tech Diagnostic Labels around perimeter (Pink & Orange accents)
        # Top-Center Stack: S.A.R.A. INTERFACE and /TELEMETRY NOMINAL/
        draw_layered_text(QRectF(cx - 150, cy - fw * 0.46, 300, 15), Qt.AlignmentFlag.AlignCenter, "S.A.R.A. INTERFACE", size=8, main_col=C.TEXT_MED)
        draw_layered_text(QRectF(cx - 150, cy - fw * 0.43, 300, 15), Qt.AlignmentFlag.AlignCenter, "/TELEMETRY NOMINAL/", size=7, main_col=C.BORDER_A)

        # Bottom-Center: /SECURITY/
        draw_layered_text(QRectF(cx - 100, cy + fw * 0.44, 200, 15), Qt.AlignmentFlag.AlignCenter, "/SECURITY/", size=8, main_col=C.TEXT_MED)

        # Middle-Left Edge: NET STATUS: OK
        draw_layered_text(QRectF(cx - fw * 0.46, cy - 7, 100, 14), Qt.AlignmentFlag.AlignLeft, "NET STATUS: OK", size=7, main_col=C.TEXT_DIM)
        
        # Middle-Right Edge: /SECURITY/
        draw_layered_text(QRectF(cx + fw * 0.35, cy - 7, 100, 14), Qt.AlignmentFlag.AlignRight, "/SECURITY/", size=7, main_col=C.TEXT_DIM)

        # Lower-Right Edge: CORE ENGINE
        draw_layered_text(QRectF(cx + fw * 0.23, cy + fw * 0.25, 120, 14), Qt.AlignmentFlag.AlignRight, "CORE ENGINE", size=7, main_col=C.BORDER_A)

        # Dynamic diagnostic telemetry seed for corners (simulates live computer readouts)
        random.seed(self._tick // 15)  # Updates periodically
        addr1 = f"0x{random.randint(0x1000, 0xFFFF):04X}"
        addr2 = f"0x{random.randint(0x1000, 0xFFFF):04X}"
        fps = f"FPS {random.randint(59, 61)}"
        baud = f"{random.randint(9600, 115200)} BPS"

        # Top-Left telemetry corner stack
        draw_layered_text(QRectF(15, 20, 200, 12), Qt.AlignmentFlag.AlignLeft, f"SYS_ADDR: {addr1}", size=6, mono=True, main_col=qcol(C.TEXT_DIM, 120))
        draw_layered_text(QRectF(15, 30, 200, 12), Qt.AlignmentFlag.AlignLeft, f"CORE_VAL: {baud}", size=6, mono=True, main_col=qcol(C.TEXT_DIM, 120))
        draw_layered_text(QRectF(15, 40, 200, 12), Qt.AlignmentFlag.AlignLeft, "S.A.R.A. LIVE LOGS", size=6, mono=True, main_col=C.WHITE)
        draw_layered_text(QRectF(22, 50, 200, 12), Qt.AlignmentFlag.AlignLeft, f"STATE_SIG: {fps}", size=6, mono=True, main_col=qcol(C.TEXT_DIM, 140))

        # Bottom-Left corner stack
        draw_layered_text(QRectF(15, H - 75, 200, 12), Qt.AlignmentFlag.AlignLeft, f"MEM_SECT: {addr2}", size=6, mono=True, main_col=qcol(C.TEXT_DIM, 120))
        draw_layered_text(QRectF(15, H - 63, 200, 12), Qt.AlignmentFlag.AlignLeft, "/ONLINE/ STABLE", size=6, mono=True, main_col=qcol(C.TEXT_DIM, 120))
        draw_layered_text(QRectF(15, H - 51, 200, 12), Qt.AlignmentFlag.AlignLeft, "SYSTEM CHECK NOMINAL", size=6, mono=True, main_col=C.WHITE)

        # Bottom-Right corner stack
        draw_layered_text(QRectF(W - 215, H - 75, 200, 12), Qt.AlignmentFlag.AlignRight, "DATA_STREAM: ACTIVE", size=6, mono=True, main_col=qcol(C.TEXT_DIM, 120))
        draw_layered_text(QRectF(W - 215, H - 63, 200, 12), Qt.AlignmentFlag.AlignRight, "/STREAMING/ 44.1KHZ", size=6, mono=True, main_col=qcol(C.TEXT_DIM, 120))
        draw_layered_text(QRectF(W - 215, H - 51, 200, 12), Qt.AlignmentFlag.AlignRight, "S.A.R.A. DEPLOYED", size=6, mono=True, main_col=C.WHITE)

        # Corner Sci-Fi Tech Brackets
        p.setPen(QPen(qcol(C.BORDER, 120), 1.5))
        bracket_len = 24
        margin = 12
        # Top-Left
        p.drawLine(QPointF(margin, margin), QPointF(margin + bracket_len, margin))
        p.drawLine(QPointF(margin, margin), QPointF(margin, margin + bracket_len))
        # Top-Right
        p.drawLine(QPointF(W - margin, margin), QPointF(W - margin - bracket_len, margin))
        p.drawLine(QPointF(W - margin, margin), QPointF(W - margin, margin + bracket_len))
        # Bottom-Left
        p.drawLine(QPointF(margin, H - margin), QPointF(margin + bracket_len, H - margin))
        p.drawLine(QPointF(margin, H - margin), QPointF(margin, H - margin - bracket_len))
        # Bottom-Right
        p.drawLine(QPointF(W - margin, H - margin), QPointF(W - margin - bracket_len, H - margin))
        p.drawLine(QPointF(W - margin, H - margin), QPointF(W - margin, H - margin - bracket_len))

        # 13. Floating dust particles overlay (very subtle)
        for pt in self._particles:
            pt["x"] += pt["vx"] * 0.4
            pt["y"] += pt["vy"] * 0.4
            if pt["x"] < 0 or pt["x"] > W: pt["vx"] *= -1
            if pt["y"] < 0 or pt["y"] > H: pt["vy"] *= -1
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(qcol(C.PRI, int(pt["alpha"] * 0.18))))
            p.drawEllipse(QPointF(pt["x"], pt["y"]), pt["r"] * 0.8, pt["r"] * 0.8)

        # Draw thought burst particles (drifting outwards from core when speaking)
        for bp in self._burst_particles:
            if bp["alpha"] > 0:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QBrush(qcol(C.BORDER_A if bp["alpha"] % 2 == 0 else C.ACC2, int(bp["alpha"] * 0.6))))
                p.drawEllipse(QPointF(bp["x"], bp["y"]), 3.0, 3.0)

        # 14. Floating Glass Menu Buttons (Cyan-blue with pink hover glow)
        r_btn = fw * 0.43
        for idx, ang in enumerate(self._btn_angles):
            rad = math.radians(ang)
            bx = cx + r_btn * math.cos(rad)
            by = cy - r_btn * math.sin(rad)
            
            is_hovered = (self._hovered_btn == idx)
            btn_col = C.BORDER_A if is_hovered else C.BORDER
            btn_alpha = 240 if is_hovered else 110
            
            if is_hovered:
                # Radial glow backing (Neon Pink glow)
                glow = QRadialGradient(bx, by, 28)
                glow.setColorAt(0.0, qcol(C.BORDER_A, 90))
                glow.setColorAt(1.0, qcol(C.BG, 0))
                p.setBrush(QBrush(glow))
                p.setPen(Qt.PenStyle.NoPen)
                p.drawEllipse(QRectF(bx - 28, by - 28, 56, 56))

            # Glass body
            p.setBrush(QBrush(qcol(C.PANEL2, 230 if is_hovered else 110)))
            p.setPen(QPen(qcol(btn_col, btn_alpha), 1.2))
            p.drawEllipse(QRectF(bx - 18, by - 18, 36, 36))
            
            p.setFont(_sans_font(6, QFont.Weight.Bold))
            p.setPen(QPen(qcol(C.WHITE if is_hovered else C.TEXT_MED, 255), 1))
            p.drawText(QRectF(bx - 18, by - 9, 36, 18), Qt.AlignmentFlag.AlignCenter, self._btn_names[idx])

        # 15. State Label (Pulsing colors based on state)
        sy = cy + fw * 0.40
        if self.muted:
            txt, col = "⊘  MUTED",     qcol(C.BORDER_A)
        elif self.speaking:
            txt, col = "●  SPEAKING",  qcol(C.BORDER_A) # Pink when speaking
        elif self.state == "THINKING":
            sym = "◈" if self._blink else "◇"
            txt, col = f"{sym}  THINKING",   qcol(C.ACC2) # Orange when thinking
        elif self.state == "PROCESSING":
            sym = "▷" if self._blink else "▶"
            txt, col = f"{sym}  PROCESSING", qcol(C.ACC2)
        elif self.state == "LISTENING":
            sym = "●" if self._blink else "○"
            txt, col = f"{sym}  LISTENING",  qcol(C.BORDER_B) # Blue when listening
        else:
            sym = "●" if self._blink else "○"
            txt, col = f"{sym}  {self.state}", qcol(C.PRI)

        p.setPen(QPen(col, 1))
        p.setFont(_mono_font(10, QFont.Weight.Bold))
        p.drawText(QRectF(0, sy, W, 22), Qt.AlignmentFlag.AlignCenter, txt)

        # 16. Audio Waveform (Vibrant multi-color voice reactions)
        wy = sy + 24
        N, bw = 36, 8
        wx0 = (W - N * bw) / 2
        for i in range(N):
            if self.muted:
                hgt, cl = 2, qcol(C.BORDER_A)
            elif self.speaking:
                hgt = random.randint(3, 20)
                # Multi-color sound wave: Pink for high peaks, Orange for medium, Blue for low
                if hgt > 13:
                    cl = qcol(C.BORDER_A) # Pink peak
                elif hgt > 7:
                    cl = qcol(C.ACC2) # Orange mid
                else:
                    cl = qcol(C.BORDER_B) # Blue low
            else:
                hgt = int(3 + 3 * math.sin(self._tick * 0.09 + i * 0.6))
                # Cycle color horizontally
                wave_val = math.sin(self._tick * 0.05 + i * 0.1)
                cl = qcol(C.BORDER_B if wave_val > 0.3 else (C.BORDER_A if wave_val < -0.3 else C.BORDER))
            p.fillRect(QRectF(wx0 + i * bw, wy + 18 - hgt, bw - 1, hgt), cl)


class MetricBar(QWidget):
    def __init__(self, label: str, color: str = C.PRI, parent=None):
        super().__init__(parent)
        self._label = label
        self._color = color
        self._value = 0.0       # 0–100
        self._text  = "--"
        self.setFixedHeight(38)
        self.setMinimumWidth(80)

    def set_value(self, pct: float, text: str):
        self._value = max(0.0, min(100.0, pct))
        self._text  = text
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()

        # Capsule Panel Body
        p.setBrush(QBrush(qcol(C.PANEL2, 120)))
        p.setPen(QPen(qcol(C.BORDER, 140), 1))
        p.drawRoundedRect(QRectF(1, 1, W - 2, H - 2), 6, 6)

        bar_h   = 4
        bar_y   = H - bar_h - 6
        bar_w   = W - 14
        bar_x   = 7
        fill_w  = int(bar_w * self._value / 100)

        # Empty bar track
        p.setBrush(QBrush(qcol(C.DARK, 230)))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(QRectF(bar_x, bar_y, bar_w, bar_h), bar_h/2, bar_h/2)

        if self._value > 85:
            bar_col = qcol(C.RED)
            grad = QLinearGradient(bar_x, bar_y, bar_x + fill_w, bar_y)
            grad.setColorAt(0.0, qcol(C.ACC2, 180))
            grad.setColorAt(1.0, qcol(C.RED))
        elif self._value > 65:
            bar_col = qcol(C.ACC)
            grad = QLinearGradient(bar_x, bar_y, bar_x + fill_w, bar_y)
            grad.setColorAt(0.0, qcol(C.ACC2, 180))
            grad.setColorAt(1.0, qcol(C.ACC))
        else:
            bar_col = qcol(self._color)
            grad = QLinearGradient(bar_x, bar_y, bar_x + fill_w, bar_y)
            grad.setColorAt(0.0, qcol(C.ACC2, 100))
            grad.setColorAt(1.0, qcol(self._color))

        # Filled track progress
        if fill_w > 0:
            p.setBrush(QBrush(grad))
            p.drawRoundedRect(QRectF(bar_x, bar_y, fill_w, bar_h), bar_h/2, bar_h/2)

        p.setFont(_sans_font(8, QFont.Weight.Bold))
        p.setPen(QPen(qcol(C.TEXT_DIM), 1))
        p.drawText(QRectF(9, 5, 50, 14), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self._label)

        p.setFont(_mono_font(9, QFont.Weight.Bold))
        p.setPen(QPen(bar_col if self._text != "--" else qcol(C.TEXT_DIM), 1))
        p.drawText(QRectF(0, 4, W - 8, 16), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, self._text)


class OscilloscopeWidget(QWidget):
    def __init__(self, label: str, color: str = C.PRI, max_points: int = 50, parent=None):
        super().__init__(parent)
        self._label = label
        self._color = color
        self._max_points = max_points
        self._history: list[float] = [0.0] * max_points
        self.setFixedHeight(68)
        self.setMinimumWidth(100)

    def set_value(self, pct: float, text: str = None):
        self._history.pop(0)
        self._history.append(max(0.0, min(100.0, pct)))
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()

        p.setBrush(QBrush(qcol(C.PANEL2, 120)))
        p.setPen(QPen(qcol(C.BORDER, 140), 1))
        p.drawRoundedRect(QRectF(1, 1, W - 2, H - 2), 6, 6)

        p.setPen(QPen(qcol(C.BORDER, 50), 1, Qt.PenStyle.DashLine))
        p.drawLine(0, int(H * 0.35), W, int(H * 0.35))
        p.drawLine(0, int(H * 0.7), W, int(H * 0.7))

        sweep_x = (int(time.time() * 25) % W)
        p.setPen(QPen(qcol(self._color, 40), 1))
        p.drawLine(sweep_x, 2, sweep_x, H - 2)

        if len(self._history) > 1:
            path = QPainterPath()
            step = W / (self._max_points - 1)
            first = True
            for i, val in enumerate(self._history):
                x = i * step
                y = H - 8 - ((val / 100.0) * (H - 22))
                if first:
                    path.moveTo(x, y)
                    first = False
                else:
                    path.lineTo(x, y)

            # Draw vertical gradient fill
            fill_path = QPainterPath(path)
            fill_path.lineTo(W, H - 2)
            fill_path.lineTo(0, H - 2)
            fill_path.closeSubpath()
            grad = QLinearGradient(0, 0, 0, H)
            grad.setColorAt(0.0, qcol(self._color, 75))
            grad.setColorAt(0.6, qcol(C.ACC2, 25))
            grad.setColorAt(1.0, qcol(C.DARK, 0))
            p.setBrush(QBrush(grad))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawPath(fill_path)

            # Glow stroke underneath
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(qcol(self._color, 50), 4.5))
            p.drawPath(path)

            # Solid neon core stroke
            p.setPen(QPen(qcol(self._color, 230), 1.6))
            p.drawPath(path)

        p.setFont(_sans_font(8, QFont.Weight.Bold))
        p.setPen(QPen(qcol(C.TEXT_DIM), 1))
        p.drawText(QRectF(9, 4, 80, 14), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self._label)

        curr_val = self._history[-1]
        p.setFont(_mono_font(9, QFont.Weight.Bold))
        p.setPen(QPen(qcol(self._color), 1))
        p.drawText(QRectF(0, 4, W - 9, 14), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, f"{curr_val:.0f}%")


class LogWidget(QTextEdit):
    _sig = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setFont(_mono_font(9))
        self.setStyleSheet(f"""
            QTextEdit {{
                background: rgba(10, 5, 22, 160);
                color: {C.TEXT};
                border: 1px solid rgba(0, 212, 255, 90);
                border-radius: 6px;
                padding: 6px;
                selection-background-color: {C.PRI_GHO};
            }}
            QScrollBar:vertical {{
                background: rgba(2, 1, 4, 80);
                width: 6px;
                border: none;
            }}
            QScrollBar::handle:vertical {{
                background: rgba(255, 0, 127, 160);
                border-radius: 3px;
                min-height: 20px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {C.ACC};
            }}
        """)
        self._queue: list[str] = []
        self._typing  = False
        self._text    = ""
        self._pos     = 0
        self._tag     = "sys"
        self._tmr = QTimer(self)
        self._tmr.timeout.connect(self._step)
        self._sig.connect(self._enqueue)

    def append_log(self, text: str):
        self._sig.emit(text)

    def _enqueue(self, text: str):
        self._queue.append(text)
        if not self._typing:
            self._next()

    def _next(self):
        if not self._queue:
            self._typing = False
            return
        self._typing = True
        self._text   = self._queue.pop(0)
        self._pos    = 0
        tl = self._text.lower()
        if   tl.startswith("you:"):    self._tag = "you"
        elif tl.startswith("sara:") or tl.startswith("sara:"): self._tag = "ai"
        elif tl.startswith("file:"):   self._tag = "file"
        elif "err" in tl:              self._tag = "err"
        else:                          self._tag = "sys"
        self._tmr.start(5)

    def _step(self):
        if self._pos < len(self._text):
            ch  = self._text[self._pos]
            cur = self.textCursor()
            fmt = cur.charFormat()
            col = {
                "you":  qcol(C.WHITE),
                "ai":   qcol(C.PRI),
                "err":  qcol(C.RED),
                "file": qcol(C.GREEN),
                "sys":  qcol(C.ACC2),
            }.get(self._tag, qcol(C.TEXT))
            fmt.setForeground(QBrush(col))
            cur.movePosition(cur.MoveOperation.End)
            cur.insertText(ch, fmt)
            self.setTextCursor(cur)
            self.ensureCursorVisible()
            self._pos += 1
        else:
            self._tmr.stop()
            cur = self.textCursor()
            cur.movePosition(cur.MoveOperation.End)
            cur.insertText("\n")
            self.setTextCursor(cur)
            self.ensureCursorVisible()
            QTimer.singleShot(15, self._next)


_FILE_ICONS = {
    "image":   ("🖼", "#00f0ff"), "video":   ("🎬", "#ff00aa"),
    "audio":   ("🎵", "#9b5de5"), "pdf":     ("📄", "#ff2a54"),
    "word":    ("📝", "#4488ff"), "excel":   ("📊", "#00f5d4"),
    "code":    ("💻", "#ffcc00"), "archive": ("📦", "#ff8844"),
    "pptx":    ("📊", "#ff6622"), "text":    ("📃", "#aaaaaa"),
    "data":    ("🔧", "#88ddff"), "unknown": ("📎", "#888888"),
}
_EXT_TO_CAT = {
    **dict.fromkeys(["jpg","jpeg","png","gif","webp","bmp","tiff","svg","ico"], "image"),
    **dict.fromkeys(["mp4","avi","mov","mkv","wmv","flv","webm","m4v"],         "video"),
    **dict.fromkeys(["mp3","wav","ogg","m4a","aac","flac","wma","opus"],        "audio"),
    **dict.fromkeys(["pdf"],                                                     "pdf"),
    **dict.fromkeys(["doc","docx"],                                              "word"),
    **dict.fromkeys(["xls","xlsx","ods"],                                        "excel"),
    **dict.fromkeys(["ppt","pptx"],                                              "pptx"),
    **dict.fromkeys(["py","js","ts","jsx","tsx","html","css","java","c","cpp",
                     "cs","go","rs","rb","php","swift","kt","sh","sql","lua"],   "code"),
    **dict.fromkeys(["zip","rar","tar","gz","7z","bz2","xz"],                   "archive"),
    **dict.fromkeys(["txt","md","rst","log"],                                    "text"),
    **dict.fromkeys(["csv","tsv","json","xml"],                                  "data"),
}

def _file_category(path: Path) -> str:
    return _EXT_TO_CAT.get(path.suffix.lower().lstrip("."), "unknown")

def _fmt_size(size: int) -> str:
    if   size < 1024:    return f"{size} B"
    elif size < 1024**2: return f"{size/1024:.1f} KB"
    elif size < 1024**3: return f"{size/1024**2:.1f} MB"
    else:                return f"{size/1024**3:.1f} GB"


class FileDropZone(QWidget):
    file_selected = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(100)
        self._current_file: str | None = None
        self._hovering  = False
        self._drag_over = False
        self._dash_offset = 0.0
        self._anim_tmr = QTimer(self)
        self._anim_tmr.timeout.connect(self._animate)
        self._anim_tmr.start(40)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self._canvas = _DropCanvas(self)
        layout.addWidget(self._canvas)

    def _animate(self):
        self._dash_offset = (self._dash_offset + 0.8) % 20
        self._canvas.update()

    def dragEnterEvent(self, e: QDragEnterEvent):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
            self._drag_over = True; self._canvas.update()

    def dragLeaveEvent(self, e):
        self._drag_over = False; self._canvas.update()

    def dropEvent(self, e: QDropEvent):
        self._drag_over = False
        urls = e.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            if Path(path).is_file():
                self._set_file(path)
        self._canvas.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._browse()

    def enterEvent(self, e):
        self._hovering = True; self._canvas.update()

    def leaveEvent(self, e):
        self._hovering = False; self._canvas.update()

    def current_file(self) -> str | None:
        return self._current_file

    def clear_file(self):
        self._current_file = None; self._canvas.update()

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select a file for SARA", str(Path.home()),
            "All Files (*.*);;"
            "Images (*.jpg *.jpeg *.png *.gif *.webp *.bmp *.svg);;"
            "Documents (*.pdf *.docx *.txt *.md *.pptx);;"
            "Data (*.csv *.xlsx *.json *.xml);;"
            "Code (*.py *.js *.ts *.html *.css *.java *.cpp *.go);;"
            "Audio (*.mp3 *.wav *.ogg *.m4a *.aac *.flac);;"
            "Video (*.mp4 *.avi *.mov *.mkv *.wmv *.webm);;"
            "Archives (*.zip *.rar *.tar *.gz *.7z)",
        )
        if path:
            self._set_file(path)

    def _set_file(self, path: str):
        self._current_file = path
        self._canvas.update()
        self.file_selected.emit(path)


class _DropCanvas(QWidget):
    def __init__(self, zone: FileDropZone):
        super().__init__(zone)
        self._z = zone

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        z    = self._z
        W, H = self.width(), self.height()
        pad  = 6
        rect = QRectF(pad, pad, W - pad * 2, H - pad * 2)

        bg_col = qcol("#0d061c" if z._drag_over else ("#120926" if z._hovering else C.PANEL), 140)
        p.setBrush(QBrush(bg_col)); p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(rect, 6, 6)

        if z._current_file:   border_col = qcol(C.GREEN, 200)
        elif z._drag_over:    border_col = qcol(C.PRI, 230)
        elif z._hovering:     border_col = qcol(C.BORDER_B, 200)
        else:                 border_col = qcol(C.BORDER, 160)

        pen = QPen(border_col, 1.5, Qt.PenStyle.DashLine)
        pen.setDashOffset(z._dash_offset)
        p.setPen(pen); p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(rect, 6, 6)

        if z._current_file:   self._paint_file(p, W, H)
        elif z._drag_over:    self._paint_drag_over(p, W, H)
        else:                 self._paint_idle(p, W, H, z._hovering)

    def _paint_idle(self, p, W, H, hover):
        cx, cy = W / 2, H / 2
        col = qcol(C.BORDER_B if not hover else C.PRI)
        p.setPen(QPen(col, 2)); p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawLine(QPointF(cx, cy - 14), QPointF(cx, cy + 4))
        p.drawLine(QPointF(cx - 8, cy - 6), QPointF(cx, cy - 14))
        p.drawLine(QPointF(cx + 8, cy - 6), QPointF(cx, cy - 14))
        p.drawLine(QPointF(cx - 14, cy + 4), QPointF(cx + 14, cy + 4))
        p.setFont(_sans_font(8))
        p.setPen(QPen(qcol(C.TEXT_MED if not hover else C.TEXT), 1))
        p.drawText(QRectF(0, cy + 8, W, 16), Qt.AlignmentFlag.AlignCenter,
                   "Drop file here  or  Click to Browse")
        p.setFont(_sans_font(7))
        p.setPen(QPen(qcol("#4a3674"), 1))
        p.drawText(QRectF(0, cy + 24, W, 14), Qt.AlignmentFlag.AlignCenter,
                   "Images · Video · Audio · PDF · Docs · Code · Data")

    def _paint_drag_over(self, p, W, H):
        cx, cy = W / 2, H / 2
        p.setFont(_mono_font(20))
        p.setPen(QPen(qcol(C.PRI), 1))
        p.drawText(QRectF(0, cy - 24, W, 32), Qt.AlignmentFlag.AlignCenter, "⬇")
        p.setFont(_sans_font(8, QFont.Weight.Bold))
        p.setPen(QPen(qcol(C.PRI), 1))
        p.drawText(QRectF(0, cy + 12, W, 16), Qt.AlignmentFlag.AlignCenter, "Release to load")

    def _paint_file(self, p, W, H):
        path = Path(self._z._current_file)
        cat  = _file_category(path)
        icon, icon_col = _FILE_ICONS.get(cat, _FILE_ICONS["unknown"])
        size_str = _fmt_size(path.stat().st_size)
        ext_str  = path.suffix.upper().lstrip(".") or "FILE"

        block_x, block_w = 10, 60
        p.setFont(QFont("Segoe UI Emoji", 22) if _OS == "Windows" else QFont("Arial", 22))
        p.setPen(QPen(qcol(icon_col), 1))
        p.drawText(QRectF(block_x, 0, block_w, H), Qt.AlignmentFlag.AlignCenter, icon)

        tx = block_x + block_w + 6
        tw = W - tx - 38

        p.setFont(_sans_font(8, QFont.Weight.Bold))
        p.setPen(QPen(qcol(C.WHITE), 1))
        name = path.name if len(path.name) <= 34 else path.name[:31] + "..."
        p.drawText(QRectF(tx, H * 0.18, tw, 16),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, name)

        p.setFont(_sans_font(7))
        p.setPen(QPen(qcol(C.TEXT_DIM), 1))
        p.drawText(QRectF(tx, H * 0.18 + 18, tw, 14),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   f"{ext_str}  ·  {size_str}")

        p.setFont(_mono_font(6))
        p.setPen(QPen(qcol("#664a9c"), 1))
        par = str(path.parent)
        if len(par) > 42: par = "…" + par[-41:]
        p.drawText(QRectF(tx, H * 0.18 + 34, tw, 12),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, par)

        p.setFont(_sans_font(9, QFont.Weight.Bold))
        p.setPen(QPen(qcol(C.RED, 180), 1))
        p.drawText(QRectF(W - 34, 0, 28, H), Qt.AlignmentFlag.AlignCenter, "✕")

    def mousePressEvent(self, e):
        z = self._z
        if z._current_file and e.pos().x() > self.width() - 34:
            z.clear_file()
        else:
            z.mousePressEvent(e)


class SetupOverlay(QWidget):
    done = pyqtSignal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            SetupOverlay {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #120a24, stop:1 #06030b);
                border: 1.5px solid rgba(255, 0, 127, 140);
                border-radius: 10px;
            }}
        """)

        detected = {"darwin": "mac", "windows": "windows"}.get(
            _OS.lower(), "linux"
        )
        self._sel_os = detected

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 22, 30, 22)
        layout.setSpacing(8)

        def _lbl(txt, font_size=9, bold=False, color=C.PRI,
                 align=Qt.AlignmentFlag.AlignCenter):
            w = QLabel(txt)
            w.setAlignment(align)
            w.setFont(_sans_font(font_size, QFont.Weight.Bold if bold else QFont.Weight.Normal))
            w.setStyleSheet(f"color: {color}; background: transparent;")
            return w

        layout.addWidget(_lbl("◈  INITIALISATION REQUIRED", 13, True))
        layout.addWidget(_lbl("Configure S.A.R.A. before first boot.", 9, color=C.TEXT_MED))
        layout.addSpacing(6)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {C.BORDER};"); layout.addWidget(sep)
        layout.addSpacing(4)

        layout.addWidget(_lbl("GEMINI API KEY", 8, color=C.TEXT_DIM,
                               align=Qt.AlignmentFlag.AlignLeft))
        self._key_input = QLineEdit()
        self._key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._key_input.setPlaceholderText("AIza…")
        self._key_input.setFont(_mono_font(10))
        self._key_input.setFixedHeight(32)
        self._key_input.setStyleSheet(f"""
            QLineEdit {{
                background: #090515; color: #ffffff;
                border: 1px solid rgba(0, 212, 255, 120); border-radius: 4px; padding: 4px 8px;
            }}
            QLineEdit:focus {{
                border: 1px solid {C.PRI};
                background: #140b28;
            }}
        """)
        layout.addWidget(self._key_input)
        layout.addSpacing(12)

        sep2 = QFrame(); sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet(f"color: {C.BORDER};"); layout.addWidget(sep2)
        layout.addSpacing(4)

        layout.addWidget(_lbl("OPERATING SYSTEM", 8, color=C.TEXT_DIM,
                               align=Qt.AlignmentFlag.AlignLeft))
        det_name = {"windows": "Windows", "mac": "macOS", "linux": "Linux"}[detected]
        layout.addWidget(_lbl(f"Auto-detected: {det_name}", 8, color=C.GREEN,
                               align=Qt.AlignmentFlag.AlignLeft))

        os_row = QHBoxLayout(); os_row.setSpacing(6)
        self._os_btns: dict[str, QPushButton] = {}
        for key, label in [("windows","⊞  Windows"),("mac","🍎  macOS"),("linux","🐧  Linux")]:
            btn = QPushButton(label)
            btn.setFont(_sans_font(9, QFont.Weight.Bold))
            btn.setFixedHeight(32)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _, k=key: self._sel(k))
            os_row.addWidget(btn)
            self._os_btns[key] = btn
        layout.addLayout(os_row)
        self._sel(detected)
        layout.addSpacing(12)

        init_btn = QPushButton("▸  INITIALISE SYSTEMS")
        init_btn.setFont(_sans_font(10, QFont.Weight.Bold))
        init_btn.setFixedHeight(36)
        init_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        init_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {C.PRI};
                border: 1px solid rgba(0, 240, 255, 120); border-radius: 4px;
            }}
            QPushButton:hover {{
                background: rgba(0, 240, 255, 30); border: 1px solid {C.PRI};
            }}
            QPushButton:pressed {{
                background: {C.PRI}; color: {C.DARK};
            }}
        """)
        init_btn.clicked.connect(self._submit)
        layout.addWidget(init_btn)

    def _sel(self, key: str):
        self._sel_os = key
        pal = {"windows":(C.PRI,"#020b12"),"mac":(C.BORDER_A,"#1c0211"),"linux":(C.GREEN,"#02120b")}
        for k, btn in self._os_btns.items():
            if k == key:
                fg, bg = pal[k]
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: {fg}; color: {bg};
                        border: none; border-radius: 4px; font-weight: bold;
                    }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: #090515; color: {C.TEXT_DIM};
                        border: 1px solid {C.BORDER}; border-radius: 4px;
                    }}
                    QPushButton:hover {{ color: {C.TEXT}; border: 1px solid {C.BORDER_B}; }}
                    QPushButton:pressed {{ background: #140b28; }}
                """)

    def _submit(self):
        key = self._key_input.text().strip()
        if not key:
            self._key_input.setStyleSheet(
                self._key_input.styleSheet() +
                f" QLineEdit {{ border: 1px solid {C.RED}; }}"
            )
            return
        self.done.emit(key, self._sel_os)


class MainWindow(QMainWindow):
    _log_sig   = pyqtSignal(str)
    _state_sig = pyqtSignal(str)

    def __init__(self, face_path: str):
        super().__init__()
        self.setWindowTitle("S.A.R.A.")
        self.setMinimumSize(_MIN_W, _MIN_H)
        self.resize(_DEFAULT_W, _DEFAULT_H)

        screen = QApplication.primaryScreen().availableGeometry()
        self.move(
            (screen.width()  - _DEFAULT_W) // 2,
            (screen.height() - _DEFAULT_H) // 2,
        )

        self.on_text_command  = None
        self._muted           = False
        self._current_file: str | None = None

        central = QWidget()
        central.setStyleSheet(f"background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #05020c, stop:0.5 #0b061b, stop:1 #05020c);")
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_header())

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        self._left_panel = self._build_left_panel()
        body.addWidget(self._left_panel, stretch=0)

        self.hud = HudCanvas(face_path)
        self.hud.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        body.addWidget(self.hud, stretch=5)

        self._right_panel = self._build_right_panel()
        body.addWidget(self._right_panel, stretch=0)

        root.addLayout(body, stretch=1)
        root.addWidget(self._build_footer())

        self._clock_tmr = QTimer(self)
        self._clock_tmr.timeout.connect(self._tick_clock)
        self._clock_tmr.start(1000)
        self._tick_clock()

        self._metric_tmr = QTimer(self)
        self._metric_tmr.timeout.connect(self._update_metrics)
        self._metric_tmr.start(2000)
        self._update_metrics()

        self._log_sig.connect(self._log.append_log)
        self._state_sig.connect(self._apply_state)

        self._overlay: SetupOverlay | None = None
        self._ready = self._check_config()
        if not self._ready:
            self._show_setup()

        sc_mute = QShortcut(QKeySequence("F4"), self)
        sc_mute.activated.connect(self._toggle_mute)
        sc_full = QShortcut(QKeySequence("F11"), self)
        sc_full.activated.connect(self._toggle_fullscreen)

    def _toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._overlay and self._overlay.isVisible():
            ow, oh = 460, 390
            cw = self.centralWidget()
            self._overlay.setGeometry(
                (cw.width()  - ow) // 2,
                (cw.height() - oh) // 2,
                ow, oh,
            )

    def _update_metrics(self):
        snap = _metrics.snapshot()

        # CPU
        cpu = snap["cpu"]
        self._bar_cpu.set_value(cpu, f"{cpu:.0f}%")

        # MEM
        mem = snap["mem"]
        self._bar_mem.set_value(mem, f"{mem:.0f}%")

        # NET
        net = snap["net"]
        if net < 1.0:
            net_str = f"{net*1024:.0f}KB/s"
        else:
            net_str = f"{net:.1f}MB/s"
        net_pct = min(100, net * 10)  # 10 MB/s = %100
        self._bar_net.set_value(net_pct, net_str)

        # GPU
        gpu = snap["gpu"]
        if gpu >= 0:
            self._bar_gpu.set_value(gpu, f"{gpu:.0f}%")
        else:
            self._bar_gpu.set_value(0, "N/A")

        # TMP
        tmp = snap["tmp"]
        if tmp >= 0:
            tmp_pct = min(100, (tmp / 100) * 100)
            self._bar_tmp.set_value(tmp_pct, f"{tmp:.0f}°C")
        else:
            self._bar_tmp.set_value(0, "N/A")

        try:
            boot_t  = psutil.boot_time()
            elapsed = time.time() - boot_t
            h = int(elapsed // 3600)
            m = int((elapsed % 3600) // 60)
            self._uptime_lbl.setText(f"UP  {h:02d}:{m:02d}")
        except Exception:
            self._uptime_lbl.setText("UP  --:--")

        try:
            proc_count = len(psutil.pids())
            self._proc_lbl.setText(f"PROC  {proc_count}")
        except Exception:
            self._proc_lbl.setText("PROC  --")


    def _build_header(self) -> QWidget:
        w = QWidget()
        w.setFixedHeight(54)
        w.setStyleSheet(f"background: rgba(12, 6, 24, 200); border-bottom: 1px solid rgba(255, 0, 170, 70);")
        lay = QHBoxLayout(w)
        lay.setContentsMargins(16, 0, 16, 0)

        def _badge(txt, color=C.TEXT_MED):
            l = QLabel(txt)
            l.setFont(_sans_font(8))
            l.setStyleSheet(f"color: {color}; background: transparent;")
            return l

        lay.addWidget(_badge("S.A.R.A.", C.PRI_DIM))
        lay.addStretch()

        right_col = QVBoxLayout(); right_col.setSpacing(2)
        self._clock_lbl = QLabel("00:00:00")
        self._clock_lbl.setFont(_mono_font(14, QFont.Weight.Bold))
        self._clock_lbl.setStyleSheet(f"color: {C.PRI}; background: transparent;")
        self._clock_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        right_col.addWidget(self._clock_lbl)
        self._date_lbl = QLabel("")
        self._date_lbl.setFont(_sans_font(7))
        self._date_lbl.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
        self._date_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        right_col.addWidget(self._date_lbl)
        lay.addLayout(right_col)
        return w

    def _tick_clock(self):
        self._clock_lbl.setText(time.strftime("%H:%M:%S"))
        self._date_lbl.setText(time.strftime("%a %d %b %Y"))

    def _build_left_panel(self) -> QWidget:
        w = QWidget()
        w.setFixedWidth(_LEFT_W)
        w.setStyleSheet(f"background: rgba(12, 6, 24, 180); border-right: 1px solid rgba(0, 212, 255, 60);")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(8, 10, 8, 10)
        lay.setSpacing(6)

        hdr = QLabel("◈ SYS MONITOR")
        hdr.setFont(_sans_font(8, QFont.Weight.Bold))
        hdr.setStyleSheet(f"color: {C.PRI}; background: transparent; "
                          f"border-bottom: 1px solid {C.BORDER}; padding-bottom: 4px;")
        lay.addWidget(hdr)
        lay.addSpacing(2)

        self._bar_cpu = OscilloscopeWidget("CPU", C.PRI)
        self._bar_mem = OscilloscopeWidget("MEM", C.ACC2)
        self._bar_net = MetricBar("NET", C.GREEN)
        self._bar_gpu = MetricBar("GPU", C.ACC)
        self._bar_tmp = MetricBar("TMP", "#ff4a77")

        for bar in [self._bar_cpu, self._bar_mem, self._bar_net,
                    self._bar_gpu, self._bar_tmp]:
            lay.addWidget(bar)

        lay.addSpacing(4)

        info_panel = QWidget()
        info_panel.setStyleSheet(
            f"background: rgba(16, 8, 32, 100); border: 1px solid rgba(255, 0, 127, 70); border-radius: 4px;"
        )
        ip_lay = QVBoxLayout(info_panel)
        ip_lay.setContentsMargins(6, 5, 6, 5)
        ip_lay.setSpacing(3)

        self._uptime_lbl = QLabel("UP  --:--")
        self._uptime_lbl.setFont(_sans_font(8, QFont.Weight.Bold))
        self._uptime_lbl.setStyleSheet(f"color: {C.GREEN}; background: transparent; border: none;")
        ip_lay.addWidget(self._uptime_lbl)

        self._proc_lbl = QLabel("PROC  --")
        self._proc_lbl.setFont(_sans_font(8))
        self._proc_lbl.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent; border: none;")
        ip_lay.addWidget(self._proc_lbl)

        os_name = {"Windows": "WIN", "Darwin": "macOS", "Linux": "LINUX"}.get(_OS, _OS.upper())
        os_lbl = QLabel(f"OS  {os_name}")
        os_lbl.setFont(_sans_font(8))
        os_lbl.setStyleSheet(f"color: {C.ACC2}; background: transparent; border: none;")
        ip_lay.addWidget(os_lbl)

        lay.addWidget(info_panel)
        lay.addStretch()

        for txt, col in [
            ("AI CORE\nACTIVE",     C.GREEN),
            ("SEC\nCLEARED",        C.PRI),
            ("S.A.R.A.\nSYSTEM",    C.TEXT_DIM),
        ]:
            lbl = QLabel(txt)
            lbl.setFont(_sans_font(7, QFont.Weight.Bold))
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(
                f"color: {col}; background: rgba(16, 8, 32, 100);"
                f"border: 1px solid rgba(255, 0, 127, 70); border-radius: 3px; padding: 4px;"
            )
            lay.addWidget(lbl)

        return w
        
    def _build_right_panel(self) -> QWidget:
        w = QWidget()
        w.setFixedWidth(_RIGHT_W)
        w.setStyleSheet(f"background: rgba(12, 6, 24, 180); border-left: 1px solid rgba(255, 0, 127, 60);")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(6)

        def _sec(txt):
            l = QLabel(f"▸ {txt}")
            l.setFont(_sans_font(7, QFont.Weight.Bold))
            l.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent;")
            return l

        lay.addWidget(_sec("ACTIVITY LOG"))
        self._log = LogWidget()
        lay.addWidget(self._log, stretch=1)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {C.BORDER}; margin: 2px 0;")
        lay.addWidget(sep)

        lay.addWidget(_sec("FILE UPLOAD"))
        self._drop_zone = FileDropZone()
        self._drop_zone.file_selected.connect(self._on_file_selected)
        lay.addWidget(self._drop_zone)

        self._file_hint = QLabel("No file loaded — drop or click above to upload")
        self._file_hint.setFont(_sans_font(7))
        self._file_hint.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent;")
        self._file_hint.setWordWrap(True)
        lay.addWidget(self._file_hint)

        sep2 = QFrame(); sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet(f"color: {C.BORDER}; margin: 2px 0;")
        lay.addWidget(sep2)

        lay.addWidget(_sec("COMMAND INPUT"))
        lay.addLayout(self._build_input_row())

        self._mute_btn = QPushButton("🎙  MICROPHONE ACTIVE")
        self._mute_btn.setFixedHeight(30)
        self._mute_btn.setFont(_sans_font(8, QFont.Weight.Bold))
        self._mute_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._mute_btn.clicked.connect(self._toggle_mute)
        self._style_mute_btn()
        lay.addWidget(self._mute_btn)

        fs_btn = QPushButton("⛶  FULLSCREEN  [F11]")
        fs_btn.setFixedHeight(26)
        fs_btn.setFont(_sans_font(7))
        fs_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        fs_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {C.TEXT_MED};
                border: 1px solid {C.BORDER}; border-radius: 4px;
            }}
            QPushButton:hover {{
                color: {C.PRI}; border: 1px solid {C.BORDER_B};
            }}
            QPushButton:pressed {{
                background: {C.PRI_GHO};
            }}
        """)
        fs_btn.clicked.connect(self._toggle_fullscreen)
        lay.addWidget(fs_btn)

        return w

    def _build_input_row(self) -> QHBoxLayout:
        row = QHBoxLayout(); row.setSpacing(5)
        self._input = QLineEdit()
        self._input.setPlaceholderText("Type a command or question…")
        self._input.setFont(_sans_font(9))
        self._input.setFixedHeight(30)
        self._input.setStyleSheet(f"""
            QLineEdit {{
                background: rgba(12, 6, 24, 200); color: #ffffff;
                border: 1px solid rgba(0, 212, 255, 100); border-radius: 6px; padding: 4px 8px;
            }}
            QLineEdit:focus {{
                border: 1px solid rgba(0, 240, 255, 200);
                background: rgba(20, 10, 38, 220);
            }}
        """)
        self._input.returnPressed.connect(self._send)
        row.addWidget(self._input)

        send = QPushButton("▸")
        send.setFixedSize(30, 30)
        send.setFont(_sans_font(11, QFont.Weight.Bold))
        send.setCursor(Qt.CursorShape.PointingHandCursor)
        send.setStyleSheet(f"""
            QPushButton {{
                background: rgba(24, 14, 42, 180); color: {C.PRI};
                border: 1px solid rgba(255, 0, 127, 120); border-radius: 6px;
            }}
            QPushButton:hover {{ background: rgba(255, 0, 127, 60); border: 1px solid {C.BORDER_A}; }}
            QPushButton:pressed {{ background: {C.BORDER_A}; color: #ffffff; }}
        """)
        send.clicked.connect(self._send)
        row.addWidget(send)
        return row

    def _build_footer(self) -> QWidget:
        w = QWidget()
        w.setFixedHeight(22)
        w.setStyleSheet(f"background: rgba(12, 6, 24, 200); border-top: 1px solid rgba(0, 212, 255, 60);")
        lay = QHBoxLayout(w); lay.setContentsMargins(14, 0, 14, 0)

        def _fl(txt, color=C.TEXT_MED):
            l = QLabel(txt); l.setFont(_sans_font(7))
            l.setStyleSheet(f"color: {color}; background: transparent;")
            return l

        lay.addWidget(_fl("[F4] Mute  ·  [F11] Fullscreen"))
        lay.addStretch()
        lay.addWidget(_fl("Mohammed Awais Industries  ·  S.A.R.A.  ·  CLASSIFIED"))
        lay.addStretch()
        lay.addWidget(_fl("© MOHAMMED AWAIS", C.PRI_DIM))
        return w

    def _on_file_selected(self, path: str):
        self._current_file = path
        p    = Path(path)
        cat  = _file_category(p)
        icon, _ = _FILE_ICONS.get(cat, _FILE_ICONS["unknown"])
        size = _fmt_size(p.stat().st_size)
        self._file_hint.setText(f"{icon}  {p.name}  ·  {size}  ·  Tell SARA what to do with it")
        self._log.append_log(f"FILE: {p.name} ({size}) loaded")
        
        def _send_file_to_sara():
            if not self.on_text_command:
                return
            
            content_summary = ""
            try:
                ext = p.suffix.lower().lstrip(".")
                f_size = p.stat().st_size
                if f_size > 150 * 1024:
                    content_summary = f"[File size is {_fmt_size(f_size)} (too large to read directly into prompt).]"
                else:
                    text_exts = {"txt", "md", "py", "js", "ts", "json", "csv", "xml", "html", "css", "yaml", "toml", "ini", "cfg", "log", "sh", "bat"}
                    if ext in text_exts:
                        text_content = p.read_text(encoding="utf-8", errors="ignore")
                        if len(text_content) > 10000:
                            content_summary = f"[First 10,000 characters of file content]:\n{text_content[:10000]}\n... [Truncated]"
                        else:
                            content_summary = f"[File Content]:\n{text_content}"
                    elif ext == "pdf":
                        try:
                            import pdfplumber
                            pdf_text = ""
                            with pdfplumber.open(p) as pdf:
                                for idx, page in enumerate(pdf.pages):
                                    if idx >= 5:
                                        pdf_text += "\n... [Truncated after 5 pages]"
                                        break
                                    pdf_text += (page.extract_text() or "") + "\n"
                            if pdf_text.strip():
                                content_summary = f"[Extracted PDF Content (First 5 pages)]:\n{pdf_text[:10000]}"
                        except Exception:
                            try:
                                import PyPDF2
                                with open(p, "rb") as f:
                                    reader = PyPDF2.PdfReader(f)
                                    pdf_text = ""
                                    for idx, page in enumerate(reader.pages):
                                        if idx >= 5:
                                            pdf_text += "\n... [Truncated after 5 pages]"
                                            break
                                        pdf_text += page.extract_text() + "\n"
                                if pdf_text.strip():
                                    content_summary = f"[Extracted PDF Content (First 5 pages)]:\n{pdf_text[:10000]}"
                            except Exception as e:
                                content_summary = f"[Could not read PDF: {e}]"
                    elif ext in ("docx", "doc"):
                        try:
                            from docx import Document
                            doc = Document(p)
                            docx_text = "\n".join(para.text for para in doc.paragraphs)
                            if len(docx_text) > 10000:
                                content_summary = f"[Extracted Word Document Content]:\n{docx_text[:10000]}\n... [Truncated]"
                            else:
                                content_summary = f"[Extracted Word Document Content]:\n{docx_text}"
                        except Exception as e:
                            content_summary = f"[Could not read Word document: {e}]"
            except Exception as e:
                content_summary = f"[Error reading file: {e}]"

            content_section = f"\n\nFile Read Result:\n{content_summary}" if content_summary else ""

            msg = (
                f"[FILE_UPLOADED] path={path} | name={p.name} | "
                f"type={p.suffix.lstrip('.')} | size={size}{content_section}\n\n"
                f"Briefly tell the user you have read the file '{p.name}' "
                f"({size}) and ask what they'd like to do with it."
            )
            self.on_text_command(msg)

        threading.Thread(target=_send_file_to_sara, daemon=True).start()

    def _toggle_mute(self):
        self._muted = not self._muted
        self.hud.muted = self._muted
        self._style_mute_btn()
        if self._muted:
            self._apply_state("MUTED")
            self._log.append_log("SYS: Microphone muted.")
        else:
            self._apply_state("LISTENING")
            self._log.append_log("SYS: Microphone active.")

    def _style_mute_btn(self):
        if self._muted:
            self._mute_btn.setText("🔇  MICROPHONE MUTED")
            self._mute_btn.setStyleSheet(f"""
                QPushButton {{
                    background: rgba(255, 0, 85, 20); color: {C.MUTED_C};
                    border: 1px solid {C.MUTED_C}; border-radius: 6px;
                }}
                QPushButton:pressed {{ background: {C.MUTED_C}; color: #ffffff; }}
            """)
        else:
            self._mute_btn.setText("🎙  MICROPHONE ACTIVE")
            self._mute_btn.setStyleSheet(f"""
                QPushButton {{
                    background: rgba(0, 245, 212, 20); color: {C.GREEN};
                    border: 1px solid {C.GREEN}; border-radius: 6px;
                }}
                QPushButton:hover {{ background: rgba(0, 245, 212, 40); }}
                QPushButton:pressed {{ background: {C.GREEN}; color: #000000; }}
            """)

    def _send(self):
        txt = self._input.text().strip()
        if not txt: return
        self._input.clear()
        self._log.append_log(f"You: {txt}")
        if self.on_text_command:
            threading.Thread(target=self.on_text_command, args=(txt,), daemon=True).start()

    def _apply_state(self, state: str):
        self.hud.state    = state
        self.hud.speaking = (state == "SPEAKING")
        if state == "THINKING":
            self._input.setEnabled(False)
            self._input.setPlaceholderText("Executing action...")
        else:
            self._input.setEnabled(True)
            self._input.setPlaceholderText("Type a command or question...")

    def _check_config(self) -> bool:
        if not API_FILE.exists(): return False
        try:
            d = json.loads(API_FILE.read_text(encoding="utf-8"))
            return bool(d.get("gemini_api_key")) and bool(d.get("os_system"))
        except Exception:
            return False

    def _show_setup(self):
        ov = SetupOverlay(self.centralWidget())
        cw = self.centralWidget()
        ow, oh = 460, 390
        ov.setGeometry(
            (cw.width()  - ow) // 2,
            (cw.height() - oh) // 2,
            ow, oh,
        )
        ov.done.connect(self._on_setup_done)
        ov.show()
        self._overlay = ov

    def _on_setup_done(self, key: str, os_name: str):
        os.makedirs(CONFIG_DIR, exist_ok=True)
        API_FILE.write_text(
            json.dumps({"gemini_api_key": key, "os_system": os_name}, indent=4),
            encoding="utf-8",
        )
        self._ready = True
        if self._overlay:
            self._overlay.hide()
            self._overlay = None
        self._apply_state("LISTENING")
        self._log.append_log(f"SYS: Initialised. OS={os_name.upper()}. SARA online.")

class _RootShim:
    def __init__(self, app: QApplication):
        self._app = app
    def mainloop(self):
        self._app.exec()
    def protocol(self, *_):
        pass


class SaraUI:
    def __init__(self, face_path: str, size=None):
        self._app = QApplication.instance() or QApplication(sys.argv)
        self._app.setStyle("Fusion")
        self._win = MainWindow(face_path)
        self._win.show()
        self.root = _RootShim(self._app)

    @property
    def muted(self) -> bool:
        return self._win._muted

    @muted.setter
    def muted(self, v: bool):
        if v != self._win._muted:
            self._win._toggle_mute()

    @property
    def current_file(self) -> str | None:
        return self._win._drop_zone.current_file()

    @property
    def on_text_command(self):
        return self._win.on_text_command

    @on_text_command.setter
    def on_text_command(self, cb):
        self._win.on_text_command = cb

    def set_state(self, state: str):
        self._win._state_sig.emit(state)

    def write_log(self, text: str):
        self._win._log_sig.emit(text)

    def wait_for_api_key(self):
        while not self._win._ready:
            time.sleep(0.1)

    def start_speaking(self):
        self.set_state("SPEAKING")

    def stop_speaking(self):
        if not self.muted:
            self.set_state("LISTENING")
