import asyncio
import time
import httpx

TARGET_URL = "http://localhost:8000/api/v1/logs"
METRICS_URL = "http://localhost:8000/api/v1/metrics"

TOTAL_REQUESTS = 200
CONCURRENCY = 20

SAMPLE_PAYLOADS = [
    {
        "service_name": "payment-service",
        "level": "ERROR",
        "message": "KeyError: 'jwt_token' missing in request header at auth_middleware.py:15",
        "stack_trace": "Traceback (most recent call last):\n  File 'auth_middleware.py', line 15, in check\nKeyError: 'jwt_token'",
        "timestamp": "2026-09-11T12:00:00Z"
    },
    {
        "service_name": "order-service",
        "level": "CRITICAL",
        "message": "psycopg2.OperationalError: server closed the connection unexpectedly",
        "stack_trace": "Traceback (most recent call last):\n  File 'db_pool.py', line 44, in get_conn\nOperationalError",
        "timestamp": "2026-09-11T12:00:01Z"
    },
    {
        "service_name": "inventory-service",
        "level": "INFO",
        "message": "Stock check completed for item #4921",
        "stack_trace": "",
        "timestamp": "2026-09-11T12:00:02Z"
    }
]


async def send_log(client: httpx.AsyncClient, semaphore: asyncio.Semaphore, payload: dict, latencies: list):
    async with semaphore:
        start = time.perf_counter()
        try:
            resp = await client.post(TARGET_URL, json=payload, timeout=5.0)
            latency = (time.perf_counter() - start) * 1000
            latencies.append((resp.status_code, latency))
        except Exception:
            latencies.append((500, (time.perf_counter() - start) * 1000))


async def run_benchmark():
    print(f"🔥 Starting load benchmark: {TOTAL_REQUESTS} requests, concurrency = {CONCURRENCY}...")
    semaphore = asyncio.Semaphore(CONCURRENCY)
    latencies = []

    limits = httpx.Limits(max_connections=CONCURRENCY, max_keepalive_connections=CONCURRENCY)
    async with httpx.AsyncClient(limits=limits) as client:
        start_total = time.perf_counter()
        tasks = []

        for i in range(TOTAL_REQUESTS):
            payload = SAMPLE_PAYLOADS[i % len(SAMPLE_PAYLOADS)]
            tasks.append(send_log(client, semaphore, payload, latencies))

        await asyncio.gather(*tasks)
        total_time = time.perf_counter() - start_total

    success_codes = [code for code, lat in latencies if code in (200, 202)]
    raw_latencies = [lat for code, lat in latencies if code in (200, 202)]

    throughput = len(latencies) / total_time
    avg_latency = sum(raw_latencies) / len(raw_latencies) if raw_latencies else 0
    p95_latency = sorted(raw_latencies)[int(len(raw_latencies) * 0.95)] if raw_latencies else 0

    print("\n" + "=" * 45)
    print("📊 INGESTION BENCHMARK RESULTS")
    print("=" * 45)
    print(f"Total Requests Sent   : {len(latencies)}")
    print(f"Successful (2xx)      : {len(success_codes)}")
    print(f"Failed / Errors       : {len(latencies) - len(success_codes)}")
    print(f"Total Elapsed Time    : {total_time:.2f}s")
    print(f"Throughput            : {throughput:.2f} req/s")
    print(f"Average Ingest Latency: {avg_latency:.2f} ms")
    print(f"p95 Latency           : {p95_latency:.2f} ms")

    # Await background triage worker completion
    print("\n⏳ Waiting 5s for background triage workers to complete...")
    await asyncio.sleep(5)

    try:
        async with httpx.AsyncClient() as client:
            res = await client.get(METRICS_URL)
            if res.status_code == 200:
                metrics = res.json()
                print("\n📈 ENGINE TELEMETRY SNAPSHOT")
                print(f"Total Logs in System  : {metrics.get('total_logs_ingested')}")
                print(f"Cache Hit Ratio       : {metrics.get('cache_hit_ratio_percent')}%")
                print(f"Cache Hits / Misses   : {metrics.get('cache_hits')} / {metrics.get('cache_misses')}")
                print(f"Total Incidents       : {metrics.get('total_incidents')}")
                print(f"Open / Resolved       : {metrics.get('open_incidents')} / {metrics.get('resolved_incidents')}")
    except Exception as e:
        print(f"Could not retrieve SLA metrics: {e}")
    print("=" * 45)


if __name__ == "__main__":
    asyncio.run(run_benchmark())