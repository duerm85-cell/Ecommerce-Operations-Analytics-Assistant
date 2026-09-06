"""Run the local ETL and quality-gate sequence without external services."""
from pathlib import Path
import subprocess, sys

ROOT=Path(__file__).resolve().parent
# ETL stage order: DWD generation -> DWS/ADS analysis -> dashboard load -> quality gate.
# MySQL remains an optional deployment target; the default executable path uses SQLite.
commands=[[sys.executable,"data/generate_data.py"],[sys.executable,"analysis/run_analysis.py"],[sys.executable,"dashboard/build_dashboard.py"],[sys.executable,"-m","unittest","discover","-s","tests","-v"]]
for command in commands:
    print("\n>"," ".join(command),flush=True)
    subprocess.run(command,cwd=ROOT,check=True)
print("\nV1.1 pipeline completed successfully.")
