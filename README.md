# Chip Test Toolkit

面向 MCU / 芯片实验室的通用测试流程与数据整理工具。包含一个可安装的 Codex skill、功耗/模拟电压/数据手册三类流程，以及可独立运行的数据校验和报告脚本。

**首版 v0.1.0：离线流程与数据工具。** 不包含任何特定芯片的寄存器地址、解锁算法、固件、真实测试数据或自动烧录流程。连接真实硬件需要另行提供经过核对的板卡适配程序和仪器驱动。示例全部是人为构造的模拟数据，不能作为芯片规格。

## 下载并运行

点击 GitHub 的 **Code → Download ZIP** 后解压，或者：

```sh
git clone https://github.com/xiatianxiatianyaya/chip-test-toolkit.git
cd chip-test-toolkit
python chip-test/scripts/results.py validate chip-test/assets/demo.json
python chip-test/scripts/results.py report chip-test/assets/demo.json --out-dir output/demo
python -m unittest discover -s tests -v
```

需要 Python 3.10 或以上；报告工具只使用 Python 标准库，没有第三方依赖。Windows 可以将 `python` 换成 `py -3`。

输出 `summary.csv`、`report.md` 和 `validated_input.json`。CSV 为 UTF-8 BOM 编码，可用 Excel 打开；原始输入一并保存。输出目录内已有同名文件时拒绝覆盖，请为每轮测试指定新目录。上述测试只检验离线工具，不表示完成了硬件验收。

## 安装为 Codex skill

把仓库中的整个 `chip-test` 文件夹复制到 `$CODEX_HOME/skills/`，未设置该变量时复制到 `~/.codex/skills/`。可使用：

> 使用 $chip-test，准备一次不同系统时钟和调压档位的低功耗测试。先给接线和条件表，按20次有效读数整理，待我确认板卡配置后再执行硬件动作。

或者：

> 使用 $chip-test，将本次测试结果整理为数据手册待回填清单，保留缺失条件和未核验状态。

## 功能与边界

| 部分 | 已提供 | 需要项目自行提供 |
|---|---|---|
| 功耗测试 | 接线核对、条件矩阵、调试器影响、前后核验、基准扣除规则 | 模式进入/退出、时钟及调压档位的芯片实现 |
| 模拟电压排查 | 单变量对照、寄存器读回、内外测量对应关系、异常保持 | 测试通道映射、ADC参考与转换公式 |
| DS整理 | 条件匹配、证据分级、缺项与候选参数表规则 | 有权使用的模板、目标文档及正式规格审核 |
| 数据工具 | 输入校验、有效样本统计、单位换算、逐点报告、原始输入保留 | 仪器采集及硬件配置核验 |

报告不会自动合并不同条件或不同芯片，也不会将实测最小/最大值填写为保证规格。状态 `review` 仅表示资料可进入人工审核，绝不表示满足指标或可以直接发布 DS。时间序列标准差不是测量不确定度。

## 数据格式

参考 [demo.json](chip-test/assets/demo.json)。顶层字段：`schema_version=1`、`campaign_id`、`points`。每个点包含：

- `id`、`sample_id`、`parameter`、`unit`、`source_ref`、`source_kind`。
- `source_kind`：`measured_auto`、`measured_manual`、`simulated`、`design`、`calculated`。设计/计算记录会明确标注，并且不自动成为实测参数。
- `conditions`：至少记录 `supply_v`、`temperature_c`、`power_mode`；未确定时填 `null`，报告列出缺项。时钟、负载、Flash/SRAM、调压档位等按实际项目添加。
- `precheck` / `postcheck`：`pass`、`fail`、`not_checked`。必须由真实配置读回和运行证据确定，数据整理工具不代替硬件核验。
- `expected_registers`、`observed_registers`：可选，使用符号名称和十六进制字符串等同类型值。不同表示法不会自动视为相等，部分读回会标为缺失。
- `min_valid_samples`：本点要求的最少有效读数，手动单次记录可设为1。
- `observations`：每条包含带时区的 `timestamp`、`status=valid/invalid`、数值 `value`；无效记录需给 `reason`，值可为 `null`。

同一个点的值使用同一个单位。支持 A/mA/uA/µA/μA/nA、V/mV、Hz/kHz/MHz、s/ms/us/µs/ns、ohm/kohm、pF、bit、dB。无法识别的单位会报错，避免默默换算。

## 参与和商用

欢迎通过 Issues 提交复现条件、脱敏数据和改进建议。提交前删除客户名称、仪器序列号、访问凭据及未公开的芯片资料。硬件适配应说明芯片/板卡版本、接线、适用条件和验证结果。

本项目使用 [MIT 许可证](LICENSE)，允许在保留许可证及版权声明的条件下使用、修改、分发和商用。基础工具免费；可在其上另行提供芯片适配、测试实施、培训或维护等付费服务。当前没有开通收款或承诺服务期限。
