import subprocess
import sys
import time
import os
import threading
import io

# Force stdout/stderr to UTF-8 to prevent encoding crashes on Windows consoles
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
if hasattr(sys.stderr, "buffer"):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

AGENTS = [
    os.path.join("agents", "researcher.py"),
    os.path.join("agents", "simplifier.py"),
    os.path.join("agents", "quiz_master.py"),
    os.path.join("agents", "evaluator.py"),
]

def log_reader(name, stream):
    try:
        for line in iter(stream.readline, ''):
            if line:
                print(f"[{name}] {line.strip()}", flush=True)
    except Exception as e:
        pass

def main():
    print("\n🎓 StudyBand — Starting all agents...\n")
    processes = []

    for agent_path in AGENTS:
        name = os.path.basename(agent_path).replace(".py", "").upper()
        p = subprocess.Popen(
            [sys.executable, agent_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        processes.append((name, p))
        
        # Start a daemon thread to read output without blocking
        t = threading.Thread(target=log_reader, args=(name, p.stdout), daemon=True)
        t.start()
        
        print(f"✅ {name} agent started (PID: {p.pid})")
        time.sleep(1.5)  # small delay so agents don't all hammer Band at once

    print("\n🚀 All 4 agents are running!")
    print("📱 Now open a NEW terminal and run: streamlit run app.py")
    print("🛑 Press Ctrl+C here to stop all agents.\n")

    try:
        while True:
            # Keep main thread alive while subprocesses are running
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\nStopping all agents...")
        for name, p in processes:
            p.terminate()
            print(f"❌ Stopped {name}")
        print("All agents stopped. Goodbye!")

if __name__ == "__main__":
    main()

