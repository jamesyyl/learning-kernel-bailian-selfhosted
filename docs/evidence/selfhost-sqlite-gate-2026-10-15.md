# Docker／SQLite 專屬 Gate：首輪驗收證據（2026-10-15）

獨立分支：`feat/selfhost-sqlite-acceptance-gate-20261015`，基於百煉複習輪替隔離分支 `4148dbfd2f209df3ee7a67b79be084bdd066b766`。**未合併、未部署**。

## 目標與界線

- 已確定未來以 Docker／Python Runtime／SQLite 為正式方向，不把 Cloudflare Workers／D1 deployment 的 platform-specific 測試視為百煉自建版發版 Gate。
- **仍保留** Runtime 內部既有 `d1_*` SQL 介面及其保護。它們在 Docker 裡由 `api/sqlite_d1.py` 實際執行本機 SQLite。
- 不改 Pack `0.3.7` 的判斷語意；未動 `8080`／`18084`／現有 learner SQLite；沒有開 Docker 測試容器、使用 Codex 或執行 GitHub Actions。

## 新增檔案

- `scripts/run_selfhost_gate.py`：Python 3.12 下執行明確選定的百煉 SQLite 與 LK 共用核心測試；拒絕 missing、unclassified 和 skipped；提供選用的 read-only Live HTTP＋SQLite consistency 檢查，產生 JSON 結果。
- `tests/test_selfhost_gate_contract.py`：Gate 自身失敗封閉測試。
- `docs/SELFHOST_ACCEPTANCE_GATE.md`：三階段自架版驗收契約及 28 個舊基線失敗的歸屬。

## 本輪真實執行數據

| 測試 | 結果 | 備註 |
|---|---|---|
| LK 可攜式 SDK 七個必要測試檔 | **74 passed** | 由專屬 Gate 執行，不跑 Wrangler／CF 部署測試 |
| 百煉自架 13 個測試檔 | **25 passed，3 subtests passed** | 第二輪修正 `LK_SDK_ROOT` 及 migration 路徑後 100% PASS；約 4 分 34 秒 |
| Gate 防護測試 | **7 passed** | 包含 missing／skipped、防止 CF Compose 回流、只讀性、revision、checksum、Pack version |
| Ruff lint | **PASS** | Gate 程式與自身測試 |
| Ruff format | **PASS** | 已格式化並提交 |
| Docker Live ready＋SQLite | **本輪未執行** | 需要新的隔離 Docker DB，不會對 8080／18084 執行 |
| 真實 Chrome 孩子 UI | **本輪未重跑** | 前次在 `18085` 的複習輪替驗收已獨立留下證據；新版本封板前仍需重新確認 |

首輪自架測試曾因缺少 `LK_SDK_ROOT` 與 migration 環境路徑而出現 **23 passed／2 failed**；確認屬於測試入口設定錯誤，修正後 25 項全部通過。不能把首輪失敗說成 Cloudflare 故障。

### SDK 來源一致性

Windows 隔離測試中，本機 Git checkout metadata 曾因鏡像落後，與遠端分支 commit SHA 不一致。為避免誤驗另一份原始碼，直接比較了 9 個關鍵 SDK 原始碼／測試檔的 Git blob SHA，包括 `spaced_review.py`、`production_surface.py`、`d1_issued_activity.py`、`runtime_http.py`、`family_generators.py`、`verification.py`、`test_runtime_spaced_review.py`、`test_runtime_vnext_activity_pool.py`、`test_math_u1_vnext_supply_continuity.py`；**九個均與 GitHub 分支一致**。這是關鍵檔案同一性的核對，並不取代完整 checkout commit 身份的正式發版檢查。

## 結論

Gate 1 核心語意與 SQLite 自架測試已分組跑通；不再因舊 Cloudflare Worker tests 的紅燈而錯誤阻擋 Docker／SQLite 專屬功能驗收。

**仍未達到最終發版條件**：Gate 2 新隔離 Docker Live＋Migration SHA 對照、Gate 3 真實 Chrome UAT、與精確 pinned SDK checkout 的乾淨版本驗收須另行完成。SDK 舊版全量的 28 個既存失敗保留為上游品質債務，並依是否涵蓋共用資料安全持續分流處理；絕不把它們一概刪除。
