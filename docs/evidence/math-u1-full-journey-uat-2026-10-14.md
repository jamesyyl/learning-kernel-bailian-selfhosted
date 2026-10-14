# Math U1 全 Journey Docker／SQLite UAT — 2026-10-14

狀態：**BLOCKED（供應範圍部分完成；不宣告 FULL SUPPLY PASS）**。測試只使用獨立 Compose 專案與 SQLite 副本；8080、8081、8084 未變更。Cloudflare／D1／Workers／Pages 不在本輪範圍。

## 根因與修正

- Runtime 原先先選一個 LK 合法路線，再只查該 Family 的 Pool；該 Family 耗盡時，即使同一 Map 決策有其他 Pack 合法且有供應的路線，也直接回 503。現在 canonical LK 將無未簽發、已驗證 Pool 候選的路線標記為 `EXECUTION_BLOCKED`，再由 LK 在剩餘合法路線中重選。Learner 明確選擇的 Family 不會被偷換；全部合法路線耗盡時回傳 `supply_state=all_legal_routes_exhausted`。
- Nginx upstream 回應標頭可達 4.1 KB，原 4 KB 預設緩衝造成 502；API location 現在配置 16 KB header buffer 與 response buffers。新 Docker／Chromium 17 Place 回合未再見 502。
- Surface 載入期間隱藏並停用「送出作答」；前端辨識 JSON 503、HTML 502、Runtime 錯誤與有限耗盡。Activity「返回」回 Learning Journey，保留數學與使用者原先選取 Place。
- Pool 中因數樹的獨立驗證允許合法因數樹，但共用文字評估器原先只接受唯一 canonical 字串。現在遇到因數樹格式會在 Runtime 檢查各父子乘積與質數葉節點；一般自由文字仍使用精確比對。前端沒有判分或改寫答案。

完整前置診斷與修正前 17 Place 故障矩陣見[診斷報告](math-u1-journey-uat-diagnosis-2026-10-14.md)。

## Docker／SQLite 證據

- Pack：0.3.4，digest `sha256:aea207d8eb59619373203dcfaa74614b4b1b6273953257620be54956f6b1cc98`。
- 18084 修正前一致性備份 SHA-256：`ee31786da9d9a096057f228801ea3ff4b3331c88d444523f3b9e92ea21d6ae31`；schema rev4、Pool 268、bindings 71、Evidence 46、Attempt Chains 46、response cache 46、`integrity_check=ok`。
- 18089 Journey 副本由該備份逐位元複製（初始 hash 相同）。17 Place 回合後，一致性備份 SHA-256：`c82663679cc98347312ac9ab92f83255873d40aca92c01976a5653e4bfb06fd2`；Pool 268、bindings 87、Evidence 66、Attempt Chains 66、response cache 66、`integrity_check=ok`。
- Runtime／refiller 重啟續學後副本 SHA-256：`6825aced75adb8291748b1e52b277d9200bfa7f5863dfc4d9758c431f90da6cd`；Pool 268、bindings 88、Evidence 67、Attempt Chains 67、response cache 67、`integrity_check=ok`。
- Nginx `nginx -t` 成功。測試專案只使用獨立 image tags 與 18088／18089／18090；原 18084 learner Evidence 尚未被本輪測試請求寫入。
- 更新 18084 前再做一致性備份；SHA-256 仍為 `ee31786da9d9a096057f228801ea3ff4b3331c88d444523f3b9e92ea21d6ae31`，Evidence canonical rows digest `d91a268b45e6c47ed453a915623460f19d81dcd5495129203c3ddf5958048a45`。更新前 Pool 268、bindings 71、Evidence 46、Attempt Chains 46、response cache 46。
- 18084 現已使用 Runtime source SHA `851698a7a79d7a6942692e97f8a54f025d09a9c2`，Runtime/Web/Refiller healthy，schema rev4；`/api/ready` 回 200，Web image 內 `nginx -t` 成功。以該真實 learner 明確要求已耗盡的 direct-classification Family，回 503 `requested_family_exhausted`，沒有建立 binding。再由 Chromium 的 Learning Journey 普通路線進入 U1-5 問題結構，Live Runtime 回 200 Activity `generated/u1-5/family/problem-structure-recognition/variant-0`。Activity「返回」回 Journey 並保留 Math／原選取 Place；重新進入時 0 個新 `/surface` 請求，恢復同一待答 Surface。最終 live counts：Pool 268、bindings 72、Evidence／Attempt Chains／response cache 各 46；Evidence digest 與更新前備份相同。這次安全驗證只新增 1 個待答 binding、沒有提交作答；18084 瀏覽器目前停在該題供使用者體驗。8080／8081／8084 containers 保持原狀。
- 最後兩個一致性 clone snapshot：18089 Journey 副本 SHA-256 `e18be666bb95bb62082c3be2a9f5f9d5cc898dd95a15cccbbe955375a34f9317`（Pool 268、bindings 89、Evidence/attempt/cache 67）；18090 Family／multi-learner 副本 SHA-256 `471704672a20a1b89652dee2e69cbf5f0c3ac4c68041cacbfb9372e16fd213ee`（Pool 268、bindings 113、Evidence/attempt/cache 69／69／70）；兩者 integrity 均為 ok。

## 同 learner、同 SQLite 的 Chromium 17 Place 回合

重現步驟：打開 18089；選數學 → Learning Journey；依表格順序選 Place →「在這裡練習」→ 完成 Surface 中的作答（若 503 則記錄合法封鎖）→ Activity「返回」。同一個 `local-learner-001`、同一份起始 Evidence／bindings 在全程保留。每次 `/surface` status 由該 Chromium tab 的 Network response 記錄；Activity ID 取自實際 Runtime Surface response。

| # | Place | HTTP | Activity ID／合法封鎖 | LK 選定 Family／作答形式 |
|---:|---|---:|---|---|
| 1 | U1-1 合數 | 503 | `all_legal_routes_exhausted`；blocked：`classification-transfer`、`direct-prime-composite-classification` | 該 Place 的兩個合法 Family 都已耗盡；UI 明確提示回 Journey 選其他地點，沒有建立新 Activity binding，送出按鈕隱藏 |
| 2 | U1-1 整數的因數結構 | 200 | `generated/u1-1/family/divisibility-composite-screening/variant-2` | `divisibility-composite-screening`，multi-choice；錯答後 LK 回 202 `incorrect/retry`，正答後回 202 `correct/complete` |
| 3 | U1-1 質數 | 200 | `generated/u1-2/family/prime-factor-selection/variant-0` | `prime-factor-selection`，multi-choice；LK 合法導向 U1-2 質因數，作答 202 correct |
| 4 | U1-2 質因數 | 200 | `generated/u1-2/family/factor-tree/variant-4` | `factor-tree`，text；三次重試後提交 canonical 因數樹，LK 回 202 correct |
| 5 | U1-2 質因數分解 | 200 | `generated/u1-2/family/factorization-reconstruction/variant-4` | `factorization-reconstruction`，math；作答 202 correct |
| 6 | U1-2 原數與質因數結構的等值關係 | 200 | `generated/u1-2/family/factorization-reconstruction/variant-5` | `factorization-reconstruction`，math；作答 202 correct |
| 7 | U1-3 公因數 | 200 | `generated/u1-3/family/direct-greatest-common-factor/variant-8` | `direct-greatest-common-factor`，math；作答 202 correct |
| 8 | U1-3 互質關係 | 200 | `generated/u1-3/family/coprime-classification/variant-2` | `coprime-classification`，single-choice；作答 202 correct |
| 9 | U1-3 最大公因數 | 200 | `generated/u1-3/family/coprime-classification/variant-3` | LK 在合法路線導向 `coprime-classification`，single-choice；作答 202 correct |
| 10 | U1-4 公倍數 | 200 | `generated/u1-4/family/bounded-common-multiples/variant-1` | `bounded-common-multiples`，multi-choice；作答 202 correct |
| 11 | U1-4 互質與最小公倍數的乘積關係 | 200 | `generated/u1-4/family/coprime-product/variant-2` | `coprime-product`，single-choice；作答 202 correct |
| 12 | U1-4 最小公倍數 | 200 | `generated/u1-4/family/coprime-product/variant-3` | LK 在合法路線導向 `coprime-product`，single-choice；作答 202 correct |
| 13 | U1-5 情境答案 | 200 | `generated/u1-5/family/second-step-reasoning/variant-2` | `second-step-reasoning`，math；作答 202 correct |
| 14 | U1-5 方法選擇 | 200 | `generated/u1-5/family/method-selection/variant-1` | `method-selection`，multi-choice；作答 202 correct |
| 15 | U1-5 模型選擇 | 200 | `generated/u1-5/family/method-selection/variant-2` | LK 在合法路線導向 `method-selection`，multi-choice；作答 202 correct |
| 16 | U1-5 模型計算結果 | 200 | `generated/u1-5/family/second-step-reasoning/variant-3` | `second-step-reasoning`，math；作答 202 correct |
| 17 | U1-5 問題結構 | 200 | `generated/u1-5/family/problem-structure-recognition/variant-0` | `problem-structure-recognition`，single-choice；作答 202 correct |

全程 16 個唯一 Surface 成功，1 個真實 Pack／Map 合法封鎖，0 個 Nginx 502；Math、原選取 Place 與 Journey 地圖狀態在返回後保留。表中 Activity ID 均來自 same-origin Runtime response，非前端合成。

## 26 Family、耗盡、重啟與多 learner

- 以 17 Place 回合後的一致性副本、同一 `local-learner-001` 逐一提出 26 個明確 Family exploration。23 個回 200 並取得正確 Family Surface；3 個回 503 `requested_family_exhausted`：U1-1 `classification-transfer`、U1-1 `direct-prime-composite-classification`、U1-5 `model-selection`。完整 status、Activity ID 與 Family matrix 見[JSON 證據](math-u1-family-exploration-after-journey-2026-10-14.json)。Pool 仍 268，refiller 重啟後也沒有超過 Pack 可驗證的 268 個唯一 variant；沒有每次載入重跑 seed。
- 使用者選取已耗盡 Family 時，前端等待有限重試後顯示「目前沒有可用的已驗證活動」，送出按鈕保持隱藏／停用；Journey 的普通 Place 決策會改選仍有供應的 Pack 合法路線，不把明確 Family 選擇偷偷改掉。
- 待答 Surface `generated/u1-2/family/factor-tree/variant-5` 在 Runtime／refiller 重啟前已寫入一個 issue binding。重啟後 Runtime healthy、schema rev4；重新整理並從 Journey 再進該 Place 時，瀏覽器 0 個 `/surface` 請求、畫面恢復同一題，bindings／Evidence 在恢復前仍是 88／66。正答後 LK 回 202 correct，Evidence 到 67。
- 多 learner 驗證在 18090 測試副本上呼叫 canonical Runtime service（Root web host 僅公開 Surface／Observation，不公開 Pack activation admin route）。新 learner `uat-isolation-check-20261014` 從共享 Pool 取得 `classification-transfer/variant-0`（HTTP 200），完成正答後 HTTP 202 correct。主 learner Evidence 保持 68，新 learner 為 1；完全相同作答重送仍回 202，Evidence 數量沒有增加。Pool 仍 268。
- SDK 修正後，在 Docker／Chromium 上輸入另一個合法因數樹 `60=6×10；6=2×3；10=2×5`，Runtime 回 202 correct。通用文字答案仍採精確比對。

## PASS／FAIL／NOT RUN

| 驗收項 | 結果 | 證據／限制 |
|---|---|---|
| SDK supply-aware canonical reroute、明確 Family fail-closed、all-legal-exhausted | PASS | 本機 3 個 Runtime 回歸測試通過 |
| LK 因數樹等價文字 Trusted Evaluation | PASS | SDK trusted-evaluation suite 8 tests；Docker／Chromium 另一個合法樹回 202 correct |
| Docker／SQLite 17 Place same learner UAT | PASS（16 Surface + 1 明確合法封鎖） | 上表；起始 Evidence／bindings 來自 18084 一致性副本 |
| Nginx 大標頭 502 修正與前端錯誤分類 | PASS | Docker Nginx config test 成功；17 次 Place Surface 中 0 個 502；wait/no-supply 時 submit 隱藏 |
| 答錯重試、回答保存、重啟後續答、精確作答冪等 | PASS | Chromium 觀察狀態及 Evidence/cache 計數 |
| 同 learner 26 Family supply | PARTIAL：23／26 可供、3／26 合法耗盡 | Pack 0.3.4 變體上限下沒有無限補題；按要求如實保留阻擋狀態 |
| 多 learner 共用 Pool、Evidence 隔離 | PASS | 同 SQLite 副本，主 learner 68、第二 learner 1，重送不增加 Evidence |
| 同一歷史 learner 新增十個連續活動 | NOT RUN | 本輪 17 Place 歷史 UAT 已新增 16 個完成 Surface；不以舊的空白／分開 learner 測試充當本輪結果 |
| 18084 更新後安全核對 | PASS | Runtime source SHA `851698a`、health 200、Nginx config OK；耗盡請求不寫入，正常 Journey Surface HTTP 200；僅新增 1 個待答 binding，Evidence rows/digest 不變 |
| Root SQLite／refiller／seed／HTTP host 回歸 | PASS | 11 項通過；先前一般 Place 耗盡測試需改為明確 Family exploration，更新後 `test_u1_pool_replenishment.py` 1 passed |
| Cloudflare／Workers／Pages／Access／WAF 專屬測試 | OUT OF SCOPE／NOT RUN | 本輪不修改、不重跑 |

## Git 與交付

- SDK PR #335 保持 Open；最終 Runtime Trusted Evaluation／route SHA：`851698a7a79d7a6942692e97f8a54f025d09a9c2`。
- Root PR #3 保持 Draft、未合併（目前分支 SHA 見 PR #3）；SDK PR #335 head `851698a7a79d7a6942692e97f8a54f025d09a9c2` 保持 Open、未合併。
- Checkpoints：Root diagnosis `a9ec086a4754295ea9c242d865a76734fe3e0d7b`、Root Runtime `76afc58f4b95bda21af93a007ab20a296c49f37c`；SDK initial safe checkpoint `bdc2c3c20a0ed62554e95223aef2b4f1566193df`、SDK pre-API local route checkpoint `c39691052493dcb705ee0a61c0d94851dc90ccae`、SDK evaluator local checkpoint `a021d8497d32e4b43807a55471cbc53388b74792`。

本輪對 18084 只做 Runtime/Web/Refiller image 更新及 no-supply safe check；原始 learner 的 Evidence 與 SQLite 內容未改。`18089` 是供使用者查看 17 Place 後 learner history 的副本；`18090` 是 26 Family 與多 learner 的獨立副本。
