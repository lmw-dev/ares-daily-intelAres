# Ares Agent Search POC (GenAI App Builder Credit Validation)

本实验是 Ares Daily Intel 项目的独立子模块，旨在通过 **Google Cloud AI Applications (Discovery Engine API / Agent Search)** 导入私有分析报告并进行检索，用以观察并测试 Google Cloud 赠送的 **$1,000 Trial credit for GenAI App Builder** 能否通过此 SKU 正常扣减消耗。

## ⚠️ 重要说明 (Important Notes)
- 本实验完全独立，**不会对线上正在运行的 Cloud Run Job、Cloud Scheduler 定时任务及 Gemini Grounding 系统产生任何干扰**。
- 请不要删除任何 GCS 文件，也不要在未经人工确认下使用命令行创建大量云端收费资源。

---

## 🛠 Google Cloud 控制台手动配置指南 (Console Setup)

因为需要精确控制测试成本与安全，本 POC 推荐在 GCP 控制台上进行人工资源创建：

### 1. 启用 API
前往 Google Cloud Console 启用以下 API 服务：
- **Discovery Engine API** (`discoveryengine.googleapis.com`)
- **Cloud Storage API** (`storage.googleapis.com`)

### 2. 创建 Data Store (数据存储)
1. 访问控制台：**AI Applications** (或在顶部搜 **Vertex AI Search and Conversation** / **Generative AI App Builder**) -> **Data Stores**。
2. 点击 **Create Data Store**：
   - 选择 **Cloud Storage**（或者选择 **Unstructured Documents** / **LlamaIndex** / **JSON**。本 POC 生成的是 JSONL，因此选择 **JSON** 格式作为数据源最为匹配，或选择 **Unstructured Documents** 导入 `.md`）。
   - 本 POC 会在本机生成 `out/ares_documents.jsonl`，请将其上传到您的 GCS 桶的特定目录下（如 `gs://ares-daily-intel-reports-20260702/config/ares_documents.jsonl`）。
   - 在 Data Store 配置中指向该 JSONL 地址。
   - Data Store 命名：`ares-daily-intel-store`
   - Location: `global`
   - Schema / Config: 默认配置，**切勿勾选开启高级加值收费功能**。

### 3. 创建 Search App (应用关联)
1. 点击 **Apps** -> **Create App**。
2. 选择 **Search** 类型。
3. 关联您刚刚创建的 Data Store：`ares-daily-intel-store`。
4. App 命名：`ares-daily-intel-search`
5. Location: `global`
6. 创建成功后，您会在 App 的 **Integration** 或 **Details** 页面中获得 **`Engine ID`** (用于 query 检索脚本)。

---

## 🚀 本地运行步骤

### 1. 环境配置
配置 `.env` 变量（可复制并修改自 `.env.example`）：
```bash
PROJECT_ID=ares-daily-intel
LOCATION=global
ENGINE_ID=your-agent-search-engine-id
ARES_VAULT_ROOT=/Users/liumingwei/vaults/AresVault
```

### 2. 准备待上传的结构化文档
该脚本会扫描您本地的 Obsidian 库，提炼最近 5-20 个文档并将其导出为 Agent Search 可直接批量导入的 JSONL 结构。

- **Dry-run 验证模式**（不写入磁盘仅作打印）：
  ```bash
  python prepare_documents.py --dry-run
  ```
- **真实生成 JSONL 导出**：
  ```bash
  MAX_DOCS=20 python prepare_documents.py
  ```
  该命令会在本地 `out/` 目录下生成 `ares_documents.jsonl`。

### 3. 执行测试检索
将 `out/ares_documents.jsonl` 上传到 GCS 并成功导入关联的 Search App 之后，运行查询脚本：
```bash
python query_agent_search.py
```
本脚本会从 `sample_queries.md` 读取样例问题并执行 Discovery Engine 进行私有检索，并在控制台输出查找到的来源文件 ID、路径和摘要。

---

## 📈 扣费账单验收
执行查询并检索后，建议在接下来的 24-48 小时前往：
- **Billing** -> **Reports**
- 在 Group by 中选择 **SKU**
- 观察是否产生了 **Agent Search** / **Discovery Engine** / **GenAI App Builder** 相关的 SKU 消费。
- 确认该消费是否成功被 **Trial credit for GenAI App Builder** 信用额度予以全额扣抵抵扣。
