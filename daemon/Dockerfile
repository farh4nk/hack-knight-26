FROM ubuntu:24.04 AS builder

RUN apt-get update && apt-get install -y \
    curl \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://packages.presagetech.com/KEY.gpg | gpg --dearmor -o /etc/apt/keyrings/presage-archive-keyring.gpg && \
    echo "deb [signed-by=/etc/apt/keyrings/presage-archive-keyring.gpg] https://packages.presagetech.com/apt/ubuntu noble main" > /etc/apt/sources.list.d/presage.list

RUN apt-get update && apt-get install -y \
    libsmartspectra-dev=3.4.0-noble1 \
    libopencv-dev \
    cmake \
    g++ \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /src
COPY presage_bridge/CMakeLists.txt .
COPY presage_bridge/src/ src/

RUN mkdir build && cd build && \
    cmake .. && \
    make -j$(nproc) && \
    mkdir -p /opt/bridge && \
    cp bridge /opt/bridge/

FROM ubuntu:24.04

RUN apt-get update && apt-get install -y \
    curl \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://packages.presagetech.com/KEY.gpg | gpg --dearmor -o /etc/apt/keyrings/presage-archive-keyring.gpg && \
    echo "deb [signed-by=/etc/apt/keyrings/presage-archive-keyring.gpg] https://packages.presagetech.com/apt/ubuntu noble main" > /etc/apt/sources.list.d/presage.list

RUN apt-get update && apt-get install -y \
    libsmartspectra-dev=3.4.0-noble1 \
    libopencv-dev \
    python3.12 \
    python3.12-venv \
    python-is-python3 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set up non-root user in video group
RUN useradd -m -G video -s /bin/bash cradleecho

WORKDIR /app
RUN chown cradleecho:cradleecho /app

USER cradleecho
ENV PATH="/app/.venv/bin:$PATH"

COPY --chown=cradleecho:cradleecho pyproject.toml uv.lock ./
# Dependencies only: the daemon runs from /app, so the project itself need not be installed.
RUN uv sync --frozen --no-dev --no-install-project

COPY --chown=cradleecho:cradleecho cradleecho/ cradleecho/
COPY --chown=cradleecho:cradleecho presage_bridge/fake_bridge.py presage_bridge/fake_bridge.py

USER root
RUN mkdir -p /opt/bridge && chown cradleecho:cradleecho /opt/bridge
USER cradleecho
COPY --from=builder --chown=cradleecho:cradleecho /opt/bridge/bridge /opt/bridge/bridge

ENV CRADLEECHO_SOURCE=presage \
    CRADLEECHO_CAMERA=/dev/video0 \
    CRADLEECHO_PRESAGE_CMD="/opt/bridge/bridge --stdin 640x480" \
    CRADLEECHO_HOST=0.0.0.0 \
    CRADLEECHO_PORT=8000

EXPOSE 8000

CMD ["python", "-m", "cradleecho"]
