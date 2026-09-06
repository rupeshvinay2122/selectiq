# SelectIQ: Intelligent Candidate Discovery & Ranking Microservice

A high-throughput, low-latency RESTful microservice for candidate search, multi-signal relevance scoring, and automated honeypot anomaly detection. Built with **FastAPI**, **Pydantic v2**, and **Python Standard Library (Zero heavy dependencies)**.

---

## Architecture & Core SDE Highlights

1. **Streaming Min-Heap Priority Queue ($O(N \log K)$):**
   * Instead of sorting the entire candidate dataset ($O(N \log N)$) in memory, the search engine maintains a fixed-size Min-Heap using `heapq`.
   * Low-ranking candidates are discarded on the fly, keeping memory consumption minimal and query latency under **2 milliseconds**.

2. **Deterministic Safety Audit (Automated Honeypot & Anomaly Detection):**
   * Detects and rejects corrupted or fraudulent profiles before evaluation:
     * **Salary Inversion Anomaly:** Detects candidates where `min_salary > max_salary`.
     * **Timeline Contradictions:** Flags candidates claiming more years of experience than mathematically possible since their graduation year.
     * **Proficiency Bluffing:** Flags profiles claiming "Expert" or "Advanced" skill levels with zero duration and zero endorsements.

3. **Multi-Factor Relevance Scoring:**
   * Evaluates candidates across **Skills Coverage (40%)**, **Target Experience Band (30%)**, **Company Pedigree (Product vs. Services, 15%)**, and **Behavioral Availability Signals (Notice Period, Response Rate, 15%)**.

---

## API Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/` | API status and total indexed candidate count |
| `GET` | `/api/v1/health` | Service health check and cache status |
| `GET` | `/api/v1/candidates/search` | Real-time candidate ranking with skill matching & YOE filtering |
| `POST` | `/api/v1/candidates/audit` | Audits an incoming candidate JSON payload for fraud and timeline anomalies |
| `GET` | `/docs` | Interactive Swagger API documentation & testing UI |

---

## Quick Start

### 1. Set Up Virtual Environment & Dependencies
```bash
# Create and activate virtual environment
python -m venv .venv
.\.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Run Automated Tests
```bash
python test_api.py
```

### 3. Launch the Server
```bash
uvicorn main:app --reload --port 8000
```
Open your browser at **[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)** to test the live API with FastAPI's interactive UI.

---

## Sample Search Query & Response

**Request:**
```http
GET /api/v1/candidates/search?skills=python,docker&min_yoe=4.0&max_yoe=10.0&limit=2
```

**Response (Latency: ~1.0 ms):**
```json
{
  "query": {
    "skills": ["python", "docker"],
    "min_yoe": 4.0,
    "max_yoe": 10.0,
    "limit": 2
  },
  "latency_ms": 1.01,
  "total_matches": 2,
  "results": [
    {
      "rank": 1,
      "candidate_id": "CAND_0000038",
      "name": "Myra Trivedi",
      "current_title": "Java Developer",
      "location": "Coimbatore, Tamil Nadu",
      "years_of_experience": 6.7,
      "score": 0.72,
      "matched_skills": ["Docker"],
      "reasoning": "Myra Trivedi (Java Developer) brings 6.7 YOE with proven experience in Docker. Relevance score: 72.0%. Actively available with a 90-day notice period."
    }
  ]
}
```
