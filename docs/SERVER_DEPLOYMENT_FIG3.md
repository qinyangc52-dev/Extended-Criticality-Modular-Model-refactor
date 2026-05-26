# Fig.3 临界线优先运行说明

本文档用于在 Linux/Ubuntu 服务器上运行 Fig.3 临界线优先 workflow。目标不是先跑满 1020 个完整网格点，而是先用粗网格定位 `chi_Q` 峰值，再围绕峰值加密，从而更快得到临界线参数和 Fig.3 风格图。

## 1. 目标输出

运行完成后应得到：

- `results/tables/fig3_parameter_space_summary.csv`
- `results/tables/fig3_critical_line_chiQ_peak.csv`
- `results/tables/fig3_transition_line_Q_gradient.csv`
- `results/tables/fig3_missing_or_failed_runs.csv`
- `results/figures/fig3_parameter_space_critical_search.png`
- `results/figures/fig3_chiQ_critical_line.png`

其中：

- `fig3_critical_line_chiQ_peak.csv`：每个 `I0` 下 `chi_Q` 最大的临界线参数。
- `fig3_transition_line_Q_gradient.csv`：每个 `I0` 下 `Q` 随 `E0` 变化最快的跃迁线参数。
- `fig3_parameter_space_critical_search.png`：`Q` 和 `chi_Q` 参数空间图，叠加临界线和跃迁线。
- `fig3_chiQ_critical_line.png`：单张 Fig.3 风格 `chi_Q` 热图，黑线为临界线。

## 2. 安装依赖

```bash
sudo apt update
sudo apt install -y git build-essential cmake python3 python3-venv python3-pip rsync tmux
```

如果没有 `sudo`，优先使用 conda/venv 安装 Python 依赖和新版 CMake。

## 3. 克隆项目

```bash
mkdir -p ~/projects
cd ~/projects
git clone https://github.com/qinyangc52-dev/Extended-Criticality-Modular-Model-refactor.git
cd Extended-Criticality-Modular-Model-refactor
```

GitHub 较慢时可用浅克隆代理：

```bash
git clone --depth 1 https://gh-proxy.com/https://github.com/qinyangc52-dev/Extended-Criticality-Modular-Model-refactor.git
```

## 4. 创建 Python 环境

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install -e .
```

## 5. 编译模拟器

```bash
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j "$(nproc)"
```

确认可执行文件存在：

```bash
ls -lh build/criticality_sim
```

如果 CMake 不可用，可直接 gcc 编译：

```bash
mkdir -p build
gcc -O3 -DNDEBUG \
  apps/simulate/main.c \
  src/model/network.c \
  src/model/neuroni.c \
  src/data/tract1.c \
  src/utils/*.c \
  -lm \
  -o build/criticality_sim
```

## 6. Dry Run

先确认任务计划：

```bash
python scripts/fig3_full_pipeline.py --config configs/fig3_critical_search.json --dry-run
```

默认计划：

- coarse stage：`I0=0.0..1.9 step 0.1`，`E0=0.0..10.0 step 0.5`，共 420 个任务。
- refine stage：围绕每条 `I0` 的 coarse `chi_Q` 峰值 `E0_peak +/- 0.4`，`step=0.1`，最多约 180 个任务。

## 7. 小规模验证

在正式运行前，可以只跑两条 `I0` 验证流程：

```bash
python scripts/fig3_full_pipeline.py \
  --config configs/fig3_critical_search.json \
  --workers 2 \
  --limit-i0 2 \
  --run-id smoke_i0_2
```

检查输出：

```bash
ls results/tables/smoke_i0_2
ls results/figures/smoke_i0_2
tail -n 30 results/logs/smoke_i0_2/fig3_critical_progress.log
cat results/logs/smoke_i0_2/fig3_critical_status.json
```

## 8. 正式运行

服务器 40 vCPU 可先用 16 workers：

```bash
mkdir -p results/logs
nohup python scripts/fig3_full_pipeline.py \
  --config configs/fig3_critical_search.json \
  --workers 16 \
  > results/logs/fig3_critical_nohup.log 2>&1 &
```

本 workflow 不提供 `--resume`。如果想重新跑一次，不要覆盖旧目录，使用新的 `--run-id`：

```bash
nohup python scripts/fig3_full_pipeline.py \
  --config configs/fig3_critical_search.json \
  --workers 16 \
  --run-id run_$(date +%Y%m%d_%H%M) \
  > results/logs/fig3_critical_nohup.log 2>&1 &
```

如果默认 `results/runs/fig3_critical_search` 已存在，脚本会直接报错，避免把半成品误当成最终结果。

## 9. 观察进度

实时日志：

```bash
tail -f results/logs/fig3_critical_progress.log
```

状态 JSON：

```bash
watch -n 30 'cat results/logs/fig3_critical_status.json; echo; df -h .; echo; uptime'
```

查看模拟器进程：

```bash
pgrep -af "/build/criticality_sim"
```

如果使用了 `--run-id smoke_i0_2` 或其它 run id，日志路径会变成：

```bash
results/logs/<run-id>/fig3_critical_progress.log
results/logs/<run-id>/fig3_critical_status.json
```

## 10. 只汇总已有结果

如果模拟已经完成，但需要重新生成 CSV 和图：

```bash
python scripts/fig3_full_pipeline.py \
  --config configs/fig3_critical_search.json \
  --summarize-only
```

如果之前使用了 `--run-id`，汇总时也必须带同一个 `--run-id`。

## 11. 结果表字段

### `fig3_critical_line_chiQ_peak.csv`

| 字段 | 含义 |
|---|---|
| `I0` | 固定抑制强度 |
| `E0_peak_grid` | 网格上 `chi_Q` 最大的 E0 |
| `E0_peak_interp` | 三点抛物线插值得到的 E0 |
| `chi_Q_peak` | 最大 `chi_Q` |
| `Q_at_peak` | 峰值处平均 Q |
| `rate_at_peak` | 峰值处 firing rate |
| `fano_at_peak` | 峰值处 Fano |
| `flexibility_at_peak` | 峰值处 replay pattern 数 |
| `run_name` | 对应运行 |
| `confidence_flag` | 插值可靠性；边界峰值会标记为 `edge_peak` |

### `fig3_transition_line_Q_gradient.csv`

| 字段 | 含义 |
|---|---|
| `I0` | 固定抑制强度 |
| `E0_transition_grid` | 网格上最大 `dQ/dE0` 的 E0 |
| `E0_transition_interp` | 三点抛物线插值得到的 E0 |
| `max_dQ_dE0` | 最大 Q 斜率 |
| `Q_before` | 跃迁点左侧 Q |
| `Q_after` | 跃迁点右侧 Q |
| `chi_Q_near_transition` | 跃迁附近 `chi_Q` |
| `rate_near_transition` | 跃迁附近 firing rate |
| `run_name` | 对应运行 |
| `confidence_flag` | 插值可靠性 |

## 12. 回传结果

从本机执行：

```bash
rsync -av user@server:~/projects/Extended-Criticality-Modular-Model-refactor/results/figures/ ./results/figures/
rsync -av user@server:~/projects/Extended-Criticality-Modular-Model-refactor/results/tables/ ./results/tables/
```

如使用 `--run-id`，结果在对应子目录下：

```bash
rsync -av user@server:~/projects/Extended-Criticality-Modular-Model-refactor/results/figures/<run-id>/ ./results/figures/<run-id>/
rsync -av user@server:~/projects/Extended-Criticality-Modular-Model-refactor/results/tables/<run-id>/ ./results/tables/<run-id>/
```

## 13. 注意事项

- 该 workflow 聚焦临界线定位，不是完整 1020 点高分辨率热图。
- 不修改 C/C++ 核心模型，只改变批量运行、进度观察和后处理。
- 不做断点续跑；异常中断后建议换新的 `--run-id` 重新跑，避免混入半成品。
- 服务器系统盘较小时要持续观察 `df -h .`，`bin=1` 会产生较多输出文件。
