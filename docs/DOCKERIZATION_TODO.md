# 百煉自架 Docker TODO

## 起點

- UI 基線：使用收到的 `bailian-option-2-subject-cards.html`，保存在 `web/index.html`；功能修改都從這份開始。
- 新 repo：`jamesyyl/learning-kernel-bailian-selfhosted`，與原百煉獨立。
- PR #3 工作分支：`codex/lk-next-decision-loop`（從 `origin/main@5e5fae53426c23a9b2c2ba57ac5882b341867e99` 建立）；Issue #4 的全 U1 Map/Pool/Surface 本機實作已完成。
- PR #1：[Pull Request #1](https://github.com/jamesyyl/learning-kernel-bailian-selfhosted/pull/1)。
- PR #2：[Pull Request #2](https://github.com/jamesyyl/learning-kernel-bailian-selfhosted/pull/2)，已合併至 main。
- Root PR #3 保持 Open Draft；SDK PR #335 保持 Open、未合併。依賴順序為先 SDK、再 Root；沒有 merge 授權。
- 原 `learning-kernel-bailian` 未修改；canonical SDK `main` 未修改。PR #3 的 Pack 供應補足只在獨立 SDK branch。

## 順序與狀態

| 順序 | 工作 | 狀態 | 完成條件／驗收紀錄 |
|---|---|---|---|
| 0 | 將指定 HTML 放進新 repo，保留原檔 | 完成 | HTML 原樣保留；後續功能修改以它為基線。 |
| 1 | 建立 Nginx＋Python Runtime 的 Compose 底座 | 完成 | 同源代理；Python 載入固定 SDK；SQLite 可另設資料目錄；瀏覽器不能呼叫 Pack 管理或 trusted returns。 |
| 2 | Windows 11＋WSL2 建置和 Runtime 驗收 | 本機通過（2026-10-12） | Docker 29.8.2、Compose 5.5.1；兩個映像成功建置，web/runtime containers healthy；`/healthz` 回 `ok`；Runtime restart 後 readiness 為 schema revision 4，`data/learning-kernel.sqlite3` 存在（4096 bytes）；完整 unittest 11 項全通過、0 skipped；首頁基礎載入確認。完整學習流程記錄於第 4 項。 |
| 3 | 準備 U1 Pack 與合法 Activity Pool 供應 | 本機通過（2026-10-12） | WSL Docker build 後，`docker compose exec runtime python -m api.seed_u1` 首次及再次執行皆成功；同源 Surface HTTP 200、schema `learning-kernel.surface-ir@1`、Pack 0.3.1。 |
| 4 | 把 Option 2 練習頁接到 LK | 程式已寫；本機瀏覽器通過（2026-10-12） | 首頁選數學 U1、載入真實 Surface、完成單選及多選兩步、每步收到 Runtime 保存回覆；頁面只送 raw observation，沒有瀏覽器判分。未接通科目與學習摘要標示尚未開放。 |
| 4.5 | LK 判斷結果與孩子可理解的回饋 | PR #2 已合併 | pinned LK SDK 是 correct/incorrect/indeterminate 唯一判斷來源。百煉只呈現安全 verdict/message/action；答錯留在原題並可重試，correct/indeterminate 依 Runtime directive；前端不取得標準答案或判分規則。exact same-request replay 使用 SQLite response cache。 |
| 4.6 | LK Next Decision 與實際活動推薦 | Docker／SQLite acceptance PASS（2026-10-14）；PR #3 保持 Draft | canonical Runtime 依 Evidence+Map 決策；Root Map 顯示 5 Regions／17 Places／37 Roads，26 Families 可探索。Pack 0.3.4 的 260 個變體全數獨立驗證並通過 Runtime Pool admission；17 Places 與 26 Families 均取得 canonical Surface／Evidence。同 learner 連續完成 10 題不同活動。Docker 真實瀏覽器核對單選、多選、數值及文字作答。最新記錄見 `docs/evidence/math-u1-docker-sqlite-acceptance-2026-10-14.json`。 |
| 4.7 | 孩子用語＋引導式因數樹作答 V1 | 部分 Docker／SQLite Chromium 驗收通過（2026-10-14）；單選 E2E 未跑 | 孩子文案、整數數字鍵盤、質因數分解式工具鍵、因數樹逐步文字及手機版均已在隔離同歷史 learner 副本驗收；整數、分解式、因數樹、多選、U1-1 耗盡、HTTP 故障、Journey 返回/捲動及重整續接通過。單選候選在同一 learner 歷史中已耗盡，不建立新 learner 或虛構供應。原始 Observation 請求值原封送入 Runtime 並收到 Evidence receipt；SQLite Evidence projection 不保留字面回答本體，如需逐字答案的重啟後保存，需另訂持久化契約。詳見 `docs/evidence/math-u1-child-language-factor-tree-uat-2026-10-14.md`。 |
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

## PR #2 本機驗收與合併（2026-10-12 至 2026-10-13）

- 以 Windows 11 + Docker Desktop/WSL2 在獨立 Compose project `lk-pr2-20261012` 驗收，前端 URL 為 `http://localhost:8081`；測試資料位於被 Git 忽略的 `data/pr2-feedback-20261012/learning-kernel.sqlite3`，既有 `data/learning-kernel.sqlite3` 未動。
- Docker Compose 兩服務 healthy；`/healthz` 與 `/api/ready` HTTP 200，schema revision 4；Math U1 seed 首次及重複執行成功。
- 完整 unittest：17 passed；`node --check web/app.js`、Python `compileall`、Ruff 與 `git diff --check` 通過。固定 SDK evaluator 實際回傳 correct、incorrect、indeterminate；未修改或更新 SDK submodule。
- 真實瀏覽器從 Option 2 首頁進入數學 U1，單選錯誤後留在原題、重試答對；多選連錯兩次後第三次答對並完成。UI 顯示 LK verdict 與 Runtime 指令，未在前端判分。
- 兩輪瀏覽器驗收後，隔離 SQLite 共保存 10 筆 observation、10 條 attempt chain、10 筆 trusted evidence 與 10 筆 exact-request response-cache 記錄。每輪 attempt ordinal/count/retryCount 依序為 `1/1/0, 2/2/1`（單選）及 `1/1/0, 2/2/1, 3/3/2`（多選）。Runtime 重啟後 readiness 與資料可讀；相同 HTTP 請求 replay 測試回傳相同 response，對應資料筆數不變。
- PR #2 已合併至 main；NAS 正式部署與備份／還原尚未驗收，其他科目與模式仍顯示未開放。

## Issue #4 全量 Math U1 本機驗收（2026-10-14）

- Pack 0.3.4 digest `sha256:aea207d8eb59619373203dcfaa74614b4b1b6273953257620be54956f6b1cc98`。5 Regions、17 Places、37 Roads、24 Capabilities、26 Task Families、26 Generator Requirements；7 個 reviewed Fixed Activities／16 points 保留，另有 26 個 Family 單點錨點，合計 33 Activities／42 points。原 Pack 0.3.2 artifact digest `sha256:5feac5c62f0510ef2ecc9851e06d15e879e6e5095838771b35543b534364fed3` 保持不變。
- Exact-Family deterministic generator registrations 對 26 個 Families 各生成 10 個不同 Activity，共 260 候選；所有候選均通過獨立 verifier、Pack validators 與 Runtime Pool admission。每個 Family 有 10 個不同 prompt/activity ID。
- Root full test suite：19 passed；`node --check web/app.js`、Python `compileall`、Ruff 與改動檔 format 通過。SDK focused suite：181 passed、2 個已確認在乾淨 PR #335 基線也會失敗的舊 D1 knowledge-read tests 排除。另確認 7 個 Worker readiness tests 在乾淨基線也失敗；未改 Cloudflare/D1 readiness 部分。GitHub Actions 未手動啟動。
- Runtime/隔離 SQLite 同 learner 完成 10 個不同生成 Activity ID／題目；Map 上 17/17 Place 取得 canonical Surface/Evidence，Family exploration 26/26 取得 Surface/Evidence。Matrix：`docs/evidence/math-u1-supply-matrix-final-0.3.4.json`；trace：`docs/evidence/math-u1-10-activity-trace.json`。
- Codex in-app Chromium 顯示完整 Map；實際沿 Road 從 U1-2→U1-3→U1-5，作答單選、多選、multi-classification、integer、structured-factorization、free text；全部由 Runtime 判定正確。單選錯答留題，可重試答對；初始題 2 的 Next Decision 回傳不同的題 3。詳細：`docs/evidence/math-u1-browser-acceptance-2026-10-14.json`。
- Local browser acceptance host 使用 TemporaryDirectory SQLite；沒有建置或操作 Docker，也沒有觸及使用者原始 checkout/SQLite。SDK #335、Root #3 均不合併，等待使用者體驗與明確授權。
- **Docker/SQLite 狀態分開記錄：** SQLite adapter 與隔離 Runtime 全套測試 PASS；Docker client 29.8.2、Compose 5.5.1 存在，但 Docker Desktop Linux engine named pipe 無法連接。Compose build/up NOT RUN、Docker acceptance BLOCKED；不啟動 daemon、不碰既有 8080/8081/8084 環境。

### Docker + SQLite recheck（2026-10-14；取代上面的暫時 BLOCKED）

- Docker Desktop daemon 已可用。只建置與操作隔離 Compose project `lk-u1-acceptance-20261014`、loopback `127.0.0.1:18084` 及專用暫存 SQLite；原 8080／8081／8084 三個專案持續 healthy 且未變動。Runtime 與 Web 均 healthy；`/healthz` 回 `ok`，`/api/ready` 為 schema revision 4。
- Docker Runtime image 現在確實包含 Math U1 Pack 0.3.4，digest `sha256:aea207d8eb59619373203dcfaa74614b4b1b6273953257620be54956f6b1cc98`。容器內 seed 生成、獨立驗證並 admission 260 entries；SQLite 查詢確認 26 Families、每個各 10 entries。完整 Pack coverage／Map routes 由前述 Python/SQLite acceptance suite 驗證：17/17 Places Surface+Evidence、26/26 Family exploration+Evidence、37 條 Road 的兩端皆為合法 Place。
- 同一 Docker learner 連續完成題目 2–11，共 10 個不同 prompt，Runtime 判對。真實瀏覽器另完成單選、多選、整數數值、因數樹文字四種答案格式；錯誤答案留在同一活動，重試後由 Runtime 判對。瀏覽器在頁面選取 17/17 Map Places，標題皆與選取項目一致；真實 Road 點選也成功導向相鄰 Place。
- SQLite Runtime restart 前後保持 260 Pool entries、15 issued bindings、15 attempt chains、15 trusted Evidence、15 response-cache rows、4 migrations；restart 後同源瀏覽器能再取得 LK Next Decision 與活動。後續受測資料總數為 16/16/16/16，沒有資料回退。
- 發現並修正 `api/seed_u1.py` 的重複執行行為：舊版每次 seed smoke check 都會額外 issue 一個 Surface；新版若已有同 learner／Pack／digest 的 canonical binding，先核對 lineage 並保留現有 binding。全新隔離 SQLite 連跑兩次後仍只有 1 個 binding；已使用中的 Docker SQLite 連跑兩次後 Pool 與 binding／attempt／Evidence／response-cache 筆數不增，兩次均成功。`Dockerfile.runtime` 也已加入 0.3.4 artifact 複製；`.gitattributes` 固定 Nginx renderer shell script 為 LF，避免 Windows CRLF 造成容器啟動失敗。
- Root 全套測試在 seed idempotency 修正前為 19 passed；修改後新增的三個 seed-lineage／reuse 回歸測試為 3 passed，並用 Docker fresh DB／既用 DB 兩條實際路徑驗收。修改檔 Ruff、Python compileall、Node syntax、diff check 通過。此輪沒有執行 Cloudflare／Worker／D1 專屬測試或 Actions；該類既知基線狀態不變且在本輪範圍外。
- Docker browser acceptance 的詳細筆數、重啟前後 SQLite 計數與回歸修正見 `docs/evidence/math-u1-docker-sqlite-acceptance-2026-10-14.json`。NAS／FnOS 部署及正式資料備份仍待另行驗收。

## PR #3 LK Next Decision 舊驗收（2026-10-13；由以上 Issue #4 驗收更新取代）

- 基於 `origin/main@5e5fae53426c23a9b2c2ba57ac5882b341867e99` 建立 `codex/lk-next-decision-loop`。pinned SDK 原 commit 為 `b63404173e39a37685e9914523ba3704ac1664ad`；Phase 7.9.4 已有 Evidence→Learner State→legal route→Next Decision→Activity Pool 的 canonical 路徑。缺口是 LK 可選到的 U1.1 transfer Task Family 沒有固定 Pack Activity/Pool 供應。
- 在私有 SDK 獨立分支 `codex/u1-classification-transfer-supply` 加入 Pack 0.3.2 transfer Activity、deterministic generator、獨立 verifier 與 artifact；SDK commit `ae263228d1d8a955a7ef8c40ef3a062f0ace8026`，保留原 0.3.1 artifact。沒有改 recommender、evaluator 或 SDK main。GitHub 以 GH007 拒絕推送該新分支；此階段明確不處理 Git Email，因此 SDK 分支未發布，PR #3 不能建立。
- 自架 branch 的 seed 以 canonical generator/verifier 建立 transfer Pool entry，變異 policy 與 SDK 已驗證的 Activity Pool admission 相同；`Dockerfile.runtime` 同時保留 Pack 0.3.1/0.3.2 供應，SQLite 中舊 release 歷史不被清除。瀏覽器完成後重新呼叫同一 canonical `/surface`，使用 session 起始 Place 且不傳固定 candidate；Runtime 回傳實際 Surface 才顯示推薦，開始時呈現該 Surface 本身。
- Windows 11 + Docker Desktop/WSL2；使用隔離 Compose project `lk-pr3c-20261013`、前端 `http://localhost:8084`、資料庫 `data/pr3-next-decision-20261013c/learning-kernel.sqlite3`。Docker build/up 成功，兩服務 healthy；`/healthz`、`/api/ready` HTTP 200，schema revision 4；Math U1 seed 首次及重複執行均成功。原 8080、8081 及其資料庫未改。
- Self-hosted unittest：17 passed；`node --check web/app.js`、`compileall`、Ruff（改動 Python 檔）、Ruff format check（改動 Python 檔）、`git diff --check` 通過。SDK Python 3.12 聚焦驗收 140 passed，涵蓋 generator、Pack artifact/runtime、Surface compatibility 及 Phase 7.9.4 evidence→decision→supply 整合測試。
- 真實瀏覽器：Option 2 首頁→數學 U1→LK Surface；第一步單選、第二步多選均由 Runtime 回傳正確回饋。活動完成後 LK 回傳 delayed-confirmation 類 route 及真實可供應 Surface；Start 載入該 Surface。重試錯誤多選後留題、再答對；SQLite Attempt Chain ordinal 為 `[1,2]`，原始 attemptCount 為 1/2，retryCount 為 0/1。這次真實 evidence path 的 LK 目前推薦再確認同一個直接分類題型；另有 SDK Phase 7.9.4 整合測試驗證在不同 sequential evidence snapshot 下 route 轉至 Pack transfer 活動。
- Runtime 重啟後 pending issued Surface 仍可啟動及提交作答；重啟前後 SQLite integrity check 為 `ok`。最新隔離資料庫共 9 observations、9 trusted Evidence、9 Attempt Chain rows；其中一條 chain 有 ordinal `[1,2]`，capture 的 attemptCount 為 `1,2`、retryCount 為 `0,1`，其餘 8 條各有一次嘗試。重啟前後總數不變。
- 前端只透過允許的 Surface/raw observation API；host allowlist tests 阻擋其他特權路由。Surface 不含 answer key/validation payload；SDK 整合測試涵蓋缺少可供應 Pool 時 fail closed。未啟動 GitHub Actions。
- 尚未發布或建立 Draft PR #3，原因是必要的私有 SDK branch push 被 GitHub GH007 拒絕；不要從公開 repo 指向遠端不可取得的 submodule commit。NAS/備份、其他科目與模式仍未驗收。

## 目前不可用的部分

PR #1、PR #2 已合併。Issue #4 的 U1 full Map/navigation/generation/Pool/Surface implementation 已完成本機驗收；Root PR #3 保持 Draft，SDK PR #335 保持未合併。2026-10-14 孩子用語＋因數樹 V1 已更新 18084 Web（僅 Web 容器；更新前備份、更新後 Evidence digest/count 相同）；隔離副本在 18092 保留供體驗。單選真實 Chromium E2E 仍因同一歷史 learner 的合法候選有限且耗盡而未跑，本輪不宣稱單選或全量供題通過。其他科目、成長與家長摘要、專項/自訂模式尚未接 Runtime；FnOS/NAS 正式部署、區網存取邊界與備份仍未驗證。SDK PR #335 基線的兩個 D1 knowledge-read tests 與七個 Worker readiness tests 有獨立既有失敗，詳見 local handoff；不在本任務範圍。
