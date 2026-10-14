# 本地 Codex 交接：Option 2 自架開發

更新：2026-10-14。PR #1 merge SHA `fbab8710315ba3cc6cb7289503ea4f37e3ac703c`、PR #2 均已合併。Issue #4 的 Math U1 全 Map、Pool/Generation、Surface 作答能力已在隔離副本實作並完成 Docker/SQLite Runtime 與真實瀏覽器驗收。Root PR #3 保持 Draft、SDK PR #335 保持未合併；使用者原始 checkout/WIP、既有 SQLite 與 8080/8081/8084 Compose 專案均未碰觸。驗收使用新建的暫存 Compose project、loopback 18084 與獨立 SQLite。

## U1-1 live supply failure follow-up (2026-10-14)

- Exact 18084 failure was HTTP 503 activity_supply_unavailable for U1-1 direct-prime-composite-classification. Read-only SQLite evidence: Pool 260, exact Family 10 entries all issued by the learner, while other U1-1 Families still had unissued candidates.
- Root cause: generator covered 2–11 despite Pack verifier domain 2–19; Runtime correctly failed closed. SDK now produces 18 direct-classification candidates and excludes previously issued Activity IDs scoped to learner/environment/exact release, including pending unanswered Surface bindings.
- Independent Docker refiller uses canonical generation, independent verification, and Runtime admission. It added eight candidates, taking Pool 260→268 without reseeding on page load or Runtime restart. Pending Surface is resumed from sessionStorage without storing response or verdict.
- Clone browser reproduced error then verified entry, wrong-answer retry, Journey return/reload, Runtime restart, and SQLite persistence. After restart integrity was ok and pending prompt 15 resumed.
- Actual 18084: Runtime healthy, refiller running, Web healthy, readiness schema rev4. Pool 268/direct Family 18. Chromium entered U1-1 from Journey, loaded prompt 12, and showed Runtime retry after a wrong answer. Original user U1-5 tab was left untouched.
- Regression results: Root 14 passed + 3 subtests; SDK 89 passed. Ruff lint, changed-file format, compileall, Node syntax, and diff check passed. Whole-directory Ruff format check reports existing drift in unchanged api/sqlite_d1.py. Cloudflare/Workers/Pages/Access/WAF/D1 tests were not run.
- SDK head bdc2c3c20a0ed62554e95223aef2b4f1566193df (PR #335 Open); Root head ab2d7cd05190a787378525118483336260ef5809 (PR #3 Open/Draft). No merge. Full Pack acceptance is not reasserted by this narrow follow-up.
- Detailed evidence: docs/evidence/math-u1-runtime-supply-recovery-2026-10-14.json. Original SQLite backup SHA-256: 650ce819c92e3815f85c7143e39bb0e0dec63052044a68f68ff9ff148aca565c.

## Issue #4 最新驗收（2026-10-14）

- Pack 0.3.4：5 Regions、17 Places、37 Roads、24 Capabilities、26 Task Families、26 Generator Requirements；保留 7 個 reviewed Fixed Activities／16 個 observation points，新增 26 個 Family 單點錨點，合計 33 Activities／42 points。0.3.2 artifact 保留，digest `sha256:5feac5c62f0510ef2ecc9851e06d15e879e6e5095838771b35543b534364fed3` 未變。
- 26 個 exact-Family deterministic generator registrations 各產生 10 個不同題目。260/260 候選均通過獨立 verifier、Pack validators 與 Runtime Pool admission。generator requirement 不單獨算作已實作供應。
- Root 全測試在最後 seed 修正前 19 passed；修正後 seed lineage/reuse regression 3 passed，Docker fresh／既用 SQLite 重跑亦通過。Python compileall、改動檔 Ruff、`node --check web/app.js` 通過。SDK focused regression 181 passed、2 個舊 D1 knowledge-read 測試排除；同兩測試在乾淨 SDK PR #335 基線也失敗。另 7 個 Worker readiness 基線測試亦在乾淨基線失敗；此工作未改 Cloudflare/D1 readiness 實作。未手動啟動 GitHub Actions。
- 同一 learner 的 Runtime/隔離 SQLite 驗收連續完成 10 個不同 Activity ID／題目；17/17 Places 有 canonical Surface/Evidence；26/26 Map Family exploration 有 Surface/Evidence。證據：`docs/evidence/math-u1-supply-matrix-final-0.3.4.json`、`docs/evidence/math-u1-10-activity-trace.json`。
- Docker-backed Codex Chromium 顯示全部 5 Regions／17 Places／37 Roads；逐一點選 17 Places 均與詳情標題相符，點選 Road 可導向合法相鄰 Place。連續十題由 Runtime 判對；真實瀏覽器核對單選、多選、數值與因數樹文字作答，答錯留在同一活動重試。舊 Python host browser report 另保留 multi-classification 與 structured-factorization 覆蓋。
- Docker 29.8.2／Compose 5.5.1；隔離 Compose project `lk-u1-acceptance-20261014`、`http://127.0.0.1:18084`、暫存 bind-mount SQLite。兩容器 healthy、`/healthz`=`ok`、`/api/ready` schema revision 4。Pack 0.3.4 的 260 候選在容器內驗證並 admission；26 Families 各 10 筆。Runtime restart 前後 DB 筆數相同；seed 在 fresh 與已使用 SQLite 重跑不新增 Surface binding。Docker驗收證據：`docs/evidence/math-u1-docker-sqlite-acceptance-2026-10-14.json`。
- Root PR #3 保持 Draft，SDK PR #335 保持未合併；合併依賴順序仍是 SDK #335 先於 Root #3。未授權合併。
- 已推送分支：SDK branch `codex/u1-classification-transfer-supply` head `1e46710473c4776cdf3a5806a7b4cf739fed8e82`；Root branch `codex/lk-next-decision-loop` Docker packaging／seed idempotency commit `29f32cf34fb2e545d38074536a6eaa73e9e2b15c`。Root gitlink 指向該 SDK SHA；Root PR #3 Open/Draft，SDK PR #335 Open/未合併。

## 配對恢復 checkpoints（2026-10-14）

- Root local checkpoint ref `checkpoint/math-u1-selfhosted-20261014` → `8cafd2122cfd7c0f8aee1801e2f0f2caf88ff833`.
- SDK local checkpoint ref `checkpoint/math-u1-selfhosted-20261014` → `1e46710473c4776cdf3a5806a7b4cf739fed8e82`；Root submodule gitlink 指向同一 SDK commit。
- 兩個 checkpoint refs 是額外本機書籤；原 PR branches 也已快轉推送。Root #3 為 Draft，SDK #335 Open，兩者都未合併。Checkpoint 只保護可恢復狀態，不代表 acceptance PASS。
- 從已有 clone 恢復：

  ```powershell
  git switch codex/lk-next-decision-loop
  git submodule update --init vendor/learning-kernel-sdk
  git -C vendor/learning-kernel-sdk switch codex/u1-classification-transfer-supply
  ```

- 從新 clone 恢復時先 fetch 並切換 Root PR branch，再初始化 submodule；若 checkout 是完整 SHA，使用 Root gitlink SDK SHA `1e46710473c4776cdf3a5806a7b4cf739fed8e82`。不要移動 SDK `main`，也不要清除使用者原工作目錄、SQLite、`.env` 或 Docker volumes。

## 使用者決定與目標

- 起點是使用者提供的 Option 2 單頁 HTML，已在 `web/index.html`。使用者喜歡部署版的功能，但單頁 HTML 與先前網站有些差異；先以這份 HTML 為基線，實測後逐步修正。保留其視覺與操作意圖。
- 新 repo 與原 `learning-kernel-bailian` 分離；SDK 以固定私有 submodule 引入。原 repo 與 SDK `main` 不變；PR #3 所需 SDK Pack 供應只可在獨立分支維護。
- 優先完成能在本機瀏覽器實際使用的數學 U1 出題、作答、原始觀察紀錄與再次讀取流程，然後再擴張。個人使用、家中區域網；加密、雲端／每日備份、登入、GitHub Actions、額外部署流程都不是當前門檻。不要因這些議題卡住功能開發。
- 不要假稱其他科目已有 LK 支援。未供應的活動可清楚標示尚未開放；不要用網頁內假進度、假判分替代 Runtime 結果。
- 不要求使用者每一步貼輸出給遠端代理。本地 Codex 可以直接在 WSL 執行、修正與驗證。PR #1 的提交身分隱私修正已依使用者授權處理；main 與 feature branch 的程式碼樹保持一致，原提交訊息、名稱、時間戳及祖先關係保留。

## PR #2 當前狀態（2026-10-12）

- pinned canonical SDK `b63404173e39a37685e9914523ba3704ac1664ad` 的 Runtime evaluation 是 correct/incorrect/indeterminate 唯一判斷來源；沒有修改 SDK 或其 submodule 指向。
- Runtime host 以最小 adapter 觀察一次 canonical verdict，僅向允許的 raw-observation response 加入非敏感 verdict、tone、message、action；既有 browser route allowlist 不變。答案、validation payload、判分規則與特權路由不提供給瀏覽器。
- 錯誤作答留在原題、清除選取並可再次送出；每次新嘗試產生新 ID、ordinal/count 遞增、retryCount 隨 ordinal 增加。網路不確定重送沿用同一個 pending capture。完全相同的 HTTP 請求由持久 SQLite response cache 回覆，避免 Runtime 重算。
- 正確與未能判斷都依 Runtime advance/complete directive；未能判斷顯示中性訊息。瀏覽器只呈現結果，不判分。
- 本機驗收使用 Windows 11 + Docker Desktop/WSL2、隔離 Compose project `lk-pr2-20261012`、`http://localhost:8081` 與隔離資料庫 `data/pr2-feedback-20261012/learning-kernel.sqlite3`；既有主資料庫保留。
- 驗收：unittest 17 passed、Node check、Python compileall、Ruff、diff check 通過；canonical evaluator 三種 verdict 均已直接核對。真實瀏覽器完成單選錯誤後重試答對、多選連錯兩次後答對；兩輪流程合計 SQLite 10 observation / 10 attempt chain / 10 trusted evidence / 10 response-cache entries，ordinal/count/retryCount 逐次為 1/1/0、2/2/1，以及 1/1/0、2/2/1、3/3/2。Runtime restart 後 readiness 與十筆記錄仍可讀；先前 exact HTTP replay 實測回傳快取 response，未增加紀錄。
- PR #2 已合併至 main。NAS 正式部署及備份／還原未驗收。

## Previous PR #3 snapshot（2026-10-13；已由以上 2026-10-14 驗收更新取代）

- 根據 pinned SDK Phase 7.9.4 確認 Next Decision 已在 canonical Runtime：讀 exact-release Evidence → project Learner State → derive legal routes → choose navigation → 驗證實際 Activity Pool supply → 回 learner-safe Surface。原 SDK Pack 缺少可供應的 U1.1 classification-transfer Activity，因此在獨立私有 SDK 分支補 Pack 0.3.2、deterministic generator、獨立 verifier 和 artifact；未改推薦器或 evaluator。
- SDK 分支 `vendor/learning-kernel-sdk:codex/u1-classification-transfer-supply` 本機 commit `ae263228d1d8a955a7ef8c40ef3a062f0ace8026`。GitHub push 回 GH007 private-email protection；本任務明確不處理 Git Email，因此沒有改 email、amend 或重寫歷史。SDK Draft PR 未建立。根工作目錄有未發布的 gitlink 指向此 commit；要 push root PR 前，先讓私有 SDK commit 可從遠端取得，否則公開 PR 將有無法 checkout 的 submodule。
- Root 分支 `codex/lk-next-decision-loop` 的 UI 在完成活動後用 session 起始 `u1-1/factor-structure` 作上下文重新呼叫 `/surface`，不送 `learnerSelectedCandidateId`；返回的真實 Surface 暫存在記憶體。孩子按「開始下一個練習」才載入相同 Surface；沒有候選或 Runtime error 時顯示中性狀態。延續 current today-practice mode；前端只展示 routeKind 和 Surface 內容。
- Seed 在 SQLite 安裝/啟用 Pack 0.3.2 並加入 direct-classification、divisibility、transfer 三個經 Pack verifier/admission 的 Pool entries。0.3.1 artifact 仍保留，沒有刪除或改寫舊 SQLite 資料。
- Windows 11 + Docker Desktop 29.8.2 / Compose 5.5.1；隔離 project `lk-pr3c-20261013`、`http://localhost:8084`、資料庫 `data/pr3-next-decision-20261013c/learning-kernel.sqlite3`。Docker build/up、雙服務 health、seed 首次/重複、`/healthz`/`/api/ready` 200、schema rev4 通過。原 8080/8081 容器及資料未變；另兩個隔離驗收 DB 8082/8083 保留，未刪除。
- Local acceptance: self-hosted unittest 17 passed; SDK Python 3.12 targeted suite covers generator, artifact/runtime, Surface compatibility, and Phase 7.9.4 evidence-to-decision/supply; `node --check`, Python `compileall`, changed-file Ruff check/format, `git diff --check` passed. GitHub Actions 未執行。
- 真實瀏覽器完成 U1.1 Surface 單選+多選，LK回正確 verdict/advance/complete；completion 後 Runtime 回 route `delayed_confirmation` 和實際可供應 Surface。Start 後的 Surface 重啟 Runtime 後仍可提交。第二步錯答會留題、可重試；DB chain ordinals `[1,2]`，capture `attemptCount` 1→2、`retryCount` 0→1。當前這條真實瀏覽器 Evidence path 下 LK 選擇再次確認 direct classification，因此 prompt 與初始題型相近；copy 說明為「再想一次」，未假稱 transfer 已在該瀏覽器路徑中被選中。SDK integration separately verifies a differing sequential Evidence snapshot selecting the real transfer Activity.
- Final isolated SQLite check before/after restart: 9 observation records, 9 trusted Evidence, 9 Attempt Chain rows (其中一條含 ordinal 1→2，其他 8 條單次), 7 issued Surface bindings；`PRAGMA integrity_check`=`ok`。Runtime 重啟後 readiness/schema rev4 與記錄數不變。
- Surface browser boundary is unchanged: same-origin host allows only Surface reads and raw-observation writes. SDK tests check no validation fields in Surface and no-supply fail-closed; local host tests block privileged/unimplemented routes. Other subjects/modes, NAS and backup remain out of scope.

### 當時記錄的發布阻礙（已由 2026-10-14 更新取代）

1. 目前不要推 root branch 或建立 PR #3；其 submodule SHA 尚未出現在 SDK remote。
2. 下一輪先解決私有 SDK repo 的 commit push identity protection（本輪未處理 email）。只有 SDK commit 可正常遠端讀取後，才可推 root branch、建立 Draft PR #3。
3. PR #3 要保留 Draft，提供使用者體驗；不得合併。不要建立 PR #4 或改 SDK main。

## 已有環境和歷史驗證事實（2026-10-12/13；最新 PR #3 狀態以上述 2026-10-14 驗收為準）

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

## 後續工作（2026-10-12 歷史快照；以本頁 Issue #4 最新驗收為準）

1. 等待使用者體驗並審閱 SDK PR #335、Root Draft PR #3；依賴順序為 SDK 先於 Root，未取得明確授權前不得合併。
2. 其他科目、學習摘要、專項/自訂模式保持尚未開放；FnOS/NAS 部署、存取邊界與 SQLite 備份仍未驗收。

## 重要檔案與參考

- `web/index.html`：指定外殼基線；`Dockerfile`、`nginx.conf`、`docker/render-nginx-config.sh`：web 與 API 同源代理。
- `compose.yaml`、`Dockerfile.runtime`、`api/app.py`、`api/sqlite_d1.py`、`api/migrations.py`、`api/seed_u1.py`。
- `vendor/learning-kernel-sdk/tests/test_runtime_vnext_d1_pack_control.py` 中 `_validated_classification_pool_entry`、`_validated_divisibility_screen_pool_entry`、`_surface_request` 及 compound Surface 測試；`apps/runtime_vnext/worker/runtime_http.py` 看實際路由與 payload。
- `README.md` 與 `docs/DOCKERIZATION_TODO.md` 是公開進度；更新時區分「程式已寫」與「本機已驗證」。

## 目前成功標準

PR #1、PR #2 已合併。Issue #4 的 U1 Map、26 Family Pool generation/admission、10 活動同 learner trace、17 Place Map trace、26 Family exploration 與真實瀏覽器回應格式均已在本機驗收。Root PR #3 保持 Draft，SDK PR #335 未合併，等待使用者體驗與明確 merge 授權。其他科目、成長/家長摘要、專項/自訂模式、FnOS/NAS 與備份仍未完成；另有兩個 D1 read-model 基線失敗和七個 Worker readiness 基線失敗未處理。
