# 🎯 S.A.R.A.: Recruiter Interview Master Prep Guide

This master guide is designed to prepare you to answer any question that recruiters or technical interviewers ask about **S.A.R.A. System**. It covers architectural justifications, deep code explanations, concurrency models, and key achievements you can talk about.

---

## 🎙️ The Project Pitches (How to describe it)

### 30-Second Elevator Pitch
> *"S.A.R.A. is a real-time voice-activated AI assistant and OS controller. It uses Gemini's Live Connect WebSocket API to process bidirectional low-latency PCM audio, allowing users to talk directly to their computer to run apps, manage files, scrape websites, or write code. Additionally, it features an autonomous background agent with self-healing capabilities that can generate, execute, debug, and correct python scripts on the fly to complete complex multi-step research or coding tasks."*

### 2-Minute Project Overview
> *"The project is divided into two primary subsystems: an interactive voice stream and an autonomous background queue. For voice, it captures audio at 16kHz via a microphone, streams it to the Gemini Live API, and plays back the 24kHz response audio in parallel threads using `sounddevice`. When you ask for something complex, the voice client delegates it to a background priority Task Queue. This queue invokes a Planner that writes a multi-step JSON plan. The Executor runs these steps, sharing context and translating search results on-the-fly. If a script fails, the system triggers a self-healing loop: an error analyst model decides whether to retry, skip, or replan, and uses an alternative model to compile and run bug-fixes directly on the system."*

---

## 🏛️ Rationale for the Tech Stack (Why these libraries?)

### 1. Why PyQt6 instead of Electron/React?
* **Native OS Integration:** PyQt6 provides direct C++ bindings to Qt, giving lightweight access to OS metrics and window handles.
* **Performance:** High-performance, low-level drawing. The glassmorphism HUD, animated rings, and particle systems are drawn procedurally at 60 FPS using `QPainter` inside a `paintEvent` loop, consuming less memory than a Chromium-based Electron app.
* **Hardware Telemetry:** Direct integration with python's `psutil` and `nvidia-smi` to monitor GPU, CPU, RAM, and thermals in real-time.

### 2. Why `google-genai` Live Connect instead of standard REST API?
* **Bidirectional Low-Latency Stream:** Standard REST API requires recording the audio, sending the file, waiting for transcription, querying the model, and text-to-speech rendering (taking 4–8 seconds). Gemini's Live Connect API uses WebSockets to stream audio bytes, dropping latency to under a second.
* **Native Audio Processing:** Uses `models/gemini-2.5-flash-native-audio-preview` which understands sound tone, inflection, and voice directly without separate Speech-to-Text and Text-to-Speech layers.

### 3. Why `sounddevice` and raw PCM?
* **Cross-platform Compatibility:** `sounddevice` wraps the PortAudio library, making mic and speaker streams work on Windows, macOS, and Linux out of the box.
* **Low Latency Callbacks:** It supports non-blocking stream callback events to pull/push raw bytes directly to memory queues.

### 4. Why `Playwright` instead of `Selenium`?
* **Speed & Reliability:** Playwright is faster and uses modern async event loops. It allows running headless browsers, custom viewport capture, and auto-waiting selectors, which is perfect for LLM-driven browser control.

---

## 🔀 Concurrency & Threading Model (Crucial for recruiters)

A common recruiter question is: **"How did you prevent blocking the GUI and audio stream while running blocking terminal or OS commands?"**

```text
                                  ┌──────────────────────────┐
                                  │      Main GUI Thread     │
                                  │  - PyQt6 Event Loop      │
                                  │  - 60 FPS HUD Drawing    │
                                  └─────────────┬────────────┘
                                                │ (Spawns)
                                  ┌─────────────▼────────────┐
                                  │   Python Runner Thread   │
                                  │  - asyncio Event Loop    │
                                  └─────────────┬────────────┘
         ┌──────────────────────────────┼──────────────────────────────┐
         ▼                              ▼                              ▼
┌──────────────────┐           ┌──────────────────┐           ┌──────────────────┐
│  _listen_audio() │           │ _receive_audio() │           │  _play_audio()   │
│ - Mic capture    │           │ - Read Websocket │           │ - Speaker output │
│ - Queue push     │           │ - Handle tools   │           │ - Queue pop      │
└──────────────────┘           └────────┬─────────┘           └──────────────────┘
                                        │ (If tool executes)
                               ┌────────▼─────────┐
                               │  Executor Thread │
                               │ - Run OS tool    │
                               │ - Run code script│
                               └──────────────────┘
```

### Thread Rationale:
1. **PyQt6 GUI** owns the main thread.
2. **asyncio loop** runs in a daemon thread. It schedules 4 async tasks to stream audio: mic collector, socket writer, socket reader, and speaker output.
3. **Blocking Actions** (e.g. running code via `subprocess` or automation via `pyautogui`) are executed inside `loop.run_in_executor(None, ...)` which delegates the work to a background thread pool. This ensures that even if a tool takes 20 seconds, the audio connection and GUI remain responsive.

---

## 🧠 Deep-Dive: How Self-Healing Code Works

If an interviewer asks: **"Walk me through your error handler and code-fixing mechanism."**

1. **Step Execution:** The `AgentExecutor` runs a tool step (e.g. executing a Python script).
2. **Failure Capture:** If the script exits with code `!= 0`, the executor catches the runtime exception and sends it to `analyze_error()` in `agent/error_handler.py`.
3. **Reasoning:** `analyze_error()` formats the failed parameters, the traceback, and the attempt number, then sends them to `gemini-2.5-flash-lite`. The model decides:
   * **`retry`:** If it's a transient network or lock error (retries up to 3 times).
   * **`replan`:** If the logic is wrong, it suggests a fix.
4. **Code Patching:** If the decision is `replan`, `generate_fix()` passes the error details to `gemini-2.0-flash` to write a corrected python script.
5. **Hot-Swap:** The executor intercepts the original tool step, replaces the tool action with `code_helper` containing the new script, and runs it again.

---

## ❓ Common Technical Interview Questions (Q&A)

### Q1: How does context injection work between steps?
> **Answer:** *"Because steps are planned independently, subsequent steps don't naturally know what prior steps did. To solve this, our executor has a context injector `_inject_context()`. It monitors step outputs. If Step 1 runs a web search and returns data, and Step 2 is a file write, the executor automatically injects the text output of Step 1 into the `content` parameter of Step 2 before executing it."*

### Q2: How do you handle language localization?
> **Answer:** *"If a user speaks or writes a goal in another language (e.g. Turkish), our system detects the goal language using `_detect_language()`. Because web searches return English results, our context injector uses `_translate_to_goal_language()` to translate the accumulated search results back to the user's native language before writing files to disk, ensuring a localized user experience."*

### Q3: Why is there a memory limit of 2200 characters in the memory manager?
> **Answer:** *"LLM context windows can get polluted if we feed them pages of long-term history. To prevent this, we enforce a strict 2200-character cap on `long_term.json`. If memory size exceeds this, we sort stored personal facts by their update timestamp and trim the oldest entries first. This simulates short-term forgetting while protecting prompt token limits."*

### Q4: How do you handle API security?
> **Answer:** *"All API keys are stored locally on the user's system in `config/api_keys.json`. We never store them in source code. During startup, the UI validates the key length. If missing or invalid, it blocks the connection loop and displays a configuration window to input the key locally."*

### Q5: How did you fix the bug in the error handler?
> **Answer:** *"I discovered that the standalone error handler module had a dependency issue where `API_CONFIG_PATH` and `BASE_DIR` were not defined globally. I patched it by declaring the paths relative to the file path (`__file__`), resolving potential `NameError` exceptions during automated recovery processes."*

### Q6: What does the name S.A.R.A. stand for, and what is its role?
> **Answer:** *"S.A.R.A. stands for **Smart Awais's Response Assistant**. It represents the custom persona of the voice assistant, serving as the user-facing AI identity."*

---

## 🏆 Key Resume Points (What to brag about)
* **Real-time Streaming:** *Integrated WebSocket-based bi-directional PCM audio streaming using Gemini Live API and sounddevice, achieving <1s response latencies.*
* **Self-Healing Agents:** *Built an autonomous background agent pipeline with dynamic JSON planning, execution state recovery, and LLM-guided runtime code generation.*
* **GUI Engineering:** *Designed a custom PyQt6 heads-up display drawn procedurally at 60 FPS using QPainter, incorporating background system metric daemon threads.*
* **Localization & Context Handling:** *Created a context injection system that shares state between execution steps and performs real-time translation for non-English users.*
