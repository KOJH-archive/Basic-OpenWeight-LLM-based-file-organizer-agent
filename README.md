# FlowGuard MVP

FlowGuard is a local-first Windows desktop helper that finds repetitive file patterns and proposes safe organization steps. It observes only a folder you explicitly select. Nothing is moved until you review a concrete plan and approve it.

## MVP scope

Included:

- Manual scan of one user-selected folder (up to 5,000 files per scan).
- Optional 10-second polling of that same folder, started and stopped visibly by the user.
- Pattern detection for common extensions, duplicate *names* and files not modified for 180 days.
- Swappable local-model suggestions through Ollama or an OpenAI-compatible local server, based only on aggregate pattern descriptions—not file contents.
- Deterministic organization plans for supported file types in the selected folder's top level.
- Dry-run enabled by default, an explicit confirmation dialog, collision-safe moves, audit journals and rollback.
- A useful non-AI fallback when the selected local server or model is unavailable.

Deliberately excluded from this MVP:

- Background startup, hidden monitoring, screenshots, keystrokes, email/browser access or network uploads.
- File deletion, arbitrary shell commands, AI-authored executable actions or changes outside the selected folder.
- Content indexing, semantic search, duplicate-content removal and automatic execution.

## Architecture

```text
Tkinter desktop UI
  ├─ scanner.py       read-only metadata scan + deterministic pattern detection
  ├─ local_llm.py     provider adapter → loopback-only local server; safe fallback
  ├─ planner.py       allowlisted extensions → constrained MoveAction list
  └─ executor.py      path boundary checks → dry-run/move → JSON journal → rollback
```

The AI is outside the execution path. Its natural-language response is displayed as advice only. `planner.py`, not the model, creates actions from a small allowlist. `executor.py` resolves every path and rejects anything outside the selected root. No delete primitive exists. Local model endpoints are restricted to `127.0.0.1`, `localhost` or `::1`; changing the model never grants it filesystem authority.

## Recommended model

The default is `qwen3.5:4b`, a practical starting point for a 32 GB LG Gram: the current Ollama package is roughly 3.3–4.0 GB. Try `qwen3.5:9b` for potentially better suggestions if latency and power use are acceptable. FlowGuard still scans, plans, dry-runs, executes and rolls back without Ollama.

For the default Ollama model, FlowGuard disables thinking output, uses an 8,192-token context, caps responses at 700 tokens and keeps the loaded model resident for 10 minutes. This favors quick, concise workflow suggestions over long reasoning traces.

The model is replaceable from the UI:

- **Ollama**: default endpoint `http://127.0.0.1:11434`; model names such as `qwen3.5:4b` or `qwen3.5:9b`.
- **OpenAI compatible**: default endpoint `http://127.0.0.1:8080/v1`; works with a local llama.cpp or LM Studio server exposing `/v1/models` and `/v1/chat/completions`.
- Select **Find models** to read the models currently exposed by the chosen local server. A model name can also be entered manually.

Only the provider adapter changes. Scanning, deterministic planning, approval, execution and rollback are model-independent.

Intel Arc B390 acceleration depends on the installed Ollama/graphics-driver combination. FlowGuard does not assume a GPU and remains functional if Ollama runs the model on CPU.

## Windows setup

Requirements: Windows 11 and Python 3.11 or newer. Ollama is optional.

1. Extract the ZIP to a normal user folder.
2. Open PowerShell in the extracted folder.
3. Run:

   ```powershell
   Set-ExecutionPolicy -Scope Process Bypass
   .\setup_windows.ps1
   ```

4. Optional: install [Ollama for Windows](https://docs.ollama.com/windows), then download the default model:

   ```powershell
   ollama pull qwen3.5:4b
   ```

5. Start with `run_flowguard.bat` (double-click) or:

   ```powershell
   .\run_flowguard.ps1
   ```

No administrator access is required for FlowGuard itself. Runtime dependencies are Python standard library only, so setup performs a Python availability check and does not download packages or create a virtual environment.

## Safe first run

1. Choose a small test folder containing at least three PDFs, images or documents.
2. Select **Scan now**. FlowGuard automatically fills **Scan result**, requests an **AI suggestion**, and builds an **Execution plan**. These analysis steps never change files.
3. Inspect the AI advice and every source/destination in the generated plan. The separate suggestion/plan buttons can be used to refresh either output.
4. Leave **Dry run** checked, select **Run plan**, and approve the preview.
5. Only after review, clear **Dry run**, run again and explicitly approve the real move.
6. Use **Undo latest run** to restore moved files. If the original path is occupied, rollback skips it instead of overwriting it.

Runtime logs are stored at `%LOCALAPPDATA%\FlowGuard\logs\flowguard.log`. Move journals are stored inside the selected folder at `.flowguard\journal\`. These journals contain paths and action metadata, not file contents.

## Tests

```powershell
.\run_tests.ps1
```

The automated suite checks pattern detection, dry-run immutability, collision handling, journal creation, rollback, folder-boundary enforcement and Ollama failure fallback.

## Verification status

Tested in the delivery environment:

- Python 3.14 import/compile behavior.
- Core scanner, planner, path safety, dry-run, move, journal, collision handling and rollback through automated tests.
- A live connection to Ollama 0.40.3 with the installed `qwen3.5:4b` Q4_K_M model: model discovery and a complete Korean suggestion request succeeded in about 5 seconds after warm-up.
- Ollama and OpenAI-compatible response adapters, remote-endpoint rejection, first-load retry and connection-failure fallback through automated tests.

Not tested here and requiring verification on the target LG Gram:

- Visual behavior of Tkinter under the machine's Windows display scaling.
- The Windows setup scripts on a clean Windows account.
- Intel Arc B390 or NPU acceleration. The live verification used Ollama's CPU backend; FlowGuard does not force unsupported accelerator selection.
- Long-running monitoring under sleep/resume and very large folders.

## Privacy and limitations

FlowGuard sends only the displayed aggregate pattern summary to the selected loopback endpoint. It does not read file contents and rejects non-local model URLs. Another process controlling the configured local port is outside FlowGuard's trust boundary, so use a trusted local runtime. The duplicate detector compares filenames, not file bytes. Monitoring is polling—not a background Windows service—and ends when the app closes.
