FROM eclipse-temurin:25-jre

ARG TARGETOS=linux
ARG TARGETARCH=arm64

ARG EASY_ADD_VERSION=0.8.14
ADD https://github.com/itzg/easy-add/releases/download/${EASY_ADD_VERSION}/easy-add_${TARGETOS}_${TARGETARCH} /usr/bin/easy-add
RUN chmod +x /usr/bin/easy-add

ARG RCON_CLI_VERSION=1.7.6
RUN easy-add --var os=${TARGETOS} --var arch=${TARGETARCH} \
  --var version=${RCON_CLI_VERSION} --var app=rcon-cli --file {{.app}} \
  --from https://github.com/itzg/{{.app}}/releases/download/{{.version}}/{{.app}}_{{.version}}_{{.os}}_{{.arch}}.tar.gz

ARG MC_MONITOR_VERSION=0.16.8
RUN easy-add --var os=${TARGETOS} --var arch=${TARGETARCH} \
  --var version=${MC_MONITOR_VERSION} --var app=mc-monitor --file {{.app}} \
  --from https://github.com/itzg/{{.app}}/releases/download/{{.version}}/{{.app}}_{{.version}}_{{.os}}_{{.arch}}.tar.gz

RUN apt-get update && apt-get install -y --no-install-recommends \
      python3 \
      python3-pip \
      tini \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /tmp/requirements.txt
RUN pip3 install --no-cache-dir --break-system-packages \
      -r /tmp/requirements.txt

COPY apps/microvm/ /opt/microvm/

ARG MINECRAFT_VERSION=26.2
RUN python3 /opt/microvm/fetch_jar.py --version ${MINECRAFT_VERSION} --output /opt/minecraft

RUN chmod +x /opt/microvm/entrypoint.sh

ENV MINECRAFT_PORT=25565 \
    WS_PORT=8080 \
    HOOK_PORT=9000 \
    RCON_PORT=25575 \
    RCON_PASSWORD=microvm-minecraft

EXPOSE 8080 9000
ENTRYPOINT ["/usr/bin/tini", "--", "/opt/microvm/entrypoint.sh"]
