import argparse
import asyncio
import sys
from time import perf_counter

import httpx

REQUESTS = 10


async def measure(url: str) -> None:
    total_bytes = 0
    total_seconds = 0.0
    line_width = 0
    interactive = sys.stdout.isatty()

    def show_speed(speed_kbps: float) -> None:
        nonlocal line_width
        line = f"Скорость скачивания: {speed_kbps:.2f} кбит/с"
        if interactive:
            line_width = max(line_width, len(line))
            print("\r" + line.ljust(line_width), end="", flush=True)
        else:
            print(line, flush=True)

    async def update_speed() -> None:
        previous_bytes, previous_time = 0, perf_counter()
        while True:
            await asyncio.sleep(0.2)
            now = perf_counter()
            show_speed((total_bytes - previous_bytes) * 8 / (now - previous_time) / 1000)
            previous_bytes, previous_time = total_bytes, now

    async with httpx.AsyncClient(
        timeout=60.0,
        follow_redirects=False,
        headers={"Accept-Encoding": "identity"},
    ) as client:
        show_speed(0.0)
        progress = asyncio.create_task(update_speed())
        try:
            for _ in range(REQUESTS):
                started = perf_counter()
                async with client.stream("GET", url) as response:
                    response.raise_for_status()
                    async for chunk in response.aiter_raw():
                        total_bytes += len(chunk)
                total_seconds += perf_counter() - started
        finally:
            progress.cancel()
            try:
                await asyncio.gather(progress, return_exceptions=True)
            finally:
                if interactive:
                    print("\r" + " " * line_width + "\r", end="", flush=True)

    average_seconds = total_seconds / REQUESTS
    print(f"Среднее время: {average_seconds:.3f} с\nСкачано: {total_bytes} байт")


def main() -> None:
    parser = argparse.ArgumentParser(description="10 последовательных загрузок URL")
    parser.add_argument("url", help="Конечный адрес файла без редиректов")
    args = parser.parse_args()
    try:
        url = httpx.URL(args.url)
        if url.scheme not in {"http", "https"} or not url.host:
            raise ValueError("Укажите полный URL с http:// или https://.")
        asyncio.run(measure(str(url)))
    except (httpx.HTTPError, httpx.InvalidURL, ValueError) as exc:
        parser.exit(1, f"Ошибка: {exc}\n")
    except KeyboardInterrupt:
        parser.exit(130, "Измерение прервано.\n")


if __name__ == "__main__":
    main()
