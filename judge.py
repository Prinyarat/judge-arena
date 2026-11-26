import os, time, requests

JUDGE0_URL = os.getenv("JUDGE0_URL", "https://ce.judge0.com").rstrip("/")
JUDGE0_TOKEN = os.getenv("JUDGE0_AUTH_TOKEN", "").strip()

# Judge0 language IDs: GNU G++17, GNU G++20, Python 3, Java 17.
LANGUAGES = {
    "cpp17": 54,
    "cpp20": 105,
    "python": 71,
    "java": 62,
}

def _headers():
    h = {"Content-Type": "application/json"}
    if JUDGE0_TOKEN:
        h["X-Auth-Token"] = JUDGE0_TOKEN
    return h

def _submit_one(language, source, stdin, time_limit_ms, memory_mb):
    payload = {
        "source_code": source,
        "language_id": LANGUAGES[language],
        "stdin": stdin,
        "cpu_time_limit": max(0.2, min(time_limit_ms / 1000, 5)),
        "wall_time_limit": max(1, min(time_limit_ms / 1000 + 2, 10)),
        "memory_limit": max(32768, min(memory_mb, 512) * 1024),
        "base64_encoded": False,
    }
    response = requests.post(
        f"{JUDGE0_URL}/submissions?base64_encoded=false&wait=false",
        json=payload, headers=_headers(), timeout=15
    )
    response.raise_for_status()
    token = response.json().get("token")
    if not token:
        raise RuntimeError("Judge service did not return a submission token")

    deadline = time.monotonic() + 35
    while time.monotonic() < deadline:
        result_response = requests.get(
            f"{JUDGE0_URL}/submissions/{token}?base64_encoded=false",
            headers=_headers(), timeout=15
        )
        result_response.raise_for_status()
        result = result_response.json()
        status = (result.get("status") or {}).get("id")
        if status not in (1, 2):
            return result
        time.sleep(0.6)
    raise TimeoutError("Judge service polling timed out")

def run_submission(language: str, source: str, tests: list, time_limit_ms: int, memory_mb: int):
    if language not in LANGUAGES:
        return "CE", 0, "Unsupported language"
    if not tests:
        return "SE", 0, "This problem has no test cases configured."

    max_ms = 0
    passed = 0
    try:
        for index, test in enumerate(tests, start=1):
            result = _submit_one(
                language, source, test.get("input", ""),
                time_limit_ms, memory_mb
            )
            status_id = (result.get("status") or {}).get("id")
            time_s = result.get("time")
            if time_s is not None:
                max_ms = max(max_ms, int(float(time_s) * 1000))
            if status_id == 6:
                return "CE", max_ms, (result.get("compile_output") or result.get("stderr") or "Compilation error")[:3000]
            if status_id in (5,):
                return "TLE", max_ms, f"Time limit exceeded on test {index}"
            if status_id in (7, 8, 9, 10, 11, 12, 13):
                return "RE", max_ms, (result.get("stderr") or (result.get("status") or {}).get("description") or "Runtime error")[:3000]
            if status_id == 14 or status_id in (1, 2) or status_id is None:
                return "SE", max_ms, "Judge service returned an incomplete or internal-error result."
            if status_id != 3:
                return "SE", max_ms, (result.get("status") or {}).get("description", "Unknown judge status")

            actual = (result.get("stdout") or "").replace("\r\n", "\n").strip()
            expected = (test.get("output") or "").replace("\r\n", "\n").strip()
            if actual != expected:
                return "WA", max_ms, f"Wrong Answer on test {index}\nExpected:\n{expected[:1000]}\n\nGot:\n{actual[:1000]}"
            passed += 1

        return "AC", max_ms, f"Passed all {passed} test cases"
    except requests.RequestException as exc:
        return "SE", max_ms, f"Judge service connection error: {str(exc)[:500]}"
    except TimeoutError as exc:
        return "TLE", max_ms, str(exc)
    except Exception as exc:
        return "SE", max_ms, f"Judge service error: {str(exc)[:500]}"
