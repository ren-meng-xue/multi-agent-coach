FROM docker:27-cli AS docker-cli

RUN mkdir -p /out/cli-plugins \
    && cp "$(command -v docker)" /out/docker \
    && find /usr/local -type f -name docker-compose -exec cp {} /out/cli-plugins/docker-compose \; \
    && test -x /out/cli-plugins/docker-compose

FROM jenkins/jenkins:lts

USER root

RUN sed -i \
      -e 's|http://deb.debian.org/debian|https://mirrors.aliyun.com/debian|g' \
      -e 's|http://deb.debian.org/debian-security|https://mirrors.aliyun.com/debian-security|g' \
      /etc/apt/sources.list.d/debian.sources \
    && apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY --from=docker-cli /out/docker /usr/local/bin/docker
COPY --from=docker-cli /out/cli-plugins/docker-compose /usr/local/libexec/docker/cli-plugins/docker-compose

USER jenkins
