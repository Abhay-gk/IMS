# Mock Data and Failure Scenario Documentation

## Overview

The IMS includes comprehensive mock data generation capabilities to simulate realistic failure scenarios across the entire system stack. This enables testing of:

- Signal ingestion at high throughput (10k+ signals/sec)
- Severity assignment via component-based strategy pattern
- Cascading failure detection
- Incident deduplication and debouncing
- RCA workflow validation

---

## Mock Data Scripts

### 1. Basic Simulation: `mock_data.py`

Simple script for rapid testing of core functionality.

```bash
python backend/mock_data.py
```

**Features**:
- RDBMS outage simulation (500 signals, P0 severity)
- Cache cluster failures (2000 signals across 2 clusters, P2 severity)
- API Gateway failures (500 signals, P1 severity)
- Parallel batch processing with 100-signal batches

**Expected Behavior**:
- Work items created for each unique component_id
- Signals deduplicated via 10-second debouncing window
- Severity auto-assigned: RDBMS → P0, API → P1, CACHE → P2

---

### 2. Advanced Scenarios: `mock_data_advanced.py`

Comprehensive scenario-based testing with detailed timing control.

```bash
python backend/mock_data_advanced.py
```

**Features**:
- 5 distinct failure scenarios with staged execution
- Configurable delays between component failures
- Real-time progress reporting
- Error handling and retry logic
- Detailed payloads with realistic failure details

**Scenarios Included**:

#### Scenario 1: RDBMS Primary Outage (P0)

Simulates primary database node failure with replica issues.

```
T+0s: RDBMS_PRIMARY_01 → CONNECTION_REFUSED (300 signals)
T+2s: RDBMS_REPLICA_01 → REPLICATION_LAG (150 signals)
```

**Expected Result**: Single P0 incident for RDBMS_PRIMARY_01

---

#### Scenario 2: Cascading Failure Chain (P0 → P2 → P1)

Demonstrates how a single failure propagates through dependent services.

```
T+0s:  RDBMS_PRIMARY_01 → CONNECTION_TIMEOUT (200 signals)
T+5s:  CACHE_CLUSTER_01 → TIMEOUT (500 signals)
       CACHE_CLUSTER_02 → TIMEOUT (500 signals)
T+10s: API_GATEWAY_EU → 503_SERVICE_UNAVAILABLE (400 signals)
       API_GATEWAY_US → 503_SERVICE_UNAVAILABLE (400 signals)
```

**Expected Result**: Three separate incidents (RDBMS P0, CACHE P2, API P1) showing cascade

---

#### Scenario 3: Slow Degradation (P2/P3)

Tests detection of gradual performance degradation without hard failures.

```
T+0s:  CACHE_CLUSTER_01 → HIGH_LATENCY wave 1 (100 signals)
T+20s: CACHE_CLUSTER_01 → HIGH_LATENCY wave 2 (150 signals)
T+40s: CACHE_CLUSTER_01 → HIGH_LATENCY wave 3 (200 signals)
T+0s:  API_GATEWAY_EU → REQUEST_TIMEOUT wave 1 (50 signals)
T+30s: API_GATEWAY_EU → REQUEST_TIMEOUT wave 2 (50 signals)
```

**Expected Result**: Incrementally increasing P2 incidents showing trend analysis capability

---

#### Scenario 4: Multi-Region Outage

Simultaneous failures across geographically distributed regions.

```
T+0s: EU Region
      RDBMS_EU_01 → CONNECTION_REFUSED (150 signals)
      CACHE_EU_01 → TIMEOUT (200 signals)

T+3s: US Region
      RDBMS_US_01 → CONNECTION_REFUSED (150 signals)
      CACHE_US_01 → TIMEOUT (200 signals)

T+6s: APAC Region
      RDBMS_APAC_01 → CONNECTION_REFUSED (150 signals)
      CACHE_APAC_01 → TIMEOUT (200 signals)
```

**Expected Result**: 3 P0 incidents + 3 P2 incidents, each region independent

---

#### Scenario 5: Data Corruption Detection (P0 - CRITICAL)

Highest severity scenario requiring immediate intervention.

```
T+0s: RDBMS_PRIMARY_01 → DATA_CORRUPTION (200 signals)
T+2s: RDBMS_BACKUP_01 → DATA_CORRUPTION (150 signals)
T+1s: API_GATEWAY_EU → 500_INTERNAL_ERROR (300 signals)
```

**Expected Result**: P0 incident with data corruption alert, backup verification failure

---

## Sample Data: `sample_failure_scenarios.json`

JSON file containing realistic failure payloads for external testing, CI/CD integration, or manual API testing.

**Structure**:
```json
[
  {
    "scenario": "Scenario Name",
    "description": "Detailed description",
    "signals": [
      {
        "signal_id": "UUID",
        "component_id": "COMPONENT_NAME",
        "component_type": "RDBMS|CACHE|API",
        "error_type": "ERROR_TYPE",
        "message": "Human-readable error message",
        "payload": { /* detailed context */ },
        "timestamp": "ISO-8601 timestamp",
        "source_ip": "IP address",
        "latency_ms": "float value"
      }
    ]
  }
]
```

**Example Payloads Included**:

1. **RDBMS Failure**:
   ```json
   {
     "error_type": "CONNECTION_REFUSED",
     "payload": {
       "host": "db-primary.us-east-1.internal",
       "port": 5432,
       "error_code": "ECONNREFUSED",
       "attempts": 3
     }
   }
   ```

2. **Cache Timeout**:
   ```json
   {
     "error_type": "TIMEOUT",
     "payload": {
       "operation": "GET",
       "key_pattern": "user_session:*",
       "timeout_ms": 5000,
       "queue_depth": 45000
     }
   }
   ```

3. **API Service Unavailable**:
   ```json
   {
     "error_type": "503_SERVICE_UNAVAILABLE",
     "payload": {
       "healthy_instances": 0,
       "total_instances": 10,
       "http_status": 503,
       "circuit_breaker_state": "OPEN"
     }
   }
   ```

4. **Data Corruption**:
   ```json
   {
     "error_type": "DATA_CORRUPTION",
     "payload": {
       "table": "work_items",
       "rows_affected": 1250,
       "expected_checksum": "abc123def456",
       "actual_checksum": "xyz789uvw012",
       "recovery_level": "CRITICAL"
     }
   }
   ```

---

## How to Use

### Running Simulations

**Option 1: Basic Test (2-3 minutes)**
```bash
cd backend
python mock_data.py
```

**Option 2: Comprehensive Test (8-10 minutes)**
```bash
cd backend
python mock_data_advanced.py
```

### Testing Specific Scenarios

Modify `mock_data_advanced.py` to select scenarios:

```python
# In main() function
scenarios = [
    # create_scenario_1_rdbms_outage(),
    create_scenario_2_cascading_failure(),
    # create_scenario_3_slow_degradation(),
    # create_scenario_4_multi_region_failure(),
    # create_scenario_5_data_corruption(),
]
```

### Manual API Testing

Send sample data directly via cURL:

```bash
curl -X POST http://localhost:8000/api/signals \
  -H "Content-Type: application/json" \
  -d @sample_failure_scenarios.json
```

Or use Python:

```python
import json
import httpx

with open('sample_failure_scenarios.json') as f:
    scenarios = json.load(f)

for scenario in scenarios:
    payload = {"signals": scenario["signals"]}
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/api/signals",
            json=payload
        )
        print(f"{scenario['scenario']}: {response.status_code}")
```

---

## Verification Checklist

After running simulations, verify the following on the IMS Dashboard (http://localhost:3001):

- [ ] All signals received and processed
- [ ] Work items created with correct severity levels:
  - RDBMS errors → P0 (RED)
  - API errors → P1 (ORANGE)
  - CACHE errors → P2 (YELLOW)
  - Other → P3 (BLUE)
- [ ] Signal counts match expected deduplication (10s window)
- [ ] Cascading scenarios show related incidents
- [ ] Multi-region failures create separate incidents
- [ ] RCA form allows field submission with validation
- [ ] MTTR calculation works after incident closure

---

## Performance Benchmarks

**Expected Results** (on modern hardware):

- **Signal Throughput**: 10,000+ signals/sec sustained
- **Debounce Effectiveness**: 95-98% reduction in duplicates
- **API Response Time**: <50ms for signal ingestion (HTTP 202)
- **Incident Creation**: <100ms from signal receipt
- **Dashboard Refresh**: 5-second polling interval

---

## Error Codes and Severity Mapping

| Component | Error Type | Severity | Example |
|-----------|-----------|----------|---------|
| RDBMS | CONNECTION_REFUSED | P0 | DB node down |
| RDBMS | DATA_CORRUPTION | P0 | Integrity failure |
| RDBMS | CONNECTION_TIMEOUT | P0 | Pool exhaustion |
| API | 503_SERVICE_UNAVAILABLE | P1 | All instances down |
| API | 500_INTERNAL_ERROR | P1 | Unrecoverable error |
| CACHE | TIMEOUT | P2 | Queue backlog |
| CACHE | HIGH_LATENCY | P2 | Performance degradation |
| Any | Unknown | P3 | Default fallback |

---

## Troubleshooting

**Issue**: No signals received
- Check API is running: `curl http://localhost:8000/api/health`
- Verify Docker containers: `docker ps`
- Check backend logs: `docker logs ims-backend`

**Issue**: Signals received but no incidents created
- Check database connectivity in backend logs
- Verify PostgreSQL is running and initialized
- Check signal format matches schema in `models/schemas.py`

**Issue**: Incorrect severity assignment
- Verify component_type matches enum values
- Check error_type mapping in `services/workflow.py`
- Review strategy pattern implementation

---

## Next Steps

1. Run `mock_data_advanced.py` to generate comprehensive test data
2. Monitor IMS Dashboard for incident creation
3. Test RCA submission with realistic incident data
4. Validate MTTR calculation on incident closure
5. Review logs for performance metrics

---

**Last Updated**: May 4, 2026  
**IMS Version**: 1.0 (Production Ready)
