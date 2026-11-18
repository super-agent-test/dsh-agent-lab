# dsh-agent-lab

期货主力连续合约 MACD 顶底背离识别工具。

## 常见问题

### 数据从哪里来？

本工具从新浪财经期货接口拉取主力连续合约的日线数据，无需额外 API Key，开箱即用。

### MACD 参数可以自定义吗？

目前使用默认参数 (12, 26, 9)。如需调整，可修改 `futures_divergence.py` 中 `calc_macd` 函数的 `fast`、`slow`、`signal` 参数。
