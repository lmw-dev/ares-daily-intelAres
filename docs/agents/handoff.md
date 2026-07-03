# Ares Daily Intel v0.2.1 Handoff Document (交接文档)

Ares Daily Intel v0.2.1 自动赛程挖掘外置配置版已完全完成开发与云端实跑闭环验证，实现了从原有的“修改配置重构发布”到“直接在 GCS 上外置修改配置”的自动化架构演进，并激活了每日早上 8 点自动触发的生产调度。

---

## 🛠 修改概要 (Changes Implemented)

1. **自动发现配置层 (data/scan_config.yml)**:
   - 默认模式转为 `auto_discovery`，配置了未来 72 小时检索跨度。
   - 设定 `competitions` 赛事监控范围和 `watch_teams` 监控队名列表。
   - 保留了 `manual_matches` 数组作为高优先级人工插塞通道。

2. **自动赛程发现引擎 (app/fixture_discovery.py)**:
   - 联网加载 `prompts/fixture_discovery.md` 模板。
   - 联网调用带有 Google Search Grounding 的 Gemini 3.5-flash，全网抓取包含 `kickoff_time`、`fixture_status` 等字段的候选赛程 JSON。
   - 对信源 `source_urls` 进行了提取与透传。

3. **优先级打分排序器 (app/priority_selector.py)**:
   - 实施打分规则：
     - 人工兜底 (`manual_matches`)：+1000（享有绝对合并优先权，且已做好模糊去重）。
     - 淘汰赛 (`knockout_match`)：+100
     - 重点赛事 (`World Cup` 等)：+50
     - 包含关注球队 (`watch_teams`)：+20
     - 检索信心 (`confidence == HIGH`)：+10
     - 支持信源量：每多一个 URL +1
   - 已完赛限制：仅保留在过去 24 小时内开球的 `COMPLETE` 赛事，其余时间较早的完赛全部过滤。
   - 最终返回数不超过 `max_matches` (默认为 3，最多限制为 5)。

4. **硬性信心修剪机制 (app/scan.py)**:
   - 加入后置修剪校验。凡是 `market_preview.source == "SEARCH_SUMMARY"` 的比赛，其实际盘口信心 `confidence` 强制限制为最高 `MEDIUM`（若原值为 HIGH，自动重写降级），防止误导输出。

5. **HOLD 无赛程兜底机制 (app/report.py & app/main.py)**:
   - 若当天无符合条件的赛事，程序绝不崩溃退出，而是生成一份带有 `HOLD` 状态标识 of No-fixtures 日报和 JSON，双写本地与云端 GCS，并正常推送 Slack 警报，以 Exit Code 0 退出，确保 Cloud Scheduler 的调用日志保持绿色健康。

6. **GCS 外部配置加载机制 (v0.2.1)**:
   - 重构配置载入层。启动时优先向 `gs://${GCS_BUCKET}/config/scan_config.yml` 动态拉取最新的扫描监控配置。
   - 设好健全的 Fallback 机制：读取 GCS 失败或桶里不存在该配置时，无阻自动回退到读取容器镜像内打包的本地 fallback 文件，系统绝不发生异常终止。

7. **Cloud Scheduler 定时触发配置 (v0.2.1)**:
   - 在 us-central1 区域内成功激活并创建了 `ares-daily-intel-schedule` 定时触发器，自动绑定服务账号凭证。
   - 每天早上 8:00 (Asia/Shanghai 北京时区) 定时发送 POST 启动 Cloud Run Job。

---

## 📂 项目文件变更列表 (Modified Files)

- **[data/scan_config.yml](file:///Users/liumingwei/01-project/12-liumw/26-ares-daily-intel/data/scan_config.yml)** [NEW]：赛程自动发现本地 Fallback 备份配置。
- **[prompts/fixture_discovery.md](file:///Users/liumingwei/01-project/12-liumw/26-ares-daily-intel/prompts/fixture_discovery.md)** [NEW]：赛程发现 Prompt 模板。
- **[app/fixture_discovery.py](file:///Users/liumingwei/01-project/12-liumw/26-ares-daily-intel/app/fixture_discovery.py)** [NEW]：利用 Grounding 获取候选赛程。
- **[app/priority_selector.py](file:///Users/liumingwei/01-project/12-liumw/26-ares-daily-intel/app/priority_selector.py)** [NEW]：基于多重策略的打分与去重。
- **[tests/test_discovery.py](file:///Users/liumingwei/01-project/12-liumw/26-ares-daily-intel/tests/test_discovery.py)** [NEW]：针对自动发现逻辑、优先级打分、HOLD 状态、SEARCH_SUMMARY 信心限制、GCS 拉取与本地 fallback 的单元测试。
- **[app/main.py](file:///Users/liumingwei/01-project/12-liumw/26-ares-daily-intel/app/main.py)** [MODIFY]：重构配置抓取和主控制流，整合外部配置载入流程。
- **[app/report.py](file:///Users/liumingwei/01-project/12-liumw/26-ares-daily-intel/app/report.py)** [MODIFY]：兼容处理空比赛结果，自动渲染为 `HOLD` 状态汇总。
- **[app/scan.py](file:///Users/liumingwei/01-project/12-liumw/26-ares-daily-intel/app/scan.py)** [MODIFY]：注入后置 `confidence` 强修剪。
- **[prompts/match_scan.md](file:///Users/liumingwei/01-project/12-liumw/26-ares-daily-intel/prompts/match_scan.md)** [MODIFY]：在铁律中新增 SEARCH_SUMMARY 信心受限说明。
- **[README.md](file:///Users/liumingwei/01-project/12-liumw/26-ares-daily-intel/README.md)** [MODIFY]：补充 Auto Fixture Discovery 运作原理与配置方式。

---

## 📈 后续运维与优化建议 (Future Suggestions)

1. **零重构配置调整 (Config Management)**：
   - 以后调整扫描范围、新增监控球队或联赛，您**完全不需要重新编译和部署镜像**！
   - 只需直接使用 gcloud storage 命令或者 GCP Cloud Console 覆盖更新 `gs://${GCS_BUCKET}/config/scan_config.yml` 即可。明早 8:00 定时任务启动时会自动抓取并套用最新监控范围。
2. **人工加塞分析 (Manual Injection)**：
   - 若要人工插队分析特定比赛，您可在 `gs://${GCS_BUCKET}/config/scan_config.yml` 文件的 `manual_matches` 数组中添加赛事即可（包含 league/home/away 三字段），无需改动 data。
