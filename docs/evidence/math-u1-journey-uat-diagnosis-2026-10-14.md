# Math U1 full Journey UAT diagnosis — 2026-10-14

Status: pre-fix diagnosis complete. No source code was changed during this phase. UAT used a Docker/SQLite copy of the verified 18084 snapshot and the existing learner identity.

## Preserved source and clone

- 18084 Compose project: lk-u1-acceptance-20261014; Runtime/Web healthy; schema revision 4.
- Pack release: 0.3.4, digest sha256:aea207d8eb59619373203dcfaa74614b4b1b6273953257620be54956f6b1cc98; learner local-learner-001, environment home; all five Regions activated.
- New consistent backup: learning-kernel.pre-journey-uat-20261014.sqlite3; SHA-256 ee31786da9d9a096057f228801ea3ff4b3331c88d444523f3b9e92ea21d6ae31; integrity_check ok; migration revision 4; pool 268, issue bindings 71, Evidence 46, Attempt Chains 46, response cache 46.
- Earlier pre-failure backup remains unchanged: SHA-256 650ce819c92e3815f85c7143e39bb0e0dec63052044a68f68ff9ff148aca565c.
- Chromium clone at http://127.0.0.1:18087 used the exact backup hash and same learner/history. Original 18084 and 8080/8081/8084 were not used for UAT writes.

## Root causes found

1. **LK selects one exact Family before checking supply, with no supply-aware reroute.** ProductionSurfaceRuntime queries Pool for the chosen Decision's exact capability/Task Family and raises activity_supply_unavailable when no unissued, validated entry remains. It does not ask canonical LK to select another legal route whose Family still has supply. Examples below show legal sibling Families with candidates while the selected Family is exhausted.
2. **Nginx rejects valid Runtime Surface responses.** The API route has no explicit proxy_buffer_size. Container page size is 4096 bytes. Same-origin Runtime responses measured 4117–4161 total header bytes, including a 3870-byte Server-Timing header with 111 metrics. Nginx logged “upstream sent too big header” and returned 502 HTML. Direct Runtime calls for these same routes returned 200 and had already persisted the Activity issue binding. The browser then received no Surface and could not answer; Evidence did not increase. This creates orphan bindings and consumes finite Pool supply.
3. **The UI collapses gateway failure into a generic Runtime error.** fetch(...).json() throws on Nginx's HTML 502; lkStartU1 displays the fallback Runtime error without preserving HTTP status. During the refill retry it leaves “送出作答” visible and enabled. It retries 503 eight times at 500 ms even when the finite generator domain is exhausted.
4. **Activity Back goes to Today, not Learning Journey.** The selected Place survives only after manually reopening Journey; the user must navigate an extra time.
5. **No infinite refill exists.** In a 64-index dry generation/independent verification scan, 25 Families yielded 10 unique prompts each; direct prime/composite classification yielded 18. Higher variant indexes produced valid Activity IDs but duplicate prompts, which the refiller correctly rejects. The Pack's current unique-prompt ceiling is 268 total. In watch mode, the refiller prints only when it admits entries or catches an error, so zero additions are silent.

No Python exception stack was found for the 502 responses: Runtime completed with 200 and Nginx rejected the response. The no-supply responses are expected ValidationError responses, not unhandled exceptions. The current generic Runtime catch still suppresses stack traces if an unrelated Python exception occurs.

## Same-learner pre-fix browser matrix

Reproducible steps for each row: open the 18087 Chromium clone, select Math in Learning Journey, check the named Place, click “在這裡練習”, wait for the Surface result, then use Activity “返回” and reopen Journey for the next Place. Same learner and copied 0.3.4 SQLite history were retained through the sequence. Each Place produced a visible load failure in this pre-fix run.

| Order | Place | HTTP/result | LK-selected Family / Activity |
|---:|---|---|---|
| 1 | U1-1 合數 | 503 activity_supply_unavailable | classification-transfer; no binding created |
| 2 | U1-1 整數的因數結構 | 503 activity_supply_unavailable | direct-prime-composite-classification; no binding |
| 3 | U1-1 質數 | 503 activity_supply_unavailable | classification-transfer; no binding |
| 4 | U1-2 質因數 | Nginx 502 HTML; UI shows generic Runtime error | factor-tree; generated variant-4 binding persisted |
| 5 | U1-2 質因數分解 | Nginx 502 HTML; UI shows generic Runtime error | factorization-reconstruction; generated variant-4 binding persisted |
| 6 | U1-2 原數與質因數結構的等值關係 | Nginx 502 HTML; UI shows generic Runtime error | factorization-reconstruction; generated variant-5 binding persisted |
| 7 | U1-3 公因數 | Nginx 502 HTML; UI shows generic Runtime error | direct-greatest-common-factor; generated variant-8 binding persisted |
| 8 | U1-3 互質關係 | Nginx 502 HTML; UI shows generic Runtime error | coprime-classification; generated variant-2 binding persisted |
| 9 | U1-3 最大公因數 | Nginx 502 HTML; UI shows generic Runtime error | direct-greatest-common-factor; generated variant-9 binding persisted |
| 10 | U1-4 公倍數 | Nginx 502 HTML; UI shows generic Runtime error | bounded-common-multiples; generated variant-1 binding persisted |
| 11 | U1-4 互質與最小公倍數的乘積關係 | Nginx 502 HTML; UI shows generic Runtime error | coprime-product; generated variant-2 binding persisted |
| 12 | U1-4 最小公倍數 | Nginx 502 HTML; UI shows generic Runtime error | coprime-product; generated variant-3 binding persisted |
| 13 | U1-5 情境答案 | Nginx 502 HTML; UI shows generic Runtime error | second-step-reasoning; generated variant-2 binding persisted |
| 14 | U1-5 方法選擇 | Nginx 502 HTML; UI shows generic Runtime error | method-selection; generated variant-1 binding persisted |
| 15 | U1-5 模型選擇 | 503 activity_supply_unavailable | model-selection; no binding created |
| 16 | U1-5 模型計算結果 | Nginx 502 HTML; UI shows generic Runtime error | second-step-reasoning; generated variant-3 binding persisted |
| 17 | U1-5 問題結構 | 503 activity_supply_unavailable | model-selection; no binding created |

The 12 Nginx 502 events are present in the clone Web error log. The Runtime returned a valid Surface internally before Nginx rejected its headers. A separate direct Runtime header sample for U1-3 coprime had status 200, 4117 header bytes, and 3870 Server-Timing bytes.

## Exact Family availability in the 18084 backup

Counts are distinct issued Activity IDs and distinct Evidence Activity IDs for the one active learner/release. “Pending” means issued with no Evidence yet.

| Family | Pool | Issued | Evidence activities | Pending | Unissued |
|---|---:|---:|---:|---:|---:|
| U1-1 classification-transfer | 10 | 10 | 9 | 1 | 0 |
| U1-1 direct-prime-composite-classification | 18 | 18 | 17 | 1 | 0 |
| U1-1 divisibility-composite-screening | 10 | 2 | 2 | 0 | 8 |
| U1-2 factor-tree | 10 | 4 | 1 | 3 | 6 |
| U1-2 factorization-reconstruction | 10 | 4 | 2 | 2 | 6 |
| U1-2 prime-factor-selection | 10 | 0 | 0 | 0 | 10 |
| U1-2 prime-factorization-production | 10 | 0 | 0 | 0 | 10 |
| U1-2 short-division | 10 | 0 | 0 | 0 | 10 |
| U1-3 coprime-classification | 10 | 2 | 0 | 2 | 8 |
| U1-3 direct-greatest-common-factor | 10 | 8 | 2 | 6 | 2 |
| U1-3 given-prime-factorization | 10 | 0 | 0 | 0 | 10 |
| U1-3 method-selection | 10 | 0 | 0 | 0 | 10 |
| U1-3 prime-factorization-method | 10 | 0 | 0 | 0 | 10 |
| U1-3 short-division-method | 10 | 0 | 0 | 0 | 10 |
| U1-4 bounded-common-multiples | 10 | 1 | 0 | 1 | 9 |
| U1-4 coprime-product | 10 | 2 | 0 | 2 | 8 |
| U1-4 direct-least-common-multiple | 10 | 0 | 0 | 0 | 10 |
| U1-4 given-prime-factorization | 10 | 0 | 0 | 0 | 10 |
| U1-4 method-selection | 10 | 0 | 0 | 0 | 10 |
| U1-4 prime-factorization-method | 10 | 0 | 0 | 0 | 10 |
| U1-4 short-division-method | 10 | 0 | 0 | 0 | 10 |
| U1-5 method-selection | 10 | 1 | 0 | 1 | 9 |
| U1-5 model-selection | 10 | 10 | 9 | 1 | 0 |
| U1-5 problem-structure-recognition | 10 | 0 | 0 | 0 | 10 |
| U1-5 second-step-reasoning | 10 | 2 | 0 | 2 | 8 |
| U1-5 selected-model-execution | 10 | 0 | 0 | 0 | 10 |

The Browser clone's post-run SQLite has 84 bindings, 46 Evidence rows, integrity ok. The 12 added browser bindings are orphaned by the Nginx 502s; one extra same-origin internal header probe added one additional diagnostic binding. No new Evidence was written. This clone is preserved separately from the original 18084 database.

## UI and service evidence

- The U1-1 factor-structure screenshot in the browser tool output showed the “Learning Kernel 正在補充已驗證的練習…” wait and an enabled “送出作答” button; after retries, it showed the no-activity error.
- Back from Activity navigated to Today. Reopening Journey kept Math selected and the last Place checked, but required an extra navigation.
- Original 18084, 8080/8081/8084 databases and containers were not changed after taking the backup.
- Root source code was not modified during diagnosis. PR #3 remains Draft; SDK PR #335 remains Open.
