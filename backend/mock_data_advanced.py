"""
Advanced Mock Data Script for IMS
Provides multiple failure scenarios and cascade simulations
"""

import asyncio
import httpx
import uuid
import json
from datetime import datetime, timedelta
import random
from typing import List, Dict

API_URL = "http://localhost:8000/api/signals"

class FailureScenario:
    """Defines a failure scenario with timing and component details"""
    
    def __init__(self, name: str, duration_sec: int = 60):
        self.name = name
        self.duration_sec = duration_sec
        self.signals: List[Dict] = []
    
    def add_component_failure(self, component_id: str, component_type: str, 
                              error_type: str, signal_count: int, delay_sec: int = 0):
        """Add a component failure to the scenario"""
        self.signals.append({
            "component_id": component_id,
            "component_type": component_type,
            "error_type": error_type,
            "signal_count": signal_count,
            "delay_sec": delay_sec,
            "message_template": f"Simulated {error_type} failure on {{component_id}}"
        })
    
    async def execute(self, client: httpx.AsyncClient):
        """Execute the scenario"""
        print(f"\n{'='*60}")
        print(f"Scenario: {self.name}")
        print(f"{'='*60}")
        
        for signal_config in self.signals:
            if signal_config["delay_sec"] > 0:
                print(f"Waiting {signal_config['delay_sec']}s before sending signals...")
                await asyncio.sleep(signal_config["delay_sec"])
            
            await self._send_signals(
                client,
                signal_config["component_id"],
                signal_config["component_type"],
                signal_config["error_type"],
                signal_config["signal_count"],
                signal_config["message_template"]
            )
    
    async def _send_signals(self, client: httpx.AsyncClient, component_id: str,
                           component_type: str, error_type: str, count: int, message_template: str):
        """Send signal batch to API"""
        print(f"\nSending {count} {error_type} signals for {component_id}...")
        
        batch = {"signals": []}
        
        for i in range(count):
            batch["signals"].append({
                "signal_id": str(uuid.uuid4()),
                "component_id": component_id,
                "component_type": component_type,
                "error_type": error_type,
                "message": message_template.format(component_id=component_id),
                "payload": {
                    "iteration": i,
                    "synthetic": True,
                    "scenario": self.name
                },
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "source_ip": f"10.0.{random.randint(0, 255)}.{random.randint(1, 254)}",
                "latency_ms": random.uniform(50.0, 8000.0)
            })
            
            # Send in batches of 100
            if len(batch["signals"]) == 100:
                try:
                    response = await client.post(API_URL, json=batch, timeout=30.0)
                    if response.status_code in [200, 202]:
                        print(f"  ✓ Batch sent ({len(batch['signals'])} signals)")
                    else:
                        print(f"  ✗ Batch failed: HTTP {response.status_code}")
                except Exception as e:
                    print(f"  ✗ Error sending batch: {e}")
                
                batch["signals"] = []
        
        # Send remaining signals
        if batch["signals"]:
            try:
                response = await client.post(API_URL, json=batch, timeout=30.0)
                if response.status_code in [200, 202]:
                    print(f"  ✓ Final batch sent ({len(batch['signals'])} signals)")
                else:
                    print(f"  ✗ Final batch failed: HTTP {response.status_code}")
            except Exception as e:
                print(f"  ✗ Error sending final batch: {e}")


def create_scenario_1_rdbms_outage() -> FailureScenario:
    """
    Scenario 1: Primary RDBMS Outage (P0)
    
    A primary database node goes down, causing immediate connection failures.
    This should trigger P0 severity and immediate escalation.
    """
    scenario = FailureScenario("RDBMS Primary Outage", duration_sec=60)
    scenario.add_component_failure(
        component_id="RDBMS_PRIMARY_01",
        component_type="RDBMS",
        error_type="CONNECTION_REFUSED",
        signal_count=300,
        delay_sec=0
    )
    scenario.add_component_failure(
        component_id="RDBMS_REPLICA_01",
        component_type="RDBMS",
        error_type="REPLICATION_LAG",
        signal_count=150,
        delay_sec=2
    )
    return scenario


def create_scenario_2_cascading_failure() -> FailureScenario:
    """
    Scenario 2: Cascading Failure Chain
    
    RDBMS outage triggers cache misses, leading to API gateway timeouts.
    This demonstrates how a single point of failure cascades through the system.
    """
    scenario = FailureScenario("Cascading Failure Chain", duration_sec=90)
    
    # T+0s: RDBMS goes down
    scenario.add_component_failure(
        component_id="RDBMS_PRIMARY_01",
        component_type="RDBMS",
        error_type="CONNECTION_TIMEOUT",
        signal_count=200,
        delay_sec=0
    )
    
    # T+5s: Cache gets hammered with requests
    scenario.add_component_failure(
        component_id="CACHE_CLUSTER_01",
        component_type="CACHE",
        error_type="TIMEOUT",
        signal_count=500,
        delay_sec=5
    )
    scenario.add_component_failure(
        component_id="CACHE_CLUSTER_02",
        component_type="CACHE",
        error_type="TIMEOUT",
        signal_count=500,
        delay_sec=5
    )
    
    # T+10s: API gateway starts timing out
    scenario.add_component_failure(
        component_id="API_GATEWAY_EU",
        component_type="API",
        error_type="503_SERVICE_UNAVAILABLE",
        signal_count=400,
        delay_sec=10
    )
    scenario.add_component_failure(
        component_id="API_GATEWAY_US",
        component_type="API",
        error_type="503_SERVICE_UNAVAILABLE",
        signal_count=400,
        delay_sec=10
    )
    
    return scenario


def create_scenario_3_slow_degradation() -> FailureScenario:
    """
    Scenario 3: Slow Degradation (P2/P3)
    
    A gradual increase in latency across multiple components.
    This tests the system's ability to detect slow burns that might not trigger immediate alerts.
    """
    scenario = FailureScenario("Slow Degradation", duration_sec=120)
    
    # Slowly increasing latency on CACHE
    for wave in range(3):
        scenario.add_component_failure(
            component_id="CACHE_CLUSTER_01",
            component_type="CACHE",
            error_type="HIGH_LATENCY",
            signal_count=100 + (wave * 50),
            delay_sec=wave * 20
        )
    
    # Background noise from API
    for wave in range(2):
        scenario.add_component_failure(
            component_id="API_GATEWAY_EU",
            component_type="API",
            error_type="REQUEST_TIMEOUT",
            signal_count=50,
            delay_sec=wave * 30
        )
    
    return scenario


def create_scenario_4_multi_region_failure() -> FailureScenario:
    """
    Scenario 4: Multi-Region Outage
    
    Simultaneous failures across different geographic regions.
    This tests the system's ability to handle distributed failures.
    """
    scenario = FailureScenario("Multi-Region Outage", duration_sec=75)
    
    # EU Region
    scenario.add_component_failure(
        component_id="RDBMS_EU_01",
        component_type="RDBMS",
        error_type="CONNECTION_REFUSED",
        signal_count=150,
        delay_sec=0
    )
    scenario.add_component_failure(
        component_id="CACHE_EU_01",
        component_type="CACHE",
        error_type="TIMEOUT",
        signal_count=200,
        delay_sec=0
    )
    
    # US Region (delayed by 3s)
    scenario.add_component_failure(
        component_id="RDBMS_US_01",
        component_type="RDBMS",
        error_type="CONNECTION_REFUSED",
        signal_count=150,
        delay_sec=3
    )
    scenario.add_component_failure(
        component_id="CACHE_US_01",
        component_type="CACHE",
        error_type="TIMEOUT",
        signal_count=200,
        delay_sec=3
    )
    
    # APAC Region (delayed by 6s)
    scenario.add_component_failure(
        component_id="RDBMS_APAC_01",
        component_type="RDBMS",
        error_type="CONNECTION_REFUSED",
        signal_count=150,
        delay_sec=6
    )
    scenario.add_component_failure(
        component_id="CACHE_APAC_01",
        component_type="CACHE",
        error_type="TIMEOUT",
        signal_count=200,
        delay_sec=6
    )
    
    return scenario


def create_scenario_5_data_corruption() -> FailureScenario:
    """
    Scenario 5: Data Corruption Detection
    
    RDBMS reports data corruption errors - highest severity.
    This tests P0 severity assignment and critical alerting.
    """
    scenario = FailureScenario("Data Corruption Detection", duration_sec=45)
    
    scenario.add_component_failure(
        component_id="RDBMS_PRIMARY_01",
        component_type="RDBMS",
        error_type="DATA_CORRUPTION",
        signal_count=200,
        delay_sec=0
    )
    scenario.add_component_failure(
        component_id="RDBMS_BACKUP_01",
        component_type="RDBMS",
        error_type="DATA_CORRUPTION",
        signal_count=150,
        delay_sec=2
    )
    scenario.add_component_failure(
        component_id="API_GATEWAY_EU",
        component_type="API",
        error_type="500_INTERNAL_ERROR",
        signal_count=300,
        delay_sec=1
    )
    
    return scenario


async def main():
    """Main entry point - execute all scenarios"""
    
    print("\n" + "="*60)
    print("IMS Advanced Mock Data Simulation")
    print("="*60)
    print(f"Start time: {datetime.utcnow().isoformat()}Z")
    print(f"Target API: {API_URL}\n")
    
    # Create all scenarios
    scenarios = [
        create_scenario_1_rdbms_outage(),
        create_scenario_2_cascading_failure(),
        create_scenario_3_slow_degradation(),
        create_scenario_4_multi_region_failure(),
        create_scenario_5_data_corruption(),
    ]
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        for scenario in scenarios:
            try:
                await scenario.execute(client)
                await asyncio.sleep(2)  # Pause between scenarios
            except Exception as e:
                print(f"\nError executing scenario {scenario.name}: {e}")
    
    print("\n" + "="*60)
    print("All scenarios complete!")
    print(f"End time: {datetime.utcnow().isoformat()}Z")
    print("="*60)
    print("\nNext steps:")
    print("1. Check the IMS Dashboard (http://localhost:3001)")
    print("2. Review incident severity assignments")
    print("3. Verify debouncing and signal deduplication")
    print("4. Test RCA submission workflow")
    print("5. Check MTTR calculation after closure")


if __name__ == "__main__":
    asyncio.run(main())
