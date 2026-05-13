---
name: dockerfile-craft
description: Write or review a Dockerfile. Use when the user asks to "containerize this", "write a Dockerfile", or has a Dockerfile that's slow/large/insecure.
---

# dockerfile-craft

A Dockerfile is the recipe for a reproducible build. A good one is small, fast to build, secure by default, and runs the right thing on `docker run`.

## When to act

- "Write a Dockerfile", "containerize this", "Docker image for X"
- Reviewing a Dockerfile that's too large, too slow to build, or has issues

## When not to act

- The project doesn't need containerization
- Existing Dockerfile is fine; user is just running it

## Structure

```dockerfile
# 1. Pin the base image to a specific version (not :latest)
FROM python:3.11-slim AS build

# 2. Set work directory early
WORKDIR /app

# 3. Copy dependency manifests FIRST and install deps — this layer caches
COPY pyproject.toml uv.lock ./
RUN pip install --no-cache-dir -e .

# 4. Copy source AFTER deps; changes here don't invalidate the deps layer
COPY src/ ./src/

# 5. Multi-stage: final image is smaller
FROM python:3.11-slim
WORKDIR /app
COPY --from=build /app /app
COPY --from=build /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages

# 6. Drop privileges
RUN useradd -r -u 1001 appuser
USER appuser

# 7. Declare the contract
EXPOSE 8080
HEALTHCHECK CMD curl -f http://localhost:8080/health || exit 1
CMD ["python", "-m", "myapp"]
```

## Key principles

### Layer order matters

Each `COPY` or `RUN` is a cached layer. If a file changes, that layer and ALL subsequent layers rebuild. So:
- Dep installs go FIRST (rarely change)
- Source code goes LAST (changes constantly)

Bad: `COPY . /app && pip install ...` — every source change reinstalls deps.

### Pin everything

- Base image: `python:3.11-slim` not `python:slim` not `python`
- Apt packages: `apt-get install foo=1.2.3` (or accept the loose pin and document it)
- Pip/npm: lockfile required; freeze versions

### Multi-stage when possible

Build artifacts often need build-only tools (gcc, header files) that the runtime doesn't. Multi-stage separates them:
- Stage 1: build everything
- Stage 2: copy only the artifacts to a clean runtime image

Output image is dramatically smaller.

### Don't run as root

`USER 1001` (or named user) near the end. If the app crashes due to permissions, the fix is to chown the relevant dirs, not to run as root.

### .dockerignore matters as much as Dockerfile

A missing `.dockerignore` means every `COPY .` copies `.git/`, `node_modules/`, IDE configs, etc. into the image. Add one:

```
.git
.github
node_modules
*.pyc
__pycache__
.env*
*.log
```

### Cache mounts (BuildKit)

For deps that download repeatedly:

```dockerfile
RUN --mount=type=cache,target=/root/.cache/pip pip install -e .
```

Faster builds without bloating the image.

## Common mistakes

- **Image is huge** — built artifacts include the whole toolchain. Use multi-stage.
- **Build is slow** — layers cached in wrong order. Deps before source.
- **Runtime fails on startup** — `CMD` wrong, missing PATH, USER lacks permission. Test the built image, not just the build.
- **HEALTHCHECK missing** — orchestrators (k8s, swarm) need it to know if the container is healthy.
- **EXPOSE missing or wrong port** — declarative only but matters for tooling.
- **No version pinning** — image works today, broken tomorrow because `latest` moved.
