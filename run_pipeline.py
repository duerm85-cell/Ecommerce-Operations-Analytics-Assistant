"""Clean local entry point: generate -> validate/analyze -> build dashboard."""
from pathlib import Path
import subprocess, sys

ROOT=Path(__file__).resolve().parent
commands=[[sys.executable,"data/generate_data.py"],[sys.executable,"analysis/run_analysis.py"],[sys.executable,"dashboard/build_dashboard.py"],[sys.executable,"-m","unittest","discover","-s","tests","-v"]]
for command in commands:
    print("\n>"," ".join(command),flush=True)
    subprocess.run(command,cwd=ROOT,check=True)
print("\nV1.1 pipeline completed successfully.")
