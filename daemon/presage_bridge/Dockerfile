FROM ubuntu:24.04

RUN apt-get update && apt-get install -y \
    curl \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://packages.presagetech.com/KEY.gpg | gpg --dearmor -o /etc/apt/keyrings/presage-archive-keyring.gpg && \
    echo "deb [signed-by=/etc/apt/keyrings/presage-archive-keyring.gpg] https://packages.presagetech.com/apt/ubuntu noble main" > /etc/apt/sources.list.d/presage.list

RUN apt-get update && apt-get install -y \
    libsmartspectra-dev \
    libopencv-dev \
    cmake \
    g++ \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /src
COPY CMakeLists.txt .
COPY src/ src/

RUN mkdir build && cd build && \
    cmake .. && \
    make -j$(nproc) && \
    mkdir -p /opt/bridge && \
    cp bridge /opt/bridge/

WORKDIR /opt/bridge
CMD ["./bridge"]
