---
name: chip-test
description: Plan MCU characterization, compare power or analog-voltage measurements, and prepare traceable datasheet updates from test records. Use for bench test workflows and result review; chip-specific register maps and firmware must be supplied by the project.
---

# 芯片测试与数据整理

将用户的测试目标变成条件明确、可复现、可追溯的结果。先确定是准备方案、执行已授权测试、分析现有数据，还是修改 DS；不要因读取测试记录自动重新测量或烧录。

## 按任务读取

- RUN/Sleep/STOP/低功耗及外设增量电流：读取 [功耗流程](references/power.md)。
- 模拟测试输出、调压档位、ADC与外测对比、运行/暂停异常：读取 [模拟电压流程](references/analog.md)。
- 更新参数表、替换旧值、审核缺项：读取 [DS回填规则](references/datasheet.md)。

## 执行与证据

1. 定位当前芯片、板号、最新资料版本及现有脚本。确认供电和测量节点，而不是只依赖电源面板或调试器的参考电压。沿用本轮已确认且未变化的条件，缺失的信息只问影响下一步的部分。
2. 从项目手册确认寄存器、时钟和电压允许范围。这个技能没有通用的寄存器地址或档位数值；不得套用另一颗 MCU 的映射。能由设计推导的项目标为计算/设计值。
3. 真实仪器用现有驱动或已验证脚本连接；若安装了 `lab-instruments` 可复用其设备发现和采集能力，没有该技能也可用项目工具。先做身份与只读检查，再执行本次授权的配置。输出改变、烧录、复位必须在当前任务范围内。
4. 每个测试点记录源文件、芯片编号、程序版本、条件、原始值、配置前后读回和结果状态。硬件动作前打印测试项及待用户配合的内容。换芯片后重新标号；复位、掉电或配置变化造成的核验失败保留原记录。
5. 通信失败、量程溢出、状态不符停止当前测试点；有依据的恢复后用新编号重测，不覆盖失败记录。不要为采完计划而反复复位或继续扫电压。

## 自带离线工具

`scripts/results.py` 不连接硬件。它验证 JSON、逐点统计并导出 CSV/Markdown，原始输入随报告保存。可先用 `assets/demo.json` 验证流程；示例数据全部为模拟数据。

```sh
python scripts/results.py validate assets/demo.json
python scripts/results.py report assets/demo.json --out-dir output/demo
```

输入格式见示例及脚本的 `validate` 函数。不同条件不要塞到同一个点。`valid` 代表该读数被采集流程接收；`precheck/postcheck` 是人工或目标适配器提供的核验结果。`review` 只表示资料齐全可供审核；不代表器件合格或规格保证。输出 `incomplete` 或 `blocked` 时先说明缺失条件或配置问题；不自动补猜。

修改文档时保留原始数据及用户指定底稿，给出变更位置与未填原因。共享的是通用流程；项目芯片的手册、校准备份、解锁程序和实测数据不会因为使用本技能自动上传。
