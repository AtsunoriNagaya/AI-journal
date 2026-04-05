"""環境変数読み取りヘルパー。"""

import os


def read_int_env(name: str, *, default: int, minimum: int) -> int:
    """整数環境変数を読み取り、未設定や不正値は default にフォールバックする。"""
    # 未設定の場合は呼び出し元の既定値をそのまま使う。
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default

    # 数値に変換できない値（例: "abc"）は安全側で既定値に戻す。
    try:
        value = int(raw)
    except ValueError:
        return default

    # minimum を下回る値は切り上げる（負数禁止の設定などに使う）。
    return max(value, minimum)