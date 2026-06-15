# Template: Car Evolution Chart (🅿️ Node Format)

## When to Use
- 呈現單一品牌或系列嘅進化圖譜（Top N 排名）
- 需要馬力排序、年份比較、規格展示
- 所有汽車品牌進化視頻嘅標準格式

## ⚠️ 絶対規則
1. **絕對唔准用 TABLE**（Telegram 唔支援 pipe table）
2. 所有資料必須經過 research核查，唔准憑空砌造
3. HP 數字一定要放型號後面最後

---

## 標準標題格式

```
🏎️ [品牌] / [系列] [定位] Top [數量]｜馬力排序（由高至低）
```

**範例：**
```
🏎️ McLaren / Ultimate Series 旗艦巔峰 Top 8｜馬力排序（由高至低）
🏎️ Porsche / 911 傳奇跑車 Top 5｜馬力排序（由高至低）
```

---

## 🅿️ Node 標準格式（每個車型一行）

```
🅿️ #N: 型號 — HP數字
• 年份: YYYY–
• 顏色: 名稱 → #HEX
• 引擎: 排量 + 類型 + 混能說明
• 馬力: 數字 HP | 扭力: 數字 Nm
• 0-100: X.Xs
• 極速: XXX km/h
• 車重: X,XXX kg
• 傳動: AWD/RWD/FWD | 變速箱類型
• 特色: 【一句核心定位】描述 + 限量/特別技術
• 🔍 外觀: https://www.google.com/search?tbm=isch&q=[車型+年份]
§
```

**嚴格規則：**
- HP 數字放最後（如：`W1 — 1,258 hp`，唔係 `1,258 hp W1`）
- 每個 Node 用 `§` 分隔
- 🔍 外觀連結係 Google Image Search，唔好自己砌 URL

---

## 核查清單（出圖前必須全部通過）

### 資料核查
- [ ] 每個車型有年份（year_start）
- [ ] 每個車型有馬力 HP（必須 50 ≤ hp ≤ 2000）
- [ ] 每個車型有引擎排量
- [ ] 每個車型有傳動配置（RWD/AWD/FWD）
- [ ] 馬力數字有 source（官方網站優先）

### 格式核查
- [ ] 標題係 `🏎️` 開頭
- [ ] 冇 pipe table（|）
- [ ] 每個 node 有 `§` 分隔
- [ ] HP 放型號後面最後
- [ ] 每個 node 有 🔍 外觀連結
- [ ] 數字使用千分位（如 1,258，唔係 1258）

### 驗證核查
- [ ] HP 範圍正常（50-2000）
- [ ] 年份合理（1885 至 current_year+2）
- [ ] 0-100 數字合理（< 30s）
- [ ] Google Image Search URL 格式正確（`tbm=isch&q=`）

---

## 已知數據問題（必須避開）

以下車型喺舊檔案入面有錯誤 HP，核查時要特別注意：

| 車型 | 舊檔案寫法 | 正確 HP |
|------|-----------|---------|
| Singer DLS Turbo | 710 HP | ~500-520 hp |
| Gordon Murray T.50 | 725 HP | ~663 PS ≈ 654 hp |
| Ferrari LaFerrari | 936 HP | 963 cv combined |
| McLaren P1 | 986 HP | 916 hp combined |

---

## 標題長度規則

- 標題 ≤ 40 字
- 加入年代範圍 `(YYYY-YYYY)` 可以 +5.4X viral
- 加入數字（如 `#1`、`Top 5`）可以 +35% viral

**範例：**
```
✅ 911 GT3 RS Evolution (2010-2022) 🔥
❌ Porsche 911 GT3 RS Car Evolution Chart Complete
```

---

## 出圖前濫查流程

```
1. 確認所有車型年份 ✓
2. 確認所有車型 HP + source ✓
3. 確認所有車型傳動 ✓
4. 確認所有車型引擎 ✓
5. 確認冇 pipe table ✓
6. 確認每個 node 有 🔍 連結 ✓
7. 確認 HP 放最後 ✓
8. 確認數字千分位格式 ✓
9. 確認冇犯已知錯誤 HP ✓
10. 標題 ≤ 40 字 ✓
```

---

## 使用場景

當老闆提「汽車進化圖譜」、「Top 10 馬力排序」、「[品牌] 系列排名」等關鍵字，自動使用呢個模板。