# macOS Performance & Accuracy Testing — Handoff Brief

> **Read this first.** You (a Claude Code instance running on macOS) are being asked to
> design **and run** a set of performance/accuracy tests for this project's AI pipeline
> **on macOS**, then produce a **separate Word (`.docx`) document** containing a macOS
> section that the user can copy‑paste into an existing online Word document.
>
> The existing document (`Performance testing.docx`, lives on the user's **Windows**
> machine) already contains the equivalent **Windows** tests. Your job is the **macOS
> counterpart** — same metrics where they apply, plus macOS‑specific tests that don't
> exist on Windows.
>
> This brief was written by a Claude Code instance on the user's Windows machine after
> exploring the repo. It is meant to be self‑contained: you should not need the original
> chat. Everything you need — pipeline facts, the macOS‑specific gotchas, exact commands,
> where to read each metric, and the target Word structure — is below.

---

## 0. TL;DR — what to deliver

1. Confirm/record the **Mac's hardware** (chip, RAM, macOS version, Docker Desktop version).
2. Bring up the stack on macOS in **two modes** and run the test matrix in §5:
   - **Native Metal Ollama** (the macOS equivalent of "GPU on") via the `native-ollama` overlay.
   - **Docker CPU Ollama** (the "GPU off" baseline).
3. Measure, for each configuration: **Whisper time, Formatting time, Total time, Transcript accuracy %** — plus the macOS‑specific tests (thermal, memory/OOM, concurrency, etc.).
4. Run the **formatter accuracy benchmark** (`transcript-formatter/benchmark/runner.py`) for a rigorous AI‑accuracy number (accuracy / completeness / hallucination rate).
5. Generate **`Performance testing - macOS additions.docx`** with the filled‑in results, formatted to match the existing document (see §7), so the user can paste it into the online Word doc.

> Use **the same benchmark audio file and reference transcript** the Windows tests used,
> so numbers are comparable. That audio is **not** in the repo — **ask the user for it.**
> The ground‑truth reference transcript for it is reproduced in Appendix B.

---

## 1. What this project is (context)

"Customer Support Call Transcription & Incident Form System" — a local‑first, Docker‑Compose
pipeline (the "AI calling assistant"):

```
Audio (upload / browser recording / telephony webhook)
   → voice-app  (:5000)         orchestrator + demo UI + /upload API
       → transcriber  (:9000)   faster-whisper STT + speaker diarization   ← AI #1
       → transcript-formatter (:5001)  Ollama LLM: extract incident fields,
                                        format transcript, optional Dutch translation  ← AI #2
       → email-sender (:5002)   SMTP dispatch (Mailpit in dev)
       → database (:5432)        PostgreSQL + pgvector
```

There are **two AI components**, and the performance doc measures both:

| AI component | Service | Knobs | Metric in the doc |
|---|---|---|---|
| **Speech‑to‑text** | `transcriber` (faster‑whisper) | `WHISPER_MODEL`, `WHISPER_DEVICE`, `WHISPER_COMPUTE_TYPE`, beam size | **Whisper time**, **Transcript accuracy %** |
| **LLM extraction/formatting** | `transcript-formatter` (Ollama / gemma3) | `OLLAMA_MODEL`, `OLLAMA_KV_CACHE_TYPE`, `OLLAMA_FLASH_ATTENTION`, `OLLAMA_KEEP_ALIVE`, Dutch translation on/off | **Formatting time**, (accuracy via the benchmark suite) |

All config is in `.env` (copy from `.env.example`). Relevant defaults today:
`OLLAMA_MODEL=gemma3:12b`, `WHISPER_MODEL=large-v2`, `WHISPER_DEVICE=cpu`,
`WHISPER_COMPUTE_TYPE=int8`, `OLLAMA_KV_CACHE_TYPE=q8_0`, `OLLAMA_FLASH_ATTENTION=1`,
`OLLAMA_KEEP_ALIVE=-1`, `DEFAULT_INCLUDE_DUTCH_TRANSLATION=true`.

---

## 2. ⚠️ The crux: why macOS is different from Windows

The existing Windows doc's "**with GPU settings**" path uses **NVIDIA** acceleration via
`docker-compose.gpu.yml` (`gpus: all`, `NVIDIA_VISIBLE_DEVICES`). **None of that works on
macOS** — Docker Desktop on macOS runs Linux containers inside a lightweight VM with **no
GPU passthrough**, and Apple Silicon has no NVIDIA/CUDA. So:

1. **Do NOT use `docker-compose.gpu.yml` on macOS.** It will fail / do nothing useful.

2. **The macOS way to get GPU acceleration is `docker-compose.native-ollama.yml`.** This
   overlay:
   - Parks the bundled CPU Docker Ollama behind a `docker-ollama` profile (so it doesn't start).
   - Points `transcript-formatter` and `dashboard` at `http://host.docker.internal:11434`
     — i.e. the **host‑native Ollama**, which on Apple Silicon uses the **Metal GPU**.
   - Republishes `voice-app` on **port 5050** (see #4).
   - **Prereq:** the host must already be running Ollama with the model pulled.

   ➜ On macOS, **"native Metal Ollama" is the analog of the Windows "GPU on"** case, and
   **"bundled Docker CPU Ollama" is the analog of "GPU off."** Frame the macOS comparison
   that way.

3. **Whisper does NOT get GPU acceleration on macOS**, even with the overlay. The overlay
   only offloads **Ollama** to the host; the `transcriber` container still runs
   faster‑whisper on **CPU inside the Docker VM** (`WHISPER_DEVICE=cpu`). So expect Whisper
   times on macOS to be **CPU‑bound and slower** than NVIDIA‑accelerated Windows. Whisper
   time should be roughly **constant** across the two macOS Ollama modes (the Ollama mode
   doesn't touch the transcriber) — call that out if you see it. (Running Whisper natively
   on Apple's MPS is **not** wired into this repo; treat that as an optional exploratory note,
   not a supported config.)

4. **Port conflict (AirPlay).** macOS's AirPlay Receiver holds port **5000**, so the overlay
   publishes the UI on **5050**. When using the overlay, the UI/API is
   **`http://localhost:5050`** (and `/upload` is `http://localhost:5050/upload`). The other
   services keep their ports: formatter `5001`, email `5002`, telephony `5010`,
   transcriber `9000`. (Alternatively the user can disable *System Settings → General →
   AirDrop & Handoff → AirPlay Receiver* and keep 5000 — note whichever you used.)

> **Net effect to expect and to document:** on macOS the **Formatting time** should improve
> dramatically with native Metal Ollama vs Docker CPU, while **Whisper time** stays high
> because it's CPU‑only. That asymmetry is the single most important macOS finding.

---

## 3. macOS setup runbook

### 3.1 Prerequisites (host)

```bash
# 1. Docker Desktop for Mac installed and running.

# 2. Native Ollama on the host (Apple Silicon → Metal GPU):
brew install ollama          # or download from ollama.com
ollama serve                 # leave running (or use the menubar app)

# 3. Pull the models you'll test BEFORE timing (first pull time is measured separately, §5.C):
ollama pull gemma3:12b
ollama pull gemma3:27b       # only if you'll test the heavy model
# If the dashboard/embeddings are exercised, also pull OLLAMA_EMBED_MODEL if set in .env.

# 4. Repo .env:
cp .env.example .env         # then edit per the matrix in §5
```

### 3.2 Bring up the stack

**Mode A — native Metal Ollama ("GPU on" analog), UI on :5050**
```bash
docker compose -f docker-compose.yml -f docker-compose.native-ollama.yml --profile dev up -d --build
```

**Mode B — bundled Docker CPU Ollama ("GPU off" baseline), UI on :5000**
```bash
docker compose --profile dev up -d --build
```

> ⚠️ When you change an AI‑affecting setting (model, cache type, formatter version), the
> existing doc warns you to **delete the `local-storage` folder** (it caches an old image of
> the model) and rebuild cleanly:
> ```bash
> docker compose down -v          # remove containers + volumes
> docker network prune -f         # drop unused networks
> ```
> Then bring the stack back up. Wait until model pulls finish (watch `ollama-init` logs in
> Docker Desktop, or `ollama list` on the host) **before** running timed tests.

### 3.3 Health check (adjust 5000→5050 in Mode A)

```bash
curl -sS http://localhost:5050/health   # voice-app (Mode A; use 5000 in Mode B)
curl -sS http://localhost:5001/health   # formatter
curl -sS http://localhost:5002/health   # email
curl -sS http://localhost:9000/health   # transcriber
```
Each returns `{"status":"ok"}`.

---

## 4. How to run one test and where to read each metric

### 4.1 Fire a call through the pipeline

Use the **same audio file** the Windows tests used (ask the user — see §0). Then:

```bash
# Mode A → :5050, Mode B → :5000
curl -sS -X POST http://localhost:5050/upload \
   -F "file=@/path/to/benchmark_call.wav" \
   -F "caller_name=Alex Jansen" \
   -F "account_or_reference=AC-7781" \
   -F "contact_info=alex@example.com" | python3 -m json.tool
```

### 4.2 Where each number comes from (verified in the code)

| Metric | Source | Exact location |
|---|---|---|
| **Whisper time** | `/upload` JSON response | `pipeline.transcription.processing_time_seconds` (the transcriber returns `processing_time_seconds`, rounded to 2 dp — `transcriber/routes.py`). |
| **Whisper time (alt)** | `voice-app` logs | `docker compose logs voice-app` → `Step 1 done … transcription: N words in X.Xs (T+Y.Ys)`. |
| **Formatting time** | `transcript-formatter` logs | `docker compose logs transcript-formatter` → `Form <id> complete … took X.Xs (confidence: …)` (`transcript-formatter/routes.py`). |
| **Total time** | `voice-app` logs | The pipeline logs cumulative `T+…` markers per step; the last `T+` (or wall‑clock around the curl) is the total. |
| **Transcript accuracy %** | computed by you | Compare the transcript text (`pipeline.transcription.text`) against the ground‑truth reference (Appendix B) — see §6. |

> Tip: also capture the formatter's `confidence.overall` and the response's
> `pipeline.incident_form.status` so you can note quality alongside speed.

### 4.3 Cold vs warm

- **First launch** = cold: includes model load (and first‑ever model **pull**, which you
  should measure separately, §5.C). Always slower.
- **Second launch** = warm: model resident (`OLLAMA_KEEP_ALIVE=-1` keeps it loaded).
  Record both, exactly like the Windows doc does ("First launch" / "Second launch").

---

## 5. The macOS test matrix (run + record)

The user asked for "**everything**", so this is the comprehensive set. Sections **A–B**
mirror the Windows doc; **C–D** are macOS‑specific additions.

### A. Environment record (fill once)

- Mac model + chip: ______ (e.g. MacBook Pro 14", M3 Pro)
- CPU/GPU cores: ______ · Unified RAM: ______ GB
- macOS version: ______ · Docker Desktop version: ______ · Docker VM RAM allotment: ______ GB
- Ollama (host) version: ______
- Benchmark audio: filename ______ · duration ______ (Windows used ~3:28)
- AirPlay Receiver: disabled / left on (UI port used: 5000 / 5050)

### B. Core performance matrix (mirrors Windows)

Run each cell **first launch (cold)** and **second launch (warm)**; record Whisper time,
Formatting time, Total time, Transcript accuracy %.

| # | Ollama mode | OLLAMA_MODEL | WHISPER_MODEL | KV cache | Dutch transl. | Notes |
|---|---|---|---|---|---|---|
| B1 | Native Metal | gemma3:12b | large-v2 | q8_0 | on | default, headline |
| B2 | Native Metal | gemma3:12b | large-v2 | q4_0 | on | cache‑type compare |
| B3 | Native Metal | gemma3:12b | large-v2 | q8_0 | off | translation cost |
| B4 | Native Metal | gemma3:27b | large-v2 | q8_0 | on | heavy model (watch RAM, §C) |
| B5 | Native Metal | gemma3:12b | medium | q8_0 | on | whisper size vs accuracy |
| B6 | Native Metal | gemma3:12b | small | q8_0 | on | whisper size vs accuracy |
| B7 | **Docker CPU** | gemma3:12b | large-v2 | q8_0 | on | "GPU off" baseline |

> Reuse the exact metric layout the Windows doc uses (bullet lists per launch) — see §7.
> The key comparison to surface in prose: **B1 (native Metal) vs B7 (Docker CPU)** for
> Formatting time, and the observation that Whisper time barely moves between them.

### C. macOS‑specific tests (new — not in the Windows doc)

1. **Native (Metal) vs Docker CPU Ollama** — the headline formatting‑time delta. Pull the
   numbers from B1 vs B7 and state the speedup factor.
2. **Whisper CPU ceiling** — since Whisper can't use Metal here, tabulate Whisper time
   across `large-v2 / medium / small` (B1/B5/B6) to show the practical macOS STT floor and
   the accuracy trade‑off at each size.
3. **Cold vs warm start** — for B1, report first‑launch (cold load) vs second‑launch (warm)
   Formatting time; note the effect of `OLLAMA_KEEP_ALIVE=-1`.
4. **Model pull / download time** — time `ollama pull gemma3:12b` and `gemma3:27b` from
   cold on this machine + connection; this is part of real first‑run experience. Record
   download size + wall‑clock.
5. **Memory pressure / OOM** — run B4 (gemma3:27b) and watch **unified memory**: Activity
   Monitor (Memory Pressure graph) or `vm_stat` / `sudo memory_pressure`, plus host Ollama
   logs for any eviction. Note whether 27b fits, swaps, or OOM‑kills, and at what RAM tier
   (it's known to be heavy/slow on macOS). Record peak memory + whether the run completed.
6. **Thermal throttling / sustained load** — fire **5–10 consecutive** B1 calls back‑to‑back
   and record per‑run Total time. On fanless Macs (MacBook Air) times may degrade as the
   chip throttles; on actively‑cooled Macs they should stay flat. Report the per‑run series
   and whether degradation appeared.
7. **Concurrency** — with `OLLAMA_NUM_PARALLEL=1` (default), submit **2 uploads
   simultaneously** and record how requests queue (latency of the 2nd vs a lone request).
   Optionally repeat with `OLLAMA_NUM_PARALLEL=2`.
8. **Port/AirPlay sanity** — confirm whether you used 5050 (overlay default) or disabled
   AirPlay Receiver to free 5000; note any friction.

### D. AI accuracy benchmark suite (rigorous extraction accuracy)

The repo ships an automated extraction benchmark (10 synthetic transcripts, scored on
**accuracy / completeness / hallucination rate**). Run it against the **native Metal Ollama**:

```bash
cd transcript-formatter/benchmark
OLLAMA_URL=http://localhost:11434 OLLAMA_MODEL=gemma3:12b python runner.py
# then repeat for the heavy model:
OLLAMA_URL=http://localhost:11434 OLLAMA_MODEL=gemma3:27b python runner.py
```

Record the **aggregate** accuracy / completeness / hallucination‑rate for each model, and
note the weakest fixtures the runner prints. (See `transcript-formatter/benchmark/README.md`
for metric definitions.) This is the cleanest "accuracy of the AI" number to put in the doc,
independent of transcription timing.

---

## 6. Measuring transcript accuracy (%)

The Windows doc reports figures like "Transcript accuracy: 96.4% / 98.8%". These come from
comparing the Whisper output against a **ground‑truth reference transcript** for one fixed
audio clip. To stay comparable:

1. Use the **same audio** the Windows run used (ask the user).
2. Use the reference transcript in **Appendix B** as ground truth.
3. Compute a word‑level match. Either:
   - **WER‑based**: `accuracy % = (1 − WER) × 100`, where WER is word error rate
     (insertions + deletions + substitutions ÷ reference word count). The `jiwer` Python
     package does this: `pip install jiwer`, then `1 - jiwer.wer(reference, hypothesis)`.
   - Normalise both strings first (lowercase, strip punctuation) so scoring matches the
     Windows methodology of "% of words correct."
4. Also record the relevant knobs the Windows doc found mattered for accuracy: **beam
   size = 3** improved transcription; **`large-v2`** was best for both Dutch and English
   (~98.8%), smaller models trade accuracy for speed.

> If the user can't supply the original audio, state that explicitly in the doc and either
> (a) use a new reference clip and re‑measure Windows too for parity, or (b) leave accuracy
> cells blank with a note. Do **not** invent numbers.

---

## 7. The Word deliverable — structure to produce

Produce **`Performance testing - macOS additions.docx`** (a *separate* file the user pastes
into the online Word doc). **Match the existing document's formatting** so it drops in
cleanly:

- Use real Word heading styles: `Heading 1` for top sections, `Heading 2`/`Heading 3` for
  subsections (the existing doc uses `#`/`##`/`###`).
- Metrics as **bullet lists**, one metric per bullet, exactly like the Windows section:
  ```
  ### First launch:
  • Whisper time:
  • Formatting time:
  • Total time:
  • Transcript accuracy:
  ```
- Commands in a monospace/code style (or a shaded paragraph) so they're copy‑pasteable.
- Fill in measured numbers where you ran them; leave clearly‑marked blanks (`____`) only
  where a run was genuinely not possible, with a one‑line reason.

### Suggested section skeleton (adapt headings to match the existing doc's voice)

```
# macOS Performance Testing

## Platform & setup (macOS)
   - Why macOS differs: no NVIDIA/CUDA in Docker; GPU = host-native Ollama (Metal).
   - Do NOT use docker-compose.gpu.yml on macOS.
   - Native Metal Ollama (GPU-on analog):
       docker compose -f docker-compose.yml -f docker-compose.native-ollama.yml --profile dev up -d --build
   - Docker CPU Ollama (GPU-off baseline):
       docker compose --profile dev up -d --build
   - Prereqs: host Ollama running + models pulled; UI on :5050 (AirPlay holds :5000).
   - Whisper stays CPU-only on macOS (no Metal in the Docker VM).

## Test machine
   - Chip / cores / unified RAM / macOS / Docker versions  (from §5.A)

## Optimal settings (macOS)
   - Best Ollama mode, model, whisper model, KV cache type — your findings.

## <audio> minute talk — native Metal Ollama
   ### First launch:   • Whisper time:  • Formatting time:  • Total time:  • Transcript accuracy:
   ### Second launch:  • Whisper time:  • Formatting time:  • Total time:  • Transcript accuracy:

## <audio> minute talk — Docker CPU Ollama (baseline)
   ### First launch:   • …
   ### Second launch:  • …

## Whisper model comparison (large-v2 vs medium vs small)   ← accuracy vs speed table
## KV cache comparison (q8_0 vs q4_0)
## Dutch translation on vs off

## macOS-specific findings
   ### Native Metal vs Docker CPU Ollama (formatting speedup: __x)
   ### Whisper CPU ceiling (Whisper can't use Metal here)
   ### Cold vs warm start
   ### Model pull/download time
   ### Memory pressure / gemma3:27b on this RAM tier
   ### Thermal / sustained-load (5–10 consecutive calls)
   ### Concurrency (NUM_PARALLEL=1)

## AI extraction accuracy benchmark (gemma3:12b / 27b)
   - accuracy: __   completeness: __   hallucination rate: __   (per model)
```

### Generating the .docx

`python-docx` is already a dependency in this repo
(`scripts/generate_word/requirements.txt`). Quickest path:

```bash
python -m pip install python-docx
```
then a small script: create a `Document()`, add headings with
`doc.add_heading(text, level=1|2|3)`, metric bullets with
`doc.add_paragraph(text, style="List Bullet")`, commands with a `"Intense Quote"` or
monospace run, and `doc.save("Performance testing - macOS additions.docx")`. Save it
somewhere obvious and tell the user the path so they can open it and copy‑paste into the
online Word document.

---

## 8. Guardrails

- **Don't fabricate measurements.** Every number must come from an actual run; mark
  anything you couldn't run as blank with a reason.
- **Keep it comparable to Windows.** Same audio, same reference transcript, same metric
  names and launch structure (first/second launch).
- **Heavy pulls cost time + disk.** `gemma3:27b` and `large-v2` are multi‑GB; warn the user
  before pulling and confirm there's disk space.
- **Don't commit** the generated `.docx` or large artifacts unless the user asks.
- Confirm the actual chip/RAM before running — macOS performance is dominated by the
  Apple Silicon generation and the unified‑memory tier.

---

## Appendix A — Existing Windows document (for format reference)

This is the content of the user's current `Performance testing.docx` (the Windows side), so
you can match its structure, headings, and the kind of numbers expected. Your macOS section
should sit alongside this.

> **Setup / commands (Windows path):**
> - GPU mode (NVIDIA): `docker compose -f docker-compose.yml -f docker-compose.gpu.yml --profile dev up -d --build`
> - CPU alternative: `docker compose --profile dev up -d --build`
> - Rebuild after changing AI settings: delete `local-storage`, then `docker compose down -v`, `docker network prune -f`.
>
> **Optimal settings (Windows):** Ollama `gemma3:12b` (optimal vs heavier 27b);
> KV cache type 8 (`OLLAMA_KV_CACHE_TYPE=8` / `q8_0`) best quality‑vs‑memory, `q4_0`
> cuts model size ~75%; Whisper `large-v2` best for Dutch+English; beam size 3 improves
> transcription accuracy.
>
> **Representative Windows numbers (3:28 talk):**
> - With GPU, 1st launch: Whisper 9.5s · Formatting 328.1s · Total 339.4s · Accuracy 96.4%
> - With GPU, 2nd launch: Whisper 8.9s · Formatting 56.2s · Total 65.3s · Accuracy 96.8%
> - With GPU, large Whisper: Whisper 14.0s · Total 138.1s · Accuracy 98.8%
> - Without GPU, 1st launch: Whisper 74.0s · Formatting 219.0s · Total 297.1s
> - gemma3:12b warm (no GPU): Whisper 68.9s · Formatting 87.7s · Total 157.8s · Accuracy 97%
>
> (The Windows doc records these as `### First/Second launch` headings with
> `• Whisper time / • Formatting time / • Total time / • Transcript accuracy` bullets —
> reproduce that exact shape for macOS.)

## Appendix B — Ground‑truth reference transcript (for accuracy %)

Use this as the reference when computing Transcript accuracy % for the same benchmark audio
(it is the "Original transcription" captured in the Windows doc):

> Tell Ingo 01010426 A new servo drive was received from a third party, the repack program
> was loaded, but the problem was not resolved. Not yet replaced, motion controller card and
> the cable between the servo drive and the card. These parts are not available from repack
> due to long product lifetime. The safety circuit is ok, no fault message, and forming
> station and sealing station do work. The forming station and sealing station complete the
> first cycle, lift up, forming and sealing, lift down, after that the transport does not
> start. No fault message on the HMI. Fault message on the servo drive, ST. The transport
> arrow on the HMI is red, so an output signal is present. Signals on the motion controller
> and the cable cannot be measured. When the cable is disconnected, a fault occurs. A
> technician is currently on site at the customer. Ingo is asking for advice on. Position of
> the rotary switches, top is 0, bottom is 1. Advice regarding the motion controller and
> cabling. Delivery time of the motion controller and cable. Service ticket, MS16000263307,
> installation console inliner. Tell Steven 130326/1110. Discharge conveyor removed, pro
> relocated, console inliner to be installed on Monday. Motor of the discharge conveyor
> disconnected from the drive. Will this cause an alarm. Does a setting need to be adjusted.
> Inliner will be connected and tested next Monday morning. In the electrical diagram, synchro
> and downstream contacts. How should the console synchro be executed. Service ticket,
> MS20650483303, sealing problem cooling water. Tell Marian 230326. Cooling water was not used
> before, now it is, but the sealing problem is still not resolved. Problem, the seal comes
> loose. Problem occurs, 3 to 4 rejects per 400 packages. In case of a reject, the seal is
> smooth at that location. Format 3.2. It is not known where exactly in this section the seal
> is poor. Seal parameters, 2 sec, 150 degrees Celsius, 4 bar. The machine has been idle for a
> long time. Format 3.2 = new section, so the Teflon coating should be ok. Checks and actions.
> Check closing of the lifting system. Check movement of the internal parts of the upper mold
> for the sealing plate / heating plate. Check compressed air / air bladder for movement of the
> sealing plate. Ensure the formed bottom web remains clean on the sealing surface. Ask the
> film supplier for the correct settings. Share photos of the poor seal and indicate the
> position within the 3.2 cycle. Marian will perform these checks first herself, experience
> with seal pack machines. If unsuccessful, a repack technician will be assigned.

---

*End of brief. Work in the repo root; the relevant files are `docker-compose.yml`,
`docker-compose.native-ollama.yml`, `.env.example`, `TESTING.md`,
`transcript-formatter/benchmark/`, and `scripts/generate_word/`.*
