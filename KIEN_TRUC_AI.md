# Tái cấu trúc AI D3KT — kế hoạch

Ngày 11/10/2026. Người dùng: "đã đến lúc tái cấu trúc cách AI hoạt động để có thể chơi tốt, không thể mãi fix từng tí một".

## 1. Vì sao phải làm lại

Hiện trạng `launcher/d3kt.py`:

| | |
|---|---|
| Kích thước | 3 390 dòng, **1 class `Brain` với 127 hàm** |
| Trạng thái | 65 chỗ gắn tạm kiểu `getattr(h, "behind_t", None)`, `h.__dict__.setdefault("pst", {})` — không ai biết một đàn hươu / một con voi đang ở trạng thái nào nếu không đọc hết code |
| Phân công dân | rải ở 6 nơi: `desired_role`, `allocate`, `assign_leads`, `helpers`, `defenders`, `retreat_until`, `berry_six`… Mỗi luật mới của người dùng ("6 dân quả trước", "dân thứ 9 mới được săn") phải vá 3–5 chỗ, và đã sót nhiều lần (dân quả bị kéo đi giết voi, dân dò bị kéo đi câu) |
| Hai vòng điều khiển | tick 0.5 s (não) và 20 Hz (micro) cùng sửa một đống trạng thái, không rõ ai sở hữu gì |
| Thử nghiệm | mỗi thay đổi cần 10–20 phút arena; các việc khó nhất (lùa hươu, câu voi) không thể thử nhanh |

Kết quả: câu voi 12/12 sau 6 lô vá; lùa hươu vẫn ~1/4 lần về nhà sau 2 ngày vá; mỗi vá lại sinh lỗi mới.

Nhận định của người dùng đúng: phần **vĩ mô** (build order, kích đời, kinh tế đời 3) là luật "nếu–thì" thuần, đã đủ kiến thức để viết thành bảng. Phần **vi mô** (lùa hươu, câu voi) không phải "nếu–thì" mà là **điều khiển** chống lại độ trễ lệnh và vật lý game — cần mô phỏng để chỉnh, không thể chỉnh bằng arena.

## 2. Nguyên tắc

1. Tách ba tầng: **biết gì** (world) → **quyết định gì** (plan + jobs) → **làm thế nào** (tasks).
2. **Một bảng phân công duy nhất.** Mọi luật "ai làm gì, khi nào" của người dùng là một dòng trong bảng, không phải một `if` rải rác.
3. **Mỗi việc là một máy trạng thái có tên.** Lure, HerdPush, Scout, Build, Gather, Flee: có `state`, `tick()`, `micro()`, `done/failed`, sở hữu dân của nó. Không có `getattr` tạm.
4. **Mô phỏng trước, arena sau.** Lùa hươu / câu voi chỉnh trong mô phỏng 2D (chạy 1 000 lần trong vài giây), arena chỉ để xác nhận.
5. **AI cũ giữ nguyên** (và exe hiện tại) cho đến khi AI mới thắng nó trong arena.

## 3. Kiến trúc

```
launcher/
  gamestate.py  aoemem.py  inject.py  pathing.py  walling.py  placement.py   (giữ nguyên)
  d3kt.py                                                                    (AI cũ, dự phòng)
  brain/
    world.py     WorldModel: snapshot + trí nhớ (vật gì, thấy ở đâu, lúc nào) + truy vấn
                 (hươu/voi trong tầm, bãi quả, rừng, công trình địch, khu địch làm ăn)
    plan.py      Strategy: giai đoạn (đời 1/2/3) → mục tiêu + bảng "điều kiện → lệnh cấp cao"
                 (build order của người dùng, kích đời, chợ/chuồng, ruộng, chuồng theo số dân)
    jobs.py      Allocator: bảng NHU CẦU có ưu tiên → phân công dân từ đầu mỗi tick, có độ dính
    tasks/       lure.py  herd.py  scout.py  build.py  gather.py  farm.py  flee.py
    military.py  Squad: tìm (quanh công trình đã thấy → cả bản đồ), đánh, về cứu dân
    micro.py     vòng 20 Hz: gọi task.micro() của các task đang chạy (kết nối hook riêng)
    brain.py     tick: world → plan → jobs → tasks → stats/watchdog
  sim/
    sim.py       mô phỏng 2D: dân, hươu, voi, sư tử, rừng, TC; trễ lệnh lockstep
    test_*.py    chạy lùa hươu / câu voi hàng loạt, in tỉ lệ thành công
tools/arena.py, diag.py, compare.py                                          (giữ, thêm --brain new|old)
```

### 3.1 Bảng phân công (jobs.py)

Mỗi tick tính lại toàn bộ phân công từ một danh sách nhu cầu, theo thứ tự ưu tiên. Mỗi nhu cầu: `tên, min, max, ai được nhận (điều kiện), độ dính`. Dân đã làm việc gì thì giữ việc đó nếu nhu cầu còn (độ dính), tránh đổi việc lung tung.

Ví dụ phần đời 1 (toàn bộ luật đã có của người dùng, viết thành bảng):

| Ưu tiên | Nhu cầu | Số dân | Ai | Ghi chú |
|---|---|---|---|---|
| 1 | Nhà đầu | 2 | dân 1–2 | dân 3 đi dò |
| 2 | Quả | 6 | dân 1–6 | **không bao giờ** bị rút đi |
| 3 | Dò | 2 | dân 7, 9 | tới khi biết 5 nguồn thức ăn |
| 4 | Gỗ sớm | 1 → 4 | dân 8, rồi 10+ | nhà thứ 2 do dân 10 xây |
| 5 | Lùa / câu (dẫn) | 1 mỗi việc | **dân ≥ 9**, không dò, không quả | task tự xin |
| 6 | Gỗ ở BS đầu | đúng 6 | bất kỳ ngoài 1–9 | |
| 7 | Ăn thịt ở TC | theo xác | 3 mỗi voi, 2 mỗi đàn | dân mới ra ở TC ưu tiên |
| 8 | Quả bãi 2, BS xa… | | | |

Đời 2/3 là bảng khác (ruộng, vàng = 2 + 2/chuồng, gỗ theo kho, quân).

### 3.2 Task (máy trạng thái)

```
Lure:     provoke → run → kill → eat        (chủ: 1 dân dẫn; chờ: 3 dân; ăn: 3 dân)
HerdPush: approach → circle → push → kill → eat   (1–2 dân lùa; phi 1 giáo/con; chỉ giết sát TC)
Scout:    frontier → avoid lion/gazelle → done khi đủ 5 nguồn
Build:    walk → build → done/failed(retry nơi khác)
Flee:     run → back to work (6 s)
```
Mỗi task tự khai báo nhu cầu dân cho `jobs.py`; task hỏng thì trả dân, không để dân đứng.

### 3.3 Mô phỏng (sim/)

Thông số đã đo trong 894 lượt hươu / 22+ lượt voi / log arena:

| | |
|---|---|
| Hươu | 8 máu; bỏ chạy khi dân vào ~2.1 ô (1.3–2.9); nhảy ~2.75 ô trong 1.7 s, thẳng ra xa dân (sai ~8°) |
| Voi | 45 máu; chạy nhanh bằng dân; húc từ ~2 ô, 10 máu/phát; bỏ đuổi khi > ~4.4 ô |
| Dân | 25 máu; giáo 4 máu; dân đã dừng cần 2–3 s game mới chạy lại |
| Lệnh | tới game trễ ~1 s game ở x1 (lockstep); x3 trễ gấp 3 |
| Sư tử | kích hoạt tấn công ~7 ô |

Mô phỏng chạy cùng code task thật (task nhận một giao diện `world/orders` giống hook). Mục tiêu trước khi lên arena: lùa đàn 3–5 con từ 15–25 ô về sát TC **> 80 %**, câu voi **> 90 %, 0 dân chết**.

### 3.4 Kho kiến thức và chiến thuật (yêu cầu bổ sung 11/10/2026)

Người dùng: AI phải **tự tổng hợp và ghi nhớ mọi tương tác, thông số trong game**, rồi tự chọn cách
chơi tối ưu theo luật D3KT: lùa hươu / câu voi thế nào, đánh / thủ / phát triển, chọn binh chủng theo
tình hình. Chỉ chơi 2 đội, nên **biết đối thủ là ai** (nền văn minh, điểm mạnh yếu) ngay từ phòng chờ.

```
brain/knowledge.py   số đo (tốc độ, tầm, sát thương, bán kính sợ, trễ lệnh), chỉ số unit / công trình /
                     công nghệ, bonus từng nền văn minh, bảng khắc chế (phù thủy ↔ ..., cung ↔ chém, lạc đà ↔ ngựa)
brain/tactics/       mỗi chiến thuật là 1 module "điều kiện → hành động", bật/tắt theo kho kiến thức:
   counter_priest    đối thủ Choson / Yamato / Minoan / Greek (quân mình không chống được phù): 1–2 nhà phù, kẹp phù thủy
   army_mix          khi nào chém, khi nào cung, theo quân đối thủ đang có
   siege             nhà đối thủ bo kín mà kinh tế hơn mình: đánh dồn dập hơn, dân lên xây BK gần nhà địch ra cẩu đá
   dodge             đạo cung của mình đấu cung địch: unit bị bắn chạy ngang qua lại cho tên trượt (điều quân)
   age4              không kết thúc được ở đời 3 → lên đời 4
```
Mỗi module chỉ đọc `world` + `knowledge`, trả về yêu cầu cho `plan` / `jobs` / `military`; thêm chiến thuật
mới = thêm 1 file, không sửa lõi. Kho kiến thức được bổ sung dần từ bản ghi (như `speed_study.py`,
`elephant_study.py`, `gazelle_study.py` đã làm).

### 3.5 Vùng cấm (reservation)

`world` giữ danh sách vùng đang được một task dùng (bầy hươu đang lùa, voi đang câu, đường về). `jobs`
không gửi dân khác vào vùng đó; dân đang đi qua được rẽ vòng. Thay cho `keep_off_herd` vá tay.

## 4. Thứ tự làm

| Bước | Việc | Tiêu chí xong |
|---|---|---|
| 1 | `sim/` + chuyển Lure, HerdPush thành task, chỉnh trong mô phỏng | lùa > 80 %, câu > 90 % trong sim; 1 lô arena xác nhận |
|   | **Kết quả 11/10/2026:** câu voi 200/200, 0 dân chết, 40 s/con; lùa đàn 95/100 với 2 dân (1 dân: 56 % → luật: luôn 2 dân). Số đo mới: dân 1.10 ô/s, voi 1.00, hươu nhảy 1.7–2.1, ngựa dò 1.87, ngựa chém 2.0; voi húc 10/1 s; thực tế cả nhóm chỉ mất ~10 máu/voi, giết ở 5.4 ô. Đã ghép vào AI cũ qua `brain/adapter.py` để chạy arena. | |
| 2 | `world.py`, `jobs.py`, `plan.py`; chuyển Scout/Build/Gather/Farm; bảng đời 1 | đời 2 trung vị ≤ 10:00 trong arena (AI cũ: ~11:45) |
|   | **Tiến độ 12/10/2026 tối (test ở x2, tiêu chí chặt của bạn):** câu voi trong game x2: lure12 5/5 (voi không tranh), lure13 7/8, lure14 7/10, lure15 4/7, **lure16 7/7 voi chết, 0 dân chết, 6/7 ≤ 4 ô** — mỗi lượt sửa một nguyên nhân cụ thể đọc từ log (voi bị tranh, sư tử, giết một mình, giao voi sát voi, hết giờ phi mồi co lại, chưa có dân chờ, vùng chết 8–9 ô, chữ chi 40° ở x2). Lỗi hạ tầng lớn: log của luồng nhanh bị nuốt → mọi chẩn đoán vi mô trước đó đều mù. Lùa hươu trong game (log GAZDEAD mới): 12/13 con chết ≤ 4 ô, pha giết đã đúng; pha lùa chậm (kẹt 40 s, 127 s/đàn 4 con) → việc kế tiếp, có HERDDBG mỗi 5 s để đo. Chạy dân giờ đứng trên mọi việc (adapter bỏ lệnh cho dân đang chạy). Bài học: sim x2 không phải trọng tài cho pha giết (dân chờ chết trong sim, không chết trong game); chỉ sim x1 + arena thật. | |
|   | **Tiến độ 11/10/2026 tối:** `jobs.py` (Allocator), `plan.py` (bảng đời 1/2/3), `brain.py` NewBrain (kế thừa Brain cũ, chỉ thay phân công dân), `world.py`, `knowledge.py`. Arena 20 phút, x1.5, cùng task săn mới: **AI cũ** 8 AI: đời 2 trung vị 10:51, đời 3 7/8 (12:21…17:15), câu voi 16/16, lùa đàn 12/12 về nhà; **AI mới** 8 AI: đời 2 11:03, đời 3 8/8 (12:48…19:35). Phần thắng lớn là task săn (sáng cùng ngày đời 3 chỉ 0–4/12); bảng phân công chưa hơn allocate cũ — đang chỉnh (dân dư → dò 2, không đổ vào gỗ; không bỏ đàn oan; đàn kẹt ≤ 8.5 ô thì giết). **Sau sửa (new4/new5, 20 AI):** đời 2 trung vị 10:15–10:18 (AI cũ 10:51), đời 3 17/20, chờ thực sau 25 dân 94 s (cũ 125). **Exe 20:00 dùng AI mới mặc định** (`AOESOLO_BRAIN=old` để quay lại). Điểm yếu tiếp theo: pha đời 2 (hết thực gần → 19–25 dân chặt gỗ, 800 thực mất 4–8 phút; người chơi 175 s) → đã thêm săn xa / dò tiếp ở đời 2, gỗ 4 trước săn, 6 dân gỗ cố định. Các lô 12 AI trong ngày (đời 2 trung vị): new2 11:03, new3 11:09, new4 10:18, new5 10:15, new6 10:40, new7 11:13 — **nhiễu giữa các lô (bản đồ) ≈ ±30 s, lớn hơn hiệu ứng của từng sửa đổi**; AI cũ cùng ngày 10:51 / 11:43. Kết luận: AI mới ≈ AI cũ về đời 2, hơn về tỉ lệ lên đời 3 (10/12 vs 7/8) và săn. Bước tiếp theo không phải chỉnh bảng nữa mà là **đo trong game thật vì sao lùa đàn "kẹt" 16/31** (mô phỏng chỉ 5 %): trích từ .aoerec vị trí dân lùa / hươu trong cửa sổ lùa, so với mô phỏng, rồi sửa mô phỏng cho khớp. **Đã đo (tools/push_study.py):** vật lý hươu giống hệt giữa AI và người (sợ ở 2.0/2.1 ô, nhảy 2.73/2.75, lệch 8°); hươu phản ứng trong 2.5 s: 67 % cả hai; góc dân so với hướng về nhà khi hươu nhảy: AI 99°, người 107° (không ai đứng thẳng sau); cú nhảy về phía TC: AI 48 %, người 57 %; "đứng kẹt" AI 102 vs người 36. Mô phỏng với trễ 1.5 s (arena x1.5): lùa 87 %, câu voi 100 % nhưng 31 dân chết khi giết → ở x1.0 của người dùng game thật sẽ tốt hơn arena. | |
| 3 | `military.py`, bảng đời 2/3, Flee | kích đời 3 < 13:00 ≥ 50 % trận; đánh dồn dập; dân sống |
|   | **Bắt đầu 11/10 đêm:** `brain/tactics.py` — đọc civ hai bên (player+0x109), nhớ quân địch 2 phút, tương quan lực lượng → thủ / đánh / tích quân, chọn ngựa chém hay lạc đà theo quân địch, nhà phù + 2 phù thủy khi gặp civ phù thủy hoặc thấy phù thủy. Nối vào `army()`, `stables()`, `buildings_program()` của Brain cũ (NewBrain kế thừa). Arena tac6/farm1: civ đọc đúng, chế độ đổi đúng, nhà phù (104) xây được, một AI quét 20 dân AI khác. **Thêm 12/10 đêm:** soi bảng thành tích (enemy_all), raid/assault, xông vào cung, dân chạy theo vùng, kế hoạch công nghệ đọc trạng thái nghiên cứu (Bánh xe trước), tỉ lệ dân đời 3 theo số BL, ruộng bất tử (Stop lên ruộng + 1 dân; chưa xác nhận được trường thực của ruộng), không còn gì ăn trong 60 ô thì tìm cả bản đồ. **eco9 (12 AI): đời 2 12/12 trung vị 9:59, đời 3 11/12 (13:12…20:00).** | |
|   | **12/10 đêm (02:00):** so bản ghi của chính người dùng (20 ván) với bản ghi arena của AI (cùng tools/learn_rec, ra thư mục tạm): số dân / vai trò từng phút giống hệt, khác ở **thu nhập thực 2 phút trước khi bấm đời 2**: người 7–13 thực/s (7–14 dân ăn đàn / voi cách 30–46 ô cạnh BS), AI 1–4 thực/s. Sửa: đàn xa = săn tập thể (10 dân, BS đóng lúc bắt đầu giết, cả nhóm phi một con, 3 dân/xác xa có BS, tầm 48/75 ô, đời 1 gỗ ≥ 300 → chỉ 5 dân gỗ). Lỗi watchdog TC (mốc cũ không reset khi TC rảnh → mỗi lần dân chết là hủy lệnh tạo dân) sửa. Bảng công nghệ thật từ empires.dat (AoE-MapCap dat.py): 77 công nghệ, tên / nhà / giá / điều kiện → `knowledge.TECHS`, research_plan dùng đúng nhà và giá (chừa 120 thực, 140 vàng). "Điều quân": cung bị bắn thì bước ngang 2.5 ô (luân phiên trái/phải) rồi bắn tiếp. Lô night1 (trận 1, code cũ hơn): đời 2 trung vị 10:24, đời 3 4/4 (13:50–16:08), voi xa giết tại chỗ 2/2, BS thịt xa 3, nghiên cứu 9 lần (Tool Working, Leather Mounted). Đang chạy: night2 (chiến thuật cung / BK / đời 4), night4 (12 AI với sửa kinh tế đêm). | |
|   | **12/10 đêm (04:30):** lô night2 (12 AI, 24 phút) đời 2 trung vị 11:40 — **bị nhiễu bởi lỗi hồi quy** của bản vá săn tập thể (mở rộng điều kiện `eat` thành `kill, eat` làm đàn xa bị đánh dấu "done" ngay khi khuất tầm nhìn; sửa 03:27). night4 (12 AI, 32 phút, code sạch): đời 2 trung vị 11:04, đời 3 12/12 (14:20–19:36), 25 dân lúc 8:22 rồi chờ thực 160 s. Nguyên nhân còn lại trên bản đồ nghèo: AI coi 17 dân gỗ là đủ việc (không tìm thực xa), BS gỗ đến muộn vì chỉ 4 dân gỗ (một AI 1356 thực không bấm được đời 2 vì chưa có BS) → đã sửa 03:45–04:17 (thiếu việc săn tính theo 7 dân gỗ, 6 dân gỗ trước BS, bấm đời 2 không cần BS khi thực ≥ 600, gỗ ≥ 300 thì dân dư đi ăn thay vì chặt). Nhà phù 19 lần, BK + cẩu đá 1 lần, nghiên cứu theo tên (Tool Working, Leather…), 0 lỗi tick. Ruộng: số ruộng còn sống ổn định ≥ 14 phút khi không bị đánh (chưa thấy hết hạn), hiệu ứng Stop chưa xác nhận (+0..+8 thực/6 s). Lô night5 (24 phút ×3) chạy 04:40–05:35 với toàn bộ sửa đổi. | |
|   | **12/10 sáng (05:20):** night5 (12 AI, 24 phút, đủ mọi sửa đổi đêm): đời 2 12/12 trung vị 10:37 (4 AI ở mức người chơi: 7:51, 8:40, 9:34, 9:41), đời 3 12/12 (14:18–20:46), 25 dân lúc 8:37 rồi chờ 106 s, lùa đàn về nhà 18/24, 1 lỗi tick (đã sửa). Tổng hợp các lô sạch trong đêm: eco9 9:59 / night1 10:34 / night4 11:04 / night5 10:37 → sai số bản đồ lớn hơn hiệu ứng từng sửa; phần còn lại là bản đồ nghèo (không đàn trong 40 ô, hết quả ở phút 8) và pha đời 2→3 (215–350 s so với 173 s của người chơi). Exe build 04:31 và build lại sau night5. | |
|   | **12/10 sáng (10:00):** theo tư duy kinh tế của người dùng (LUAT 2b): lùa chỉ đàn ≤ 16 ô (xa hơn → BS), giết ở TC ghép ≥ 2 dân/con có dân quanh TC vào giúp, BS thú kéo về phía vàng/gỗ gần, dò tới khi tổng thực đã biết ≥ nhu cầu đời 2+3, dân thừa đi dò (tối đa 4) không chặt gỗ, xác ở TC ≥ 2 dân/xác. Lùa hình học (herd.py push_point: điểm bước vào cực tiểu độ tản, lái theo điểm rơi dự đoán, lao chỉ phi con thẳng trước): mô phỏng 12–16 ô có dân TC giúp giết — 1 dân 72 %, 2 dân 95 % (74 s) → giữ 2 dân. Đo từ bản ghi người dùng: tốc độ gặt hiệu dụng quả 0,45 / thịt 0,43 / ruộng 0,41 / vàng 0,45 / gỗ 0,58, gặt tại chỗ ~1,05/s; xác hươu/voi là đồng hồ 300/400 s. Lô human1 (12 AI, 24 phút): đời 2 12/12 trung vị **10:05**, 5 AI ≤ 9:35 (8:32, 8:40, 8:53, 9:01, 9:35), đời 3 12/12 (13:54–17:52), chờ thực sau 25 dân 73 s (đêm: 98–160). Đàn kẹt rừng/mép giờ không lùa lại mà BS ăn tại chỗ. Exe build 10:01 / 10:03. | |
| 4 | arena so sánh AI mới / AI cũ 10 trận; **đổi exe** khi AI mới không thua ở kích đời và hơn ở săn | |

Mỗi bước có lô arena riêng; AI cũ vẫn là exe cho người dùng tới bước 4.

## 5. Giữ nguyên

`gamestate`, `aoemem`, `inject`, `pathing`, `walling`, `placement`, toàn bộ launcher/lobby/orchestrator, arena/diag/learn_*, hook DLL. Các số đo và luật trong `LUAT_D3KT.md` là đầu vào của bảng trong `plan.py` / `jobs.py`.
