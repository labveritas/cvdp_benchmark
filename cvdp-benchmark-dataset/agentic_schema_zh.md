# CVDP Agentic 记录结构说明（System Message / Prompt / Context / Patch / Harness）

本文档整理 CVDP 数据集中 **agentic** 类型 JSONL 记录里各字段的“常规骨架”。

## 记录级字段（Agentic JSONL）
每一行是一条样本，常见字段如下：
- `id`：样本唯一标识
- `categories`：如 `["cid013", "medium"]`
- `system_message`：工具与流程约束说明
- `prompt`：任务描述
- `context`：可读文件（路径 -> 内容）
- `patch`：需要修改/生成的文件（路径 -> 初始内容）
- `harness`：评测文件（路径 -> 内容）

## system_message：常见骨架
通常包含以下结构块：
1) **可用工具/命令列表**
   - 列目录：`ls`、`tree`
   - 读文件：`cat <filename>`
   - 写文件：`echo <content> > <filename>`
   - 编译 Verilog：`iverilog -o ... -g2012 ...`
   - 运行仿真：`vvp <output>.out`
   - 有时包含：`sed -i ...`（原位替换）
   - 常见：`pwd`

2) **任务总述**
   - “根据 prompt 解决问题，必要时使用上述命令。”
   - 要求最终输出 Linux patch。

3) **思考/行动/观察流程**
   - 必须按 `thought -> action -> observation` 步骤进行。

4) **最终输出格式约束**
   - 最后一步包含 summary + patch。
   - patch 为 Linux diff。
   - **只允许修改一个文件**。

### system_message 模板（近似）
```text
You are a language model that has the following file operations available at your disposal:
  - List files: ls, tree
  - Read files: cat <filename>
  - Write files: echo <content> > <filename>
  - Compile Verilog: iverilog -o <out>.out -g2012 <verilog> <testbench>
  - Run simulation: vvp <out>.out
  - (optional) Update file: sed -i '...'
  - (often) pwd

You will be given a prompt and your task is to solve the issue using the commands above.
At the end, create a Linux patch highlighting the necessary file updates.

Use the following approach:
  - thought
  - action
  - observation

Final output format:
  - thought (summary + intro to the patch)
  - patch (Linux patch)

The patch should only be applied to a single file.
```

## prompt：常见骨架
`prompt` 是具体任务描述，典型结构：
- **总体目标**（实现/修改模块，加入 checker 等）。
- **引用规范文档**（如 `docs/specification.md`）。
- **目标文件路径**（`rtl/` 或 `verif/`）。
- **功能与接口要求**（列点说明）。
- **约束**（必须复用已有模块、保持接口不变等）。

### prompt 模板（近似）
```text
任务概述（要实现/修改什么）

参考资料：
- 规格说明：<context 里的文档路径>
- 相关模块/测试：<context 中路径>

要求：
- 功能行为：...
- 接口/时序：...
- 覆盖或边界条件：...

交付：
- 修改或创建 <目标文件路径>
```

## context：常见结构
- `context` 为字典：**文件路径 -> 文件内容**。
- 包含 agent 可读取的文件（规格、RTL、测试等）。

## patch：常见结构
- `patch` 为字典：**文件路径 -> 文件内容**。
- 通常是需要编辑/生成的文件。
- system_message 要求最终 patch 只涉及一个文件。

## harness：常见结构
- `harness` 为字典：**文件路径 -> 文件内容**。
- 评测用文件（仿真脚本、docker 配置、测试运行器）。
- 不需要也不应该被 agent 修改。

## 备注
- 不同样本会有轻微差异（比如工具列表里是否包含 `sed -i`），但整体骨架一致。
- Agentic 任务常见于模块复用/整合、或在已有 testbench 中补充 checker 逻辑。

## 示例片段（cid014，agentic）
下面摘取一条 cid014（断言生成）样本的片段，内容已截断以便阅读。

```text
id: cvdp_agentic_AES_encryption_decryption_0020
categories: ["cid014", "medium"]

system_message（片段）:
You are a language model that has the following file operations available at your disposal:
  - List files: ls, tree
  - Read files: cat <filename>
  - Write files: echo <content> > <filename>
  - Compile Verilog: iverilog -o <out>.out -g2012 <verilog> <testbench>
  - Run simulation: vvp <out>.out
  - ...

prompt（片段）:
I have a hierarchical AES encryption design with 3 main modules:
- aes_enc_top
- aes_encrypt
- sbox
These modules are located in the rtl directory. Please enhance the design
by adding SystemVerilog Assertions (SVA) to verify control logic, functional
behavior, round sequencing, and mode-dependent correctness.
...

context 文件:
- rtl/aes_enc_top.sv
- rtl/aes_encrypt.sv
- rtl/sbox.sv

patch 文件:
- rtl/aes_enc_top.sv
- rtl/aes_encrypt.sv

harness 文件:
- Dockerfile
- docker-compose.yml
- src/harness_library.py
- src/test_aes_enc_top.py
- src/test_runner.py
```
