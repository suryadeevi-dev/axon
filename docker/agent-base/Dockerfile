FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=UTC
ENV HOME=/home/axon
ENV PATH="/home/axon/.local/bin:/home/axon/.pyenv/shims:/home/axon/.pyenv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

# Core tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    curl \
    wget \
    git \
    vim \
    nano \
    jq \
    htop \
    tree \
    unzip \
    zip \
    tar \
    make \
    build-essential \
    libssl-dev \
    libffi-dev \
    libreadline-dev \
    zlib1g-dev \
    libbz2-dev \
    libsqlite3-dev \
    python3 \
    python3-pip \
    python3-venv \
    nodejs \
    npm \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 -s /bin/bash axon

USER axon
WORKDIR /home/axon

# Create workspace
RUN mkdir -p /home/axon/workspace

# Install common Python packages
RUN pip3 install --user --no-cache-dir \
    requests \
    httpx \
    rich \
    click \
    pydantic \
    python-dotenv

# Install common Node packages globally (user-level)
RUN npm install -g typescript ts-node 2>/dev/null || true

WORKDIR /home/axon/workspace

# Persistent loop: keep container alive
CMD ["/bin/bash", "-c", "echo 'AXON agent node ready' && tail -f /dev/null"]
