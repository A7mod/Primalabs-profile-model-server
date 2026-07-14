#!/bin/bash
set -uo pipefail

IMAGE_NAME="profile-model-server:test"
CONTAINER_NAME="profile-model-server-test"
PORT=8000
PASS=0
FAIL=0

cleanup() {
    docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "==> Building image..."
if ! docker build -t "$IMAGE_NAME" .; then
    echo "FAIL: image build failed"
    exit 1
fi
echo "==> Build OK"

wait_for_ready() {
    local timeout=60
    local elapsed=0
    while [ $elapsed -lt $timeout ]; do
        status=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:${PORT}/v1/health/ready")
        if [ "$status" = "200" ]; then
            return 0
        fi
        sleep 2
        elapsed=$((elapsed + 2))
    done
    return 1
}

test_profile() {
    local profile=$1
    echo ""
    echo "==> Testing profile: $profile"

    cleanup
    docker run -d --name "$CONTAINER_NAME" -p ${PORT}:8000 -e PROFILE="$profile" "$IMAGE_NAME" >/dev/null

    if ! wait_for_ready; then
        echo "FAIL [$profile]: /v1/health/ready never returned 200"
        docker logs "$CONTAINER_NAME" --tail 50
        FAIL=$((FAIL + 1))
        return
    fi
    echo "PASS [$profile]: health/ready returned 200"
    PASS=$((PASS + 1))

    resp=$(curl -s -X POST "http://localhost:${PORT}/v1/chat/completions" \
        -H "Content-Type: application/json" \
        -d '{"messages":[{"role":"user","content":"Say hello in one word."}], "max_tokens": 20}')

    if echo "$resp" | grep -q '"choices"'; then
        echo "PASS [$profile]: chat completion returned choices"
        PASS=$((PASS + 1))
    else
        echo "FAIL [$profile]: chat completion malformed: $resp"
        FAIL=$((FAIL + 1))
    fi

    prof_resp=$(curl -s "http://localhost:${PORT}/v1/profiles")
    active=$(echo "$prof_resp" | python3 -c "import sys,json; print(json.load(sys.stdin).get('active_profile',''))" 2>/dev/null)

    if [ "$active" = "$profile" ]; then
        echo "PASS [$profile]: /v1/profiles reports correct active profile"
        PASS=$((PASS + 1))
    else
        echo "FAIL [$profile]: /v1/profiles reported '$active', expected '$profile'"
        FAIL=$((FAIL + 1))
    fi

    docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1
}

test_profile "balanced"
test_profile "throughput"
test_profile "latency"

echo ""
echo "==> Testing invalid profile fails fast..."
cleanup
invalid_output=$(docker run --rm -e PROFILE="not-a-real-profile" "$IMAGE_NAME" 2>&1 || true)

if echo "$invalid_output" | grep -q "FATAL"; then
    echo "PASS: invalid profile fails fast with clear error"
    PASS=$((PASS + 1))
else
    echo "FAIL: invalid profile did not fail as expected"
    echo "$invalid_output"
    FAIL=$((FAIL + 1))
fi

echo ""
echo "===================="
echo " PASS: $PASS   FAIL: $FAIL"
echo "===================="

if [ "$FAIL" -gt 0 ]; then
    exit 1
fi