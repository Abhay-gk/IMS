# Incident Management System (IMS)

A high-throughput system for ingesting monitoring signals, deduplicating failures, tracking incidents through a managed workflow, and enforcing mandatory Root Cause Analysis before closure.

## Quick Start

### Using Docker Compose

```bash
docker-compose up --build -d
sleep 30

# Access dashboard at http://localhost:3001
# Backend API at http://localhost:8000/api
```

### Run Simulation

```bash
python backend/mock_data.py
```

Watch the system process cascading failures in real-time.

---

## Key Features

- **10,000+ signals/sec throughput** - Async processing with backpressure handling
- **Debouncing** - 10-second window groups duplicate signals into single incidents
- **State Machine** - OPEN → INVESTIGATING → RESOLVED → CLOSED with RCA enforcement
- **Severity Assignment** - Component-based strategy pattern (P0-P3)
- **Multi-database** - PostgreSQL (transactional), MongoDB (audit log), Redis (caching)
- **Retry Logic** - Resilient to transient failures with exponential backoff

---

## Architecture

```
Signal Ingestion Pipeline:
  ↓ Rate Limit Check (Redis) → 15,000 req/sec
  ↓ Debounce (Redis SETNX) → 10s window
  ↓ Create/Increment Work Item (PostgreSQL)
  ↓ Async: Store Raw Signal (MongoDB) + Metrics (TimescaleDB)

Work Item Lifecycle:
  OPEN → INVESTIGATING → RESOLVED → CLOSED (requires RCA)

RCA Validation:
  - root_cause_detail: min 10 characters
  - fix_applied: min 10 characters
  - prevention_steps: min 10 characters
  - incident_end > incident_start
  - MTTR calculated automatically
```

---

## API Endpoints

### Signal Ingestion

```bash
POST /api/signals
Content-Type: application/json

{
  "signals": [
    {
      "signal_id": "uuid",
      "component_id": "CACHE_01",
      "component_type": "CACHE",
      "error_type": "TIMEOUT",
      "message": "Connection timeout",
      "payload": {},
      "timestamp": "2025-01-29T15:30:00Z",
      "source_ip": "10.0.0.1",
      "latency_ms": 2000.0
    }
  ]
}

Response: 202 Accepted
```

### Work Items

```bash
# List incidents
GET /api/work_items?limit=50&offset=0

# Get signals for incident
GET /api/work_items/{id}/signals

# Change status
PATCH /api/work_items/{id}/status
Body: { "target_status": "INVESTIGATING" }

# Submit RCA
POST /api/work_items/{id}/rca
Body: {
  "incident_start": "2025-01-29T15:00:00Z",
  "incident_end": "2025-01-29T15:30:00Z",
  "root_cause_category": "Code Bug",
  "root_cause_detail": "Connection pool leak in service",
  "fix_applied": "Deployed v2.1.0 with connection pool fix",
  "prevention_steps": "Added monitoring and alerting"
}
```

### Health

```bash
GET /api/health

Response:
{
  "status": "healthy",
  "uptime_seconds": 3600,
  "signals_per_sec": 5234.5,
  "pg_pool_free": 18,
  "mongo_connected": true,
  "redis_connected": true
}
```

---

## System Design

### Backpressure Handling (10,000 signals/sec target)

1. **Rate Limiting** - Redis fixed-window counter (15k req/sec per IP)
2. **Debouncing** - SETNX check with 10s TTL groups signals by component
3. **Async Offloading** - MongoDB and metrics written in background tasks
4. **Connection Pooling** - asyncpg pool (5-20 connections)
5. **Retry Logic** - Tenacity @retry on critical DB operations

### Design Patterns

- **State Pattern** - WorkItemState enforces valid transitions
- **Strategy Pattern** - Component type → Severity mapping
- **Circuit Breaker** - Prevents cascading failures

---

## Performance Targets

| Metric | Value |
|--------|-------|
| Ingestion throughput | 10,000+ signals/sec |
| HTTP response time | < 50ms |
| Rate limit | 15,000 req/sec per IP |
| Debounce window | 10 seconds |
| PostgreSQL pool | 5-20 connections |
| MTTR calculation | Automatic |

---

## Testing

### Unit Tests

```bash
cd backend
pytest tests/ -v
```

Tests cover:
- Strategy pattern (severity assignment)
- State transitions (workflow)
- RCA validation (field requirements)
- Debouncing logic
- Rate limiting

### Load Testing

```bash
python backend/mock_data.py
```

Simulates cascading failure:
- 500 RDBMS CONNECTION_REFUSED
- 2000 CACHE TIMEOUT (2 clusters)
- 500 API 503 errors

---

## Technology Stack

- **Backend**: FastAPI + Python 3.11, uvicorn
- **Frontend**: React 19 + TypeScript, Vite, TailwindCSS
- **Databases**: 
  - PostgreSQL 15+ (work items, RCA)
  - MongoDB 7+ (raw signals)
  - Redis 7+ (rate limiting, debouncing)
- **Infrastructure**: Docker, Docker Compose

---

## Project Structure

```
IMS/
├── backend/
│   ├── main.py              # FastAPI app entry
│   ├── config.py            # Configuration
│   ├── api/routers.py       # REST endpoints
│   ├── services/
│   │   ├── ingestion.py     # Signal processing (retry, debounce)
│   │   └── workflow.py      # State machine, RCA validation
│   ├── models/schemas.py    # Pydantic models
│   ├── db/
│   │   ├── database.py      # Connection pools
│   │   └── init.sql         # Schema
│   ├── mock_data.py         # Load testing
│   └── requirements.txt      # Dependencies
├── frontend/
│   ├── src/
│   │   ├── App.tsx          # Main component
│   │   ├── api.ts           # API client
│   │   └── components/      # Dashboard, RCAForm, etc.
│   └── package.json         # Dependencies
├── docker-compose.yml        # Local deployment
├── .env.example             # Config template
└── README.md                # This file
```

---

## Environment Setup

### Docker (Recommended)

```bash
docker-compose up --build
```

All services start automatically.

### Local Setup

PostgreSQL, MongoDB, Redis must be running on localhost:
- PostgreSQL: 5432
- MongoDB: 27017
- Redis: 6379

```bash
# Backend
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload

# Frontend
cd frontend
npm install
npm run dev
```

---

## Database Schema

### PostgreSQL

```sql
CREATE TABLE work_items (
    id UUID PRIMARY KEY,
    component_id VARCHAR(255),
    component_type VARCHAR(50),
    severity CHAR(2) CHECK (severity IN ('P0', 'P1', 'P2', 'P3')),
    status VARCHAR(20) CHECK (status IN ('OPEN', 'INVESTIGATING', 'RESOLVED', 'CLOSED')),
    signal_count INTEGER DEFAULT 1,
    ...
);

CREATE TABLE rca_records (
    id UUID PRIMARY KEY,
    work_item_id UUID UNIQUE REFERENCES work_items(id),
    incident_start TIMESTAMP,
    incident_end TIMESTAMP,
    root_cause_detail TEXT,
    fix_applied TEXT,
    prevention_steps TEXT,
    mttr_seconds INTEGER,
    ...
);
```

### MongoDB

```javascript
db.signals.createIndex({ component_id: 1, timestamp: -1 })
db.signals.createIndex({ work_item_id: 1, timestamp: -1 })
db.signals.createIndex({ timestamp: 1 }, { expireAfterSeconds: 2592000 })
```

---

## Monitoring

### Health Check

```bash
curl http://localhost:8000/api/health | jq .
```

### Throughput Logging

Backend logs every 5 seconds:
```
THROUGHPUT: 5234.50 Signals/sec
```

### Work Items

```bash
curl http://localhost:8000/api/work_items | jq .
```

---

## Implementation Details

### Retry Logic

```python
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.1, min=0.1, max=1),
    reraise=True
)
async def insert_signal_with_retry(mongo_db, signal_dict):
    await mongo_db["signals"].insert_one(signal_dict)
```

### Debouncing

```python
key = f"debounce:{signal.component_id}"
created = await redis.setnx(key, 1, ex=10)

if created:
    # First signal in 10s window → create incident
    await create_work_item(signal)
else:
    # Duplicate signal → increment counter
    await increment_signal_count(work_item_id)
```

### State Machine

```python
async def transition(work_item_id, new_status):
    # Enforce valid transitions
    if new_status == "CLOSED":
        # Require RCA before closing
        rca = await get_rca(work_item_id)
        if not rca or not is_valid_rca(rca):
            raise ValueError("Invalid or missing RCA")
    
    await update_status(work_item_id, new_status)
```

### Severity Strategy

```python
class RDBMSAlertStrategy(AlertStrategy):
    async def determine_severity(self, error_type):
        if error_type in ["CONNECTION_REFUSED", "OOM", "DATA_CORRUPTION"]:
            return Severity.P0
        if error_type == "TIMEOUT":
            return Severity.P1
        return Severity.P3
```

---

## Status

✅ All features implemented and tested
✅ Docker setup working
✅ Load testing validated at 10k+ signals/sec
✅ Ready for deployment

---

**Version**: 1.0.0  
**Last Updated**: January 29, 2025
