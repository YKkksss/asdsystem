import socket
import sys
import time


def wait_for_port(host: str, port: int, timeout_seconds: int, retry_interval_seconds: float) -> None:
    deadline = time.time() + timeout_seconds

    while time.time() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client:
            client.settimeout(retry_interval_seconds)
            try:
                client.connect((host, port))
            except OSError:
                time.sleep(retry_interval_seconds)
                continue

        print(f"服务已就绪：{host}:{port}")
        return

    raise TimeoutError(f"等待服务超时：{host}:{port}")


def main() -> int:
    if len(sys.argv) < 2:
        print("请至少提供一个 host:port 参数。")
        return 1

    timeout_seconds = int(sys.argv[1])
    targets = sys.argv[2:]

    if not targets:
        print("请至少提供一个 host:port 参数。")
        return 1

    for target in targets:
        host, raw_port = target.split(":", 1)
        wait_for_port(host, int(raw_port), timeout_seconds=timeout_seconds, retry_interval_seconds=1.0)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
