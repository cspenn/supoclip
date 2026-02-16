# start backend/tests/unit/test_async_helpers.py
"""Comprehensive tests for utils/async_helpers.py to achieve 100% line coverage.

Covers:
- run_in_thread: success and error paths
- async_wrap: decorator creates awaitable wrapper, success and error paths
"""

import pytest
from unittest.mock import patch

from src.utils.async_helpers import run_in_thread, async_wrap


# ---------------------------------------------------------------------------
# run_in_thread
# ---------------------------------------------------------------------------


class TestRunInThread:
    @pytest.mark.asyncio
    async def test_success(self) -> None:
        """Runs sync function in thread and returns result."""

        def add(a: int, b: int) -> int:
            return a + b

        result = await run_in_thread(add, 2, 3)
        assert result == 5

    @pytest.mark.asyncio
    async def test_with_kwargs(self) -> None:
        """Passes kwargs correctly to the wrapped function."""

        def greet(name: str, greeting: str = "Hello") -> str:
            return f"{greeting}, {name}!"

        result = await run_in_thread(greet, "World", greeting="Hi")
        assert result == "Hi, World!"

    @pytest.mark.asyncio
    async def test_error_logged_and_reraised(self) -> None:
        """Logs error and re-raises the exception."""

        def failing_func() -> None:
            raise ValueError("test error")

        with pytest.raises(ValueError, match="test error"):
            await run_in_thread(failing_func)


# ---------------------------------------------------------------------------
# async_wrap
# ---------------------------------------------------------------------------


class TestAsyncWrap:
    @pytest.mark.asyncio
    async def test_wraps_sync_function(self) -> None:
        """Decorator turns sync function into awaitable."""

        @async_wrap
        def multiply(a: int, b: int) -> int:
            return a * b

        result = await multiply(3, 4)
        assert result == 12

    @pytest.mark.asyncio
    async def test_preserves_function_name(self) -> None:
        """Wrapped function preserves original name via @wraps."""

        @async_wrap
        def my_function() -> str:
            return "hello"

        assert my_function.__name__ == "my_function"

    @pytest.mark.asyncio
    async def test_error_propagation(self) -> None:
        """Errors from wrapped functions propagate correctly."""

        @async_wrap
        def kaboom() -> None:
            raise RuntimeError("boom")

        with pytest.raises(RuntimeError, match="boom"):
            await kaboom()

    @pytest.mark.asyncio
    async def test_with_kwargs(self) -> None:
        """Wrapped function handles kwargs."""

        @async_wrap
        def format_msg(msg: str, upper: bool = False) -> str:
            return msg.upper() if upper else msg

        result = await format_msg("hello", upper=True)
        assert result == "HELLO"


# end backend/tests/unit/test_async_helpers.py
