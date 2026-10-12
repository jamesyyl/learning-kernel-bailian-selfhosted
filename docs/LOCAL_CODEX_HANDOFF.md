# 本地 Codex 交接：Option 2 自架開發

更新：2026-10-12。這份文件是下一位在使用者 Windows 11／WSL2 Ubuntu 24.04 本機操作的 Codex 的起點。工作 repo：`jamesyyl/learning-kernel-bailian-selfhosted`，分支 `feat/option2-docker-shell`，草稿 [PR #1](https://github.com/jamesyyl/learning-kernel-bailian-selfhosted/pull/1)。先讀本文件、`README.md`、`docs/DOCKERIZATION_TODO.md`、程式及 SDK 的相關測試；以實際本機執行結果更新狀態。

## 使用者決定與目標

- 起點是使用者提供的 Option 2 單頁 HTML，已在 `web/index.html`。使用者喜歡部署版的功能，但單頁 HTML 與先前網站有些差異；先以這份 HTML 為基線，實測後逐步修正。保留其視覺與操作意圖。
- 新 repo 與原 `learning-kernel-bailian` 分離；SDK 以固定私有 submodule 引入。不要為了此任務更改原 repo 或 SDK 上游。
- 優先完成能在本機瀏覽器實際使用的數學 U1 出題、作答、原始觀察紀錄與再次讀取流程，然後再擴張。個人使用、家中區域網；加密、雲端／每日備份、登入、GitHub Actions、額外部署流程都不是當前門檻。不要因這些議題卡住功能開發。
- 不要假稱其他科目已有 LK 支援。未供應的活動可清楚標示尚未開放；不要用網頁內假進度、假判分替代 Runtime 結果。
- 不要求使用者每一步貼輸出給遠端代理。本地 Codex 可以直接在 WSL 執行、修正、驗證、提交分支；完成後簡短交代結果與剩餘事項。不要擅自合併 PR。

## 已有環境和已驗證事實

- 使用者工作目錄先前是 `/mnt/c/Users/jamesyyliao/learning-kernel-bailian-selfhosted`。先 `pwd`、`git status -sb`、`git branch --show-current`，保留任何本機未提交修改；確認目錄存在後再操作。
- Docker 29.8.2／Compose 5.5.1／Engine 29.8.2 在 WSL 可用。2026-10-12 實際執行 `docker compose up -d --build`，兩個服務 healthy；`/healthz`、`/api/ready` 均 HTTP 200，schema revision 4。
- `python3 -m unittest discover -s tests -v`：11 passed，0 skipped；`node --check web/app.js` 和 `git diff --check` 通過。
- 私有 `vendor/learning-kernel-sdk` 鎖在 `b63404173e39a37685e9914523ba3704ac1664ad`。最初 HTTPS submodule 因 GitHub 密碼登入失敗，後來使用者已成功初始化並跑完 SDK migration 測試。若目前未初始化，先檢查本機 Git 認證／submodule 狀態，不要請使用者貼 token。不要任意改 submodule 指向。
- Dockerfile.runtime 已加入 U1 Pack artifact 複製；`api/seed_u1.py` 已在使用者 Docker 實跑並證明可重複執行。首次及再次執行都安裝/確認 U1 0.3.1、啟用 `local-learner-001/home`、加入分類與整除兩個 Pool entry，並自查 Surface 200。
- Runtime HTTP host `api/app.py` 僅讓同源 Nginx 代理過來的 Surface 與 raw observations 通過；Pack 安裝／Pool admission 是 seed CLI 在容器內直接呼叫 SDK service，不要讓網頁呼叫管理 API。現有服務綁定配置已運作，無須為本任務重設加密方案。
- `web/index.html` 是約 2.5 MB 的原始單頁，含大量內嵌圖像；保留 Option 2 外觀，Runtime 接線放在 `web/app.js`、`web/app.css`。Math U1 已從真正 Surface 渲染並提交 raw observations；未接通科目、成長/家長摘要、專項/自訂模式標示尚未開放。
- `data/learning-kernel.sqlite3` 是持久資料；不可刪除、覆寫或用 `docker compose down -v`。資料從先前只建立 schema 開始，seed 之後可能有內容。先看 `git status`，不要清掉使用者資料。

## 已完成的本機驗收（2026-10-12）

- `docker compose up -d --build` 成功；`api.seed_u1` 首次與再次執行成功；Nginx 同源 Surface 回真正的 `learning-kernel.surface-ir@1`，含兩個 reportable observation points。
- 本機瀏覽器完成首頁 → Math U1 → 單選 → raw observation → 多選 → raw observation → Runtime complete。頁面只顯示 Runtime 中性保存訊息，不做本機判分；重啟 Runtime 後可重新載入活動。
- SQLite 中有 4 筆 observation、4 條 attempt chain、4 筆 evidence。這是完整兩步練習加上驗證過程中的兩筆部分練習紀錄；資料已跨 Runtime restart 保留，**不要清除**。
- 已確認英文等未接通科目、成長摘要及家長摘要都顯示尚未開放；專項/自訂入口停用。

## 後續工作

1. 擴充 Math U1 題目覆蓋前，沿用 pinned SDK Surface 和 observation 契約；完成後仍需逐步在本機瀏覽器驗收。
2. 其他科目、學習摘要、專項/自訂模式尚未接通，繼續保持尚未開放狀態，不顯示推算進度。
3. FnOS/NAS、區網存取邊界及備份是獨立後續項目，不阻擋本機數學 U1 使用。
4. 本次程式與文件已在本機 commit；WSL `git push` 因缺少 GitHub Username/write 認證而未完成，draft PR #1 的遠端 head 尚未更新。認證可用後推送到 `feat/option2-docker-shell` 並確認 PR head；不要 merge，也不要主動觸發 GitHub Actions。

## 重要檔案與參考

- `web/index.html`：指定外殼基線；`Dockerfile`、`nginx.conf`、`docker/render-nginx-config.sh`：web 與 API 同源代理。
- `compose.yaml`、`Dockerfile.runtime`、`api/app.py`、`api/sqlite_d1.py`、`api/migrations.py`、`api/seed_u1.py`。
- `vendor/learning-kernel-sdk/tests/test_runtime_vnext_d1_pack_control.py` 中 `_validated_classification_pool_entry`、`_validated_divisibility_screen_pool_entry`、`_surface_request` 及 compound Surface 測試；`apps/runtime_vnext/worker/runtime_http.py` 看實際路由與 payload。
- `README.md` 與 `docs/DOCKERIZATION_TODO.md` 是公開進度；更新時區分「程式已寫」與「本機已驗證」。

## 目前成功標準

本機數學 U1 的 Docker、seed、Surface、兩步 raw-observation 瀏覽器流程、SQLite 持久化與 11 項 unittest 都已通過。其他科目、成長/家長摘要、專項/自訂模式、FnOS/NAS 與備份未完成，已如實標示。
