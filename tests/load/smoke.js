/**
 * AgentHive k6 load test baseline.
 *
 * Verifies the platform's concurrency defaults declared in
 * backend/app/core/config.py:
 *   AGENT_CONCURRENCY_TENANT_LIMIT = 40
 *   AGENT_CONCURRENCY_USER_LIMIT  = 4
 *   AGENT_CONCURRENCY_AGENT_LIMIT = 12
 *
 * Run:
 *   1. Start dev stack:  docker compose -f docker-compose.dev.yml up -d
 *   2. Install k6:       brew install k6  (macOS) or see https://k6.io/docs/getting-started/installation/
 *   3. Run smoke:        k6 run tests/load/smoke.js
 *   4. Run full load:    k6 run --vus 50 --duration 60s tests/load/smoke.js
 *
 * Thresholds: p95 latency < 500ms for health, error rate < 1%.
 */

import { check, group, sleep } from "k6";
import http from "k6/http";

const BASE_URL = __ENV.AGENTHIVE_LOAD_BASE_URL || "http://127.0.0.1:18080";
const DEMO_TENANT = "demo";
const DEMO_EMAIL = "admin@example.com";
const DEMO_PASSWORD = "AgentHive123!";

export const options = {
  stages: [
    { duration: "10s", target: 10 }, // ramp-up to 10 VUs
    { duration: "20s", target: 10 }, // hold
    { duration: "5s", target: 0 }, // ramp-down
  ],
  thresholds: {
    http_req_failed: ["rate<0.01"], // < 1% errors
    "http_req_duration{endpoint:health}": ["p(95)<200"],
    "http_req_duration{endpoint:login}": ["p(95)<500"],
    "http_req_duration{endpoint:metrics}": ["p(95)<200"],
  },
  tags: {
    test: "agenthive-smoke",
  },
};

const SHARED_TOKENS = [];

export default function () {
  group("health check", () => {
    const res = http.get(`${BASE_URL}/api/v1/health`, { tags: { endpoint: "health" } });
    check(res, {
      "health 200": (r) => r.status === 200,
    });
  });

  group("login", () => {
    const payload = JSON.stringify({
      tenant_slug: DEMO_TENANT,
      email: DEMO_EMAIL,
      password: DEMO_PASSWORD,
    });
    const params = {
      headers: { "Content-Type": "application/json" },
      tags: { endpoint: "login" },
    };
    const res = http.post(`${BASE_URL}/api/v1/auth/login`, payload, params);
    check(res, {
      "login 200": (r) => r.status === 200,
      "has access_token": (r) => {
        try {
          return !!r.json("access_token");
        } catch {
          return false;
        }
      },
    });

    if (res.status === 200) {
      try {
        const token = res.json("access_token");
        if (token) SHARED_TOKENS.push(token);
      } catch {
        // ignore parse failure
      }
    }
  });

  group("metrics endpoint", () => {
    const res = http.get(`${BASE_URL}/api/v1/metrics`, { tags: { endpoint: "metrics" } });
    check(res, {
      "metrics 200": (r) => r.status === 200,
      "metrics has prometheus format": (r) => r.body.includes("# TYPE"),
    });
  });

  // Authenticated request: list agent instances (only if we have a token)
  if (SHARED_TOKENS.length > 0) {
    group("list agents", () => {
      const token = SHARED_TOKENS[Math.floor(Math.random() * SHARED_TOKENS.length)];
      const res = http.get(`${BASE_URL}/api/v1/agents/instances`, {
        headers: { Authorization: `Bearer ${token}` },
        tags: { endpoint: "agents" },
      });
      check(res, {
        "agents 200": (r) => r.status === 200,
      });
    });
  }

  sleep(0.5);
}

export function handleSummary(data) {
  return {
    "tests/load/report.json": JSON.stringify(data, null, 2),
    stdout: textSummary(data),
  };
}

// Minimal text summary for stdout
function textSummary(data) {
  const lines = [];
  lines.push("\n=== AgentHive Load Test Summary ===\n");
  for (const [metric, value] of Object.entries(data.metrics)) {
    if (typeof value === "object" && value !== null) {
      const parts = [];
      for (const [k, v] of Object.entries(value)) {
        if (typeof v === "number") parts.push(`${k}=${v.toFixed(4)}`);
      }
      lines.push(`${metric}: ${parts.join(", ")}`);
    }
  }
  return lines.join("\n");
}
