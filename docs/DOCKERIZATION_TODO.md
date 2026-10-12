# 百煉自架 Docker TODO

## 起點

- UI 基線：使用收到的 `bailian-option-2-subject-cards.html`，保存在 `web/index.html`；功能修改都從這份開始。
- 新 repo：`jamesyyl/learning-kernel-bailian-selfhosted`，與原百煉獨立。
- 工作分支：`feat/option2-docker-shell`。
- 草稿 PR：[PR #1](https://github.com/jamesyyl/learning-kernel-bailian-selfhosted/pull/1)。
- 原 `learning-kernel-bailian` 與 canonical `learning-kernel-sdk` 沒有被修改。

## 順序與狀態

| 順序 | 工作 | 狀態 | 完成條件／依賴 |
|---|---|---|---|
| 0 | 將指定 HTML 放進新 repo，保留原檔 | 完成 | HTML 原樣保留；後續功能修改以它為基線。 |
| 1 | 建立 Nginx＋Python Runtime 的 Compose 底座 | 程式已提交，待 Docker 實跑 | 同源代理；Python 載入固定 SDK；SQLite 可另設資料目錄；瀏覽器不能呼叫 Pack 管理或 trusted returns。 |
| 2 | Windows 11＋WSL2 建置和 Runtime 驗收 | 待做 | 私有 SDK submodule 可讀；通過 `docker compose config`、amd64 build、readiness、重啟後 SQLite 資料仍在。開發環境沒有 Docker。 |
| 3 | 準備 U1 Pack 與合法 Activity Pool 供應 | 未完成，等 SDK 供應流程 | 安裝確切 Pack release，匯入同一 release/digest 且通過驗證的 Pool Entry。SDK 的 U1 Activity Pool Gate B 尚未封板；不可塞入未驗證題目或測試資料冒充通過。 |
| 4 | 把 Option 2 練習頁接到 LK | 未完成，依賴 2、3 | 用 Runtime Surface IR 顯示活動；只送 raw observation；不在瀏覽器判分。LK 尚未供應的科目如實顯示未開放；保留三種模式與 Learning Journey，但不造假進度。 |
| 5 | NAS 持久化與存取邊界 | 未完成 | SQLite 放在 repo 外的 FnOS 資料夾；先只供家中網路／既有 Tailscale；不做路由器埠轉發。此版沒有帳號登入。 |
| 6 | 每日加密備份至 Google Drive | 未完成 | 先產生一致性快照，再加密上傳並設定輪替；實際還原資料庫、驗證 schema。密鑰與 OAuth 設定不進 repo。 |
| 7 | FnOS/N100 驗收 | 未完成，依賴 2–6 | linux/amd64 冷啟、重啟、資料保存、raw observation、備份及還原全通過，才算自架可用。 |

## 已驗證的基礎

- SQLite adapter 的 first/all/run/batch 測試通過，批次失敗會 rollback。
- migration runner 有 checksum、冪等和失敗 rollback 測試。
- SDK 正式 `0001`–`0004` migration 曾在 SQLite 3.53.1 實際套用至 schema revision 4，重跑不會重複套用。
- 本地測試：10 項通過、1 項因本環境未初始化私有 submodule 而略過；Python compileall、Compose YAML 結構及 shell 語法檢查通過。

## 目前不可用的部分

Option 2 仍是示範頁，沒有呼叫 Runtime，也不保存學習資料。尚未安裝 Pack，且沒有已驗證的 Activity Pool Entry；即使 Runtime 容器成功啟動，也不能宣稱已有真實練習可用。Docker image 尚未建置，NAS 備份亦未實作。PR 維持 draft，不供孩子作正式學習使用。
