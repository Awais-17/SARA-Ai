# 🧩 S.A.R.A.: Actions & Custom Tools Guide

This document catalogs all the custom actions (tools) available to S.A.R.A. and provides a step-by-step tutorial on how to build and register your own tool.

---

## 📂 Catalog of Registered Tools

All local actions are stored in the [actions/](file:///c:/Users/mdawa/OneDrive/Desktop/Tuninig%20my%20ai/actions/) directory. The system has **18 registered tools** (including 17 custom handlers and 1 shutdown handler):

| Tool Name | Action Module | Parameters | Strategic Purpose |
| :--- | :--- | :--- | :--- |
| **`open_app`** | [open_app.py](file:///c:/Users/mdawa/OneDrive/Desktop/Tuninig%20my%20ai/actions/open_app.py) | `app_name` (str) | Launches local software (Chrome, Spotify) or common websites. |
| **`web_search`** | [web_search.py](file:///c:/Users/mdawa/OneDrive/Desktop/Tuninig%20my%20ai/actions/web_search.py) | `query`, `mode`, `items`, `aspect` | Fetches answers, comparing items or prices via search queries. |
| **`weather_report`** | [weather_report.py](file:///c:/Users/mdawa/OneDrive/Desktop/Tuninig%20my%20ai/actions/weather_report.py) | `city` (str), `time` (str) | Opens Google search displaying forecast page. |
| **`send_message`** | [send_message.py](file:///c:/Users/mdawa/OneDrive/Desktop/Tuninig%20my%20ai/actions/send_message.py) | `receiver`, `message_text`, `platform` | Sends text notifications via WhatsApp or Telegram web handlers. |
| **`reminder`** | [reminder.py](file:///c:/Users/mdawa/OneDrive/Desktop/Tuninig%20my%20ai/actions/reminder.py) | `date`, `time`, `message` | Registers Windows Task Scheduler entries to pop up timed alerts. |
| **`youtube_video`** | [youtube_video.py](file:///c:/Users/mdawa/OneDrive/Desktop/Tuninig%20my%20ai/actions/youtube_video.py) | `action`, `query`, `save`, `url` | Plays specific videos, lists trending feeds, or summarizes a transcript. |
| **`screen_process`** | [screen_processor.py](file:///c:/Users/mdawa/OneDrive/Desktop/Tuninig%20my%20ai/actions/screen_processor.py) | `angle` ("screen"/"camera"), `text` | Captures displays or webcam feeds, sending frames to Gemini's vision channel. |
| **`computer_settings`**| [computer_settings.py](file:///c:/Users/mdawa/OneDrive/Desktop/Tuninig%20my%20ai/actions/computer_settings.py)| `action` (str), `description`, `value`| Adjusts OS volumes, monitor brightness, dark modes, WiFi toggles, etc. |
| **`browser_control`** | [browser_control.py](file:///c:/Users/mdawa/OneDrive/Desktop/Tuninig%20my%20ai/actions/browser_control.py) | `action`, `browser`, `url`, `selector`, `text` | Uses Playwright to click links, fill web forms, or scrape website text. |
| **`file_controller`** | [file_controller.py](file:///c:/Users/mdawa/OneDrive/Desktop/Tuninig%20my%20ai/actions/file_controller.py) | `action`, `path`, `destination`, `content` | Performs basic local file operations (list, delete, write, disk usage). |
| **`desktop_control`** | [desktop.py](file:///c:/Users/mdawa/OneDrive/Desktop/Tuninig%20my%20ai/actions/desktop.py) | `action`, `path`, `url`, `mode`, `task` | Changes wallpaper images or runs automated desktop organization. |
| **`code_helper`** | [code_helper.py](file:///c:/Users/mdawa/OneDrive/Desktop/Tuninig%20my%20ai/actions/code_helper.py) | `action`, `description`, `file_path`, `args` | Compiles, runs, reviews, or debugs coding scripts (supports multi-attempts). |
| **`dev_agent`** | [dev_agent.py](file:///c:/Users/mdawa/OneDrive/Desktop/Tuninig%20my%20ai/actions/dev_agent.py) | `description`, `language`, `project_name` | Creates whole project folders, writing multiple files from scratch. |
| **`agent_task`** | [task_queue.py](file:///c:/Users/mdawa/OneDrive/Desktop/Tuninig%20my%20ai/agent/task_queue.py) | `goal` (str), `priority` (str) | Queues complex, multi-step tasks in the background executor. |
| **`computer_control`**| [computer_control.py](file:///c:/Users/mdawa/OneDrive/Desktop/Tuninig%20my%20ai/actions/computer_control.py)| `action`, `text`, `x`, `y`, `keys`, `key` | Performs raw mouse/keyboard movements and hotkeys via PyAutoGUI. |
| **`game_updater`** | [game_updater.py](file:///c:/Users/mdawa/OneDrive/Desktop/Tuninig%20my%20ai/actions/game_updater.py) | `action`, `platform`, `game_name` | Installs, updates, or schedules Steam and Epic game downloads. |
| **`flight_finder`** | [flight_finder.py](file:///c:/Users/mdawa/OneDrive/Desktop/Tuninig%20my%20ai/actions/flight_finder.py) | `origin`, `destination`, `date`, `save` | Searches Google Flights to find the best itineraries. |
| **`file_processor`** | [file_processor.py](file:///c:/Users/mdawa/OneDrive/Desktop/Tuninig%20my%20ai/actions/file_processor.py) | `file_path`, `action`, `instruction`, `format` | Parses drag-and-dropped user files (PDFs, CSVs, audio/video, Word). |

---

## 🛠️ Anatomy of an Action Function

All tools follow a uniform signature to communicate cleanly with the main event loops:

```python
def my_custom_action(
    parameters: dict,
    player=None,
    speak=None,
) -> str:
    """
    Args:
        parameters (dict): Arguments generated by Gemini.
        player (SaraUI): Handle to UI console to print logs via player.write_log().
        speak (callable): Announce status messages back to speakers immediately.
        
    Returns:
        str: Result description sent back to Gemini's prompt loop.
    """
    # 1. Extract arguments
    arg_value = parameters.get("my_arg", "default")
    
    # 2. Perform local operations (system calls, scraping, calculations)
    result_text = f"Action finished with {arg_value}."
    
    # 3. Log to PyQt6 console
    if player:
        player.write_log(f"SARA: {result_text}")
        
    return result_text
```

---

## ➕ Tutorial: How to Add a New Action/Tool

Let's say we want to add a tool called **`get_system_uptime`** that queries how long your PC has been running.

### Step 1: Create the Python Module
Create a new file: `actions/system_uptime.py`.
```python
# actions/system_uptime.py
import psutil
import time
from datetime import datetime

def get_uptime_action(parameters: dict, player=None, speak=None) -> str:
    boot_time_timestamp = psutil.boot_time()
    bt = datetime.fromtimestamp(boot_time_timestamp)
    uptime_seconds = time.time() - boot_time_timestamp
    
    # Convert seconds to hours/minutes
    hours = int(uptime_seconds // 3600)
    minutes = int((uptime_seconds % 3600) // 60)
    
    msg = f"Sir, the system has been running for {hours} hours and {minutes} minutes (since {bt.strftime('%H:%M')})."
    
    if player:
        player.write_log(f"SYS: {msg}")
    if speak:
        speak(f"Sir, the system has been running for {hours} hours.")
        
    return msg
```

### Step 2: Declare the Schema in `main.py`
Open `main.py` and locate the `TOOL_DECLARATIONS` list (around line 84). Add the schema for the new tool:
```python
# inside TOOL_DECLARATIONS list in main.py
{
    "name": "get_system_uptime",
    "description": (
        "Calculates and returns the computer's system uptime. "
        "Use this whenever the user asks how long the PC has been running or turned on."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {},
        "required": []
    }
},
```

### Step 3: Import and Register in `main.py`
1. At the top of `main.py`, import your new action function:
```python
from actions.system_uptime import get_uptime_action
```
2. Scroll to `_execute_tool()` inside `main.py` and register the handler route:
```python
# inside _execute_tool() in main.py
elif name == "get_system_uptime":
    r = await loop.run_in_executor(None, lambda: get_uptime_action(parameters=args, player=self.ui, speak=self.speak))
    result = r or "Uptime calculated."
```

### Step 4: Teach the Planner Module
To make the background agent queue aware of the new tool:
1. Open `agent/planner.py` and update the `PLANNER_PROMPT` docstring to include the tool description and parameters:
```text
get_system_uptime
  (no parameters required)
```
2. Add an example goal showing how the planner should route uptime tasks in the prompt:
```text
Goal: "check how long the computer has been on and save it to a note"
Steps:
get_system_uptime |
file_controller | action: write, path: desktop, name: uptime.txt, content: "Uptime: [insert]"
```
3. Register the command import in `agent/executor.py`:
```python
# inside _call_tool() in agent/executor.py
elif tool == "get_system_uptime":
    from actions.system_uptime import get_uptime_action
    return get_uptime_action(parameters=parameters, player=None, speak=speak) or "Done."
```

---

**Next Steps to Study:**
* Study how configurations and memory keys are structured: **[5. Memory & Configuration Systems](file:///c:/Users/mdawa/OneDrive/Desktop/Tuninig%20my%20ai/working%20behind/memory_and_configs.md)**
