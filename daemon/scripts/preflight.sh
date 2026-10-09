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

# Check /dev/video10
if [ -c /dev/video10 ]; then
    echo "PASS: /dev/video10 exists"
else
    echo "WARN: /dev/video10 not found"
    [ $run_presage_checks -eq 1 ] && fail_count=$((fail_count + 1))
fi

# Check /dev/video11
if [ -c /dev/video11 ]; then
    echo "PASS: /dev/video11 exists"
else
    echo "WARN: /dev/video11 not found"
    [ $run_presage_checks -eq 1 ] && fail_count=$((fail_count + 1))
fi

# Check v4l2loopback
if lsmod | grep -q "v4l2loopback"; then
    echo "PASS: v4l2loopback module loaded"
else
    echo "WARN: v4l2loopback module not loaded"
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

# Check Presage bridge image
if docker image inspect cradleecho-presage-bridge >/dev/null 2>&1; then
    echo "PASS: docker image cradleecho-presage-bridge found"
else
    echo "WARN: docker image cradleecho-presage-bridge not found"
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
