FROM plexinc/pms-docker:latest

RUN apt-get update && apt-get install -y --no-install-recommends \
    mesa-va-drivers \
    && rm -rf /var/lib/apt/lists/*
