"""
Trinethra — Supervisor Feedback Analyzer
Backend: FastAPI + Ollama (local LLM)
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests
import json
import re

app = FastAPI(title="Trinethra API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "llama3.2"  # Change to "mistral" or "phi3" if preferred

# ─── Data Models ────────────────────────────────────────────────────────────

class TranscriptRequest(BaseModel):
    transcript: str
    fellow_name: str = ""
    company_name: str = ""

# ─── Prompt Engineering ─────────────────────────────────────────────────────

SYSTEM_CONTEXT = """
You are an expert analyst for DeepThought, a company that places early-career Fellows 
inside manufacturing businesses to build systems and improve operations.

FELLOW PERFORMANCE FRAMEWORK:
Fellows have TWO layers of work:
- Layer 1 (Execution): Attending meetings, tracking output, coordination, data entry. NECESSARY but NOT sufficient.
- Layer 2 (Systems Building): Creating SOPs, trackers, dashboards, workflows that SURVIVE after the Fellow leaves.
A Fellow who only does Layer 1 leaves zero lasting value. This is the most important distinction.

SURVIVABILITY TEST: "If the Fellow left tomorrow, would any system they built keep running?"

RUBRIC (1-10):
- 1 (Not Interested): Disengaged, no effort
- 2 (Lacks Discipline): Works only when told
- 3 (Motivated but Directionless): Enthusiastic but unfocused
- 4 (Careless and Inconsistent): Output exists but quality varies
- 5 (Consistent Performer): Reliable task execution, does what is asked, meets standards
- 6 (Reliable and Productive): High trust, "give task and forget", efficient — but still executing ASSIGNED tasks
- 7 (Problem Identifier): EXPANDS scope — notices problems the supervisor never articulated, flags patterns
- 8 (Problem Solver): Identifies AND fixes problems, builds solutions, creates tools/processes
- 9 (Innovative and Experimental): Tests multiple approaches, iterates, builds new things
- 10 (Exceptional Performer): Flawless, others learn from them, organizational impact

CRITICAL BOUNDARY — 6 vs 7:
- Score 6: "He does everything I give him. Very reliable." → executes within assigned scope
- Score 7: "She noticed our rejection rate goes up on Mondays and started tracking why." → identifies problems supervisor hadn't asked about
The KEY difference: A 6 takes initiative WITHIN assigned scope. A 7 EXPANDS the scope.

SUPERVISOR BIASES TO DETECT AND CORRECT:
1. Helpfulness bias: "She handles all my calls" sounds like 8, but is actually 5-6 (task absorption)
2. Presence bias: "Always on the floor" rated higher than "builds trackers on laptop" — WRONG
3. Halo/horn effect: One big story coloring entire assessment
4. Recency bias: Remembers last 2 weeks, not full tenure
5. Dependency trap: If supervisor says "don't know how we managed before" — check if Fellow's work would COLLAPSE on their departure (that's a 5, not a 9)

ASSESSMENT DIMENSIONS (check all 4):
1. Driving Execution: Gets things done on time, follows up without reminders
2. Systems Building: Created trackers, SOPs, processes others use independently
3. KPI Impact: Connected work to measurable outcomes (speed, quality, cost, satisfaction)
4. Change Management: Got floor team to adopt new processes, handled resistance

8 KPIs:
- Lead Generation: New customers identified/contacted
- Lead Conversion: Leads becoming paying customers  
- Upselling: Selling more to existing customers
- Cross-selling: Selling additional products to existing customers
- NPS: Customer satisfaction
- PAT: Profitability / cost reduction
- TAT: Turnaround time / process speed
- Quality: Defect rates, rejection rates, complaints
"""

def build_prompt(transcript: str, fellow_name: str, company_name: str) -> str:
    fellow_ref = fellow_name if fellow_name else "the Fellow"
    company_ref = company_name if company_name else "the company"

    return f"""
{SYSTEM_CONTEXT}

---
TRANSCRIPT TO ANALYZE:
Fellow: {fellow_ref}
Company: {company_ref}

"{transcript}"
---

INSTRUCTIONS:
Analyze this supervisor transcript carefully. 

IMPORTANT SCORING WARNINGS — avoid these common errors:
- Do NOT give high scores (8-9) just because the supervisor sounds happy. Check if the work would survive the Fellow's departure.
- Do NOT give low scores just because the supervisor sounds critical. Check if there's real systems work being dismissed due to presence bias.
- Do NOT confuse task absorption (Fellow doing manager's job) with systems building. Absorption = score 5-6 max.
- DO detect supervisor bias and note it explicitly in your justification.

Return ONLY a valid JSON object. No explanation before or after. No markdown. No ```json``` fences. Just raw JSON.

The JSON must have exactly this structure:
{{
  "score": {{
    "value": <integer 1-10>,
    "label": "<one of: Not Interested | Lacks Discipline | Motivated but Directionless | Careless and Inconsistent | Consistent Performer | Reliable and Productive | Problem Identifier | Problem Solver | Innovative and Experimental | Exceptional Performer>",
    "band": "<one of: Need Attention | Productivity | Performance>",
    "justification": "<2-3 sentences explaining the score, citing specific transcript evidence, and noting any supervisor bias detected>",
    "confidence": "<one of: high | medium | low>",
    "bias_detected": "<name any supervisor biases present, or 'none detected'>"
  }},
  "evidence": [
    {{
      "quote": "<exact quote from transcript>",
      "signal": "<positive | negative | neutral>",
      "dimension": "<execution | systems_building | kpi_impact | change_management>",
      "interpretation": "<1-2 sentences: what this quote actually means for scoring, including if it's being over/under-weighted by the supervisor>"
    }}
  ],
  "kpiMapping": [
    {{
      "kpi": "<Lead Generation | Lead Conversion | Upselling | Cross-selling | NPS | PAT | TAT | Quality>",
      "evidence": "<what in the transcript connects to this KPI>",
      "systemOrPersonal": "<system | personal>"
    }}
  ],
  "gaps": [
    {{
      "dimension": "<execution | systems_building | kpi_impact | change_management>",
      "detail": "<what specific information is missing from the transcript about this dimension>"
    }}
  ],
  "followUpQuestions": [
    {{
      "question": "<specific question the intern should ask in the next call>",
      "targetGap": "<which gap this addresses>",
      "lookingFor": "<what answer would change the score up or down>"
    }}
  ]
}}

Extract at least 3 evidence quotes. Identify all gaps where transcript coverage is absent or weak. Write 3-5 follow-up questions. Return only the JSON.
"""

# ─── Ollama Call with Retry ──────────────────────────────────────────────────

def call_ollama(prompt: str, attempt: int = 1) -> str:
    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.1,   # Low temp for consistent structured output
                    "top_p": 0.9,
                    "num_predict": 2000
                }
            },
            timeout=120
        )
        response.raise_for_status()
        return response.json()["response"]
    except requests.exceptions.ConnectionError:
        raise HTTPException(
            status_code=503,
            detail="Ollama is not running. Start it with: ollama serve"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ollama error: {str(e)}")


def extract_json(raw: str) -> dict:
    """
    Robust JSON extraction — handles LLM output that may include
    preamble text, markdown fences, or trailing commentary.
    """
    # Strategy 1: Direct parse
    try:
        return json.loads(raw.strip())
    except json.JSONDecodeError:
        pass

    # Strategy 2: Strip markdown fences
    cleaned = re.sub(r"```(?:json)?", "", raw).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Strategy 3: Find first { to last }
    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(raw[start:end+1])
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Could not extract valid JSON from LLM response. Raw output (first 500 chars): {raw[:500]}")


# ─── Routes ─────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    # Check Ollama is reachable
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=5)
        models = [m["name"] for m in r.json().get("models", [])]
        return {"status": "ok", "ollama": "connected", "available_models": models}
    except Exception:
        return {"status": "ok", "ollama": "not_reachable — start with: ollama serve"}


@app.post("/analyze")
def analyze(req: TranscriptRequest):
    if len(req.transcript.strip()) < 100:
        raise HTTPException(status_code=400, detail="Transcript too short. Paste the full supervisor transcript.")

    prompt = build_prompt(req.transcript, req.fellow_name, req.company_name)
    raw_output = call_ollama(prompt)

    try:
        result = extract_json(raw_output)
    except ValueError as e:
        raise HTTPException(
            status_code=422,
            detail=f"LLM returned unparseable output. Try again. Error: {str(e)}"
        )

    # Validate required keys exist
    required_keys = ["score", "evidence", "kpiMapping", "gaps", "followUpQuestions"]
    missing = [k for k in required_keys if k not in result]
    if missing:
        raise HTTPException(
            status_code=422,
            detail=f"LLM output missing required fields: {missing}. Try running analysis again."
        )

    return result
