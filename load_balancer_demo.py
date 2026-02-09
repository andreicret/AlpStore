import sys
import requests
from collections import Counter

URL = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1/api/").rstrip("/") + "/"
# Number of requests
try:
    N = int(input("Number of requests to send: "))
except ValueError:
    print("Invalid number")
    sys.exit(1)

seen = []

print(f"\nHitting {URL} {N} times...\n")

# Send requests
for i in range(1, N + 1):
    try:
        r = requests.get(URL, timeout=5)
        backend = (
            r.headers.get("X-Backend-ID")
            or r.headers.get("X-Backend-Id")
            or "NO_HEADER"
        )
        seen.append(backend)
        print(f"[{i:02d}] Backend: {backend}")
    except Exception as e:
        seen.append("ERROR")
        print(f"[{i:02d}] ERROR: {e}")

print("\n" + "=" * 50)
print("Summary (hits per backend):")

c = Counter(seen)
for backend, count in c.most_common():
    print(f"{count:>3}  {backend}")
