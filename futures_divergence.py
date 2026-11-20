#!/usr/bin/env python3
"""
期货主力连续合约 MACD 顶底背离识别工具

从新浪期货接口拉取主力连续合约日线数据，计算 MACD(12,26,9)，
识别顶背离/底背离，输出 markdown 表格。

无需额外依赖，仅使用 Python 标准库。
"""

import json
import re
import sys
import urllib.request
import urllib.error
from datetime import datetime
from typing import List, Optional, Tuple, Dict

# ── 品种列表（新浪期货主力连续合约代码） ──────────────────────────────
FUTURES_LIST = [
    {"symbol": "RB0", "name": "螺纹钢"},
    {"symbol": "I0",  "name": "铁矿石"},
    {"symbol": "HC0", "name": "热卷"},
    {"symbol": "MA0", "name": "甲醇"},
    {"symbol": "TA0", "name": "PTA"},
    {"symbol": "PP0", "name": "聚丙烯"},
    {"symbol": "CU0", "name": "沪铜"},
    {"symbol": "AL0", "name": "沪铝"},
    {"symbol": "AU0", "name": "沪金"},
    {"symbol": "AG0", "name": "沪银"},
    {"symbol": "M0",  "name": "豆粕"},
    {"symbol": "Y0",  "name": "豆油"},
    {"symbol": "CF0", "name": "棉花"},
    {"symbol": "SR0", "name": "白糖"},
    {"symbol": "SC0", "name": "原油"},
    {"symbol": "NI0", "name": "沪镍"},
    {"symbol": "ZN0", "name": "沪锌"},
    {"symbol": "FU0", "name": "燃料油"},
    {"symbol": "BU0", "name": "沥青"},
    {"symbol": "RM0", "name": "菜粕"},
]

SINA_KLINE_URL = (
    "https://stock2.finance.sina.com.cn/futures/api/jsonp.php/"
    "var%20_data=/InnerFuturesNewService.getDailyKLine"
    "?symbol={symbol}"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://finance.sina.com.cn",
}


def fetch_daily_kline(symbol: str) -> Optional[List[Dict]]:
    """从新浪期货接口获取日线数据，返回按日期升序排列的记录列表"""
    url = SINA_KLINE_URL.format(symbol=symbol)
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            text = resp.read().decode("utf-8")
    except (urllib.error.URLError, OSError) as e:
        print(f"  [WARN] 获取 {symbol} 数据失败: {e}", file=sys.stderr)
        return None

    # 解析 JSONP: var _data=([{...},...]);
    match = re.search(r'\((\[.*\])\)', text, re.DOTALL)
    if not match:
        print(f"  [WARN] {symbol} JSONP 解析失败", file=sys.stderr)
        return None

    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError:
        print(f"  [WARN] {symbol} JSON 解析失败", file=sys.stderr)
        return None

    if not data:
        return None

    # 转换类型并按日期排序
    records = []
    for row in data:
        try:
            records.append({
                "date": row["d"],
                "open": float(row["o"]),
                "high": float(row["h"]),
                "low": float(row["l"]),
                "close": float(row["c"]),
            })
        except (KeyError, ValueError):
            continue

    records.sort(key=lambda r: r["date"])
    return records


def calc_ema(values: List[float], span: int) -> List[float]:
    """计算指数移动平均 (EMA)"""
    if not values:
        return []
    multiplier = 2.0 / (span + 1)
    ema = [values[0]]
    for i in range(1, len(values)):
        ema.append(values[i] * multiplier + ema[-1] * (1 - multiplier))
    return ema


def calc_macd(closes: List[float], fast: int = 12, slow: int = 26, signal: int = 9):
    """
    计算 MACD(12,26,9)
    返回 (dif, dea, macd_hist) 三个列表
    """
    ema_fast = calc_ema(closes, fast)
    ema_slow = calc_ema(closes, slow)
    dif = [f - s for f, s in zip(ema_fast, ema_slow)]
    dea = calc_ema(dif, signal)
    hist = [2 * (d - e) for d, e in zip(dif, dea)]
    return dif, dea, hist


def find_local_extrema(values: List[float], window: int = 5):
    """
    寻找局部极值点
    返回 (peaks, troughs) 其中每个元素为 (index, value)
    """
    peaks = []
    troughs = []
    n = len(values)
    for i in range(window, n - window):
        local_slice = values[i - window: i + window + 1]
        if values[i] == max(local_slice):
            peaks.append((i, values[i]))
        if values[i] == min(local_slice):
            troughs.append((i, values[i]))
    return peaks, troughs


def detect_divergence(records: List[Dict], lookback: int = 60) -> Optional[Tuple[str, str]]:
    """
    检测 MACD 顶背离和底背离

    顶背离：价格创新高，但 MACD DIF 未创新高（DIF 走低）
    底背离：价格创新低，但 MACD DIF 未创新低（DIF 走高）

    返回 (方向, 信号日期) 或 None
    """
    if len(records) < 60:
        return None

    # 取最近 lookback 条数据
    records = records[-lookback:]
    closes = [r["close"] for r in records]
    dates = [r["date"] for r in records]

    dif, dea, hist = calc_macd(closes)

    # 寻找价格和 DIF 的局部极值
    price_peaks, price_troughs = find_local_extrema(closes, window=5)
    dif_peaks, dif_troughs = find_local_extrema(dif, window=5)

    signals = []

    # 顶背离检测：价格相邻波峰升高，DIF 相邻波峰降低
    if len(price_peaks) >= 2 and len(dif_peaks) >= 2:
        p1_idx, p1_val = price_peaks[-2]
        p2_idx, p2_val = price_peaks[-1]

        # 找对应时间段内的 DIF 波峰（允许 ±3 根 K 线的偏移）
        d1_candidates = [(i, v) for i, v in dif_peaks if p1_idx - 3 <= i <= p1_idx + 3]
        d2_candidates = [(i, v) for i, v in dif_peaks if p2_idx - 3 <= i <= p2_idx + 3]

        if d1_candidates and d2_candidates:
            d1_val = max(d1_candidates, key=lambda x: x[1])[1]
            d2_val = max(d2_candidates, key=lambda x: x[1])[1]
            if p2_val > p1_val and d2_val < d1_val:
                signal_date = dates[p2_idx]
                signals.append(("顶背离", signal_date))

    # 底背离检测：价格相邻波谷降低，DIF 相邻波谷升高
    if len(price_troughs) >= 2 and len(dif_troughs) >= 2:
        t1_idx, t1_val = price_troughs[-2]
        t2_idx, t2_val = price_troughs[-1]

        d1_candidates = [(i, v) for i, v in dif_troughs if t1_idx - 3 <= i <= t1_idx + 3]
        d2_candidates = [(i, v) for i, v in dif_troughs if t2_idx - 3 <= i <= t2_idx + 3]

        if d1_candidates and d2_candidates:
            d1_val = min(d1_candidates, key=lambda x: x[1])[1]
            d2_val = min(d2_candidates, key=lambda x: x[1])[1]
            if t2_val < t1_val and d2_val > d1_val:
                signal_date = dates[t2_idx]
                signals.append(("底背离", signal_date))

    if not signals:
        return None

    # 返回最近的信号
    return signals[-1]


def main():
    print("# 期货主力连续合约 MACD 背离分析")
    print(f"# 分析时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("# MACD 参数: (12, 26, 9)")
    print("# 数据源: 新浪期货日线")
    print()

    results = []

    for item in FUTURES_LIST:
        symbol = item["symbol"]
        name = item["name"]
        print(f"正在分析 {name}({symbol})...", file=sys.stderr)

        records = fetch_daily_kline(symbol)
        if records is None or len(records) < 60:
            continue

        current_price = records[-1]["close"]
        signal = detect_divergence(records)

        if signal:
            direction, signal_date = signal
            results.append({
                "name": name,
                "symbol": symbol,
                "direction": direction,
                "price": f"{current_price:.2f}",
                "signal_date": signal_date,
            })

    # 输出 Markdown 表格
    print("## 背离信号结果\n")

    if not results:
        print("当前未检测到明显的 MACD 背离信号。\n")
        return

    print("| 品种 | 方向 | 当前价 | 信号日期 |")
    print("|------|------|--------|----------|")
    for r in results:
        print(f"| {r['name']} | {r['direction']} | {r['price']} | {r['signal_date']} |")

    print()
    print(f"*共检测到 {len(results)} 个背离信号*")


if __name__ == "__main__":
    main()
