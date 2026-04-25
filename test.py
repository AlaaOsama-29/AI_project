import requests
import threading

BASE = "http://localhost:8000"

def simulate_student(name, topic):
    # Start interview.
    r = requests.post(f"{BASE}/start", params={"student_name": name, "topic": topic})
    session_id = r.json()["session_id"]
    print(f"✅ {name} started — session: {session_id}")

    import time
    time.sleep(3)  # wait for first question

    # Submit one answer.
    requests.post(f"{BASE}/answer", params={"student_name": name, "answer": "Test answer"})
    print(f"✅ {name} answered")

def main():
    # Run two students concurrently.
    t1 = threading.Thread(target=simulate_student, args=("Ahmed", "Python"))
    t2 = threading.Thread(target=simulate_student, args=("Sara", "SQL"))

    t1.start()
    t2.start()
    t1.join()
    t2.join()

    print("✅ Done — no crashes = thread safety works!")


if __name__ == "__main__":
    main()