import asyncio
import httpx
import uuid
from datetime import datetime
import random

API_URL = "http://localhost:8000/api/signals"

async def send_signals(client, component_id, component_type, error_type, count):
    print(f"Simulating {count} {error_type} signals for {component_id}...")
    batch = {
        "signals": []
    }
    for i in range(count):
        batch["signals"].append({
            "signal_id": str(uuid.uuid4()),
            "component_id": component_id,
            "component_type": component_type,
            "error_type": error_type,
            "message": f"Simulated failure: {error_type} at {datetime.utcnow().isoformat()}",
            "payload": {"iteration": i, "synthetic": True},
            "timestamp": datetime.utcnow().isoformat(),
            "source_ip": "10.0.0.1",
            "latency_ms": random.uniform(10.0, 5000.0)
        })
        
        # Send in batches of 100 to avoid overly large payloads
        if len(batch["signals"]) == 100:
            try:
                await client.post(API_URL, json=batch)
                batch["signals"] = []
            except Exception as e:
                print(f"Failed to send batch: {e}")
                
    if batch["signals"]:
        try:
            await client.post(API_URL, json=batch)
        except Exception as e:
            print(f"Failed to send batch: {e}")


async def simulate_outage():
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Step 1: Massive RDBMS Outage (P0) - 500 signals
        rdbms_task = send_signals(client, "RDBMS_PRIMARY_01", "RDBMS", "CONNECTION_REFUSED", 500)
        
        # Wait a bit
        await asyncio.sleep(2)
        
        # Step 2: Cascading Cache Failures (P2) - 2000 signals across 2 clusters
        cache1_task = send_signals(client, "CACHE_CLUSTER_01", "CACHE", "TIMEOUT", 1000)
        cache2_task = send_signals(client, "CACHE_CLUSTER_02", "CACHE", "TIMEOUT", 1000)
        
        # Step 3: API Gateway failures (P1)
        api_task = send_signals(client, "API_GATEWAY_EU", "API", "503_SERVICE_UNAVAILABLE", 500)

        await asyncio.gather(rdbms_task, cache1_task, cache2_task, api_task)
        print("Simulation complete! Check the UI and backend logs.")

if __name__ == "__main__":
    asyncio.run(simulate_outage())
