# 💾 S.A.R.A.: Memory & Configuration Systems

This document explains how S.A.R.A. remembers personal details about you across sessions and manages API configurations.

---

## 🧠 Persistent Long-Term Memory (`memory_manager.py`)

S.A.R.A. stores facts about you in [memory/long_term.json](file:///c:/Users/mdawa/OneDrive/Desktop/Tuninig%20my%20ai/memory/long_term.json). The memory engine in [memory/memory_manager.py](file:///c:/Users/mdawa/OneDrive/Desktop/Tuninig%20my%20ai/memory/memory_manager.py) manages this file.

### 🗂️ Memory Structure Categories
Data is organized into 6 schema categories:
* **`identity`:** Personal details (your name, age, city, job, nationality).
* **`preferences`:** Likes and dislikes (favorite foods, colors, game genres, sports).
* **`projects`:** Active work items or goals you are developing.
* **`relationships`:** Details about family members, friends, or colleagues.
* **`wishes`:** Short-term plans, shopping lists, or travel dreams.
* **`notes`:** Random details and schedules.

```json
// Example of how memory looks inside long_term.json
{
  "identity": {
    "name": {
      "value": "Mohammed Awais",
      "updated": "2026-06-04"
    }
  },
  "preferences": {
    "programming_style": {
      "value": "Vibe coding with Python",
      "updated": "2026-06-04"
    }
  }
}
```

---

## 🛡️ Memory Truncation & Optimization Limits

To keep network payloads slim and avoid exceeding model context prompt structures, the memory manager implements two optimization filters:

### 1. Value Length Truncation (`MAX_VALUE_LENGTH = 380`)
When saving a memory via `remember()`, individual string values are limited to 380 characters. Any value exceeding this is sliced and appended with an ellipsis (`…`).

### 2. Characters Buffer Trimming (`MEMORY_MAX_CHARS = 2200`)
The total size of `long_term.json` is capped at **2200 characters**:
* When updating memory, the function `_trim_to_limit()` is triggered.
* If the total serialized length of the JSON exceeds 2200 characters, the manager extracts all memory keys, sorts them by their `updated` date stamp, and deletes the **oldest keys first**.
* This acts as an automated "forgetting" loop for old facts.

---

## 💉 Prompt Context Formatting (`format_memory_for_prompt`)

Every time the Live Connect session connects to Gemini, the system loads the memory JSON, processes it, and structures it into a text prompt block starting with:
`[WHAT YOU KNOW ABOUT THIS PERSON — use naturally, never recite like a list]`

The assistant uses these facts to guide its conversation. For instance, if it knows your name is Mohammed Awais, it will address you as such without you having to introduce yourself.

---

## 🔑 Configuration & API Keys (`config_manager.py`)

Local environment configurations are managed by [memory/config_manager.py](file:///c:/Users/mdawa/OneDrive/Desktop/Tuninig%20my%20ai/memory/config_manager.py) and stored in [config/api_keys.json](file:///c:/Users/mdawa/OneDrive/Desktop/Tuninig%20my%20ai/config/api_keys.json).

### 🔄 Startup API Validation Loop
1. When `main()` starts in [main.py](file:///c:/Users/mdawa/OneDrive/Desktop/Tuninig%20my%20ai/main.py#L887), it instantiates the PyQt6 interface.
2. It immediately launches the runner in a daemon thread:
```python
def runner():
    ui.wait_for_api_key() # 🛑 BLOCKS here if no key exists
    sara = SaraLive(ui)
    asyncio.run(sara.run())
```
3. `wait_for_api_key()` checks if `config/api_keys.json` contains a valid `gemini_api_key` (length > 15 characters).
4. If a valid key is missing, it displays an API key configuration window on the PyQt6 interface.
5. Once you enter and save a key, `save_api_keys()` writes the key to disk, releases the blocking thread lock, and allows the async client connection loop to proceed.

---

## ⚠️ Known Debugging Insights

* **Missing Constant in Error Handler:** In [agent/error_handler.py](file:///c:/Users/mdawa/OneDrive/Desktop/Tuninig%20my%20ai/agent/error_handler.py), the function `_get_api_key()` uses the global variable `API_CONFIG_PATH` to resolve the JSON configuration file, but `API_CONFIG_PATH` is not defined in the scope of that file. It relies on the caller or requires adding this definition at the top:
  ```python
  API_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "api_keys.json"
  ```
  *(You may want to add this line to error_handler.py to avoid runtime `NameError` exceptions during standalone module debugging).*

---

Congratulations! You have completed the S.A.R.A. System study guides. Return to the **[Main Roadmap Index](file:///c:/Users/mdawa/OneDrive/Desktop/Tuninig%20my%20ai/working%20behind/index.md)** to navigate other folders.
