"""
Verification script for Agent 4: The Forensic Analyst
Tests the ForensicDatabase, EvidenceLog, and BloodTestSim systems.
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from systems.forensics import ForensicDatabase, EvidenceLog, BloodTestSim, BiologicalSlipGenerator

def test_forensic_database():
    print("Testing ForensicDatabase...")
    db = ForensicDatabase()
    db.add_tag("Norris", "SUSPICION", "Found in kennel alone", 5)
    db.add_tag("Norris", "IDENTITY", "Claims to be human", 2)
    
    report = db.get_report("Norris")
    print(report)
    
    assert "SUSPICION: Found in kennel alone" in report
    assert "[TURN 2]" in report
    print("  [PASS] ForensicDatabase works.")

def test_evidence_log():
    print("\nTesting EvidenceLog (Chain of Custody)...")
    log = EvidenceLog()
    log.record_event("Blood Key", "GET", "MacReady", "Infirmary", 1)
    log.record_event("Blood Key", "DROP", "MacReady", "Rec Room", 3)
    
    history = log.get_history("Blood Key")
    print(history)
    
    assert "GET by MacReady in Infirmary" in history
    assert "[TURN 3] DROP" in history
    print("  [PASS] EvidenceLog works.")

def test_blood_test():
    print("\nTesting BloodTestSim...")
    sim = BloodTestSim()
    
    # Test Human
    print(sim.start_test("Blair"))
    print(sim.heat_wire())
    print(sim.heat_wire())
    print(sim.heat_wire())
    print(sim.heat_wire())
    result_human = sim.apply_wire(is_infected=False)
    print(f"Human Result: {result_human}")
    assert "HUMAN" in result_human
    
    # Test Infected
    print(sim.start_test("Norris"))
    sim.wire_temp = 100 # Cheat to hot
    result_infected = sim.apply_wire(is_infected=True)
    print(f"Infected Result: {result_infected}")
    assert "SCREAMS" in result_infected or "expands" in result_infected.lower() or "shatters" in result_infected.lower()
    print("  [PASS] BloodTestSim works.")

def test_biological_slips():
    print("\nTesting BiologicalSlipGenerator...")
    slip = BiologicalSlipGenerator.get_visual_slip()
    print(f"Visual Slip: {slip}")
    assert slip in BiologicalSlipGenerator.VISUAL_TELLS
    
    slip_audio = BiologicalSlipGenerator.get_audio_slip()
    print(f"Audio Slip: {slip_audio}")
    assert slip_audio in BiologicalSlipGenerator.AUDIO_TELLS
    print("  [PASS] BiologicalSlipGenerator works.")

if __name__ == "__main__":
    try:
        test_forensic_database()
        test_evidence_log()
        test_blood_test()
        test_biological_slips()
        print("\n*** ALL FORENSIC TESTS PASSED ***")
    except Exception as e:
        print(f"\n[FAIL] Forensic tests failed: {e}")
        sys.exit(1)
