"""Async TCP client for Real Flame MWIL protocol."""

from __future__ import annotations

import asyncio
import logging

from .const import CONNECT_TIMEOUT, DEFAULT_PORT, MODE_OFF, READ_TIMEOUT
from .protocol import (
    FireplaceStatus,
    build_control_frame,
    is_control_ack,
    parse_status,
    status_request,
)

_LOGGER = logging.getLogger(__name__)

# Live: status can lag 1.5–2.5 s behind MWIL20
CONTROL_SETTLE_S = 1.8
CONTROL_SETTLE_RETRIES = 4


class RealFlameClient:
    """Short-lived TCP sessions with a shared lock."""

    def __init__(self, host: str, port: int = DEFAULT_PORT) -> None:
        self.host = host
        self.port = port
        self._lock = asyncio.Lock()

    async def async_validate(self) -> FireplaceStatus:
        """Connect and perform a status poll (used by config flow)."""
        return await self.async_get_status()

    async def async_get_status(self) -> FireplaceStatus:
        raw = await self._transact(status_request(), expect_read=True)
        if not raw:
            raise TimeoutError(f"no status response from {self.host}:{self.port}")
        return parse_status(raw)

    async def async_send_control(
        self,
        mode: int,
        temperature: int,
        flame: int,
        *,
        led_r: int = 0,
        led_g: int = 0,
        led_b: int = 0,
        wait_for_mode: bool = True,
    ) -> FireplaceStatus | None:
        """Send MWIL20; expect ACK `MWIL2,`. Optionally poll until op_state matches."""
        frame = build_control_frame(
            mode, temperature, flame, led_r=led_r, led_g=led_g, led_b=led_b
        )
        _LOGGER.debug("Control frame to %s: %s", self.host, frame)
        ack = await self._transact(frame.encode("ascii"), expect_read=True, read_timeout=1.5)
        if ack and not is_control_ack(ack):
            _LOGGER.warning("Unexpected control reply from %s: %r", self.host, ack)
        elif not ack:
            _LOGGER.debug("No ACK bytes for control to %s (device may still apply)", self.host)

        if not wait_for_mode:
            return None

        await asyncio.sleep(CONTROL_SETTLE_S)
        last: FireplaceStatus | None = None
        for _ in range(CONTROL_SETTLE_RETRIES):
            last = await self.async_get_status()
            if last.op_state == mode:
                return last
            # Off is special: also accept if already off and we asked off
            if mode == MODE_OFF and last.is_off:
                return last
            await asyncio.sleep(0.8)
        _LOGGER.warning(
            "Status did not settle to mode %s after control (last op_state=%s)",
            mode,
            None if last is None else last.op_state,
        )
        return last

    async def _transact(
        self,
        payload: bytes,
        *,
        expect_read: bool,
        read_timeout: float | None = None,
    ) -> bytes:
        async with self._lock:
            reader: asyncio.StreamReader
            writer: asyncio.StreamWriter
            try:
                async with asyncio.timeout(CONNECT_TIMEOUT):
                    reader, writer = await asyncio.open_connection(self.host, self.port)
            except (TimeoutError, OSError) as err:
                raise ConnectionError(
                    f"connect failed {self.host}:{self.port}: {err}"
                ) from err

            try:
                writer.write(payload)
                await writer.drain()
                if not expect_read:
                    try:
                        async with asyncio.timeout(0.3):
                            await reader.read(256)
                    except TimeoutError:
                        pass
                    return b""

                timeout = read_timeout if read_timeout is not None else READ_TIMEOUT
                chunks: list[bytes] = []
                async with asyncio.timeout(timeout):
                    while True:
                        try:
                            async with asyncio.timeout(0.6):
                                chunk = await reader.read(1024)
                        except TimeoutError:
                            break
                        if not chunk:
                            break
                        chunks.append(chunk)
                        joined = b"".join(chunks)
                        if b"," in joined or len(joined) > 8:
                            try:
                                async with asyncio.timeout(0.2):
                                    extra = await reader.read(1024)
                                    if extra:
                                        chunks.append(extra)
                            except TimeoutError:
                                pass
                            break
                return b"".join(chunks)
            finally:
                writer.close()
                try:
                    await writer.wait_closed()
                except OSError:
                    pass
