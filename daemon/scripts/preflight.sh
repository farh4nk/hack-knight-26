#!/usr/bin/env bash
# Preflight checks for CradleEcho daemon

fail_count=0
run_presage_checks=0

if [ "$CRADLEECHO_SOURCE" = "presage" ]; then
    run_presage_checks=1
fi

for arg in "$@"; do
    if [ "$arg" = "--presage" ]; then
        run_presage_checks=1
    fi
done

echo "Running preflight checks..."

# Check /dev/video0
if [ -c /dev/video0 ]; then
    echo "PASS: /dev/video0 exists"
else
    echo "WARN: /dev/video0 not found"
    [ $run_presage_checks -eq 1 ] && fail_count=$((fail_count + 1))
fi

# Check Docker
if command -v docker >/dev/null 2>&1; then
    if docker info >/dev/null 2>&1; then
        echo "PASS: docker is available and daemon is reachable"
    else
        echo "WARN: docker daemon not reachable"
        [ $run_presage_checks -eq 1 ] && fail_count=$((fail_count + 1))
    fi
else
    echo "WARN: docker not on PATH"
    [ $run_presage_checks -eq 1 ] && fail_count=$((fail_count + 1))
fi

# Check daemon image
if docker image inspect cradleecho-daemon >/dev/null 2>&1; then
    echo "PASS: docker image cradleecho-daemon found"
else
    echo "WARN: docker image cradleecho-daemon not found"
    [ $run_presage_checks -eq 1 ] && fail_count=$((fail_count + 1))
fi

# Check .env for PRESAGE_API_KEY
if grep -q "^[[:space:]]*PRESAGE_API_KEY=.\+" .env 2>/dev/null; then
    echo "PASS: PRESAGE_API_KEY found in .env"
else
    echo "WARN: PRESAGE_API_KEY not found or empty in .env"
    [ $run_presage_checks -eq 1 ] && fail_count=$((fail_count + 1))
fi

if [ $run_presage_checks -eq 1 ] && [ $fail_count -gt 0 ]; then
    echo "Preflight failed: $fail_count required checks for presage mode failed."
    exit 1
fi

echo "Preflight complete."
exit 0
