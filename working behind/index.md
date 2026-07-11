# 🤖 S.A.R.A. — Study Roadmap & Architecture Guide
Welcome to the study directory for **S.A.R.A. System**. This guide has been compiled to help you understand the architectural pipeline, task execution loops, visual interface logic, and custom actions that form the ultimate autonomous assistant.

---

## 🗺️ Study Guide Index
We have compiled detailed study resources for you. Use the links below to study each system in detail:

* **[🎯 Recruiter Interview Master Prep Guide](file:///c:/Users/mdawa/OneDrive/Desktop/Tuninig%20my%20ai/working%20behind/recruiter_interview_prep.md) (Highly Recommended for Tomorrow)**
  * Study this cheat sheet to answer recruiter questions about threading safety, custom components, self-healing code, and tech stack choices.

1. [🏛️ Architecture Overview](file:///c:/Users/mdawa/OneDrive/Desktop/Tuninig%20my%20ai/working%20behind/architecture_overview.md)
   * High-level system structure, multi-threading model, directory map, and sequence flow diagram.
2. [🎙️ Core Engine & Live Audio](file:///c:/Users/mdawa/OneDrive/Desktop/Tuninig%20my%20ai/working%20behind/core_engine_study.md)
   * Deep dive into the Gemini Live Connect API (Websockets), real-time PCM audio streaming, audio hardware handling, and startup event loops.
3. [🧠 Agentic Planning, Execution & Self-Healing](file:///c:/Users/mdawa/OneDrive/Desktop/Tuninig%20my%20ai/working%20behind/agentic_system_study.md)
   * How the planner decomposes goals into steps, how the task queue operates in the background, and how the error-handling module performs self-healing code generation.
4. [🧩 Actions & Custom Tools Guide](file:///c:/Users/mdawa/OneDrive/Desktop/Tuninig%20my%20ai/working%20behind/actions_and_tools_guide.md)
   * Breakdown of all 17 custom actions/tools, their parameters, and a step-by-step tutorial on how to build and register a new tool.
5. [💾 Memory & Configuration Systems](file:///c:/Users/mdawa/OneDrive/Desktop/Tuninig%20my%20ai/working%20behind/memory_and_configs.md)
   * Details on key/value memory storage, JSON schema truncation logic, prompt injection context, and API key management.

---

## 📂 Codebase Directory Structure
Here is an overview of where files live in your workspace:
```text
Tuninig my ai/
│
├── actions/                  # 🧩 CUSTOM TOOLS (Action Handlers)
│   ├── browser_control.py    # Playwright-powered browser automation
│   ├── code_helper.py        # LLM-guided code generation/running/fixing
│   ├── computer_control.py   # PyAutoGUI mouse clicks, keys, and coordinates
│   ├── dev_agent.py          # Multi-file project developer agent
│   ├── file_processor.py     # Image/PDF/Audio/Video processing engine
│   └── (12 other actions...)  # Weather, flights, open_app, reminders, etc.
│
├── agent/                    # 🧠 AGENTIC ENGINE & CONTROL LAYER
│   ├── error_handler.py      # Error analysis & self-healing code fixer
│   ├── executor.py           # Linear step runner & tool dispatcher
│   ├── planner.py            # Goal decomposer (Gemini 2.5 Flash Lite)
│   └── task_queue.py         # Thread-safe background task queue
│
├── config/                   # ⚙️ SECURE KEYS & LOCAL SETTINGS
│   └── api_keys.json         # Gemini API credential storage
│
├── core/                     # 📝 SYSTEM INSTANCES & PROMPTS
│   └── prompt.txt            # Master SARA personality system prompt
│
├── memory/                   # 💾 CONTEXT PERSISTENCE
│   ├── config_manager.py     # API key validation and management
│   ├── memory_manager.py     # JSON memory loader, updater, and size trimmer
│   └── long_term.json        # Saved user attributes (hobbies, names, etc.)
│
├── main.py                   # 🎙️ GEMINI LIVE STREAMING CLIENT & EVENT LOOPS
├── ui.py                     # 🎨 PYQT6 OBSIDIAN GLASSMORPHISM HUD INTERFACE
└── requirements.txt          # 📦 Python project dependencies
```

---

## ⚡ Quick Architecture Summary
S.A.R.A. functions as a **Hybrid Interactive Assistant**:
* **Voice Mode:** You talk directly to it. A real-time PCM audio stream goes up to Gemini (`models/gemini-2.5-flash-native-audio-preview`). The model streams response audio back, which is played on your speakers, and automatically calls tools on your PC in real-time.
* **Agent Mode (Task Queue):** If you give it a complex goal like *"Research the latest AI trends and save the summary on my Desktop as a text file"*, it spawns a background queue task that creates a multi-step plan, calls multiple tools in sequence, analyzes execution errors, and self-heals script failures.

> [!TIP]
> Start your study with **[1. Architecture Overview](file:///c:/Users/mdawa/OneDrive/Desktop/Tuninig%20my%20ai/working%20behind/architecture_overview.md)** to see the overall flow before digging into individual Python modules!
