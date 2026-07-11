# 🧠 S.A.R.A.: Planning, Execution & Self-Healing

This document details the background agentic architecture of S.A.R.A., illustrating how multi-step goals are planned, queued, executed, and healed when code failures occur.

---

## 📋 The Planning Module (`planner.py`)

When the user gives S.A.R.A. a complex task, the request is not executed directly. It is first routed to the **Planner** in [agent/planner.py](file:///c:/Users/mdawa/OneDrive/Desktop/Tuninig%20my%20ai/agent/planner.py) to be decomposed.

### 🧠 Planning Logic (`create_plan`)
1. **Model Selection:** Uses the highly efficient `gemini-2.5-flash-lite` model.
2. **Contextual Instruction:** The `PLANNER_PROMPT` enforces strict rules:
   * Break the goal down into a maximum of **5 steps**.
   * Use **only** the list of 17 registered tools.
   * Every step must be **independent** (never reference variables like `step_1_result` in parameters).
   * **JSON Output Only:** Returns a clean JSON structure containing the goal and step dictionaries.
3. **Fallback Plan:** If Gemini returns invalid JSON or errors out, the system uses a fallback plan: a single step invoking a `web_search` with the user's raw goal text.

### 🔄 Replanning Logic (`replan`)
If a step fails during execution and the error handler determines a new path is needed, it calls `replan()`.
* **Model:** Uses `gemini-2.5-flash` for deeper reasoning.
* **Input State:** Passes the original goal, the list of completed steps, the failed step, and the error traceback.
* **Output:** Generates a revised list of steps starting *after* the successfully completed steps, avoiding redundant actions.

---

## 📥 The Task Queue (`task_queue.py`)

To prevent blocking the voice interface during long-running tasks, S.A.R.A. includes a thread-safe background **Task Queue** in [agent/task_queue.py](file:///c:/Users/mdawa/OneDrive/Desktop/Tuninig%20my%20ai/agent/task_queue.py).

### ⚙️ Task Dataclass Properties
Each task is wrapped in a `Task` dataclass:
```python
@dataclass(order=True)
class Task:
    priority:    int             # HIGH (1), NORMAL (2), LOW (3)
    created_at:  float           # Timestamp for FIFO sorting within priority
    task_id:     str             # Unique 8-character ID
    goal:        str             # User request string
    status:      TaskStatus      # PENDING, RUNNING, COMPLETED, FAILED, CANCELLED
    cancel_flag: threading.Event # Event set to abort task mid-execution
```

### 🧵 The Queue Worker Thread
* When `get_queue()` is first called, it spawns a daemon worker thread running `_worker_loop()`.
* It utilizes a `threading.Condition` lock. The thread sleeps when the queue is empty and wakes up immediately when a new task is submitted.
* It pops the highest-priority task, spawns a new thread named `AgentTask-{task_id}`, and executes the `AgentExecutor.execute()` process within that thread.

---

## 🚀 The Agent Executor (`executor.py`)

The **Executor** in [agent/executor.py](file:///c:/Users/mdawa/OneDrive/Desktop/Tuninig%20my%20ai/agent/executor.py) is the controller that steps through the plan, runs the tools, and acts as the orchestrator.

### 💉 Context Injection & Translation (`_inject_context`)
To share data across independent steps (e.g., searching for facts in Step 1 and saving them in Step 2):
1. **Information Extraction:** Prior to running a step, `_inject_context()` inspects the results of previously completed steps.
2. **Result Accumulation:** It collects outputs that represent search findings or text summaries.
3. **Translation:** If the user's goal was written in a non-English language (e.g., Turkish), it uses `gemini-2.5-flash` to translate the consolidated English search results into the user's language before inserting them into a file write parameter.
4. **Parameter Injection:** Replaces empty text parameters in `file_controller` actions with this compiled text.

### 🐍 Dynamic Script Execution (`_run_generated_code`)
If a task cannot be achieved using standard tools, the system falls back to **Code Generation**:
1. Uses `gemini-2.5-flash` with system paths (Desktop, Downloads, Documents) provided in the prompt.
2. Prompts the model to return **only** pure Python code to complete the task.
3. Saves the code to a temporary file (`.py`).
4. Executes the file locally using `subprocess.run()`, capturing `stdout` and `stderr` with a 120-second timeout.
5. Deletes the temporary file and returns the command output.

---

## 🛠️ The Error Recovery Handler (`error_handler.py`)

The system's "self-healing" capability is located in [agent/error_handler.py](file:///c:/Users/mdawa/OneDrive/Desktop/Tuninig%20my%20ai/agent/error_handler.py). When a step fails, the executor calls `analyze_error()` to decide how to recover.

### ⚖️ The Recovery Decision Matrix
Using `gemini-2.5-flash-lite` and the error context, the system makes one of four decisions:

| Decision | Explanation | Handler Action |
| :--- | :--- | :--- |
| **`retry`** | Transient failure (network glitch, locked file) | Sleeps 2s and runs the step again (up to 3 times). |
| **`skip`** | Non-critical step failure | Logs the warning and moves directly to the next step. |
| **`replan`** | Incorrect strategy or parameter design | Stops, calls the planner to generate a revised plan. |
| **`abort`** | Unrecoverable or unsafe condition | Immediately terminates the task queue run. |

### 🩹 Self-Healing Code Fixing (`generate_fix`)
If a step fails and the decision is **`replan`** with a specific fix suggestion, S.A.R.A. automatically triggers a self-healing code fix:
1. Calls `generate_fix()` using `gemini-2.0-flash`.
2. Passes the original step details, the error message, and the fix suggestion.
3. Generates a custom Python script designed to correct the error.
4. **Replaces** the failed step with a `code_helper` tool action set to run the generated script.

---

**Next Steps to Study:**
* Look at how custom tools are written: **[4. Actions & Custom Tools Guide](file:///c:/Users/mdawa/OneDrive/Desktop/Tuninig%20my%20ai/working%20behind/actions_and_tools_guide.md)**
* Study the memory management functions: **[5. Memory & Configuration Systems](file:///c:/Users/mdawa/OneDrive/Desktop/Tuninig%20my%20ai/working%20behind/memory_and_configs.md)**
