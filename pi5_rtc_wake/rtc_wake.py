#!/usr/bin/env python3
"""RTC alarm verification shared by the setup wizard and scheduler."""

from __future__ import annotations

import calendar
from datetime import UTC, datetime, timedelta
import fcntl
import json
import logging
import os
from pathlib import Path
import re
import struct
import threading
import time
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

LOG = logging.getLogger("pi5_rtc_wake")
RTC_TIME = struct.Struct("=9i")
RTC_ALARM = struct.Struct("=BB2x9i")
# Linux generic ioctl ABI, shared by aarch64 and x86_64.
RTC_RD_TIME = 0x80247009
RTC_WKALM_RD = 0x80287010
RTC_WKALM_SET = 0x4028700F
RTC_AIE_OFF = 0x7002
MIN_WAKE_SECONDS = 180
MIN_VERIFY_SECONDS = 120
MAX_WAKE_SECONDS = 7 * 24 * 60 * 60
MAX_CLOCK_DRIFT = 10
TRANSACTION_LIFETIME = 60


class PolicyError(Exception):
    """A request that must not permit shutdown."""


def rtc_fields(epoch: int) -> tuple[int, ...]:
    utc = time.gmtime(epoch)
    return (
        utc.tm_sec, utc.tm_min, utc.tm_hour, utc.tm_mday,
        utc.tm_mon - 1, utc.tm_year - 1900, (utc.tm_wday + 1) % 7,
        utc.tm_yday - 1, 0,
    )


def fields_epoch(fields: tuple[int, ...]) -> int:
    sec, minute, hour, day, month, year, *_ = fields
    # Validate rather than allowing calendar.timegm to normalize invalid dates.
    value = datetime(year + 1900, month + 1, day, hour, minute, sec, tzinfo=UTC)
    return calendar.timegm(value.timetuple())


def iso_utc(epoch: int) -> str:
    return datetime.fromtimestamp(epoch, UTC).isoformat()


def next_daily_epoch(wake_time: str, timezone: str, now: float) -> int:
    """Find the next real wall-clock occurrence, including both DST folds."""
    if not isinstance(wake_time, str) or not re.fullmatch(
        r"(?:[01]\d|2[0-3]):[0-5]\d(?::[0-5]\d)?", wake_time
    ):
        raise PolicyError("Wake time must be HH:MM or HH:MM:SS.")
    if not isinstance(timezone, str) or len(timezone) > 100:
        raise PolicyError("A valid Home Assistant time zone is required.")
    try:
        zone = ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError) as error:
        raise PolicyError("Unknown time zone.") from error
    parts = [int(part) for part in wake_time.split(":")]
    hour, minute = parts[:2]
    second = parts[2] if len(parts) == 3 else 0
    local_now = datetime.fromtimestamp(now, zone)
    for day_offset in range(3):
        date = local_now.date() + timedelta(days=day_offset)
        naive = datetime(date.year, date.month, date.day, hour, minute, second)
        candidates = set()
        for fold in (0, 1):
            epoch = int(naive.replace(tzinfo=zone, fold=fold).timestamp())
            round_trip = datetime.fromtimestamp(epoch, zone).replace(tzinfo=None)
            if round_trip == naive:
                candidates.add(epoch)
        if not candidates and naive > local_now.replace(tzinfo=None):
            raise PolicyError(
                "The next wake time does not exist on the daylight-saving "
                "transition. Choose a wake time outside the skipped hour."
            )
        for epoch in sorted(candidates):
            if epoch > now:
                return epoch
    raise PolicyError("No valid wake time was found.")


class LinuxRTC:
    """Use /dev/rtc0 instead of a writable host /sys mount."""

    def __init__(self, device: str = "/dev/rtc0"):
        self.device = device

    def name(self) -> str:
        value = Path("/sys/class/rtc/rtc0/name").read_text().strip()
        if "rpi-rtc" not in value and "rpi_rtc" not in value:
            raise PolicyError("rtc0 is not the Raspberry Pi built-in RTC: " + value)
        return value

    def _read(self, operation: int, size: int) -> bytearray:
        buffer = bytearray(size)
        descriptor = os.open(self.device, os.O_RDONLY | os.O_CLOEXEC)
        try:
            fcntl.ioctl(descriptor, operation, buffer, True)
        finally:
            os.close(descriptor)
        return buffer

    def read_time(self) -> int:
        return fields_epoch(RTC_TIME.unpack(self._read(RTC_RD_TIME, RTC_TIME.size)))

    def read_alarm(self) -> dict[str, Any]:
        values = RTC_ALARM.unpack(self._read(RTC_WKALM_RD, RTC_ALARM.size))
        try:
            epoch = fields_epoch(values[2:])
        except (ValueError, OverflowError):
            if values[0]:
                raise
            epoch = 0  # An unused, disabled alarm may have empty date fields.
        return {"enabled": bool(values[0]), "epoch": epoch}

    def set_alarm(self, epoch: int) -> None:
        buffer = RTC_ALARM.pack(1, 0, *rtc_fields(epoch))
        descriptor = os.open(self.device, os.O_RDWR | os.O_CLOEXEC)
        try:
            fcntl.ioctl(descriptor, RTC_AIE_OFF)
            fcntl.ioctl(descriptor, RTC_WKALM_SET, buffer)
        finally:
            os.close(descriptor)

    def clear_alarm(self) -> None:
        descriptor = os.open(self.device, os.O_RDWR | os.O_CLOEXEC)
        try:
            fcntl.ioctl(descriptor, RTC_AIE_OFF)
        finally:
            os.close(descriptor)


class Controller:
    def __init__(
        self, rtc: Any, *, firmware_configured: bool,
        ownership_file: Path, clock=time.time, monotonic=time.monotonic,
    ):
        self.rtc = rtc
        self.firmware_configured = firmware_configured
        self.ownership_file = ownership_file
        self.clock = clock
        self.monotonic = monotonic
        self.lock = threading.RLock()
        self.transaction: dict[str, Any] | None = None
        try:
            data = json.loads(ownership_file.read_text())
            self.owned_epoch = data["wake_epoch"] if type(data["wake_epoch"]) is int else None
        except (OSError, ValueError, KeyError, TypeError):
            self.owned_epoch = None

    def _probe(self) -> dict[str, Any]:
        name = self.rtc.name()
        rtc_now = self.rtc.read_time()
        drift = rtc_now - self.clock()
        alarm = self.rtc.read_alarm()
        return {
            "rtc_name": name, "rtc_epoch": rtc_now,
            "clock_drift_seconds": round(drift, 3),
            "clock_valid": abs(drift) <= MAX_CLOCK_DRIFT,
            "alarm_enabled": alarm["enabled"], "wake_epoch": alarm["epoch"],
            "wake_iso": iso_utc(alarm["epoch"]) if alarm["enabled"] else None,
            "firmware_configured": self.firmware_configured,
            "observed_at": iso_utc(int(self.clock())),
        }

    def status(self) -> dict[str, Any]:
        with self.lock:
            try:
                result = self._probe()
                result["status"] = (
                    "clock_error" if not result["clock_valid"] else
                    "ready" if self.firmware_configured else "needs_firmware_setup"
                )
                result["message"] = ""
                return result
            except (OSError, PolicyError, ValueError, OverflowError) as error:
                return {
                    "status": "error", "message": str(error),
                    "firmware_configured": self.firmware_configured,
                    "clock_valid": False, "alarm_enabled": False, "wake_iso": None,
                }

    def _require_ready(self) -> dict[str, Any]:
        if not self.firmware_configured:
            raise PolicyError("Complete the one-time EEPROM setup before arming a wake alarm.")
        result = self._probe()
        if not result["clock_valid"]:
            raise PolicyError("RTC and system UTC differ by more than 10 seconds; host stays on.")
        return result

    @staticmethod
    def _request_id(payload: dict[str, Any]) -> str:
        value = payload.get("request_id")
        if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,100}", value):
            raise PolicyError("A valid request_id is required.")
        return value

    def arm(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self.lock:
            # Every arm attempt invalidates any earlier shutdown acknowledgement.
            self.transaction = None
            request_id = self._request_id(payload)
            status = self._require_ready()
            now = self.clock()
            timezone = payload.get("timezone", "UTC")
            if not isinstance(timezone, str) or len(timezone) > 100:
                raise PolicyError("A valid time zone is required.")
            try:
                zone = ZoneInfo(timezone)
            except (ZoneInfoNotFoundError, ValueError) as error:
                raise PolicyError("Unknown time zone.") from error
            if payload.get("mode") == "daily":
                epoch = next_daily_epoch(payload.get("wake_time"), timezone, now)
            elif payload.get("mode") == "relative":
                seconds = payload.get("seconds")
                if type(seconds) is not int:
                    raise PolicyError("seconds must be an integer.")
                epoch = int(now) + seconds
            elif payload.get("mode") == "at":
                epoch = payload.get("wake_epoch")
                if type(epoch) is not int:
                    raise PolicyError("wake_epoch must be an integer.")
            else:
                raise PolicyError("mode must be daily, relative, or at.")
            if epoch - now < MIN_WAKE_SECONDS:
                raise PolicyError("Wake must be at least three minutes away; host stays on.")
            if epoch - now > MAX_WAKE_SECONDS or epoch > 0xFFFFFFFF:
                raise PolicyError("Wake must be within the next seven days.")
            if (
                status["alarm_enabled"] and status["wake_epoch"] > now
                and status["wake_epoch"] != self.owned_epoch
            ):
                raise PolicyError("An RTC alarm set outside this add-on already exists.")
            self.rtc.set_alarm(epoch)
            alarm = self.rtc.read_alarm()
            if not alarm["enabled"] or alarm["epoch"] != epoch:
                raise PolicyError("RTC readback did not match; host stays on.")
            self.ownership_file.parent.mkdir(parents=True, exist_ok=True)
            temp = self.ownership_file.with_suffix(".tmp")
            temp.write_text(json.dumps({"wake_epoch": epoch}) + "\n")
            os.replace(temp, self.ownership_file)
            self.owned_epoch = epoch
            self.transaction = {
                "request_id": request_id, "wake_epoch": epoch,
                "issued_monotonic": self.monotonic(),
            }
            return {
                "verified": True, "request_id": request_id,
                "wake_epoch": epoch, "wake_iso": iso_utc(epoch),
                "wake_local": datetime.fromtimestamp(epoch, zone).isoformat(),
            }

    def verify(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self.lock:
            request_id = self._request_id(payload)
            transaction = self.transaction
            if (
                transaction is None or transaction["request_id"] != request_id
                or type(payload.get("wake_epoch")) is not int
                or transaction["wake_epoch"] != payload["wake_epoch"]
                or self.monotonic() - transaction["issued_monotonic"] > TRANSACTION_LIFETIME
            ):
                raise PolicyError("Missing, mismatched, or expired arm request; host stays on.")
            status = self._require_ready()
            if (
                not status["alarm_enabled"] or status["wake_epoch"] != transaction["wake_epoch"]
                or status["wake_epoch"] - self.clock() < MIN_VERIFY_SECONDS
            ):
                raise PolicyError("Wake alarm is no longer valid; host stays on.")
            return {
                "verified": True, "shutdown_allowed": True,
                "request_id": request_id, "wake_epoch": status["wake_epoch"],
                "wake_iso": status["wake_iso"], "verified_at": status["observed_at"],
            }

    def clear(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self.lock:
            request_id = self._request_id(payload)
            if self.transaction is None or self.transaction["request_id"] != request_id:
                raise PolicyError("Only the current arm request can clear its alarm.")
            alarm = self.rtc.read_alarm()
            if alarm["enabled"] and alarm["epoch"] != self.transaction["wake_epoch"]:
                raise PolicyError("RTC was changed outside this request; leaving it unchanged.")
            self.rtc.clear_alarm()
            if self.rtc.read_alarm()["enabled"]:
                raise PolicyError("RTC alarm did not disable.")
            self.transaction = None
            return {"cleared": True, "request_id": request_id}


