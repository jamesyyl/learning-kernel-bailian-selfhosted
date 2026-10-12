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
- Docker 29.8.2／Compose 5.5.1／Engine 29.8.2 在 WSL 可用；原兩個服務已 build 且 healthy。`http://localhost:8080/healthz` 回 `ok`；`/api/ready` 回 `ready:true`、schema revision 4。瀏覽器 `/#today` 首頁載入正常。
- `python3 -m unittest discover -s tests -v` 在使用者本機為 11 passed，0 skipped（在新增 U1 seed 之前）。
- 私有 `vendor/learning-kernel-sdk` 鎖在 `b63404173e39a37685e9914523ba3704ac1664ad`。最初 HTTPS submodule 因 GitHub 密碼登入失敗，後來使用者已成功初始化並跑完 SDK migration 測試。若目前未初始化，先檢查本機 Git 認證／submodule 狀態，不要請使用者貼 token。不要任意改 submodule 指向。
- Dockerfile.runtime 已加入 U1 Pack artifact 複製；`api/seed_u1.py` 是最近加入的本機種子命令，**只做了 Python 語法檢查，尚未在使用者 Docker 實跑**。它按 SDK `tests/test_runtime_vnext_d1_pack_control.py` 的驗證樣本安裝 U1 0.3.1、啟用 `local-learner-001/home`、加入分類與整除兩個 Pool entry，最後檢查 Surface 200。若失敗，就用 SDK 測試及實際錯誤修正，不要因文件敘述當成已通過。
- Runtime HTTP host `api/app.py` 僅讓同源 Nginx 代理過來的 Surface 與 raw observations 通過；Pack 安裝／Pool admission 是 seed CLI 在容器內直接呼叫 SDK service，不要讓網頁呼叫管理 API。現有服務綁定配置已運作，無須為本任務重設加密方案。
- `web/index.html` 是約 2.5 MB 的原始單頁，含大量內嵌圖像；現有 JS 的科目與出題／提交邏輯是展示資料。修改時盡量保留基線，可選擇獨立 JS 模組並在 HTML 引入。先讀實際結構，再決定最小改動。
- `data/learning-kernel.sqlite3` 是持久資料；不可刪除、覆寫或用 `docker compose down -v`。資料從先前只建立 schema 開始，seed 之後可能有內容。先看 `git status`，不要清掉使用者資料。

## 建議執行順序（請自主推進）

1. 在既有 checkout 更新此分支（先確認無未提交修改），`git submodule status`；必要時 `git submodule update --init --recursive`。檢查 `.env` 已設，不輸出密鑰。
2. `docker compose up -d --build`，接著 `docker compose exec runtime python -m api.seed_u1`。若有 traceback，依 pinned SDK 的 Pack control tests 修正 seed；重跑驗證冪等性，至少首次與第二次都成功。注意 SQLite 已存在，保留資料。
3. 確認同源 `POST /api/learners/local-learner-001/environments/home/packs/org.learning-kernel.tw-math-g6-u1/surface` 能從 Nginx 返回真正的 `learning-kernel.surface-ir@1`。Surface request 可參考 `api/seed_u1.py` 的 `currentContext` 與 SDK 測試 `_surface_request`。檢查回傳 payload 的實際 schema、活動步驟和 lineage。
4. 把 Option 2 練習互動接上真實 Surface：數學 U1 路徑載入，渲染支援的步驟與選項，完成作答；使用正式 raw observation 端點與 SDK 契約記錄提交。不要把 trusted evaluation 或正確答案放入瀏覽器。若某些 UI 功能無 Runtime 契約，清楚顯示尚未開放，優先讓一條完整練習路徑可用。
5. 用本機瀏覽器實際點過首頁→數學 U1→出題→作答→提交→重新整理／重新進入，核對 Runtime／SQLite 紀錄。測試真正風險點，修復錯誤；更新 README/TODO 的驗收事實。若有用戶資料，使用可辨識的測試 learner 或記錄測試行為，不要為測試刪正式資料。
6. 將程式及文件 commit/push 到本分支與草稿 PR #1。不要 merge、不要觸發 Actions。若 GitHub 認證阻擋 push，先完成本機可執行成果，說明具體阻擋及待推 commit。

## 重要檔案與參考

- `web/index.html`：指定外殼基線；`Dockerfile`、`nginx.conf`、`docker/render-nginx-config.sh`：web 與 API 同源代理。
- `compose.yaml`、`Dockerfile.runtime`、`api/app.py`、`api/sqlite_d1.py`、`api/migrations.py`、`api/seed_u1.py`。
- `vendor/learning-kernel-sdk/tests/test_runtime_vnext_d1_pack_control.py` 中 `_validated_classification_pool_entry`、`_validated_divisibility_screen_pool_entry`、`_surface_request` 及 compound Surface 測試；`apps/runtime_vnext/worker/runtime_http.py` 看實際路由與 payload。
- `README.md` 與 `docs/DOCKERIZATION_TODO.md` 是公開進度；更新時區分「程式已寫」與「本機已驗證」。

## 目前成功標準

本地 Docker 可重建；seed 首次和重跑成功；`/healthz`、`/api/ready` 正常；網頁透過同源 API 顯示一題真正來自 U1 Pack 的數學活動並可提交 raw observation；重開頁面仍能確認 Runtime 紀錄存在；既有 11 項測試與必要的新整合檢查通過。未完成的 UI／科目／FnOS 項目如實列出，先交付這條可用的垂直流程。
