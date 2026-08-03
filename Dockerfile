# jobcube — runs the tooling and serves the visualizations.
#
# The point is not deployment. It is that a fork should be able to run the
# validators and see the coverage map without first winning an argument with a
# local Python install. Everything the container needs is in requirements.txt.
#
#   docker compose up            → http://localhost:8000
#   docker compose run --rm checks   → the same gates CI runs
#
# What is deliberately NOT in the image: your profile, your documents, and your
# outreach logs. They are mounted at run time by compose and gitignored besides,
# so nothing personal is ever baked into a layer that could be pushed.

FROM python:3.12-slim

# tini so Ctrl-C reaches the server instead of being swallowed by PID 1.
RUN apt-get update \
    && apt-get install -y --no-install-recommends tini \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Dependencies first, so editing a script does not re-resolve pip.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Non-root. The server needs to write working/active/, nothing else.
RUN useradd --create-home --uid 10001 jobcube \
    && mkdir -p working/active \
    && chown -R jobcube:jobcube /app/working
USER jobcube

EXPOSE 8000

# 0.0.0.0 inside the container is required for the port mapping to reach it.
# On the host, compose binds it to 127.0.0.1 only — see docker-compose.yml.
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["python", "-B", "tools/serve.py", "--host", "0.0.0.0", "--port", "8000"]
