# Math U1 孩子用語與因數樹 V1 本機驗收

日期：2026-10-14
結果：**部分通過；未宣告 Math U1 全量供應或單選端到端驗收通過。**

## 範圍與修正

- 首頁、Journey、活動頁、提示、等待、提交、答題回饋、缺題及錯誤改用孩子看得懂的繁體中文。缺題訊息不承諾稍後補題；真正的載入錯誤與供應耗盡分開顯示。
- 活動載入期間不顯示可送出按鈕。工程錯誤碼與 HTTP 狀態只留在瀏覽器診斷日誌，不放入孩子畫面。
- 整數欄位為 `type=text`、`inputmode=numeric`，標示「請輸入一個整數」。質因數分解使用單行文字欄位，按鈕可在游標或選取位置插入 `×`，清除後把焦點還給欄位。
- 因數樹只對 `u1-2/family/factor-tree` 活動啟用引導文字區；包含逐步拆分說明、避開題目原數的範例、`×`／`； 下一步`／`重寫`鍵。原始回答字串直接送到 Runtime，前端沒有判分或修改答案。
- 返回 Journey 會還原孩子開始活動前的科目、Place 與清單捲動位置。Journey→未答活動→重整→從同一 Place/Family 重新進入會恢復原 Surface。

## 備份與資料保護

- 更新 18084 Web 前，先在該 Runtime 已停止的維護窗口用 SQLite backup API 建立一致性備份：[備份檔](C:/Users/jamesyyliao/AppData/Local/Temp/lk-u1-live-pre-child-ui-20261014.sqlite3)。SHA-256：`86fdf230deddb42222f598454534ab5f0d66480211910001c447fe2581d59811`；schema revision 4；`PRAGMA integrity_check=ok`。
- 備份的 Evidence／Attempt Chain／response cache 各 134 筆、Pool 268 筆、issued binding 153 筆。Evidence canonical digest：`7fa7795c44819fcacb853256ec8a6accd44c54948b4566e4e8be4c41712e18e0`。
- 18084 只重建 Web 容器；Runtime、Pool Refiller、SQLite 檔案未重建或清除。更新後 Evidence 數與 digest 仍為 134／上述 digest，SQLite 完整性 `ok`。Runtime readiness HTTP 200、schema revision 4。8080、8081、8084 未改動，仍健康。
- 真實瀏覽器原有的 18084 分頁未重新載入，避免碰觸其中待答狀態；重新整理後會載入新版 Web。
- 最終隔離驗收使用 Docker named volume `lk-u1-child-ui-volume-data-20261014`，由上述一致性備份建立；使用同一 learner 歷史，不另建 learner。測試後 SQLite 備份：[驗收副本](C:/Users/jamesyyliao/AppData/Local/Temp/lk-u1-child-ui-after-uat-20261014.sqlite3)，SHA-256：`29fa1300a90c7453a4188849894085cfd69ef7761a7df0c91149109710b996ea`；Evidence 141、Attempt Chain 141、response cache 141、Pool 268、bindings 165；`PRAGMA integrity_check=ok`。
- 曾試用 Windows bind mount 副本；Runtime 執行時由 Windows 主機再開 SQLite 讀連線導致該副本出現 `disk I/O`，其資料檔 hash 未變且未用作驗收。後續端到端驗收改在 Docker 原生 volume，資料只由容器內 SQLite 讀寫。

## Docker／Chromium 驗收

最終互動副本網址：[http://127.0.0.1:18092/](http://127.0.0.1:18092/)。Compose project：`lk-u1-child-ui-volume-20261014`。同一 learner、同一歷史 SQLite 副本。

| 項目 | 結果 | 實際證據 |
|---|---|---|
| 首頁、Journey、孩子活動文案 | PASS | 實際 Chromium DOM 檢視；活動文字不含 `integer`、`response.text@1`、Runtime、HTTP、Nginx、D1、SQLite、raw observation、Task Family 等工程字詞。 |
| 整數輸入及可信判斷 | PASS | U1-4 direct-LCM Surface；一個故意錯答由 Runtime HTTP 202 判為 incorrect 並允許重試，後續正確作答收到 202／correct。瀏覽器欄位屬性實測 `type=text`、`inputmode=numeric`。不在報告中重複列出題目數值或答案。 |
| 質因數分解式 | PASS | U1-2 Factorization Surface；單行輸入包含 `×`、`x`、`*` 混用，Runtime HTTP 202／correct。瀏覽器實測為單行 `INPUT`、`inputmode=text`。游標插入、選取範圍取代、清除／重寫與焦點返回均通過。SDK 現有可信評估器的 `×`、`x`、`*` 及混合分隔測試通過，未改 SDK；原始答案字串未在報告中公開。 |
| 引導式因數樹 | PASS | U1-2 Factor Tree Surface；非 canonical、但結構合法的替代分解由 Runtime HTTP 202 判為 correct，receipt 含 evaluated=true、Evidence ID 與 Attempt Chain ID。CDP 唯讀檢查確認完整多步字串原封送出；不在報告中公開題目或答案數值。 |
| 因數樹手機畫面 | PASS | Chromium 390×844；引導、格式例、四列 textarea、工具鍵與送出按鈕均在一個視窗內；實測 document 高度 844px、送出按鈕底部 732px，無需捲動。 |
| 多選 | PASS | U1-1 divisibility Surface；同時選取兩個選項得到 Runtime HTTP 202／incorrect 並可重試，改選正確集合後收到 202／correct。報告不列出選項答案。 |
| 單選 | NOT RUN | 同歷史 learner 的五條單選候選 Family 均沒有未發行 Pool variant；逐項查詢未使用候選為空。未建立新 learner、未生成或補入測試題來冒充驗收。單選 renderer 未更動，但缺少真實單選 Surface 的 Chromium E2E 證據。 |
| U1-1 供應耗盡 | PASS | `u1-1/family/direct-prime-composite-classification` 的 Surface 回 HTTP 503，`activity_supply_unavailable`／`requested_family_exhausted`；畫面顯示「這裡目前沒有新的練習了。你可以回到學習旅程，看看其他想練習的地方。」且沒有送出按鈕。 |
| 真實載入故障 | PASS | 暫停隔離 Runtime 後，瀏覽器實收 HTTP 502；孩子畫面顯示「題目載入出了點問題，請再試一次。」且沒有送出按鈕。DevTools 日誌保留 `errorCode=runtime_http_502; httpStatus=502`。重啟後 readiness HTTP 200，重新進入活動收到 Surface HTTP 200。 |
| Journey 返回及重整續接 | PASS | LK Surface 從孩子選的 U1-5「方法選擇」改走 U1-4「最小公倍數」後，按返回仍選中 U1-5「方法選擇」、數學頁籤不變、清單 `scrollTop=546` 不變。因數樹未答 Surface 重整後從同 Place/Family 進入時沒有新的 `/surface` 請求，原題與輸入方式恢復。 |
| SQLite 重啟 | PASS | 隔離 Runtime／Refiller restart；schema revision 4、SQLite integrity `ok`，Evidence 仍為 141；之後重新開始練習成功。 |

### 原始回答與資料保存邊界

CDP 唯讀檢查確認因數樹的 Observation request 保留完整原始字串；HTTP 202 receipt 的 Evidence ID 與 Attempt Chain ID 均在隔離 SQLite 中各有對應 row。Trusted Evaluation 與 Evidence 持久化由 Runtime 負責，前端沒有解析或改寫。SQLite Evidence projection 不保存字面答案字串本身；本輪沒有新增逐字答案保存表，也不把 Evidence receipt 誤稱為該 raw 字串的持久副本。

## 本機程式檢查

- `node --check web/app.js`：PASS。
- Root focused pytest（`test_runtime_http_host.py`、`test_learning_map.py`、`test_u1_pool_replenishment.py`）：4 passed。
- SDK `test_runtime_vnext_trusted_evaluation.py --no-cov`：8 passed；SDK working tree／commit 未更動。
- `ruff check api tests`：FAIL，回報 7 個既有 Python lint 問題；本次沒有修改 Python 檔案，未藉機擴大範圍修整。
- 標準 `Dockerfile` 重新拉取 `nginx:stable-alpine` 受失效的本機代理 `127.0.0.1:7897` 阻擋。驗收 Web image 使用既有本機 Nginx image 作 base，僅複製更新後的 `web/`；Runtime image 未重建。
- 未執行 GitHub Actions；沒有 merge PR。

## 尚未通過／下一步

- 單選端到端驗收受同一歷史 learner 的有限候選池耗盡所阻擋；需有新的合法單選候選或安全的正式測試 fixture 後才能補驗。現階段不宣稱單選瀏覽器通過，也不宣稱題庫無限供應或學習掌握度。
- Web 更新已在本機 18084 服務；使用者原分頁保留原待答狀態，手動重新整理後體驗新版。隔離副本可直接在 18092 體驗。
