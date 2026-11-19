#!/usr/bin/env python3
"""Print the current time."""

from datetime import datetime


def main():
    now = datetime.now()
    print(f"当前时间: {now.strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()
