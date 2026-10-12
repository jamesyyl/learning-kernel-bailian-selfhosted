# 百煉自架 Docker TODO

## 起點

- UI 基線：使用收到的 `bailian-option-2-subject-cards.html`，保存在 `web/index.html`；功能修改都從這份開始。
- 新 repo：`jamesyyl/learning-kernel-bailian-selfhosted`，與原百煉獨立。
- 工作分支：`feat/option2-docker-shell`。
- 草稿 PR：[PR #1](https://github.com/jamesyyl/learning-kernel-bailian-selfhosted/pull/1)。
- 原 `learning-kernel-bailian` 與 canonical `learning-kernel-sdk` 沒有被修改。

## 順序與狀態

| 順序 | 工作 | 狀態 | 完成條件／驗收紀錄 |
|---|---|---|---|
| 0 | 將指定 HTML 放進新 repo，保留原檔 | 完成 | HTML 原樣保留；後續功能修改以它為基線。 |
| 1 | 建立 Nginx＋Python Runtime 的 Compose 底座 | 完成 | 同源代理；Python 載入固定 SDK；SQLite 可另設資料目錄；瀏覽器不能呼叫 Pack 管理或 trusted returns。 |
| 2 | Windows 11＋WSL2 建置和 Runtime 驗收 | 本機通過（2026-10-12） | Docker 29.8.2、Compose 5.5.1；兩個映像成功建置，web/runtime containers healthy；`/healthz` 回 `ok`；Runtime restart 後 readiness 為 schema revision 4，`data/learning-kernel.sqlite3` 存在（4096 bytes）；完整 unittest 11 項全通過、0 skipped；瀏覽器成功載入 `http://localhost:8080/#today`，首頁畫面確認正常。 |
| 3 | 準備 U1 Pack 與合法 Activity Pool 供應 | 進行中 | 先使用 SDK 現有、經測試的 U1 範例，安裝確切 Pack release 並匯入通過驗證的 Pool Entry，跑通本機數學活動；完整題目覆蓋後續擴充。 |
| 4 | 把 Option 2 練習頁接到 LK | 未完成，依賴 3 | 用 Runtime Surface IR 顯示活動；只送 raw observation；不在瀏覽器判分。LK 尚未供應的科目如實顯示未開放；保留三種模式與 Learning Journey，但不造假進度。 |
| 5 | NAS 持久化與存取邊界 | 未完成 | SQLite 放在 repo 外的 FnOS 資料夾；先只供家中網路／既有 Tailscale；不做路由器埠轉發。此版沒有帳號登入。 |
| 6 | 簡單 SQLite 備份（後置） | 暫緩，不阻擋開發 | 先完成 LK 活動與作答流程；有正式學習資料後，再加入本機資料庫快照和還原。 |
| 7 | FnOS/N100 驗收 | 未完成，依賴 2–5 | linux/amd64 冷啟、重啟、資料保存、raw observation 通過；備份後續補上。 |

## 已驗證的基礎

- SQLite adapter 的 first/all/run/batch 測試通過，批次失敗會 rollback。
- migration runner 有 checksum、冪等和失敗 rollback 測試。
- SDK 正式 `0001`–`0004` migration 已在 SQLite 3.53.1 實際套用至 schema revision 4，重跑不會重複套用。
- Windows 11＋WSL2 完整 unittest：11 項通過、0 skipped；已包含 pinned SDK migration 測試。
- Windows 11＋WSL2 實際 Docker Compose build、Runtime/web health、readiness 與 restart 後資料檔檢查通過。
- 使用者提供的瀏覽器截圖確認 Option 2 首頁可在 `localhost:8080/#today` 顯示；按鈕與導覽流程尚未逐項驗收。

## 目前不可用的部分

Option 2 仍是示範頁，沒有呼叫 Runtime，也不保存學習資料。首頁畫面已確認可載入，但互動流程尚未逐項驗收。尚未安裝 Pack，且沒有已驗證的 Activity Pool Entry；即使 Runtime 容器成功啟動，也不能宣稱已有真實練習可用。FnOS 驗收仍待完成；備份後置。PR 維持 draft，不供孩子作正式學習使用。
