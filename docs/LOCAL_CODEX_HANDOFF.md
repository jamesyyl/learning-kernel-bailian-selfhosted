# 本地 Codex 交接：Option 2 自架開發

更新：2026-10-12。這份文件記錄 PR #1 最終驗收與後續交接。工作 repo：`jamesyyl/learning-kernel-bailian-selfhosted`，分支 `feat/option2-docker-shell`。目前 main／feature refs 的 commit Author/Committer 已改用 GitHub noreply；改寫前後 tree 與 PR diff 相同。不過 GitHub Commit API 仍可讀取改寫前的 main 與 feature SHA，回傳舊 metadata，因此 PR #1 仍為 Draft、未合併。開始新工作前先 fetch 並查看 GitHub PR 的最新狀態。

## 使用者決定與目標

- 起點是使用者提供的 Option 2 單頁 HTML，已在 `web/index.html`。使用者喜歡部署版的功能，但單頁 HTML 與先前網站有些差異；先以這份 HTML 為基線，實測後逐步修正。保留其視覺與操作意圖。
- 新 repo 與原 `learning-kernel-bailian` 分離；SDK 以固定私有 submodule 引入。不要為了此任務更改原 repo 或 SDK 上游。
- 優先完成能在本機瀏覽器實際使用的數學 U1 出題、作答、原始觀察紀錄與再次讀取流程，然後再擴張。個人使用、家中區域網；加密、雲端／每日備份、登入、GitHub Actions、額外部署流程都不是當前門檻。不要因這些議題卡住功能開發。
- 不要假稱其他科目已有 LK 支援。未供應的活動可清楚標示尚未開放；不要用網頁內假進度、假判分替代 Runtime 結果。
- 不要求使用者每一步貼輸出給遠端代理。本地 Codex 可以直接在 WSL 執行、修正與驗證。PR #1 的提交身分隱私修正已依使用者授權處理；main 與 feature branch 的程式碼樹保持一致，原提交訊息、名稱、時間戳及祖先關係保留。

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
- 最新驗收後 SQLite 中共有 14 筆 observation、14 條 attempt chain、14 筆 trusted evidence。Runtime restart 後 schema revision 仍為 4，三類資料筆數皆為 14；**不要清除**。
- 已確認英文等未接通科目、成長摘要及家長摘要都顯示尚未開放；專項/自訂入口停用。
- Windows 11＋WSL2 Ubuntu-24.04：Compose build/up、Math U1 seed 首次及重複執行、`/healthz`、`/api/ready`、Python compileall、Node check、`git diff --check` 與完整 unittest 11 項均通過；兩服務 healthcheck healthy。PR 無已回報的必要 GitHub checks。
- GitHub 原本只有 main 與 feature branch、PR #1 一筆 open PR、0 筆 deployment，沒有 Actions workflow；本次只更新這兩條分支。
- 隱私殘留：舊 main SHA `8b1555205e7b` 與舊 feature head `f2acdcdcd25a` 仍可由 GitHub Commit API 讀取，回傳非 noreply metadata；未宣稱舊提交或外部快取已徹底清除。依本次條件不改 Ready、不合併。

## 後續工作

1. 暫停 PR #1 merge；先確認 GitHub 對舊 SHA 可達物件的清理／保留方式，再重新檢查 API 可達性、PR diff 與 mergeability。不得宣稱舊外部快取已清除。
2. 隱私風險解除並合併 PR #1 後，下一階段才是 PR #2「LK Trusted Evaluation Feedback + Retry」：LK 判斷正誤，百煉只呈現結果；錯題可再次挑戰；保留正確 Attempt Chain/Evidence；前端不接觸答案或判分規則。本次未建立或開始 PR #2。
3. 其他科目、學習摘要、專項/自訂模式保持尚未開放；FnOS/NAS 部署、存取邊界與 SQLite 備份仍未驗收。

## 重要檔案與參考

- `web/index.html`：指定外殼基線；`Dockerfile`、`nginx.conf`、`docker/render-nginx-config.sh`：web 與 API 同源代理。
- `compose.yaml`、`Dockerfile.runtime`、`api/app.py`、`api/sqlite_d1.py`、`api/migrations.py`、`api/seed_u1.py`。
- `vendor/learning-kernel-sdk/tests/test_runtime_vnext_d1_pack_control.py` 中 `_validated_classification_pool_entry`、`_validated_divisibility_screen_pool_entry`、`_surface_request` 及 compound Surface 測試；`apps/runtime_vnext/worker/runtime_http.py` 看實際路由與 payload。
- `README.md` 與 `docs/DOCKERIZATION_TODO.md` 是公開進度；更新時區分「程式已寫」與「本機已驗證」。

## 目前成功標準

本機數學 U1 的 Docker、seed、Surface、兩步 raw-observation 瀏覽器流程、SQLite 持久化與 11 項 unittest 都已通過。PR #1 目前 refs 的提交身分已修正，但舊 SHA 仍由 GitHub API 提供非 noreply metadata，故仍 BLOCKED；其他科目、成長/家長摘要、專項/自訂模式、FnOS/NAS 與備份未完成，已如實標示。
