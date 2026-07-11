# 🎙️ S.A.R.A.: Core Engine & Live Audio

This document goes deep into the main entry point of the application, showing how the real-time voice interface and HUD visual loops are structured.

---

## 🔌 The Gemini Live Connect API

The engine in [main.py](file:///c:/Users/mdawa/OneDrive/Desktop/Tuninig%20my%20ai/main.py) uses the Google GenAI SDK's async live client wrapper (`client.aio.live.connect`). Under the hood, this establishes a persistent, full-duplex Websocket connection to Google's Gemini servers using the **v1beta API version**.

### ⚙️ Session Connection Configuration
At session startup, `_build_config()` returns a `LiveConnectConfig` defining:
* **Response Modalities:** `["AUDIO"]` — the model will respond with a high-fidelity voice stream.
* **Prebuilt Voice:** `Kore` — S.A.R.A.'s bright female voice.
* **System Prompt Injection:** Injects the current date/time, personal details loaded from memory (`long_term.json`), and the S.A.R.A. personality.
* **Tools Declarations:** Declares the available actions as JSON function schemas so Gemini can decide when to trigger local functions.

```python
# From main.py: _build_config()
return types.LiveConnectConfig(
    response_modalities=["AUDIO"],
    output_audio_transcription={},
    input_audio_transcription={},
    system_instruction="\n".join(parts),
    tools=[{"function_declarations": TOOL_DECLARATIONS}],
    speech_config=types.SpeechConfig(
        voice_config=types.VoiceConfig(
            prebuilt_voice_config=types.PrebuiltVoiceConfig(
                voice_name="Kore"
            )
        )
    ),
)
```

---

## 🎧 Real-time PCM Audio Pipeline

Voice data is processed as raw PCM (Pulse Code Modulation) signed 16-bit integers in mono-channel format. There is a mismatch between recording and playback sample rates, which matches the Gemini Live specifications:
* **Microphone (Send Rate):** `16,000 Hz` (16kHz PCM)
* **Speakers (Receive Rate):** `24,000 Hz` (24kHz PCM)
* **Frame Chunk Size:** `1024` samples

Here is how the four loops run concurrently in `TaskGroup` tasks:

### 1. `_listen_audio()` (Microphone Capture)
* Utilizes the `sounddevice` library to open an input stream.
* Selects the physical microphone automatically by filtering out virtual lines, loopback lines, and sound mappers.
* Pushes raw audio buffers captured by the callback into `self.out_queue` whenever the assistant is *not* speaking and *not* muted.

### 2. `_send_realtime()` (Websocket Transmitter)
* A loop that continuously pops audio chunks from `self.out_queue`.
* Sends them instantly to Gemini Live using `session.send_realtime_input(media=msg)`.

### 3. `_receive_audio()` (Websocket Receiver)
* A listener loop that processes incoming packets from `session.receive()`.
* **Audio Data:** When raw audio chunks arrive, they are placed directly into `self.audio_in_queue`.
* **Transcription Text:** User transcriptions (`input_transcription`) and model transcriptions (`output_transcription`) are cleaned of command code signals and logged to the UI console.
* **Tool Calls:** When the model calls a tool, the listener loops through the requested functions, calls `_execute_tool(fc)` to get a return value, and sends the result back to Gemini over the socket.

### 4. `_play_audio()` (Speaker Output)
* Opens a `sounddevice.RawOutputStream` configured for **24kHz**.
* Pulls audio buffers from `self.audio_in_queue`.
* Feeds them to the speakers using a blocking thread-pool executor write command `asyncio.to_thread(stream.write, chunk)`.
* Changes the UI status to `"SPEAKING"` when writing audio, and resets it to `"LISTENING"` when the queue becomes empty.

---

## 🎨 The PyQt6 HUD GUI: Obsidian Glassmorphism

The visual interface [ui.py](file:///c:/Users/mdawa/OneDrive/Desktop/Tuninig%20my%20ai/ui.py) is built on PyQt6, using custom painting techniques to create a futuristic transparent HUD (Heads-Up Display).

### 🖥️ Hardware Telemetry Thread (`_SysMetrics`)
A background Python thread continuously reads machine specs every 1.5 seconds:
* **CPU & RAM:** Read via `psutil`.
* **Network Throughput:** Derived from `psutil.net_io_counters()` bandwidth difference.
* **GPU Utilization:** Queries `nvidia-smi` (Windows/Linux), falling back to `rocm-smi` (AMD), `intel_gpu_top` (Intel Linux), or `powermetrics` (Apple Silicon).
* **CPU Temperature:** Queries WMI on Windows and sensors on Linux/macOS.

### 🖌️ Custom Canvas Drawing (`HudCanvas`)
The visual avatar runs in a custom `QWidget` that overloads the `paintEvent` method. Instead of basic static textures, the interface is drawn procedurally at **60 FPS** using a `QTimer` firing every 16ms:

```text
HUD Draw Pipeline (paintEvent):
├── 1. Fine Square Cyber Grid (Tech-pattern grid backing)
├── 2. Background Tech Diagnostic Labels (AVENGERS, S.H.I.E.L.D., /SECURITY/)
├── 3. Corner Radar Launch Queries ("S.A.R.A. LAUNCH?", "/YES/ S.A.R.A. ONLINE")
├── 4. Diagonal Telemetry Status ("S.A.R.A. STATUS: ACTIVE", "/SUIT ENGINE LINKED/")
├── 5. Background Concentric Wireframes (Thin orange-red circles)
├── 6. Core Radial Ticks (Amber-Orange ticks with diagnostic gaps)
├── 7. Segmented Inner Core Ring (Neon orange arcs with a green segment on the left)
├── 8. Four glowing green diagnostic dots on the left inner arc
├── 9. Thick Segmented Outer HUD Ring (with animated rotation)
├── 10. Four outer circular diagnostic markers (orange dots ● ● ● ● rotating on segment)
├── 11. Large Holographic Glow (radial gradient backing behind center text)
├── 12. Sci-Fi "S.A.R.A." Center Text (Dual-layered with text drop-glow)
├── 13. Floating Glass HUD Buttons (SYS, CORE, NET, MEM, VIS, SEC)
└── 14. Animated Audio Equalizer Waveform
```

---

## ⚠️ Key Design Pattern: The Blocking Tool Executor

If a tool (like `browser_control`) is called directly inside the async event loop, it will block the network socket tasks, causing audio to skip or disconnect due to lost ping packets.

**Solution:**
In `_execute_tool()`, all action functions are executed in a separate thread pool using `loop.run_in_executor(None, lambda: tool_func(...))`. This offloads synchronous OS commands to Python's thread pool, allowing the core voice engine to continue transmitting audio frames smoothly.

---

**Next Steps to Study:**
* Learn about the multi-step background planner: **[3. Agentic Planning, Execution & Self-Healing](file:///c:/Users/mdawa/OneDrive/Desktop/Tuninig%20my%20ai/working%20behind/agentic_system_study.md)**
* Read the custom tools directory: **[4. Actions & Custom Tools Guide](file:///c:/Users/mdawa/OneDrive/Desktop/Tuninig%20my%20ai/working%20behind/actions_and_tools_guide.md)**
