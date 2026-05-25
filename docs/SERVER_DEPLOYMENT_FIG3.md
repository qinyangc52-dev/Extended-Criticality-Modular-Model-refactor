# Fig.3 服务器部署与运行说明

本文档用于在 Linux/Ubuntu 服务器上运行 Fig.3 完整参数空间复现，导出 `Q`、`chi_Q` 热图和三张参数表。

## 1. 目标输出

运行完成后应得到：

- `results/figures/fig3_order_parameter_Q_full.png`
- `results/figures/fig3_order_parameter_fluctuations_chiQ_full.png`
- `results/figures/fig3_parameter_space_full.png`
- `results/tables/fig3_parameter_space_summary.csv`
- `results/tables/fig3_critical_line_chiQ_peak.csv`
- `results/tables/fig3_transition_line_Q_gradient.csv`
- `results/tables/fig3_missing_or_failed_runs.csv`

其中：

- `fig3_parameter_space_summary.csv`：所有 `(E0, I0)` 参数点总表。
- `fig3_critical_line_chiQ_peak.csv`：每个 `I0` 下 `chi_Q` 最大的临界线参数。
- `fig3_transition_line_Q_gradient.csv`：每个 `I0` 下 `Q` 随 `E0` 变化最快的跃迁线参数。

## 2. 安装系统依赖

```bash
sudo apt update
sudo apt install -y git build-essential cmake python3 python3-venv python3-pip rsync tmux
```

## 3. 上传或克隆项目

如果项目已有远程仓库：

```bash
mkdir -p ~/projects
cd ~/projects
git clone <你的仓库地址> Extended-Criticality--Modular-Model
cd Extended-Criticality--Modular-Model
```

如果没有远程仓库，从本机上传：

```bash
rsync -av --exclude build --exclude results/runs --exclude outputs \
  ./Extended-Criticality--Modular-Model/ user@server:~/projects/Extended-Criticality--Modular-Model/
```

进入服务器项目目录：

```bash
cd ~/projects/Extended-Criticality--Modular-Model
```

## 4. 创建 Python 环境

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install -e .
```

## 5. 编译 C/C++ 模拟器

```bash
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j "$(nproc)"
```

确认可执行文件存在：

```bash
ls -lh build/criticality_sim
```

## 6. Smoke Test

```bash
mkdir -p results/runs/smoke_server
cp configs/experiments/smoke.seed results/runs/smoke_server/SEED
cd results/runs/smoke_server
../../../build/criticality_sim > stdout.log 2> stderr.log
cd ../../..
```

检查输出：

```bash
ls results/runs/smoke_server/output
tail -n 20 results/runs/smoke_server/stdout.log
tail -n 20 results/runs/smoke_server/stderr.log
```

## 7. Fig.3 完整扫描前验证

先 dry-run，确认会生成 1020 个任务：

```bash
source .venv/bin/activate
python scripts/fig3_full_pipeline.py --config configs/fig3_full_grid.json --dry-run
```

再跑 4 个小任务验证流程：

```bash
python scripts/fig3_full_pipeline.py --config configs/fig3_full_grid.json --workers 2 --limit 4 --resume
```

验证输出：

```bash
head results/tables/fig3_parameter_space_summary.csv
ls results/figures/fig3_*full.png
```

## 8. 启动完整 Fig.3 扫描

建议在 `tmux` 中运行，避免 SSH 断开导致任务停止：

```bash
tmux new -s fig3
source .venv/bin/activate
python scripts/fig3_full_pipeline.py --config configs/fig3_full_grid.json --workers 4 --resume
```

如果服务器 CPU 和内存充足，可把 `--workers 4` 调高；如果出现内存压力或 I/O 压力，降低 workers。

## 9. 查看进度

另开一个 SSH 或 tmux pane：

```bash
tail -f results/logs/fig3_full_pipeline.log
```

查看已完成任务数量：

```bash
find results/runs/fig3_full_grid -name "q3-*.dat" | wc -l
find results/runs/fig3_full_grid -name "medie3-*.dat" | wc -l
```

## 10. 断点续跑

脚本支持 `--resume`。如果中断，直接重新运行：

```bash
source .venv/bin/activate
python scripts/fig3_full_pipeline.py --config configs/fig3_full_grid.json --workers 4 --resume
```

已有完整 `q3` 和 `medie3` 输出的参数点会被跳过。

如果只想重新汇总已有输出，不启动模拟：

```bash
python scripts/fig3_full_pipeline.py --config configs/fig3_full_grid.json --summarize-only
```

## 11. 回传结果

从本机执行：

```bash
rsync -av user@server:~/projects/Extended-Criticality--Modular-Model/results/figures/ ./results/figures/
rsync -av user@server:~/projects/Extended-Criticality--Modular-Model/results/tables/ ./results/tables/
```

如需回传全部运行数据：

```bash
rsync -av user@server:~/projects/Extended-Criticality--Modular-Model/results/runs/fig3_full_grid/ ./results/runs/fig3_full_grid/
```

## 12. 结果表字段说明

### `fig3_parameter_space_summary.csv`

| 字段 | 含义 |
|---|---|
| `run_name` | 参数点运行名称 |
| `E0` | 结构化兴奋强度，对应 `sigma` |
| `I0` | 全局抑制强度，对应 `delta` |
| `seed` | 随机种子 |
| `bin_ms` | 输出时间分辨率 |
| `tmax_ms` | 模拟时长 |
| `Q_mean` | 后半段平均 `q_max` |
| `chi_Q` | 后半段平均 `q_var` |
| `Q_max` | 后半段最大 `q_max` |
| `rate_mean` | 后半段平均 firing rate |
| `fano_mean` | 后半段平均 Fano factor |
| `cv_count_mean` | 后半段 spike count CV |
| `flexibility_n0` | 后半段超过 0.8 的 pattern 数 |
| `status` | `ok`、`missing` 或错误信息 |
| `output_dir` | 该参数点输出目录 |

### `fig3_critical_line_chiQ_peak.csv`

这张表按每个 `I0` 找 `chi_Q` 最大的 `E0`。

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
| `confidence_flag` | 插值可靠性 |

### `fig3_transition_line_Q_gradient.csv`

这张表按每个 `I0` 找 `Q` 随 `E0` 变化最快的位置。

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

## 13. 注意事项

- 1020 个模拟计算量很大，建议优先在服务器上运行。
- 如果只想快速验证流程，使用 `--limit 4`。
- 如果要调整扫描密度，修改 `configs/fig3_full_grid.json` 中的 `e0` 和 `i0`。
- 当前 workflow 不改核心模型，只改变批量运行和后处理方式。
