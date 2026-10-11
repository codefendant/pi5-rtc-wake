FROM alpine:3.23
RUN apk add --no-cache python3 tzdata util-linux-misc py3-websocket-client \
    && /usr/bin/nsenter --help | grep -q -- '--wdns'
WORKDIR /app
COPY LICENSE ./LICENSE
COPY rtc_wake.py state.py services.py host_helper.py calendar_schedule.py power_sources.py ha_registry.py ups_recovery.py phone_messages.py server.py ./
COPY assist.py assist_http.py assist_install.py dashboard.py wake_devices.py ./
COPY companion ./companion
COPY web ./web
LABEL io.hass.type="addon" io.hass.arch="aarch64"
CMD ["python3", "-u", "/app/server.py"]
