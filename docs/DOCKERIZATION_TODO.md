# 百煉自架 Docker TODO

## 起點

- UI 基線：使用收到的 `bailian-option-2-subject-cards.html`，保存在 `web/index.html`；功能修改都從這份開始。
- 新 repo：`jamesyyl/learning-kernel-bailian-selfhosted`，與原百煉獨立。
- 工作分支：`feat/option2-docker-shell`。
- PR #1：[Pull Request #1](https://github.com/jamesyyl/learning-kernel-bailian-selfhosted/pull/1)。
- 原 `learning-kernel-bailian` 與 canonical `learning-kernel-sdk` 沒有被修改。

## 順序與狀態

| 順序 | 工作 | 狀態 | 完成條件／驗收紀錄 |
|---|---|---|---|
| 0 | 將指定 HTML 放進新 repo，保留原檔 | 完成 | HTML 原樣保留；後續功能修改以它為基線。 |
| 1 | 建立 Nginx＋Python Runtime 的 Compose 底座 | 完成 | 同源代理；Python 載入固定 SDK；SQLite 可另設資料目錄；瀏覽器不能呼叫 Pack 管理或 trusted returns。 |
| 2 | Windows 11＋WSL2 建置和 Runtime 驗收 | 本機通過（2026-10-12） | Docker 29.8.2、Compose 5.5.1；兩個映像成功建置，web/runtime containers healthy；`/healthz` 回 `ok`；Runtime restart 後 readiness 為 schema revision 4，`data/learning-kernel.sqlite3` 存在（4096 bytes）；完整 unittest 11 項全通過、0 skipped；首頁基礎載入確認。完整學習流程記錄於第 4 項。 |
| 3 | 準備 U1 Pack 與合法 Activity Pool 供應 | 本機通過（2026-10-12） | WSL Docker build 後，`docker compose exec runtime python -m api.seed_u1` 首次及再次執行皆成功；同源 Surface HTTP 200、schema `learning-kernel.surface-ir@1`、Pack 0.3.1。 |
| 4 | 把 Option 2 練習頁接到 LK | 程式已寫；本機瀏覽器通過（2026-10-12） | 首頁選數學 U1、載入真實 Surface、完成單選及多選兩步、每步收到 Runtime 保存回覆；頁面只送 raw observation，沒有瀏覽器判分。未接通科目與學習摘要標示尚未開放。 |
| 4.5 | LK 判斷結果與孩子可理解的回饋 | PR #2 本機驗收通過，Draft PR 等待體驗 | pinned LK SDK 是 correct/incorrect/indeterminate 唯一判斷來源。百煉只呈現安全 verdict/message/action；答錯留在原題並可重試，correct/indeterminate 依 Runtime directive；前端不取得標準答案或判分規則。exact same-request replay 使用 SQLite response cache。 |
| 5 | NAS 持久化與存取邊界 | 未驗證（不阻擋本機使用） | 本機 bind mount 的 SQLite 已保存 observation/attempt/evidence，Runtime 重啟後計數不變；FnOS/NAS 路徑、區網存取與正式部署仍待另行驗收。此版沒有帳號登入。 |
| 6 | 簡單 SQLite 備份（後置） | 暫緩，不阻擋開發 | 先完成 LK 活動與作答流程；有正式學習資料後，再加入本機資料庫快照和還原。 |
| 7 | FnOS/N100 驗收 | 未完成，依賴 2–5 | linux/amd64 冷啟、重啟、資料保存、raw observation 通過；備份後續補上。 |

## 已驗證的基礎

- SQLite adapter 的 first/all/run/batch 測試通過，批次失敗會 rollback。
- migration runner 有 checksum、冪等和失敗 rollback 測試。
- SDK 正式 `0001`–`0004` migration 已在 SQLite 3.53.1 實際套用至 schema revision 4，重跑不會重複套用。
- Windows 11＋WSL2 完整 unittest：11 項通過、0 skipped；已包含 pinned SDK migration 測試。
- Windows 11＋WSL2 實際 Docker Compose build、Runtime/web health、readiness 與 restart 後資料檔檢查通過。
- 使用者提供的瀏覽器截圖確認 Option 2 首頁可在 `localhost:8080/#today` 顯示；按鈕與導覽流程尚未逐項驗收。
- 2026-10-12 在 WSL Docker 首次和重複執行 Math U1 seed 均成功；`/healthz`、`/api/ready` HTTP 200，readiness schema revision 4。
- 經 `http://localhost:8080` 的 Nginx 同源代理取得真正 Surface IR，schema 為 `learning-kernel.surface-ir@1`，包含兩個 reportable observation points。
- 本機瀏覽器完成 U1 的 2 個觀察步驟；單選提示及多選作答按 SDK 契約提交 raw observation，Runtime 回覆 advance/complete 與中性保存訊息。
- 最新驗收時 SQLite 共保存 14 筆 observation、14 條 attempt chain、14 筆 trusted evidence；兩步瀏覽器流程收到 Runtime advance/complete，Runtime 重啟後三類資料筆數均維持 14；未清除 SQLite。
- 專案 unittest：11 passed、0 skipped；`node --check web/app.js` 與 `git diff --check` 通過。
- Python 靜態編譯檢查 `python3 -m compileall -q api tests` 通過；Docker Compose build/up、seed 首次及重複執行、兩服務 healthcheck 均通過。

## PR #2 本機驗收（2026-10-12）

- 以 Windows 11 + Docker Desktop/WSL2 在獨立 Compose project `lk-pr2-20261012` 驗收，前端 URL 為 `http://localhost:8081`；測試資料位於被 Git 忽略的 `data/pr2-feedback-20261012/learning-kernel.sqlite3`，既有 `data/learning-kernel.sqlite3` 未動。
- Docker Compose 兩服務 healthy；`/healthz` 與 `/api/ready` HTTP 200，schema revision 4；Math U1 seed 首次及重複執行成功。
- 完整 unittest：17 passed；`node --check web/app.js`、Python `compileall`、Ruff 與 `git diff --check` 通過。固定 SDK evaluator 實際回傳 correct、incorrect、indeterminate；未修改或更新 SDK submodule。
- 真實瀏覽器從 Option 2 首頁進入數學 U1，單選錯誤後留在原題、重試答對；多選連錯兩次後第三次答對並完成。UI 顯示 LK verdict 與 Runtime 指令，未在前端判分。
- 兩輪瀏覽器驗收後，隔離 SQLite 共保存 10 筆 observation、10 條 attempt chain、10 筆 trusted evidence 與 10 筆 exact-request response-cache 記錄。每輪 attempt ordinal/count/retryCount 依序為 `1/1/0, 2/2/1`（單選）及 `1/1/0, 2/2/1, 3/3/2`（多選）。Runtime 重啟後 readiness 與資料可讀；相同 HTTP 請求 replay 測試回傳相同 response，對應資料筆數不變。
- NAS 正式部署與備份／還原尚未驗收；其他科目與模式仍顯示未開放。PR #2 未合併，等使用者體驗後決定。

## 目前不可用的部分

PR #1 已合併。PR #2 的 LK Trusted Evaluation Feedback + Retry 已完成本機驗收，Draft PR 等待使用者體驗；PR #2 尚未合併。其他科目、成長與家長摘要、專項/自訂模式尚未接 Runtime，頁面明確標為尚未開放。更廣的 U1 題目覆蓋、FnOS/NAS 正式部署、區網存取邊界與備份仍未完成。
