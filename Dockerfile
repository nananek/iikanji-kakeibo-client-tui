FROM python:3.13-slim AS builder

WORKDIR /build

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --no-cache-dir build && \
    python -m build --wheel --outdir /wheels


FROM python:3.13-slim

LABEL org.opencontainers.image.source="https://github.com/nananek/iikanji-kakeibo-client-tui"
LABEL org.opencontainers.image.description="TUI client for iikanji-kakeibo"
LABEL org.opencontainers.image.licenses="MIT"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    XDG_CONFIG_HOME=/config \
    TERM=xterm-256color

# 非 root ユーザーで実行
RUN groupadd --gid 1000 iikanji && \
    useradd --uid 1000 --gid iikanji --shell /bin/bash --create-home iikanji && \
    mkdir -p /config && chown -R iikanji:iikanji /config

COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir /wheels/*.whl && rm -rf /wheels

USER iikanji
WORKDIR /home/iikanji

VOLUME ["/config"]

ENTRYPOINT ["iikanji-tui"]
CMD []
