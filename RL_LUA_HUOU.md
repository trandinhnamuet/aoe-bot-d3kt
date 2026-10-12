# Học tăng cường cho bài lùa hươu (bắt đầu 12/10/2026 tối)

Viết cho: bạn (người dùng), để theo dõi cách đặt bài toán, cách huấn luyện và kết quả.

## 1. Bài toán và chuẩn pass

- **Chuẩn pass (bạn đặt):** *mọi con* trong đàn chết cách mép nhà chính ≤ 4 ô, không con nào chết ngoài đồng, cả lượt ≤ 120 s.
- **Phạm vi RL:** chỉ **pha lùa** (từ lúc hai dân lùa rời nhà chính tới khi đàn vào trong 4 ô mép TC). **Pha giết** giữ mã tay hiện có (ném từ phía ngoài đồng, hai dân cùng ném, mục tiêu dính) vì trong trận thật nó đã đúng (lure16: 12/13 con chết ≤ 4 ô). Các luật dừng của game (kẹt 40 s không tiến, hết 150 s, mất dấu) cũng áp trong môi trường để chính sách học đúng điều kiện trong game.
- **Baseline cần vượt** (mã tay trên cùng 40 tập đánh giá, 2 dân lùa + 2 dân giúp ở TC): trễ lệnh x2: **1/40** đạt chuẩn, 45/148 con chết ≤ 4 ô, 88 con còn sống khi hết giờ; x1: **4/40**, 70/148.

## 2. Môi trường (`launcher/rl/herd_env.py`)

- Mô phỏng 2D có sẵn (`sim/sim.py`): hươu với vật lý đo từ bản ghi (sợ ở ~2,1 ô, nhảy 2,75 ô, tốc độ 1,85, nghỉ 0,4 s), dân 1,10 ô/s, giáo 4 máu/3 ô, rừng ngẫu nhiên, nhà chính 3×3, **trễ lệnh lockstep** 2 s (x2, 70 % số tập) hoặc 1 s (x1, 30 %).
- Mỗi tập: đàn 3–5 con cách TC 12–25 ô; 2 dân lùa xuất phát ở TC; 2 dân giúp đứng ở TC cho pha giết.
- Một quyết định mỗi **0,5 giây-game** cho **mỗi dân lùa**; cùng một mạng dùng cho cả hai dân (quan sát lấy theo góc nhìn từng dân), thưởng chung cho cả đội.

### Quan sát (60 số, `rl/features.py`)
Tất cả trong **khung lùa**: gốc = tâm đàn, trục x = hướng lùa về TC (đã né rừng), trục y = pháp tuyến, **lật gương** để dân đang xét luôn ở phía y ≥ 0 (đối xứng trái/phải, bớt một nửa việc học).
- 5 con hươu (xa TC nhất trước): toạ độ (x, y), đang nhảy hay không, độ tươi của vị trí (1 = đang thấy, 0 = nhớ từ 8 s trước);
- số con, bề rộng đàn theo hai trục, khoảng cách tâm đàn tới mép TC;
- vị trí dân mình, khoảng cách tới con gần nhất, vị trí dân lùa kia;
- lưới 5×5 ô đi được quanh dân (theo khung), 3 ô phía trước đàn có đi được không;
- thời gian đã dùng / 150, trễ lệnh / 2.

### Hành động (51)
- 49 điểm đi tới, đặt **tương đối với con hươu cuối** (xa TC nhất): dọc ∈ {−4, −3, −2, −1, 0, +1, +2} ô, ngang ∈ {−4, −2, −1, 0, +1, +2, +4} ô (trong khung đã lật; ±4 để đi vòng đàn ngoài bán kính sợ);
- 1 phát giáo nhắc vào con cuối (chỉ khi nó còn đầy máu, mỗi con một lần; môi trường tự gửi lệnh dừng đúng lúc như mã tay để không có phát thứ hai);
- đứng lại.

### Thưởng
- Mỗi bước: **+ số ô tâm đàn tiến gần mép TC** (động lực chính), +0,03 cho mỗi dân đang đứng sau con cuối trên đường lùa (0,5–3,5 ô sau, lệch ngang ≤ 1,5; kiến thức sẵn có, nhỏ để không lấn át), −0,02 (thời gian), −0,1 × phần bề rộng đàn vượt 4 ô, **−1 mỗi con tách đàn** (xa tâm > 7 ô, tính một lần), **−6 mỗi con chết ngoài đồng** (> 6,5 ô).
- Kết thúc: **+4 mỗi con chết ≤ 4 ô**, +1 mỗi con chết 4–6,5 ô, **−3 mỗi con còn sống**, **+8 nếu đạt chuẩn** (mọi con ≤ 4 ô và ≤ 120 s).
- Kết thúc tập: hết hươu, hết 150 s, kẹt 40 s không tiến (luật game), hoặc pha giết tay bỏ cuộc quá 3 lần.

## 3. Huấn luyện (`launcher/rl/ppo.py`)

- PPO, mạng 60→128→128→(51 + 1), tanh; khởi động bằng bắt chước mã tay (`rl/bc.py`: ghi lệnh của HerdPush trong môi trường, ánh xạ về hành động rời rạc gần nhất, cross-entropy 15 epoch); GAE λ 0,95, γ 0,995; clip 0,2; 4 epoch; minibatch 1024; lr 3e-4; entropy 0,01; chuẩn hoá quan sát chạy.
- Môi trường chạy trong **tiến trình con** (`rl/vec.py`, 12 tiến trình × 2 môi trường: ~3 000 bước-môi-trường/giây; chạy tuần tự trong một tiến trình chỉ được ~640), 128 bước mỗi môi trường mỗi lần cập nhật → 6 144 mẫu/lần (torch 2.1 CPU, Python hệ thống; venv của exe không có torch/numpy).
- **Chương trình học theo bậc:** giai đoạn 1 đàn 8–16 ô (dễ, học được động tác lùa cơ bản), giai đoạn 2 tiếp tục từ trọng số đó với 12–25 ô và 70 % x2 (`--dmin --dmax --lag2`, `--resume`).
- Đánh giá mỗi 10 lần cập nhật trên 40 hạt giống cố định ở x2 và x1 (chính sách tham lam); giữ bản tốt nhất theo điểm = pass x2 + 0,5 × pass x1 + 0,2 × tỉ lệ con chết ≤ 4 ô.
- Lệnh: `python -m rl.ppo --minutes 90 --envs 16 --steps 128` (log `rl/policies/train1.log`); baseline: `python -m rl.baseline 40`; đánh giá: `python -m rl.evaluate rl/policies/herd_push.npz 40`.

## 4. Nối vào game

- `brain/tasks/herd_rl.py`: `HerdPushRL` kế thừa `HerdPush`, thay phần điều khiển pha lùa bằng chính sách (cùng khung / quan sát / hành động), giữ nguyên tick (luật kẹt, hết giờ, chuyển sang giết) và pha giết tay.
- Chính sách xuất ra JSON (`rl/policies/herd_push.json`), suy luận bằng Python thuần (exe không có numpy); `build.py` đóng gói file này; `d3kt` dùng `HerdPushRL` khi file tồn tại, tắt bằng `AOESOLO_HERD_RL=0`.
- Chỉ bật mặc định sau khi arena x2 cho thấy hơn mã tay theo log GAZDEAD / HERDOK.

## 5. Kết quả

| mốc | x2 (40 tập) | x1 (40 tập) | ghi chú |
|---|---|---|---|
| mã tay (baseline) | 1/40 đạt chuẩn, 45/148 con ≤ 4 ô | 4/40, 70/148 | nhiều đàn còn sống khi hết 150 s |
| lần 1: 16 môi trường trong một tiến trình, 573 k mẫu / 10 phút | 0/40, 2/148 con | 0/40 | quá chậm (640 bước/s), chưa học được gì; bỏ, chuyển sang tiến trình con |
| lần 2, giai đoạn 1: 24 môi trường / 12 tiến trình con (3 000 bước/s), đàn 8–16 ô, 50 % x2, 40 phút, 10 M mẫu | 0–1/40, ≤ 9/148 con | 0–1/40 | có học (thưởng −28 → −9, entropy 3,3 → 2,5) nhưng chưa khái quát sang 12–25 ô; 27 hành động quá hẹp (±2,5 ô ngang) để đi vòng đàn |
| bắt chước mã tay (BC): 600 tập, 219 k mẫu, lưới hành động mở rộng 7×7 (dọc −4…+2, ngang ±4) | 0/40, 5/148 | 1/40 | khớp 48 % hành động (mã tay dựa trạng thái nội bộ); dùng làm điểm xuất phát |
| lần 3, giai đoạn 2: PPO từ BC, 12–25 ô, 70 % x2, thêm thưởng "đứng sau con cuối" (+0,03/bước), 28 phút, 2,5 M mẫu | 0/40, 0–2/148 con, tập kết thúc ~53 s vì kẹt | 0–1/40 | thưởng −14,6, entropy 1,3 → 2,3: PPO xoá dần phần bắt chước mà chưa tìm ra động tác lùa |

**Kết luận 12/10/2026 21:55 — bạn quyết định dừng huấn luyện lùa hươu.** Sau ~13 M mẫu (3 lần chạy) chính sách vẫn kém mã tay (x2: 0/40 so với 1/40; con chết ≤ 4 ô 0–9/148 so với 45/148). Nguyên nhân chính: thành công quá hiếm để tự khám phá (ngay mã tay cũng ≤ 10 %), luật kẹt 40 s cắt tập sớm, trễ lệnh 2 s làm khó gán công cho hành động. Mã môi trường / PPO / BC / task trong game giữ lại trong `launcher/rl` và `brain/tasks/herd_rl.py` nhưng **tắt mặc định** (chỉ bật khi `AOESOLO_HERD_RL=1` và có file chính sách). Hướng còn mở nếu quay lại: học tham số của bộ điều khiển tay bằng CEM/ES trên cùng hàm điểm (rẻ, chắc hơn), hoặc PPO với tắt luật kẹt 30 s đầu, quyết định mỗi 1 s, thưởng định hình theo khoảng cách tới điểm đứng lý tưởng, chạy nhiều giờ.

*(cập nhật khi có kết quả)*
