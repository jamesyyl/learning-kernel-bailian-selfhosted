# 數學 U1｜Evidence 驅動複習輪替實測（2026-10-15）

狀態：**隔離 SQLite/Runtime E2E 與 Chrome 桌面／手機 UI 驗收通過；正式 18084／8080 未變更，PR 未合併。**

## 版本與隔離條件

- SDK 隔離分支：`fix/u1-evidence-review-rotation-20261015`，精確 source SHA `4924faaf3a2336674a6ef0914faa8779e1385a33`。
- 百煉隔離分支：`fix/pr3-u1-review-rotation-20261015`；source pin／vendor gitlink 與 SDK SHA 一致。
- Knowledge Pack：`org.learning-kernel.tw-math-g6-u1@0.3.7`，17 Places／28 Task Families。
- 測試過程只在新建的暫存 SQLite／Docker 專案 `lk-owner-review-uat-20261015`（localhost:18085）執行。沒有對 8080／18084 的使用者資料或容器進行修改。

## 實際 SQLite + LK Runtime 端對端

正式納入百煉分支：`tests/test_u1_spaced_review_runtime.py`，本機 WSL Python 3.12 執行 **1 passed**。

1. 真正安裝 0.3.7 Pack，維持已驗證的 immutable Pool，不刪題、不直接修改 issued history。
2. 同一個學習者連續完成 U1-1 直接分類的 10 道初始題，各次都以 Runtime 原始作答接口保存。
3. 在新題耗盡、未達冷卻時，Runtime 不允許重發。
4. 模擬 8 天後，Runtime 重新簽發到期複習題；連續要求不得立即重複同一題。
5. 複習作答後，SQLite 計數：**12 筆 issued binding、11 筆 Observation、11 筆 Evidence**，完整性 `PRAGMA quick_check=ok`；舊紀錄未被覆寫。
6. 另一學習者仍能取得其個別的未用新題。該學習者已有到期舊題但仍有合格新題時，LK **先選新題**。

另有 SDK 隔離回歸 **63 passed**，涵蓋複習規則、D1 issued history、Surface 編譯、U1 供題與五步情境；Ruff 檢查通過；在 WSL Python 3.12 使用 mypy，4 個 Runtime 相關模組 **Success: no issues found**。

## 真實 Chrome 瀏覽器：UI 驗收

透過隔離站 `http://127.0.0.1:18085`，使用無頭 Chrome：

| 場景 | 結果 |
|---|---|
| 桌面 1365×900 正常載題（真 Runtime 題目） | PASS |
| 桌面 1365×900：暫無新題或到期複習 | PASS |
| 手機 390×844：暫無新題或到期複習 | PASS |

- 正常題目有實際 prompt、選項與可見的「送出作答」。
- 「無供應」畫面使用**在 Chrome 測試中攔截並模擬 HTTP 503**，不是把隔離 SQLite 全部耗盡。測試證明前端在 API 503 時顯示適合孩子的說明文字，隱藏題目、作答按鈕與無用的陪練提示，且手機無水平溢出。不可把此項誤記為瀏覽器直接操作完全部題目。
- 模擬 503 時 Chrome console 會自然回報兩條預期的 HTTP 資源錯誤，**沒有 pageerror/JavaScript exception**。
- Windows 測試時外部字型、圖示 CDN 連線不穩，測試瀏覽器將其 CSS 攔截為離線空樣式；**正式網站資源設定未修改**。

## 仍須注意

- SQLite E2E 使用時間模擬驗證 8 天冷卻規則；未真實等待 8 天。
- 更多 Task Family、多月／跨 Pack 升級的長期複習策略還需要擴展測試。
- 百煉「沒有題目」現在有友善引導，但 Runtime API 仍回傳 503 供服務內判斷；這是刻意保留的後端語意。
- PR3/main 與正式服務未合併或升級；封板前仍需完整測試及使用者最後體驗確認。


## 2026-10-15 暫停後的接續基線（不得誤判為本輪回歸）

- SDK `fix/u1-evidence-review-rotation-20261015` 在 **WSL Python 3.12** 完整執行 `pytest -q -o addopts= --tb=short`：**1,766 passed、28 failed、71 subtests passed**，約 7 分 43 秒。這表示目前**全量驗收不綠**，不得宣告可合併。
- 為釐清起因，回到複習輪替前的 SDK 0.3.7 基線 `5eaa458df923b4face4720b553ce8566c41359d7`，以**同一 Python 3.12 測試環境**重跑上述 28 個精確測試 ID：**28 個全數重現失敗**。
- 28 項分成兩批：**14 項**屬於舊版 Pack artifact／內容／preview 的測試預期，**14 項**屬於 D1 migration／Pack control／Worker readiness 與投影驗收；只能確認它們在本次複習輪替前就存在，**不能因此認定它們無害或無須修復**。
- 本輪新增的複習輪替範圍：**63 個相關 SDK 回歸通過、Python 3.12 mypy 4 個模組 PASS、SQLite E2E PASS、Chrome 3 種情境 PASS**。這是功能範圍驗收，與「全套綠燈」是兩件不同的事。
- 18085 隔離 Docker：專案容器、兩個專用 image 與臨時服務密鑰均已移除；8080／18084 均回 HTTP 200。Docker 其餘建置快取未做全域清理。
- **接續順序**：先保持已驗收的複習輪替分支不變；將 28 項舊失敗獨立分組逐批修復／確認語意，優先處理可能代表真實執行錯誤的 D1/Worker 驗收；每一批都以原來斷言的目的為準，不透過刪測試或放鬆必要檢查取得綠燈；最後再整套重跑，才討論合併或部署。
- 本機 `lk-owner-review-rotation-20261015/sdk` 是**用於驗收的隔離目錄**；曾因 GitHub clone 鏡像落後而留下 6 個不同於本機 HEAD 的測試／格式修改，這不是使用者 canonical repo，也**不應以 `git reset --hard` 強行覆蓋**。GitHub 隔離分支為發版核對依據。
