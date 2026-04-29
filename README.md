# Trinethra — Supervisor Feedback Analyzer

A web tool that analyzes supervisor call transcripts and produces a structured draft assessment for DT psychology interns to review, edit, and finalize.

**The AI suggests. The intern decides.**

---

## Setup Instructions

### Prerequisites
- Python 3.9+
- [Ollama](https://ollama.com) installed on your machine (free, local, no API key)

### Step 1 — Pull the LLM model

```bash
ollama pull llama3.2
```

> If your machine is slow or has < 8GB RAM, use a smaller model: `ollama pull phi3`
> Then update `MODEL = "phi3"` in `backend/main.py`

### Step 2 — Start Ollama

Ollama runs as a background service after install. If it's not running:

```bash
ollama serve
```

Test it works:
```bash
curl http://localhost:11434/api/generate -d '{"model":"llama3.2","prompt":"Hello","stream":false}'
```

### Step 3 — Install and start the backend

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

You should see: `Uvicorn running on http://127.0.0.1:8000`

### Step 4 — Open the frontend

Open `frontend/index.html` directly in your browser. No build step required.

> The frontend connects to the backend at `http://localhost:8000`.
> The green dot in the top-right confirms Ollama is connected.

### Step 5 — Run an analysis

1. Paste a supervisor transcript (or click one of the 3 sample buttons)
2. Optionally add the Fellow name and company name
3. Click **Run Analysis**
4. Wait 20–60 seconds (depends on your hardware and model size)
5. Review the 5-section output

---

## Architecture

```
[Browser — frontend/index.html]
        |
        | POST /analyze (JSON: transcript, fellow_name, company_name)
        ↓
[FastAPI backend — backend/main.py :8000]
        |
        | POST http://localhost:11434/api/generate
        ↓
[Ollama — llama3.2 running locally]
        |
        | Returns raw text (attempted JSON)
        ↓
[backend: extract_json() with 3-stage fallback parser]
        |
        | Returns structured JSON
        ↓
[Browser — renders 5 sections]
```

**Frontend:** Vanilla HTML/CSS/JS — single file, no build step, no dependencies.  
**Backend:** Python + FastAPI — handles prompt construction, Ollama call, JSON extraction, validation.  
**LLM:** Ollama running llama3.2 locally — no cloud API, no cost, no key.  

---

## Model Choice: llama3.2

I chose **llama3.2 (3B)** because:
- Runs on most laptops (needs ~4GB RAM)
- Follows JSON formatting instructions reliably
- Fast enough for a 10-minute use case

If your machine has 16GB+ RAM, `mistral` (7B) produces better scoring nuance.

---

## Design Challenges Tackled

### Challenge 2: Structured Output Reliability

LLMs don't always return clean JSON. My approach uses a 3-stage extraction fallback in `extract_json()`:

1. Direct `json.loads()` — works if model returns clean JSON
2. Strip markdown fences (` ```json ``` `) and retry
3. Find first `{` to last `}` and extract just that slice

Additionally, I set `temperature: 0.1` to make the output deterministic and consistent. Required fields are validated after parsing — if any of the 5 sections are missing, the API returns a clear error asking the user to retry.

### Challenge 3: Evidence Linking

Each evidence quote is tagged with its `dimension` (execution / systems_building / kpi_impact / change_management) and `signal` (positive / negative / neutral), plus a human-readable `interpretation` explaining what the quote actually means for scoring — including cases where the supervisor is over- or under-weighting it. The dimension coverage grid at the top of the score card gives the intern an at-a-glance view of what was and wasn't covered.

### Challenge 4: Showing Uncertainty

Three design decisions prevent automation bias:

1. The yellow banner at the top of every session: **"This is a draft. The AI suggests — you decide."**
2. Each score includes a `confidence` field (high/medium/low) surfaced in the UI
3. The section header says "Suggested Score" and "Review before finalizing"

The UI deliberately uses neutral language ("suggested", "draft") to prime the intern to treat the output critically.

### Challenge 5: Gap Detection

The prompt explicitly lists all 4 assessment dimensions and instructs the model to flag each one where transcript coverage is absent or weak. The prompt also includes the "Survivability Test" logic and supervisor bias definitions — this is what enables the tool to distinguish Karthik (6, not 8) and Anil (5-6, not 9) from their supervisors' surface-level praise.

---

## Sample Transcript Expected Scores

| Fellow | Expected | Why it's a trap |
|--------|----------|-----------------|
| Karthik | 6–7 | Supervisor is warm. Production sheet is personally maintained — not a self-sustaining system. One genuine Layer 2 signal (cycle time study). |
| Meena | 7–8 | Supervisor is critical due to presence bias. But dispatch risk alert saved a real shipment. Quantified Line 3 rejection — nobody had done this before. |
| Anil | 5–6 | Supervisor is glowing. But Anil is absorbing the founder's work. If he leaves, everything stops. The 3AM story proves personal dependency, not systems. |

---

## What I'd Improve With More Time

1. **Side-by-side view**: Split the screen — transcript on the left, analysis on the right. The intern could see the quote in context without scrolling.

2. **Inline transcript highlighting**: Click an evidence quote → the corresponding sentence in the original transcript highlights. Currently the quotes are shown in isolation.

3. **Confidence-based prompting**: Make a second, focused Ollama call specifically for the 6-vs-7 boundary decision, since this is the most consequential scoring judgment.

4. **Edit and finalize workflow**: Let the intern adjust the score, mark quotes as accepted/rejected, and export a finalized PDF assessment.

5. **Ollama model selection UI**: Let the user pick their model from the frontend rather than editing Python code.

---

## Project Structure

```
trinethra/
├── backend/
│   ├── main.py              ← FastAPI app, prompt engineering, Ollama integration
│   └── requirements.txt
├── frontend/
│   └── index.html           ← Single-file UI, vanilla JS
└── README.md
```
