# 百煉／LK 自建版：Docker＋SQLite 驗收邊界

2026-10-15。目標是回到已確認的 **NAS／Docker＋Python Runtime＋SQLite** 主線，不再以 Cloudflare 部署結果決定百煉能否驗收。

## 真正的正式執行鏈

```text
百煉 Web (Nginx)
     ↓ same-origin
Python LK Runtime
     ↓ canonical LK decisions / Evidence / trusted evaluation
既有 D1-shaped SQL 存取介面
     ↓ api/sqlite_d1.py（本機 SQLite adapter，沒有網路 D1）
/data/learning-kernel.sqlite3（持久化）
```

`d1_*` 是現階段沿用的 Python 模組／介面名稱，不代表 Docker 版會連 Cloudflare。立即刪改這些模組會牽動可信判分、證據與已發活動 lineage，不在本階段做。

## Gate 1｜離線、必須全綠

從本 repo 根目錄、在 Python 3.12 環境執行：

```sh
python scripts/run_selfhost_gate.py
```

可個別定位：
```sh
python scripts/run_selfhost_gate.py --scope selfhost
python scripts/run_selfhost_gate.py --scope sdk
```

此 Gate **明確列出**百煉自架測試與 SDK 的可攜式核心測試：
- 自架：SQLite transaction rollback／foreign-key／migration checksum，Pack bootstrap／啟用、17 Places、可信作答、完整 U1 供題、五步整組補題、Evidence 驅動複習、資料與學習者隔離、API 權限邊界。
- LK 共用：Pool 驗證／不可繞過、Surface 組合、可信判分、服務簽章安全、複習輪替、U1 決定性產生與情境。
- 任何必要測試檔消失、根 repo 新增未分類測試、pytest 有失敗、錯誤或 **skipped**，都不准標記 PASS。
- 執行結果輸出 `bailian.selfhost-acceptance@1` JSON；此 Gate 不呼叫 GitHub Actions、不啟動 Docker、不變動學習資料、不需 Cloudflare。

這不是「刪除 D1 測試」：**SQLite 需要的資料完整性保護已用本機 SQLite 直接測試，SDK 的可攜式共用語意另外驗證。**

## Gate 2｜隔離 Docker Live，必須全綠

只有在明確建立**新的**隔離環境後，才使用：

```sh
python scripts/run_selfhost_gate.py \
  --live-url http://127.0.0.1:18085 \
  --sqlite-db /path/to/isolated/learning-kernel.sqlite3 \
  --report /path/to/acceptance-result.json
```

此檢查只讀 `/api/ready`、`/api/learning-map` 與 SQLite：
- HTTP ready 真實可用，學習地圖至少 17 Places；
- SQLite `PRAGMA quick_check=ok`，`foreign_key_check` 無違反；
- schema family 必須是 `learning-kernel-runtime-vnext`、revision `4`；
- 四筆已記錄的 migration 需在正式 DB 中存在；
- 禁止為了跑檢查而對 8080 或 18084 原有 SQLite seed、delete、upgrade、寫入或重新掛載。

此 Gate 只驗證 read-only live consistency；**它不代表測過瀏覽器互動**。

## Gate 3｜孩子的真實體驗，必須獨立完成

在新的隔離 Docker URL 上以真實 Chrome 驗收，並保留截圖與結果：
1. 學習旅程 U1：5 Regions、17 Places、各 Task Family 可載題；
2. 問題的題幹與答案格式符合台灣國小用語；一題主要操作不必捲動；
3. 答錯可重試，瀏覽器不判分；五步情境沿用同一題的數學脈絡；
4. 新題優先、用盡後到期複習，重新作答保留 Observation、Attempt Chain 與 Evidence；
5. 無新題也無到期複習時，顯示孩子看得懂的引導，隱藏作答與不適用的陪練提示；
6. 桌面與 390×844 手機尺寸；不得有水平溢出。

先前已在隔離 18085 完成複習輪替的 SQLite E2E 與 Chrome 三場景測試，見 `docs/evidence/u1-spaced-review-uat-2026-10-15.md`。每次發版仍需對待驗版本重新記錄；不可把舊截圖冒充最新版本。

## 原 SDK 全量 28 個失敗的去向

SDK 複習輪替分支的完整 Python 3.12 測試基線是 **1,766 passed／28 failed**。回到 0.3.7 複習輪替前基線，28 個相同測試失敗全部重現；不能說是新輪替造成，但也**不能稱它們全部無害**。

| 群組 | 數量 | 處理原則 |
| --- | ---: | --- |
| Knowledge Pack／教材與 preview 舊斷言 | 14 | 隸屬 SDK 上游相容性／版本基線債務；另列修復。不能因 Docker Gate 通過就聲稱 SDK 全量綠。 |
| `test_runtime_vnext_d1_migrations.py` | 2 | revision 3 舊斷言與目前 revision 4 不符；schema、不可變 migration、rollback 必須由自架測試保留，舊測試另修。 |
| `test_runtime_vnext_d1_pack_control.py` | 5 | 大多屬共用 Pack lifecycle、Evidence、projection 安全語意；**不能單純刪除**，應查明是舊 fixture／失效預期還是實際 bug，與真實 SQLite E2E 對照。 |
| `test_runtime_vnext_worker.py` | 7 | 包含 Wrangler／Cloudflare deployment identity、D1 fake readiness，亦包含通用 ready fail-closed；平台專屬斷言另列，SQLite readiness 仍須在自架 Gate 實測。 |

重點：**不把含有 D1 名稱的共用安全邏輯排除；只把 CF 平台環境假設從自架版的發版條件分離。**

## 不做與待做

- 不改 Pack 0.3.7 的學習語意、不重寫 Python 的可信判分與 Evidence。
- 不在這階段刪 `d1_*`、不把 SQLite 改為另一個資料庫。
- 不觸發 GitHub Actions、不使用 Codex、不合併 PR3／SDK PR335，不改既有 8080／18084。
- 待本次 Gate 1／2／3 合格後，再獨立規劃將 `d1_*` 改成通用持久化介面；須附遷移前後觀察／Evidence／Pack lifecycle 完整等價驗證，不能只為名稱美觀而重構。
