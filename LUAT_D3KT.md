# Luật D3KT và lối chơi của AI trong AoESolo



Tài liệu này ghi lại **luật D3KT ("Đời 3 không thành")**, **các quy tắc bạn đã đặt cho AI** và lối chơi chuẩn D3KT của người Việt mà AI học theo, tính đến 10/10/2026. Đây cũng là những gì brain của bot (`launcher/d3kt.py`) đang làm.



Ký hiệu: **BE** nhà, **BG** kho lương thực (Granary), **BS** kho gỗ/đá/vàng (Storage Pit), **BM** chợ (Market), **BL** chuồng ngựa (Stable), **BB** nhà lính (Barracks), **BA** nhà bắn cung, **TC** nhà chính. Khoảng cách tính bằng ô (tile). "1 móng nhà" = 2 ô, "1 móng nhà chính" = 3 ô.



---



## 1. Luật D3KT (luật chung của trận)



Hai bên cam kết, **cho tới khi một bên phạm luật trước**:



1. Không xây thành, không xây chòi canh.

2. Không nâng cấp/nghiên cứu thành hoặc chòi trong BG.

3. Không tấn công trước khi **kích** lên đời 3 (Bronze). Tính từ lúc bấm nút lên đời, không phải lúc lên xong.

4. Không có quá **1 đơn vị quân** trước khi **lên xong** đời 3.

5. Không dùng dân tấn công dân đối phương trước khi lên xong đời 3.



**Khi đối phương phạm luật trước** (xây thành/chòi, dùng dân đánh dân, có hơn 1 quân hoặc đem quân đánh trước đời 3), AI được **phá toàn bộ luật** và đáp trả bằng mọi thứ: dân đánh lại, xây BB ra quân, đi đánh ngay.



**Bổ sung mới — quyền phản công (không tính là phá luật):**

- Khi bị **đơn vị quân** của đối phương tấn công, AI được phép phản công đơn vị đó, kể cả khi chưa kích đời 3.

- Nếu kẻ tấn công là **một con ngựa dò (Scout) đi một mình** (trong bán kính 10 ô không có quân nào khác của đối phương), **mọi dân trong bán kính 5 ô** quanh chỗ bị đánh sẽ bỏ việc để đánh nó.

- Khi ngựa dò chạy ra **xa hơn 4 ô** khỏi chỗ đó thì bỏ đuổi, dân quay lại việc cũ.

- Ngựa dò tấn công không bị coi là phạm luật (luật cho phép 1 quân trước đời 3). Mọi đơn vị quân khác tấn công trước khi đối phương lên đời 3 thì bị coi là phạm luật.



---



## 2. Lối chơi gốc bạn đưa ra



> Vào game ở đời 1: xin dân liên tục bằng toàn bộ thực đang có. Cứ còn 2 chỗ nữa là chạm giới hạn dân thì xây BE. 3 dân đầu xây BE ngay rồi đi bãi quả đầu. Thấy quả thì xây BG rồi cho 6 dân đầu ăn. Dân 7 đi dò, dân 8 ăn gỗ, dân 9 cũng đi dò, dân 10 xây BE rồi ăn gỗ. Tất cả dân tiếp theo ăn gỗ cho đến khi đủ 120 gỗ thì xây BS đầu cạnh rừng rồi cho 6 dân ăn gỗ. Số dân thừa đi phi hươu/voi, đóng BS ăn, hoặc tìm thấy quả thì đóng BG ăn quả. Dân 7 và 9 dò không ngừng cho đến khi đủ đồ ăn. Đủ 25 dân thì dừng xin dân để kích lên đời 2. Lên xong đời 2 thì đóng BM, BL rồi kích đời 3 luôn khi đủ thực. Chuyển dần dân sang xây ruộng và làm ruộng. Sau đó xin ngựa dò tìm nhà đối phương. Lên xong đời 3 thì xin quân đời 3 (ngựa chém, lạc đà) để tấn công dân đối phương. Thừa lực thì xây thêm nhà quân để ra nhiều quân cùng lúc.



Các mục dưới đây là bản chi tiết hóa và các chỉnh sửa bạn đưa thêm sau đó. Chỗ nào khác với đoạn gốc thì làm theo bản mới hơn.



---



## 2b. Tư duy của bạn về kinh tế đầu trận (12/10/2026) — AI phải làm theo "vì sao", không chỉ "làm gì"

- Vào trận có 3 dân + 200 thực = 7 dân. Mỗi dân quả ăn ~0,95 → **6 dân quả đầu** để TC xóc liên tục và dư một chút (không trễ).
- **Dân 7 và 9 đi dò**, dò muộn thì không tìm đủ đồ ăn. **Chưa đủ đồ ăn cho đời 3 thì chưa dừng dò** (AI: dò tới khi tổng thực đã biết ≥ 500 + 800 + 50 × dân còn thiếu − thực đang có).
- **Dân 8 ăn gỗ** vì lúc đó 8/12 dân và 20 gỗ → kịp 30 gỗ xây BE ở 10/12.
- Gỗ để đủ BE (không kẹt dân) và **BS đầu sớm** (ăn gỗ ở BS hiệu quả hơn hẳn gỗ lẻ quanh TC). Có BS rồi thì **6–7 dân gỗ là đủ tới khi kích đời 3**, còn lại đi làm thực — không bao giờ đổ dân thừa vào gỗ.
- Lùa hươu / câu voi về TC để dồn thực nhanh hơn 30–60 s và tiết kiệm 120 gỗ — **chỉ khi lùa đủ nhanh**. AI lùa yếu thì mặc định **đóng BS ăn tại chỗ**; voi thì câu về (đã ổn). AI: chỉ lùa đàn ≤ 16 ô (người chơi 10–23), xa hơn → BS. Về số dân lùa: mô phỏng 40 đàn 12–16 ô, có 2 dân ở TC giúp giết — **1 dân lùa thành công 72 %, 2 dân 95 %** (74 s mỗi đàn); dân thứ hai mất ~75 s việc (≈ 30 thực) nhưng tránh mất cả đàn, nên AI vẫn dùng 2 dân từ 12 dân trở lên, 1 dân khi đàn < 3 con.
- **BS ăn thú đặt giữa xác và bãi vàng / bãi gỗ gần đó** (nếu có, trong ~10 ô) để sau dùng tiếp.
- **Phi hươu luôn ≥ 2 dân cùng lúc** để chết ngay, không nhảy tản xác (xác xa nhau ăn kém). AI: khi đàn về TC, dân quanh TC (trừ dân quả) vào giúp, ghép ≥ 2 dân một con, con ít máu trước.
- Lùa là bài toán hình học: hươu chạy thẳng ra xa dân, nên **điểm bước vào được chọn để mọi con bị kích đều chạy về phía TC** (cực tiểu độ tản, kích nhiều con cùng lúc khi chúng thẳng hàng, không bao giờ kích con chạy ngược); hươu đang nhảy thì lái theo **điểm rơi dự đoán** (nhảy 2,75 ô thẳng) để lệnh tiếp đi ra khi nó còn trên không (trễ lệnh ~1 s).

**Số đo từ bản ghi của bạn (12/10/2026, 3 ván, 1 600–4 300 chuyến mỗi loại):** tốc độ gặt hiệu dụng mỗi dân tính cả đường đi về chỗ trả (cách bạn đặt BG/BS): quả 0,45, thịt 0,43, ruộng 0,41, vàng 0,45, gỗ 0,58 đơn vị/giây (gặt tại chỗ ~1,05/s với mọi loại — chênh nhau là ở quãng đường về). Xác thú: ô "lượng" của xác là **đồng hồ đếm ngược** (hươu 300, voi 400, giảm 1,0/s dù có ăn hay không) → xác hươu biến mất 300 s sau khi chết, voi 400 s; phải ăn ngay và đông.

**Từ trận solo 12/10/2026 10:16 (bạn Minoan, AI Phoenician + Palmyran):**
- **Palmyran**: dân giá 75 thực (không phải 50) → AI dừng ở **19 dân** như bạn, mọi phép "đủ thực để xin dân" dùng giá 75 (trước đây lệnh xin dân bị game từ chối âm thầm khi 50 ≤ thực < 75, TC đứng không).
- **Đàn giết tại chỗ: ít nhất 2 dân phi cùng một con cùng lúc** *(bạn nhắc 12/10/2026 trưa)*: dân tới đứng cách con mục tiêu 3,3 ô (trong tầm lao 3 ô + một bước, ngoài vòng sợ 2,1 ô) và **không ai phi cho tới khi có ≥ 2 dân ở đó**, rồi tất cả phi trong cùng một nhịp lệnh (2 × 4 sát thương = 8 máu, chết tại chỗ, không nhảy loạn). Chỉ khi điểm săn có đúng 1 dân quá 12 s thì mới cho phi một mình.
- **Giết hết đàn rồi mới ăn** (đàn giết tại chỗ): khi còn con sống chạy khuất, dân đi tới chỗ thấy lần cuối tối đa 30 s sau con đầu tiên chết, hết 30 s mới ăn (xác chỉ tồn tại 300 s).
- **BS vàng sát mỏ**: luôn đóng BS cách mỏ một móng (không cần đi), chỉ bỏ qua khi chính TC kề mỏ (≤ 3 ô); trước đây mỏ trong 7 ô quanh TC thì dân mang vàng về TC.
- **Ngựa dò ngay khi kích đời 3** (đã có) nhưng giờ đi thẳng về phía nhà địch dự đoán (điểm đối xứng qua tâm bản đồ) thay vì dò sương mù gần nhà; **quân khi đã mạnh hơn (assault) đi ngay từ 2 lính**, cũng theo hướng đó khi chưa biết địa chỉ.
- BS gỗ đầu: tìm rừng tới 42 ô (TC sát mép bản đồ có thể cách rừng 35+ ô; trước đây dừng ở 30 ô nên BS bị đặt sát TC, dân gỗ đi bộ cả trận).

**Tốc độ test (bạn chỉ ra 12/10/2026 16:15):** chơi multiplayer chỉ lên được **x2** và bạn chơi 99 % ở x2 → mọi trận arena chạy ở x2 (trước đây x3 để rút ngắn test, x1.5 cho một số lô; x3 được đặt qua lệnh host trong hook, vượt giới hạn giao diện). Trễ lệnh lockstep tính theo giây-game tỉ lệ với tốc độ: ~1 s ở x1 → ~2 s ở x2, nên mô phỏng vi mô (câu voi, lùa hươu) phải đạt chuẩn ở `SIM_LAG=2.0`.

## 3. Quy tắc chi tiết AI đang làm theo



Mục tiêu: **kích đời 3 trước phút 13** trong 90% số trận. Mốc của cao thủ Việt Nam:

- Kích đời 2 ở phút 6:50–9:20 với 17–24 dân.

- Kích đời 3 ở phút 9–12.



Người mới thường kích đời 3 ở phút 13–16.



### 3.1 Dân và nhà (BE)

- Xin dân liên tục. Khi còn ≤ 2 chỗ trống thì xây BE.

- **BE đầu tiên: 2 dân xây, dân thứ 3 đi dò** tìm quả ngay khi vào trận. 2 dân xây xong cũng đi dò tiếp.

- **Các BE sau: mỗi BE chỉ 1 dân xây, không bao giờ 2 dân.**

- Dân thứ 10 xây 1 BE rồi đi ăn gỗ.

- **Trước khi có BS đầu**, chỉ xây BE khi nhà chính sắp hết chỗ ra dân, để 120 gỗ đầu tiên dành cho BS.

- Móng nhà nào mất dân xây (dân chết, bị điều đi) thì gán ngay dân gần nhất. Móng xây quá 45 giây thì thêm dân.

- BE đặt **xa TC**: vòng quanh TC bán kính ~6.5 ô để dành cho ruộng. Các BE xếp thành dải, dùng để làm tường ("bo nhà", xem 3.8).



### 3.2 Tìm quả và BG

- **Chia bụi quả theo quãng trả thực (bạn yêu cầu 13/10):** dân ăn quả chọn bụi có **đường đi thật** (vòng qua cây, bụi, nhà) từ bụi tới chỗ trả thực gần nhất (BG / nhà chính) ngắn nhất — những bụi đó được ăn trước; ưu tiên 1 dân 1 bụi, bụi đã có người thì tính thêm 2,5 ô nên chỉ chung khi bụi trống kế tiếp xa hơn hẳn; tối đa 3 dân một bụi. Chỗ đặt BG: chấm điểm bằng đường đi thật từ từng bụi tới BG, phạt bụi bị bít, và **phải đi được từ nhà chính tới** (BG trong túi rừng bị loại).

- Dân đầu đi dò thẳng vào **vùng đen gần nhà chính nhất**, mỗi dân một hướng; tới nơi là đổi sang vùng đen kế tiếp. Không đi lại vùng đã thấy, nên vùng dò nở dần ra như vòng tròn.

- Thấy bụi quả đầu tiên thì **tất cả dân đầu kéo về đó** để lộ cả bãi.

- **6 dân đầu, mỗi dân 1 bụi**, hạn chế 2 dân chung 1 bụi.

- 6 dân đầu chỉ ăn quả ở bãi trong tầm: có BG, gần TC, hoặc trong vòng 22 ô. Không đi hái bãi xa nửa bản đồ.

- Chỉ đặt BG khi đã thấy **≥ 5 bụi** của bãi (hoặc vùng quanh bãi đã khám phá hết). BG đặt ở chỗ tổng quãng đi bộ tới các bụi ngắn nhất và **không chặn bụi nào**: mỗi bụi còn ít nhất 2 mặt trống.

- Bãi sát TC (< 8 ô) thì không cần BG, trả quả thẳng vào TC.

- BG thứ hai chỉ làm cho bãi cách TC ≤ 22 ô. **Chưa đủ gỗ xây BG thì dân đứng chờ ở bãi**, tối đa 30 giây; quá 30 giây thì cứ hái và mang về chỗ trả gần nhất.



### 3.3 Gỗ và BS đầu

- **Ngay sau BG đầu, công trình tiếp theo bắt buộc là BS cạnh rừng.**

- **Trước khi có BS đầu**, mọi dân dư đều ăn gỗ ở các cây gần TC:

  - Cây 75 gỗ cho 2 dân, cây 40 gỗ cho 1 dân (2 cây 40 tính bằng 1 cây 75).

  - Chia đều, hạn chế nhiều dân ăn chung 1 cây.

- **Đủ 120 gỗ là xây BS ngay.** Gom các dân đang ăn gỗ dở (tối đa 6, gần nhất trước) vào xây, xong thì ăn gỗ tại đó.

- **Sau khi có BS đầu: đúng 6 dân ăn gỗ, tất cả dân còn lại chuyển sang ăn thực** (voi, hươu, quả).

- **Chỗ đặt BS đầu**:

  - **Sát rừng**: có cây ngay cạnh móng.

  - Lượng gỗ trong **bán kính 4 ô quanh BS** là nhiều nhất (gỗ trước mắt), ưu tiên chỗ có cây ở **2 bên trở lên**.

  - Cộng thêm lượng gỗ trong bán kính 8 ô (gỗ lâu dài).

  - Không quá xa TC, BS còn lối đi vào.

- **Số dân gỗ theo giai đoạn**:



  | Giai đoạn | Số dân gỗ |

  |---|---|

  | Đời 1 sau BS | 6 |

  | Từ lúc kích đời 2 | 9, cho tới khi đủ ~360 gỗ (BM 150 + BL 150 + nhà); thêm gỗ ruộng nếu hết thực tự nhiên |

  | Sau khi kích đời 3 | 4–8, tùy lượng gỗ đang có |



- **Trước BS đầu: 6 dân gỗ từ dân thứ 14** *(sửa 12/10/2026 04:00)*: người chơi có 5–7 dân gỗ ở phút 4–6 và BS lúc ~5:40; AI để 4 dân gỗ thì nhà và BG thứ hai ăn hết 120 gỗ của BS (night4 trận 2: BS lúc 12:00, 1356 thực mà chưa bấm đời 2). BG thứ hai chỉ được xây trước BS khi gỗ ≥ 240. Bấm đời 2 không còn bắt buộc có BS khi thực ≥ 600.

### 3.4 Dò bản đồ và đồ ăn

- Dân 7 và 9 đi dò cho đến khi biết đủ **5 nguồn đồ ăn** (1 bãi quả = 1, 1 đàn hươu = 1, 2 con voi = 1), hoặc khi đã có BS mà chưa có bãi săn nào. Dừng dò khi kích đời 2 hoặc sau phút 12.

- **Bản đồ nghèo thực**: nếu đã có BS mà không có bãi săn nào và gỗ đã > 250, dân dư đi dò tìm thực (tối đa 4 người dò) thay vì chặt thêm gỗ.

- **Né sư tử**:

  - Dân đi dò thấy sư tử thì tránh ra, giữ cách nó **7 ô** (ngoài tầm kích hoạt tấn công), rồi dò tiếp theo đường vòng.

  - Không chọn điểm dò, cũng không đi đường thẳng, lọt vào vùng đó.

- **Bị sư tử tấn công**:

  - Dân đi dò đánh trả sư tử, vì dân không chạy thoát được sư tử.

  - Thắng mà dân còn sống thì **đi dò tiếp ngay, không ăn thịt sư tử**. Nói chung, dân đi dò không bao giờ đứng ăn xác thú.

- **Dân dò quét vành đai 15–45 ô** *(sửa 12/10/2026 03:00)*: sau khi có BG, hai dân dò không dò ô chưa khám phá gần nhà nữa mà ưu tiên vành đai cách TC ~28 ô (người chơi: bãi săn cách 15–18 ô ở phút 2–3, 27–46 ô ở phút 8–10), vì ở bản đồ nghèo AI chỉ tìm thấy đàn ở 33–41 ô lúc phút 9 trong khi người chơi đã có dân săn từ phút 4–5. Số dân "thiếu việc săn" được tính so với 7 dân gỗ như người chơi (không phải so với chỉ tiêu gỗ đang cao vì gỗ ít), nếu không AI coi 17 dân chặt gỗ là "đúng việc" và không đi tìm thực (night4 trận 1). Khi 30 s không có việc săn nào trong tầm (≥ 18 dân) thì mở tầm toàn bản đồ và tăng lên 4 dân dò.

### 3.5 Săn bắn

- **Trước khi có BS đầu: chỉ săn kiểu mang về nhà chính** (câu voi, lùa hươu về nhà chính rồi ăn tại nhà chính). Đàn ở xa cần BS thì để sau BS đầu. *Bạn đồng ý đổi luật này ngày 10/10/2026*, vì người chơi trong 36 lượt ghi hình đều câu/lùa về nhà từ ~4:00, trước BS đầu (~5:40).

- Trước BS đầu, 4 dân ăn gỗ rồi mới tới dân săn; dân dư còn lại ăn gỗ.

- **Câu voi = thả diều.** Mặc định voi nào trong vòng 25 ô quanh TC cũng câu về nhà chính. Ưu tiên câu voi trước, vì dễ hơn lùa hươu.
  0a. **Đích câu = công trình trả thực gần voi nhất** (TC / BG / BS), không nhất thiết TC; **dân chờ được cử sẵn ở đó** từ lúc bắt đầu câu (bảng phân công: 3 dân, ưu tiên 4; dân đang ăn ở đó tính là đang chờ; lấy dân gỗ cũng được, bảng tự bù gỗ sau); voi phải chết **≤ 4 ô mép công trình** (trước 9 ô); không ai chờ thì dân câu tự phi–đi tiếp quanh công trình (chỉ TC / BS lẻ có chỗ đi vòng, BS sát rừng thì về TC) — *bạn đặt 12/10/2026 15:00*. Mô phỏng tiêu chí chặt: về TC 100/100, về BS 98/100; chế độ một mình 0/60 trong mô phỏng (voi không bỏ đuổi dân chạy vòng) nên chỉ là dự phòng, chưa kiểm chứng trong game.
  0. **Voi luôn câu về, kể cả voi xa (tới 60 ô)** — *bạn nhắc lại 12/10/2026 sau trận solo (voi 36 ô bị giết tại chỗ là sai)*; đường giết tại chỗ chỉ còn cho voi ngoài 60 ô (gần như không bao giờ).
  0b. **Luật bổ sung sau các trận test x2 (12/10/2026 tối)** — chuẩn đạt: voi chết ≤ 4 ô mép công trình, 0 dân chết, ≤ 150 s:
     - **Không câu voi đang bị tranh**: voi có dân địch trong 6 ô, hoặc gần công trình địch đã thấy hơn gần TC mình → bỏ qua (lure12: hai bot cùng câu một con, nó chết cách cả hai nhà 32/37 ô).
     - **Sư tử trong 5 ô dân câu trên đường đi → bỏ câu, chạy về, thử lại sau 90 s** (lure13: dân câu chết vì sư tử cách 0,4 ô). Voi có sư tử trong 8 ô thì chưa câu.
     - **Không còn "giết một mình"**: không có dân chờ thì dân câu **chạy vòng quanh công trình** giữ voi ở nhà cho tới khi bảng phân công cử dân giết tới (lure14: dân giết một mình bị kéo xa nhà 20 ô rồi chết). Bạn đề xuất lối "phi 1 cái rồi đi tiếp quanh công trình" — mô phỏng 0/60 và trận thật chết dân, nên tạm bỏ.
     - **Dân chờ thứ nhất lấy từ dân thứ 7 trở đi** (dân gỗ, như bạn cho phép); dân câu vẫn từ dân thứ 9. Trước đây cả hai suất đều đòi dân thứ 9+ nên câu sớm không có ai chờ.
     - **Dân câu còn 15 máu**: có dân khỏe trong 8 ô thì giao ngay; chưa có thì **vẫn chạy về nhà kéo voi theo**, dân khỏe đi ra đón và nhận voi ở 8 ô (trước đây dân mới đi bộ 36 ô ra phi lại từ đầu; voi 43 ô quá giờ). Trong pha giết, dân chạy vòng bị thương thì **đổi người chạy vòng, không phi lại** (phi lại sát voi làm dân mới bị húc ngay — mô phỏng 6/60 hỏng).
     - **Thời gian và trễ lệnh (x2 ≈ 2 s)**: lệnh chạy sau phát giáo phải *tới game* trong khoảng (giáo bay, voi húc ≈ +2 s) nên gửi khi dân còn (L − 1) s là vào tầm, tính theo tốc độ áp sát đo được; bước chạy chữ chi 40° ở x1 → 25° ở x2 (chạy chéo 40° chậm hơn voi, ở x2 voi áp từ 3,0 xuống 0,6 ô trong một đoạn). Hết giờ phi mồi tính theo quãng đường lúc bắt đầu, không theo quãng còn lại.
     - **Kết quả trận thật x2 (4 bot, 16 phút)**: lure12 5/5 voi không tranh chết 0,5–3,0 ô; lure13 7/8 (0,3–2,3 ô, 31–117 s; 1 sư tử, 1 quá giờ 43 ô); lure14 8/11 (1 solo chết, 1 giao voi sát voi chết, 2 hết giờ phi mồi); lure15 4/7 (2 chưa có dân chờ, 1 vùng chết 8–9 ô) → các lỗi này đã sửa ở trên; **sau sửa: lure16 7/7 voi chết, 0 dân chết, 6/7 ≤ 4 ô; lure17 6/6, 0 dân chết, 6/6 ≤ 4 ô, 5/6 ≤ 150 s; lure18 6/6, 1 dân chết (phi lại khi voi đã ở 2,5 ô → nay voi đã áp sát thì chạy, không phi)** ; lure19 lộ lỗi bảng phân công (không có dân chờ → sửa); **lure20: 10/10 voi câu được đều chết, 9/10 ≤ 4 ô, 9/10 ≤ 150 s, 1 dân chết** ; **lure21 (giết từ 3,2 ô): 5/5 voi chết 0,6–1,5 ô, 0 dân chết** — năm trận mã cuối: 34/34 voi chết, 2 dân chết, 29/34 đạt chuẩn chặt (85 %). Mô phỏng x1: 59/60.
     - **Khoảng bắt đầu giết 3,2 ô mép, dân câu chạy vòng cách 3,2 ô** (trước 3,5/3,5; trước nữa 4,5): trận thật vài con chết 4,9–5,4 ô vì bắt đầu giết ở 3,5 rồi trôi ra; mô phỏng x1 56/60 → 59/60, về BS 38/40.
     - **Đứng lại chờ voi (làm 12/10 23:10 theo trận test của bạn):** voi trong game ở x2 chỉ đuổi ~5 s sau mỗi phát giáo rồi bỏ (ở cách 3,5–4,5 ô); trước đây dân chạy tiếp tới 6–7 ô, đợi 2,5 s + giãn 6 s mới phi lại nên voi kịp đi ngược về (voi #5581 trận của bạn: 6 lần phi lại, chết cách nhà 10 ô). Nay voi vừa bỏ đuổi là dân **dừng ngay tại chỗ**, phi lại tức thì (giãn 2 s), bước chạy 3,5 ô để khi voi dừng dân vẫn trong tầm giáo; voi xa không theo sau 12 phát mà còn ≤ 15 máu thì giết tại chỗ. Arena lure22 x2: 9 câu, 7 voi chết 0,5–3,0 ô, 6/7 ≤ 150 s, 0 dân chết; 2 voi 37–47 ô không theo. Đích câu chỉ còn **nhà chính / BS** (BG không nhận thịt — bạn chỉ ra sau trận test).
     - *(ghi chú cũ)* Làm sau (bạn hỏi 12/10 tối): dân câu đứng lại một thoáng để giữ khoảng cách. Hiện dân không đứng khi voi còn đuổi mà chạy chéo (40° ở x1, 25° ở x2) để giữ 2,8–3,6 ô; chỉ dừng sau khi voi đã bỏ đuổi rồi phi lại (4 máu/lần). Trận thật x2: voi bỏ đuổi kiểu hết giờ mỗi 5–8 s dù chỉ cách 3,4 ô (phi lại 0 lần: 45 mẫu, 1: 31, 2: 25, 3: 8, 4–5: 5). Ở x2 cửa sổ đứng chờ rất hẹp: lệnh trễ 2 s = voi áp 2 ô, nên phải ra lệnh chạy khi voi còn 4,3 ô. Việc thử: bản "đứng khi voi đang đuổi mà cách > 3,8 ô, chạy lại ở 4,3 ô" so với bản chạy chéo bằng arena x2, đếm số lần phi lại và voi chết dọc đường.
     - **Lỗi hạ tầng đã sửa**: log của luồng điều khiển nhanh (phi mồi, "cả làng đánh", LUREDBG) từng bị nuốt (chỉ in dòng sinh ra trong tick chậm) → từ nay in đủ; đừng kết luận "không chạy" khi không thấy dòng log.

  1. 1 dân phi voi **đúng 1 phát** rồi chạy ngay về phía TC.

  2. **Phi 1 phát rồi chạy ngay — lệnh chạy được gửi ngay khi dân vào tầm ném (3 ô)**, vì lệnh tới game trễ ~1 s: dân rời chỗ ngay sau khi giáo bay, voi (1.00 ô/s, húc từ 2 ô) không bao giờ chạm được dân (1.10 ô/s). Mô phỏng: 200/200 lần, 0 dân chết; trước đây dân câu luôn dính 1 phát (10 máu). **Voi còn đuổi thì dân chạy liên tục, không dừng; khi khoảng cách > 3.4 ô thì chạy chéo ~40° (slalom) để voi theo kịp mà không bỏ đuổi** (voi bỏ đuổi khi cách > 4.4 ô).

  3. **Chỉ phi thêm 1 phát khi voi đã đứng hẳn**, không phi khi voi đang đuổi; phi liên tục làm voi mất máu và quay đầu. Phi lại quá 12 lần mà voi không theo thì bỏ con đó. Dân câu còn dưới 20 máu thì không phi nữa (mỗi lần phi phải áp sát, bị húc 10–20 máu), giao voi cho 1 dân khỏe (≥20 máu) rồi về đứng chờ ở TC; mỗi con voi đổi người tối đa 2 lần. Chỉ dân được giao câu mới được dắt voi.

  4. Khi voi còn cách TC dưới 16 ô: **3 dân ra đứng chờ sẵn** ở phía TC hướng về con voi.

  5. Voi về **trong vòng 3 móng nhà chính (9 ô tính từ mép TC)**: dân chờ (đứng sẵn cách TC 3.5 ô phía con voi) và dân gỗ/ruộng gần đó xông vào giết, ném từ tầm 3 ô. **Dân nào bị voi quay sang nhắm thì lùi ra (điều quân), những dân khác ném tiếp**; voi chậm hơn dân nên không bắt được ai. Thực tế đo được: cả nhóm chỉ mất ~10 máu mỗi con voi, giết ở ~5.4 ô cách tâm TC, ~11 giáo trong ~30 s.

  6. Trong lúc giết, **dân câu vẫn chạy vòng quanh TC** để voi tiếp tục đuổi nó, không quay sang húc dân đang đánh. Voi còn dưới 30% máu thì dân câu mới đánh cùng.

  7. **Mỗi con voi: 3 dân ăn.** Voi đã hạ thì không bao giờ câu lại; xác khuất tầm nhìn thì dân vẫn tới ăn.

- **Lùa hươu**:

  - **Luật bổ sung sau test x2 (12/10/2026 tối)** — chuẩn bạn đặt: *mọi con* chết ≤ 4 ô mép TC, không con nào chết ngoài đồng, cả lượt ≤ 120 s:
    - **Giáo "nhắc" khi lùa chỉ đúng 1 phát**: lệnh dừng gửi 1 s sau lệnh phi (cộng quãng đi vào tầm) và chỉ khi *đã thấy* dân trong tầm — đợi thấy trúng rồi mới dừng là trễ 1 nhịp lệnh ở x2, phát thứ hai (4 + 4 = 8 máu) giết hươu ngoài đồng (mô phỏng x2: 10/40 lượt có hươu chết ngoài đồng → 1/40).
    - **Pha giết ở TC: dân luôn phi từ phía ngoài đồng** (đứng ở phía xa TC của con hươu) để cú nhảy sau khi trúng giáo hướng vào TC (bị chặn) chứ không văng ra đồng; dân từ trong nhà ra thì đi vòng (giữ 3 ô với đàn) rồi áp sát 2,5 ô; **hai dân cùng một con, cùng ném** (đợi nhau tối đa 5 s), mục tiêu cố định cho tới khi con đó chết. Mô phỏng pha giết x2: *mọi con* chết ≤ 4 ô 15/40 → 26/40, hươu chết xa 32 → 7.
    - **Lùa "đều" khi đàn còn xa TC (> 8 ô mép)**: dân đứng sau đàn đi *xuyên qua* chỗ con cuối hướng về TC và đi liên tục (lệnh làm mới mỗi 1 s), không dừng-đợi-áp từng bước (mỗi lần dừng mất một nhịp trễ lệnh); trong 8 ô cuối mới áp từng bước để đàn dồn sát TC. Mô phỏng x2 (2 dân lùa, đàn 12–25 ô): về tới TC 22/40 → 34/40, nhưng tốc độ dồn đàn vẫn ~0,2 ô/s (người ~0,5–0,8) → **chưa đạt chuẩn 120 s**, đang tìm nguyên nhân (68 % thời gian dân lùa đi chỉnh vị trí: trượt ngang / đi vòng).
    - **Log mới trong trận**: `GAZDEAD` (mỗi con hươu: chết cách mép TC bao nhiêu ô, sau bao lâu, pha nào) và `HERDOK` (mỗi đàn: số con chết ≤ 4 ô / chết xa / chạy thoát, thời gian, có đạt chuẩn không) — để đo đúng chuẩn trong trận thật thay vì mô phỏng.

  - **Chỉ từ dân thứ 9 trở đi mới được câu voi, lùa hươu.** Chưa đủ 9 dân thì không bắt đầu câu/lùa; người câu/lùa luôn là dân thứ 9 trở đi (theo thứ tự ra đời), 8 dân đầu (6 dân quả, 2 dân dò, 1 dân gỗ) không bao giờ bị kéo đi. Dân ăn quả cũng không bị gọi sang giết voi. *(Bạn bổ sung 11/10/2026, sau trận AI câu voi khi chưa đủ dân ăn quả.)*

- **Ưu tiên số 1 là đủ 6 dân ăn quả.** Đã thấy bãi quả thì 6 dân đầu (theo thứ tự ra đời) chỉ ăn quả, không bao giờ đi lùa hươu hay câu voi; người lùa/câu lấy từ dân thứ 7 trở đi. Dân trong nhóm 6 đang lùa dở thì bỏ lùa về ăn quả (đàn hươu được lùa lại sau); chỉ ngoại lệ khi voi đang đuổi theo dân đó. *(Bạn bổ sung 11/10/2026, xem trận 2026-10-11_094124, màu nâu.)*

  - **Lùa cả đàn, không lùa từng con, luôn bằng 2 dân** (chia trái/phải, mỗi dân đẩy con đi sau cùng của nửa mình). Mô phỏng theo số đo thật (11/10/2026): 2 dân lùa về được 95/100 đàn, 1 dân chỉ 56/100. Dân lùa vòng ra sau đàn theo tiếp tuyến quanh từng con (giữ ≥3.2 ô), rồi đứng vào điểm cách con sau cùng 2.6 ô phía đối diện TC và tiến vào; con đó nhảy ~2.75 ô về phía TC.

  - **Nhịp lùa đầu: phi mỗi con đúng 1 phát** rồi đẩy tiếp. Hươu còn nửa máu, nhảy về phía TC; về đến nơi chỉ cần 1 phát nữa là chết, không kịp chạy loạn. *(Bạn bổ sung 11/10/2026.)*

  - **Mỗi con đầy máu chỉ phi 1 lần**, mỗi lúc chỉ 1 giáo đang bay (2 người lùa không phi cùng 1 con: hươu 8 máu, mỗi giáo 4, phi 2 phát là chết ngoài đồng). Ném xong thì chờ xác nhận trúng; trúng rồi mới chỉnh lại vị trí (~1.5 giây) trước khi phi con khác. Trượt (3 giây không mất máu) thì con đó được phi lại sau khi chỉnh vị trí. *(Bạn bổ sung 11/10/2026, trận lúc ~4:00.)*

  - **Chỉ kết liễu khi đàn đã về sát nhà chính** (trong ~3 ô tính từ mép TC; người chơi giết hươu cách tâm TC 2.5–3.4 ô). Lùa thất bại (kẹt, mất dấu, quá giờ) thì **không giết tại chỗ**: đàn được lùa lại sau 15 giây. Con nào chạy thoát khỏi TC cũng được lùa lại, không đuổi giết. *(Bạn bổ sung 11/10/2026; trước đây giết khi cách mép TC 9 ô.)*

  - **Dân khác không được đi xuyên qua bầy đang lùa.** Dân nào đi tới gần một con hươu dưới ~3.2 ô thì bị cho đi vòng quanh bầy, về phía nơi nó định tới. *(Bạn bổ sung 11/10/2026, xem trận 2026-10-11_102020 lúc 5:01.)*

  - **Hươu đứng sát tường/rừng/vật cản hoặc sát mép bản đồ thì bỏ, không lùa.** Đàn có từ một nửa số con như vậy thì bỏ cả đàn; đàn lùa hỏng 2 lần (hoặc không vòng ra sau được) cũng bỏ. Sau 60 giây xem lại, nếu đàn đã ra chỗ thoáng thì lùa. *(Bạn nhắc lại 11/10/2026.)*

  - **Đàn hươu mà đường về nhà chính đi qua bãi quả đang có dân hái, bãi gỗ đang có dân chặt, hoặc nhà cửa thì không lùa** (lùa sẽ loạn): giết tại chỗ rồi đóng BS ăn. Kiểm tra lại mỗi phút. **Voi thì luôn câu về**, voi không sợ vướng. *(Bạn bổ sung 11/10/2026, trận solo 22:30.)*

  - **Trong lúc lùa, khu vực quanh bầy cấm mọi dân trừ người lùa.** Dân đang đi mà hướng vào bầy, hoặc tới gần dưới 3.2 ô, thì phải đi vòng quanh bầy (cách bầy ~4.5 ô) từ khi còn cách 5 ô, vì lệnh tới game bị trễ.

- **Đàn hươu ở xa**:

  - **Giết hết cả đàn rồi mới ăn**, kể cả con đã chạy khuất tầm nhìn (AI theo dõi từng con bằng con trỏ, đuổi giết trong vòng 15 ô quanh bãi trước khi ăn). *(Bạn nhắc lại 11/10/2026, trận solo lúc 8:03.)*
  - **Về tới nhà chính là ăn ngay**: thịt hươu bay rất nhanh theo thời gian, nên xác ở gần TC được ưu tiên ngay sau 6 dân hái quả, **ít nhất 1 dân mỗi xác**, nhiều hơn khi có dân. *(Bạn bổ sung 11/10/2026 đêm.)*

  - Giết hết cả đàn tại chỗ, rồi đặt BS ở chỗ đi bộ tới xác ngắn nhất (tối đa 4 dân xây).

  - **Đàn xa là một "cuộc săn tập thể" (sửa 12/10/2026 từ 20 bản ghi của chính bạn):** trong 2 phút trước khi bấm đời 2 bạn cho 7–14 dân ăn một đàn / voi cách TC 30–46 ô ngay cạnh BS → thu nhập 7–13 thực/giây (AI trước đó chỉ 1–4 thực/giây: 2 dân mỗi xác xa, không BS, 4–7 dân mỗi đàn, BS chỉ đóng sau khi giết xong, phi tản mát). Giờ: đàn xa nhận tới **10 dân** (2 + 2 dân mỗi con), **BS đóng ngay khi bắt đầu giết** (dân tới là đóng), **cả nhóm phi cùng một con** (một loạt 8–10 ngọn lao là chết ngay, không chạy loạn), xác xa cạnh BS 3 dân mỗi xác. Đàn tới 48 ô (bạn: tới 46 ô); 75 ô khi không có bãi săn nào. Ở đời 1 nếu gỗ ≥ 300 thì chỉ giữ 5 dân chặt gỗ (bạn giữ 180–290 gỗ ở phút 8–10), số còn lại đi săn.

  - **Chưa đủ 120 gỗ cho BS thì dân đứng chờ cạnh xác**, tối đa 30 giây; quá 30 giây thì cứ ăn.

  - Ưu tiên đàn trong vòng 25 ô. Đàn tới 40 ô chỉ khi không còn thực gần; tới 60 ô khi cả vùng không có bãi săn nào.

- **Nhà (BE) không xây sát nhà chính:** cách tâm nhà chính ít nhất 7 ô (đây là chỗ giết voi, hươu), và không xây trên đường lùa đàn hươu về nhà chính. *(Bạn bổ sung 11/10/2026, trận 2026-10-11_140105, AI 1 lúc 9:32.)*

- **Chia dân theo bãi**:

  - Mỗi bãi hươu/voi chỉ **4–7 dân**, tùy số dân đang ở gần bãi. Voi: 1 dân câu, 3 dân chờ, 3 dân ăn.

  - Dân thừa đi ăn bãi đồ ăn khác.

  - Tối đa 3 bãi săn cùng lúc, cộng với bãi quả là **2–4 khu vực ăn thực song song** để lên đời nhanh.



### 3.6 Lên đời

- **Đời 2 (Tool)**: đủ **22 dân**, đã có BG + BS và đủ 500 thực thì kích. Nếu sau khi có BS mà không tìm được bãi săn nào (chỉ có quả) thì kích ở **18 dân**. Trong lúc lên đời 2 thì dừng xin dân.

  - *Đổi so với luật gốc của bạn (25 dân)*: chuẩn D3KT của người Việt là 20–24 dân. Mỗi dân thừa làm chậm việc kích đời 2 khoảng 20 giây.

- Lên xong đời 2: xây BM trước, rồi BL (mỗi nhà 3 dân, đặt sao cho giúp bịt tường), rồi kích **đời 3** ngay khi cả hai xong và đủ 800 thực. Trong đời 2 không xin thêm dân.

- **Trong lúc nghiên cứu đời 2 và ở đời 2 vẫn phải có thực:** thực gần hết thì dân 7, 9 tiếp tục đi dò, bãi quả xa (tới 60 ô) và đàn hươu xa được ăn với BS tại chỗ. Người chơi ở phút 11–13 vẫn có 7–9 dân săn cách TC ~32 ô; ruộng chỉ xuất hiện từ phút 15. AI trước đây để 19–25 dân chặt gỗ trong 2 phút nghiên cứu đời 2 vì hết thực gần, rồi mất 4–8 phút ruộng mới đủ 800 thực. *(Sửa 11/10/2026.)* **Từ lúc kích đời 2, luôn cho phép quả xa và đàn xa (tới 60 ô)**, dân 7 và 9 dò tiếp. Dân dò thêm chỉ cho phép trước phút 8 (tối đa 2), vì so với 80 người chơi AI đang để 2–4 dân dò tới phút 12. Mỗi voi câu về cho **5 dân ăn** (trước 3). BG thứ hai xây ngay khi bãi đầu còn ≤ 2 bụi (người chơi: ~8:00), không chờ BS. *(Sửa 12/10/2026 từ so sánh từng phút với 80 người chơi.)*
- **Không còn gì để ăn trong 60 ô thì tìm trên cả bản đồ**: khi không còn dân nào ăn thực (từ 12 dân trở đi), AI bỏ mọi giới hạn khoảng cách (quả, đàn, xác ở bất kỳ đâu; voi tới 70 ô) và cho 4 dân đi dò, cho tới khi có ≥ 3 dân ăn thực lại. Lý do: hai AI đứng ở 494 và 168 thực với 23 dân chặt gỗ suốt 8 phút, không bao giờ kích được đời 2. *(Sửa 12/10/2026.)*

- **Ruộng**: làm khi đã có BM và hết thực tự nhiên gần nhà.

  - Cách BG/TC đúng **1 móng nhà (2 ô)**.

  - Đường đi về ngắn, không đi vòng.

  - Không đặt ruộng ở chỗ không tới được, và không chặn lối ra của TC (dân mới ra không bị kẹt).

  - Chỉ chi gỗ cho ruộng khi không ảnh hưởng nhà và công trình đang chờ.



### 3.7 Chiến lược đời 3: quân, nhà quân, kinh tế

- **Ngay sau khi kích đời 3** (luật Việt Nam cho phép chọc dò từ lúc này):

  - Xin 1 ngựa dò đi tìm nhà và dân đối phương, chọc dân.

  - Nghiên cứu **Tool Working** (tăng công cận chiến), rồi **Leather Armor (Cavalry)**.

- **Kinh tế: phát triển lâu dài** *(bạn bổ sung 11/10/2026)*:

  - **Ruộng bất tử** *(bạn cho phép 11/10/2026 đêm — quy ước được cộng đồng công nhận)*: lệnh **Stop** lên một nhóm gồm tất cả ruộng + 1 dân (người chơi gom ruộng vào đạo, kéo chọn thêm 1 dân, bấm S hai lần) làm ruộng được **reset thực**. AI gửi lệnh Stop với danh sách ruộng + 1 dân qua hook **mỗi ~25 s** rồi ra lệnh lại cho dân đó về ruộng ngay. *Đo trong bộ nhớ 12/10/2026 02:20:* ô "thực" của ruộng (unit+0x44) trong bản game này chỉ chứa **0–15** (kho thực của thửa, tự đầy lại ~0,25/s, thường bằng 0 khi dân đang gặt → dân bị chờ), không có số 250 nào trong vật thể; **ngay sau lệnh Stop nhiều ruộng nhảy lên 15.00** → mỗi lần bấm là +15 thực mỗi ruộng. Ruộng có hết hạn hay không: kiểm tra trong lô trận 32 phút.
  - **Tỉ lệ dân đời 3 để xóc đều các BL** *(bạn yêu cầu 11/10/2026 đêm)*: mỗi BL ra ngựa chém liên tục (70 thực + 80 vàng mỗi ~40 s) cần ~5 dân ruộng + ~5 dân vàng (ước tính 0.35 thực/s một dân ruộng, 0.4 vàng/s một dân vàng — sẽ đo lại từ bản ghi). Vì vậy: số BL = số dân ÷ 10 (tối đa 6); vàng = 2 + 5 × số BL (chặn ở nửa số dân); gỗ 4–6; còn lại làm ruộng.
  - Sau khi lên đời 3 **vẫn xin dân đều** (tới 60 dân). TC và BL chia thực: TC chỉ nhường khi không đủ thực cho BL đang rảnh, và cứ 3 lượt vẫn xin 1 dân.

  - Dân mới chủ yếu xây ruộng và làm ruộng (1 dân 1 ruộng). Vàng = 2 + 2 dân mỗi BL (thử 2 + 4 thì dư 1000–1700 vàng, hết thực); gỗ 4–8 dân tùy gỗ đang có (ruộng, nhà, BL).

  - **Xây nhiều BL nhất có thể để xóc quân đều:** khoảng 1 BL cho mỗi 12 dân (tối thiểu 2, tối đa 6), xây thêm khi các BL đang có đều đang ra quân (hoặc dư 200 thực + 200 vàng), mỗi BL 150 gỗ.

  - **Tăng tần:** càng nhiều BL thì xây nhà sớm hơn (còn ≤ 3 + số BL chỗ trống là xây).

  - *Thử nghiệm trước đó: dừng ở 30 dân và 10 dân vàng thì dư vàng, thiếu thực; xin dân tới 45 không giới hạn thì không ra quân. Giờ cân bằng cả hai.*

- **Giữ dân** *(bạn bổ sung 11/10/2026)*: dân bị quân địch đánh thì chạy về phía TC (6 giây rồi làm việc lại); quân của mình quay về đánh bất kỳ kẻ nào đang đánh dân mình, ở đâu cũng vậy. Ngựa dò đi một mình thì dân quanh đó đánh lại như luật cũ.

- **Chiến thuật thi đấu** *(bắt đầu 11/10/2026 đêm, `brain/tactics.py`)*:

  - Vào trận AI đọc **nền văn minh hai bên** từ bộ nhớ game và ghi vào log (`civs: ...`).

  - AI **nhớ mọi quân địch đã thấy** (2 phút) và tính tương quan: mỗi loại quân một trọng số (voi 4, phù thủy/cẩu 3, ngựa chém 2, lạc đà 1.6, cung 1.2, dò 0.8, chém bộ 0.8).

  - **Chế độ**: *thủ* khi quân địch trong 22 ô quanh TC có sức mạnh ≥ ½ quân mình (cả đoàn về đánh tại nhà, không đuổi ra ngoài); *đánh* khi quân mình ≥ 1.3× quân địch + 2 (hoặc chưa thấy quân địch mà đã có ≥ 2 ngựa); còn lại *tích quân* ở nhà, chỉ ra tay với kẻ đang đánh dân.

  - **Chọn quân khắc chế** theo loại quân địch nhiều nhất: cung/xe ngựa/phù thủy/cẩu/bộ binh → ngựa chém; ngựa/lạc đà địch/chiến voi/hoplite → lạc đà. Chưa thấy gì thì ngựa chém xen lạc đà.

  - **Nhà phù**: đối thủ là Choson/Yamato/Minoan/Greek (ở đời 3) hoặc đã thấy phù thủy địch → xây 1 nhà phù, ra 2 phù thủy.

  - **Cung, cẩu đá, đời 4** *(thêm 12/10/2026 đêm, chưa kiểm chứng)*: địch có ≥ 4 bộ binh/hoplite → xây nhà cung, ra cung thủ; đang tổng tấn công mà nhà địch ≥ 25 công trình hoặc dân địch ≥ 1.3× dân mình (bo kín, phát triển hơn) → xây BK, ra tối đa 3 cẩu đá; sau phút 20 mà trận chưa kết thúc và đủ 1200 thực + 950 vàng → xây đủ 2 công trình đời 3 (nhà phù + BK) rồi **kích đời 4**. Chưa làm: điều quân né tên.

- **Tìm nhà đối phương** *(bạn bổ sung 11/10/2026)*:

  - AI nhớ mọi công trình và mọi khu dân đối phương đang làm việc đã thấy (theo ô 8×8).

  - Thấy 1 công trình thì nhà và khu làm ăn của đối phương nhiều khả năng ở quanh đó: tìm quanh các công trình đã thấy trước (vòng 7, 12, 17 ô; chỗ quân mình chưa qua trong 2 phút).

  - Không thấy gì thì tìm khắp bản đồ (vùng chưa khám phá).

  - **Thỉnh thoảng quay lại đánh các khu làm ăn đã biết**: khu nào quân chưa ghé trong 90 giây thì quay lại; khu có dân làm việc ưu tiên trước khu chỉ có công trình.

- **Đánh dồn dập** *(bạn bổ sung 11/10/2026)*:

  - **Bị cung bắn thì xông vào cung, không quay đầu chạy** (bạn phản hồi 11/10/2026, trận 1 vs 2 AI): quân chỉ lùi khi còn dưới 35 % máu.
  - **Soi bảng thành tích như người chơi**: AI đọc tổng số dân, quân (theo loại) và vị trí nhà chính của đối thủ từ bộ nhớ game (tương đương bảng Achievements). Có ≥ 3 quân thì đi *quấy rối* dân đối thủ (raid); khi sức mạnh quân mình ≥ 1.2 × toàn bộ quân đối thủ + 2 thì *tổng tấn công* thẳng vào nhà chính địch; quân địch áp sát nhà với sức mạnh ≥ ½ quân mình thì cả đoàn về *thủ*. *(Bạn yêu cầu 11/10/2026 đêm.)*
  - **Công nghệ** *(bạn yêu cầu 11/10/2026 đêm)*: AI đọc bảng nghiên cứu của mình từ bộ nhớ (0 chưa mở, 1 có thể nghiên cứu, 2 đang, 3 xong) nên biết chính xác đã nâng gì. Từ lúc kích đời 3, mỗi lúc nghiên cứu một công nghệ theo thứ tự: **Bánh xe trước** (dân chạy nhanh), Tool Working, Giáp da ngựa, Wood Working, rồi các công nghệ người chơi hay nâng (id 69, 92, 55, 59, 17, 41, 68 theo bản ghi), rồi **mọi công nghệ khác đang mở** — trừ đào đá, tường/chòi (cấm theo luật) và các đời (do kế hoạch bấm). Chỉ nghiên cứu khi còn ≥ 200 thực (và ≥ 60 vàng ở đời 3) để không chặn dân và quân. Không biết nhà nào nghiên cứu thì thử lần lượt chợ, BS, BG, BL, BB, nhà phù, nhà cung, TC và kiểm tra trạng thái "đang nghiên cứu".
  - **Dân chạy theo vùng** *(bạn bổ sung 11/10/2026 đêm)*: thấy quân địch (không phải ngựa dò đi lẻ) trong vòng 10 ô là **mọi dân trong vùng chạy về TC ngay**, không đợi bị đánh; 8 giây sau bảng phân công đưa về việc cũ, còn địch gần thì chạy tiếp.
  - **Chạy dân đứng trên mọi việc** *(sửa 12/10/2026 tối, trả lời câu hỏi "chạy dân nằm ở ưu tiên mấy")*: trước đây luồng điều khiển nhanh (câu voi, lùa hươu) ra lệnh 4–20 lần/giây cho dân của nó, đè lên lệnh chạy chỉ sau một phần giây; nay mọi lệnh của các việc đó **bỏ qua dân đang trong thời gian chạy** (retreat_until), nên lệnh chạy giữ nguyên tới hết 6–8 s. Còn lại chưa làm: bán kính chạy cố định 10 ô, chưa nhớ "vùng nóng" để tránh quay lại.
  - Đủ 3 quân thì đi đánh; quân mới ra nhập đoàn luôn, không chờ.

  - Cả đoàn đi chung một điểm, chọn lại mỗi 20 giây hoặc khi tới nơi; ngựa dò đi tìm riêng.

  - Mục tiêu: dân trước, quân sau. Không thấy dân thì đánh công trình gần đó (trừ TC) để kéo dân ra.

  - Đánh và chạy: bị đánh đau thì lùi ra rồi quay lại.

- Trước khi kích đời 3, quân không đi đánh, chỉ đánh trả quân đang tấn công mình (xem mục 1).



- **Có 2 lính là đi đánh ngay, chỉ thủ khi bị đánh** *(bạn đặt 12/10/2026 trưa)*: chế độ "tích quân" chỉ còn khi có đúng 1 lính; từ 2 lính là quấy rối dân địch (raid), mạnh hơn địch thì tổng tấn công (assault); "thủ" chỉ khi quân địch đang ở nhà mình với lực lượng đáng kể (≥ nửa quân mình trong 22 ô quanh TC). Chưa biết nhà địch thì đi thẳng về phía đối xứng qua tâm bản đồ.

- **BY (Academy) cho Greek / Macedonian** *(bạn đặt 12/10/2026 trưa)*: sau nhà BL đầu, mọi nhà quân tiếp theo là BY (id 0), ra hoplite (Soldier-Phal1 id 93, 60 thực 40 vàng); số nhà quân = dân/10 như BL. **Nhà quân xây ngoài bo**: BL / BY / cung / BK / BB đặt ngay ngoài vành tường (cách tâm bản vẽ + 2,5…+8 ô), lệch về phía địch, để quân ra đời ở ngoài không cần mở cổng; dân đi xây thì gác cổng xoá BE cho ra, xây xong quay vào thì bịt lại. Bản vẽ **rộng** (cả thị trấn, r=10–18, 0 lỗ rò) là bản vẽ duy nhất kín được — vòng nhỏ quanh BG/BS có 7 lỗ rò; trước đây hễ có địch đời 3 hoặc quân địch trong 30 ô là AI đổi về vòng nhỏ (trận gate1: không AI nào kín được). Giờ "bị đe doạ" chỉ làm xây nhanh hơn, không đổi bản vẽ. Bản vẽ tường rộng một khi đã xây ≥ 3 BE thì giữ nguyên (không đổi về nhỏ khi cờ "bị đe doạ" nhấp nháy) để có thể kín.

- **Chọn quân theo phe và theo vàng (bạn yêu cầu 13/10):**
  - Trước đây hầu hết bot đánh ngựa chém; lạc đà chỉ ra khi địch dùng ngựa; cung chỉ ra 8 lần (cung thường) trong ~60 trận arena, chưa có cung A / cung R; BY = 0 vì nhà BY chỉ được xây ở phút 23–29.
  - **Palmyran, Persian đánh lạc đà** làm quân chính (chỉ đổi sang ngựa khi quân địch chủ yếu là lạc đà).
  - **Hết vàng trên bản đồ** (sau 15 phút không còn mỏ vàng nào bot biết, kho < 200 vàng): BL ra **xe chiến (chariot, thực + gỗ)** khi đã có Bánh xe, chưa có thì ra ngựa dò (chỉ thực); bật nhà cung (cung thường → cung A sau Improved Bow → cung R sau Bánh xe); không xây BY nữa (BY tốn vàng). Bánh xe đứng đầu thứ tự nghiên cứu.
  - **Hy Lạp / Macedonia xây nhà BY ngay khi lên xong đời 3** (không chờ đủ thực/vàng dư như nhà quân thứ hai).

- **Lối cung R (học từ trận của bạn — ChimSeDiNet, 13/10 00:19 và 00:49):** nhà cung là nhà thứ hai để lên đời 3 (cùng chợ, không xây chuồng ngựa); giáp da cho cung (~770 s) và Bánh xe ngay sau khi lên đời 3 (~880 s); cung thường trước Bánh xe, cung R từ ~1 000 s; 4–8 nhà cung, 13–15 cung R. Bot: Ai Cập / Assyria / Hittite luôn theo lối này, các phe khác (trừ phe lạc đà và Hy Lạp / Macedonia) ~35 % số trận; một cung thường đi tìm nhà địch thay ngựa dò; thứ tự nghiên cứu Bánh xe → giáp da cung → Improved Bow → giáp vảy cung.
  - *Lỗi đã sửa:* mã quân cung R bị đảo (bot gửi mã 40 = xe chiến của chuồng ngựa tới nhà cung, game từ chối) nên **chưa bao giờ ra được cung R**; đúng là 41 = cung R (nhà cung), 40 = xe chiến (chuồng ngựa). Giá cung R: 40 thực 70 gỗ.
- **Cách đánh cung R của bạn (13/10, bổ sung):** trước Bánh xe chỉ **1 cung thường** để thủ, chết mới ra con khác; số nhà cung theo ruộng (**2 ruộng nuôi 1 nhà cung**, 4 nhà cung cần ≥ 8 ruộng); **đợt cung R đầu tiên đi dò nhà địch ngay** (đi nhanh, tầm nhìn rộng), thấy là đánh, không chờ đủ quân; cung thường ở nhà thủ. **Địch bo kín:** bot tìm đường từ chỗ quân đứng tới nhà chính địch; không có đường thì bắn BE của tường (BE nằm giữa phía mình và phía nhà chính địch; tường hai lớp thì bắn lớp ngoài gần nhà chính địch nhất), và **ưu tiên bắn dân địch đi tới được** (dân ra sửa BE / xây BE mới cạnh BE cũ).
  - *Sửa nghiên cứu:* công nghệ đang được giữ thực (ví dụ Bánh xe 175 thực) chỉ cần đúng giá; công nghệ xếp sau chỉ làm khi còn dư cả phần giữ đó (trước đây Bánh xe không bao giờ đủ thực vì các công nghệ 100 thực chen vào trước, nên lối cung R không lên được cung R).
  - *Sửa chỗ đặt nhà quân:* đặt ngoài tường hỏng 2 lần thì đặt trong làng (trước đây nhà BY hỏng 8 lần liền ở ngoài tường).
- **Cây công nghệ của phe (bạn chỉ ra 14/10, trận 1v4: Yamato không có cung R mà vẫn đánh cung R):** đầu trận bot đọc trạng thái nghiên cứu (−1 = phe không bao giờ có): cung R (59), cung A 1 áo / 2 áo (56 / 57), xe chiến (68), ngựa chém (69), lạc đà (124), horse (60), Y đẹp (73). Lối cung R chỉ chọn khi phe có cung R; không có thì đánh cung A (nếu có), không có cả cung A thì theo lối chuồng ngựa. Lạc đà / ngựa chém / xe chiến chỉ ra khi phe có (Ai Cập không có ngựa chém → lạc đà; Yamato, Hy Lạp không có lạc đà → ngựa chém).
- **Cung A đi dò lẻ (bạn yêu cầu 14/10, Minoan tấn công quá muộn, quá ít quân):** lối cung A, đã nâng xong 2 áo (hoặc 1 áo với phe không có 2 áo) mà vẫn chưa thấy nhà địch → 2 cung A (≥ 3 cung) hoặc 3 cung A (≥ 6 cung) **đi lẻ từng con**, mỗi con một chỗ chưa thám hiểm khác nhau (cách nhau ≥ 20 ô), ưu tiên phía xa nhà mình nhất (đối diện bản đồ); thấy nhà địch là thôi.
- **Đội bạn chung tầm nhìn (trận 2v2 14/10: Palmyran đóng BS bằng 200 gỗ đầu, không đóng BG đầu):** quả / thú / gỗ gần nhà chính của đồng minh hơn nhà mình (trong 45 ô) không được tính là của mình — trước đây bot thấy bãi quả ở làng đồng minh và đi ăn ở đó.
- **Địa hình, độ cao, dốc (phát hiện 14/10):** mỗi ô của bản đồ có byte 5 = id địa hình (5 bit thấp) + độ cao (3 bit cao) và byte 4 = dạng dốc (0 phẳng). Bot từng đọc nguyên byte 5 làm id địa hình nên rừng trên nền cao không được nhận ra (60 % bản đồ Hill Country là nền cao); đã sửa. Đo bằng chính `can_place` của game trên 6 000 móng: **nhà 3×3 (BG, BS, BM, BB...) cần cả 9 ô phẳng** (0/376 được chấp nhận khi có ô dốc), **BE 2×2 xây được trên dốc và trên ô khác độ cao** (97 %). Độ cao và dốc không chặn đường đi (16/19 thử nghiệm đến nơi), nên không là tường khi bo nhà. Địa hình Desert/Water/Grass Impassable (14, 15, 16) là vật cản.
- **Cung A nâng cả 1 áo lẫn 2 áo trước (bạn chỉ ra 14/10, Minoan có 200 thực 150 gỗ mà không nâng 2 áo):** với lối cung A, Improved Bow (56) rồi Composite Bow (57) đều là công nghệ ra quân: được giữ thực, làm ở giá đúng, không bị luật "chưa đủ 4 lính" chặn, xếp trước giáp da / giáp vảy cung. Nhà cung đang ra lính thì không tính là nghiên cứu thất bại (trước đây 4 lần như vậy = nghỉ 120 s, 1 áo trễ 200 s); khi đủ tiền nghiên cứu thì nhà cung không nhận thêm lính.
- **Yamato đánh chuồng ngựa, không đánh cung (bạn hỏi 14/10):** Yamato có quân ngựa rẻ hơn 25 %. Phần "35 % số trận đánh cung" chỉ còn cho các phe có cung R; phe không có cung R (trừ Minoan) không còn rơi vào cung A.
- **Gốc cây không phải tường (bạn chỉ ra 14/10: bo mãi không kín ở chỗ rừng bị chặt hết):** cây chặt hết để lại gốc cây (`Tree_Stump`, class 16, bán kính 0), quân và dân đi qua được. Trước đây bot tính gốc cây là vật cản nên không thấy khe hở và không bịt. Giờ gốc cây không chặn trên lưới đi được, và BE được đặt lên chỗ gốc cây để bịt khe.
- **Ruộng trong tường (bạn chỉ ra 14/10):** quân không đi qua ruộng được, nhưng ruộng bị phá rất nhanh. Ruộng đã có được dùng làm tường, nhưng không ưu tiên: một ô ruộng trên đường cắt có giá gần bằng một ô BE mới (80 so với 100), còn rừng, nước, mỏ, mép bản đồ thì miễn phí. Ruộng bị phá thì lưới đi được đổi và kế hoạch tính lại, đặt BE vào chỗ đó.
- **Gỗ ruộng tính từ lúc nghiên cứu đời 2 khi thú sắp hết (15/10, các trận 14/10: Yamato 7 phút, Minoan 5 phút ở đời 2 trước khi kích đời 3, chuẩn của bạn 150–200 s):** thức ăn tự nhiên còn ≤ 4 dân thì gỗ cho các ruộng cần (tối đa 8, trừ phần thú còn) được đưa vào dự báo ngay trong lúc nghiên cứu đời 2, không chờ có BM (số dân gỗ vẫn bị chặn ở 7–10). Trước khi kích đời 3, BE tường chỉ xây khi trong kho còn đủ gỗ cho các ruộng đã định; xây 3 BE một lúc chỉ sau khi kích đời 3 hoặc khi bị đe doạ; luật "tường trước ruộng" chỉ áp sau khi kích đời 3.
- **Khe chéo không phải lỗ hở (đo 15/10):** dân không lách được giữa hai vật cản chỉ chạm góc (2/2 thử nghiệm). Bước kiểm tra rò không tính bước chéo như vậy nữa (trước đây báo "corner squeeze" hàng chục lần mỗi trận và tường đổi qua lại kín / rò).
- **Dân không bị cử quay lại chỗ có quân địch (15/10, v10b: 30 dân chết mỗi trận, phần lớn bị cử về lại bãi gỗ / ruộng / móng 8 s sau khi chạy):** mọi lệnh cho dân tới mục tiêu trong 10 ô quanh quân địch đời 3 bị giữ lại, dân chạy về TC và giữ trạng thái chạy chừng nào quân địch còn ở đó.
- **Móng bị game từ chối vì dân mình đứng trên đó (15/10):** log mới ghi lý do từ chối (mã 6, object chặn = Builder / Lumberjack): mọi ca "không rõ lý do" trước đây đều là thế. Giờ ứng viên móng có dân mình đứng trên bị bỏ qua, và chỗ bị từ chối vì dân mình không bị đưa vào sổ đen.
- **Dân xây đứng xa móng không nhúc nhích (v10b: 4 dân đứng 5 ô cạnh móng BS của đàn hươu 584 s):** dân có lệnh xây nhưng không tới được và không di chuyển trong 20 s được tính là kẹt; kẹt 4 lần thì xoá móng và thu hồi dân (trước đây chỉ tính khi dân không có lệnh).
- **Cổng mở cả khi tường chưa kín hẳn (v10b: 4 dân vàng bị dãy BE phía bắc chặn, mỏ cách 6 ô, "idle sau 6 lệnh" 3 phút):** khi dân và mục tiêu ở hai phía của vòng bo và trên lưới không còn đường vòng, một BE trên đường bị xoá như cổng, dù các đoạn khác còn hở.
- **Người dẫn voi bàn giao ngay từ cú đánh đầu tiên khi voi sát (≤ 2,5 ô):** trước đây chờ còn ≤ 15 máu; v10b người dẫn bàn giao ở 15 máu khi voi cách 1,7 ô và chết 2 s sau vì cú tiếp theo tới trước khi lệnh chạy có hiệu lực.
- **Cụm cách vòng bo ít nhất 6 ô, và chọn lại khi hết chỗ (v10d, 15/10: cụm của Minoan cách TC 29 ô với vòng r=26 nằm đúng trên đường cắt thật, BB và nhà cung không bao giờ xây được, không kích đời 3):** tâm cụm tìm từ R+6 tới R+19 ô (mọi phía: tới R+29); móng trong cụm cách TC ≥ R+4; 3 lần liền không có móng trống trong cụm thì bỏ cụm và chọn lại.
- **Sư tử đánh dân làm việc thì cả nhóm đánh lại (v10d, 15/10: một sư tử ở bãi gỗ / ruộng giết 5 dân Greek lần lượt trong 2,5 phút; luật tránh sư tử chỉ áp cho dân dò):** nạn nhân và tối đa 3 dân trong 7 ô (máu ≥ 12) cùng đánh sư tử, được giữ khỏi phân việc tới khi sư tử chết hoặc đi mất.
- **Móng có quân địch trong 12 ô thì không cử dân tới (v10e, 15/10: một móng BE nhận dân xây mới 6 lần trong 47 s, 17 dân Persian bị cung R bắn chết lần lượt):** dân đang xây ở đó được thả ra (và chạy), không bổ sung người, không ra lệnh xây mới ở chỗ như vậy; móng giữ lại để xây tiếp khi địch đi.
- **Cổng giữ mở chừng nào còn dân mình ở phía ngoài trong 14 ô (v10e: dân vàng ở mỏ cách tường 6 ô, cổng bị xây lại rồi phá mỗi chuyến, 30 gỗ một lần).**
- **Không mở cổng khi quân địch trong 30 ô quanh TC, cổng đang mở thì xây lại ngay (v11a, 15/10: một BE bị xoá làm cổng ở 1118 s, 3 kỵ binh vào làng ở 1146 s, 18 dân Minoan chết trong 90 s).**
- **Quân lẻ đời 1–2 tới gần dân (bạn chốt 15/10 sáng):** một đơn vị địch đời 1 hoặc 2 (ngựa dò, cung T, lính dùi cui...) đi lẻ mà vào trong 3 ô của một dân thì dân đó chủ động tấn công và gọi dân trong 8 ô cùng đánh (tối đa 5); nó ra khỏi tầm 3 ô của mọi dân đang làm việc thì dân quay lại làm, mặc kệ. Quân đời 3 thì dân luôn chạy.
- **Bo nhà sau khi kích đời 3 (bạn chốt 15/10 sáng):** trước khi kích đời 3 không xây BE để bo; chỉ tận dụng các công trình bắt buộc phải xây mà không có yêu cầu vị trí (BE tăng dân, BB, BM) đặt lên đường bo. Sau khi kích đời 3: gỗ ưu tiên 4–8 ruộng trước (tuỳ số dân rảnh), rồi mới bo; dân rảnh còn lại chặt gỗ, đủ gỗ thì tách từng người đi xây ruộng. Bạn: bo thường không tốn 20–28 BE; phương án bo của bot chưa chuẩn, sẽ chốt lại bằng ảnh 8 thế nhà.
- **BB không phải nhà quân (bạn chốt 15/10 sáng):** không bot nào đánh quân BB, nên BB không vào cụm nhà quân; nó chỉ được tận dụng đặt lên đường bo như BE, BM. Cụm nhà quân gồm BL, BA, BY, BK.
- **Cụm nhà quân (bạn yêu cầu 14/10):** mọi nhà quân (BB, chuồng ngựa, nhà cung, BY, xưởng) xây thành một cụm. Chỗ đặt cụm chốt một lần lúc bấm lên đời 2: ngoài vòng bo (quân sinh ra không bị nhốt, không đè lên đường tường), về phía nhà địch đã thấy, chưa thấy thì về phía tâm bản đồ (nhà ở giữa bản đồ: phía có nhiều vùng tối nhất), chỗ có nhiều móng 3×3 phẳng, trống, đã dò nhất; giữa các nhà chừa 1 ô để đi. BB đầu và nhà quân của lên đời cũng vào cụm (trước đây chúng bịt khe tường). Ngoại lệ giữ nguyên: BY tiền tuyến.
- **Tổng tấn công đi tới TC địch gần nhất** (trước đây: TC đầu tiên trong danh sách, trận 2v2 đi 110 ô thay vì 57).
- **BY tiền tuyến (bạn yêu cầu 13/10):** BY đi chậm, nên khi đã có một nhà BY gần nhà, 2 dân gỗ đi xây nhà BY tiếp theo cách nhà chính địch 20–26 ô về phía mình (không sát công trình địch), để BY sinh ra ở gần trận. Dân đi xây qua tường thì cổng tự mở.

### 3.8 Tường bằng nhà ("bo nhà")

- **Bo theo địa hình (bạn chỉ ra 12/10/2026 23:00, đang thay thế vòng nhà):** vực, rừng, nước, tàn tích, mép bản đồ là tường có sẵn; chỉ xây BE để **nối các mảng địa hình đó với nhau**, không xây BE thành vòng tròn quanh nhà chính. Cài đặt: `walling.plan_cut` tìm **lát cắt nhỏ nhất** (max-flow/min-cut trên lưới ô, 4 hướng, không cắt góc) ngăn khu nhà (TC + BG + BS) với mọi ô cách TC ≥ 14 ô (hoặc 20 ô nếu rẻ hơn); mỗi ô cắt được phủ bằng móng 2×2; ô không đặt được nhà (khe 1 ô giữa hai rừng) không được cắt, nên đường cắt tự dịch tới chỗ đặt được; cắt lại với nhà đã đặt tới khi không còn đường ra. Ô chưa thám hiểm không được dùng làm tường cũng không được cắt. Mô phỏng 40 bản đồ có rừng: **kín 40/40, trung vị 12 nhà** (vòng cũ: 42 nhà, vẫn rò 1–3 chỗ).
- **Học từ trận của bạn (13/10 02:00, bản ghi trận với 7 AI):** bạn bo ở **20–25 ô** từ nhà chính: mép bản đồ ↔ rừng bằng BE + chuồng ngựa, nhà lính ↔ rừng bằng chuỗi BE, BS + BE trong khe rừng; cổng là BE sát mép bản đồ cạnh chuồng ngựa, xoá rồi xây lại sau 4–34 s. → bot thử bán kính 14 / 26 / 40 và chọn lát cắt ít nhà nhất (bản đồ giống của bạn: bán kính 20 cần 20 nhà, 32–40 chỉ 5 nhà); "đã biết địa hình" = 90 % ô dọc đường cắt đã thám hiểm (không đòi cả đĩa); ô chưa thám hiểm vẫn cắt được, nhà ở đó chờ thám hiểm; vòng đã chốt mà không khép được nữa thì chọn lại. Arena wall4 (x2): bot chọn lại r=40 chỉ **8 nhà**, **kín lúc 11:30**, 9 lần mở/đóng cổng (mở 15–60 s).
- *Sửa 13/10 03:40:* BS/BG ở xa (bãi gỗ, mỏ vàng xa) không còn bắt buộc phải nằm trong bo — trước đây một BS cách 37 ô làm mọi bán kính bị loại và bot không bao giờ bo rộng lại; chỗ đặt nhà mà bộ kiểm tra của bot liên tục từ chối (rừng địa hình, vật trang trí) được tính là bị từ chối để lát cắt đi vòng (trước đây một chỗ bị bỏ qua lặng lẽ suốt 25 phút).
- **BB/BM dùng làm đoạn tường**: nhà chợ và chuồng ngựa đầu (phải xây để lên đời) đặt lên đường cắt (móng 3×3 che ≥ 2 ô cắt) thay cho 2 BE; nhà quân sau đó vẫn ở ngoài bo, sát mép khu kín về phía địch.
- *Sửa 13/10 00:40 sau trận test dài của bạn:* vòng ruộng quanh BG (bán kính 6,5) từng bị coi là "không cắt được", với BG cách TC 8 ô nó vươn quá bán kính 14 nên lát cắt vô hạn → bot không bao giờ bo rộng, chỉ bo nhỏ (lại là vòng BE); nay vòng ruộng chỉ "đắt" chứ không cấm. Kế hoạch không có lát cắt không còn bị tính là "đã kín" (P3 báo kín với 0 nhà ở giây 71). Dân bị nhốt chỉ được mở cổng khi trạng thái kín là thật — nay đúng.
- "Trong bo" = tập ô kín của kế hoạch (không còn là đĩa bán kính); nhà tường = BE đứng trên móng đã từng được lập kế hoạch; cổng (xoá BE cho dân/quân ra vào) giữ nguyên.

- Cứ 20 giây AI tính lại kế hoạch bo nhà theo địa hình đã khám phá. Có hai kiểu:

  - **Bo nhỏ** quanh khu ruộng/BS.

  - **Bo rộng** cả khu nhà. Chỉ làm khi đã khám phá ≥ 85% vùng xung quanh, đối phương chưa đe dọa, và đủ gỗ.

- Để 1 ô làm cổng ở phía xa đối phương.

- Dùng BE, BB, BM, BA, BL để bịt các khe. BS và BG đặt theo hướng tối ưu cho việc ăn, không dùng để bịt.

- Chọn bo nhỏ hay bo rộng tùy lượng gỗ, đời của đối phương và việc đối phương đã có ý đánh hay chưa.

- **Bo kín hoàn toàn, không cổng** *(bạn đặt 12/10/2026 trưa; trước đó tôi tự để một cổng 1 ô phía xa địch)*: bản vẽ tường không chừa lỗ nào. Khi quân hoặc dân phải ra/vào, AI **xoá (Delete) BE gần đường đi nhất** (lệnh 0x6A tại 0x4EBBF0, kiểm chứng trong arena: nhà biến mất sau 6 s), tối đa 2 lỗ cùng lúc; lỗ được **xây lại ngay** khi 5 s không còn quân/dân nào của mình trong 4 ô quanh đó (và ít nhất 8 s sau khi mở). Mọi lệnh di chuyển/tấn công đi qua một chỗ (order/move và adapter của task) nên dân đi săn xa, dân xây BS ngoài, quân xuất kích, ngựa dò đều tự xin mở cổng. **Lỗ rò 1 ô** (khe cạnh vách đá / cây mà BE 2×2 không đặt lên được) *(bạn chỉ 12/10/2026 trưa)*: vẫn bịt bằng BE đặt **lùi vào trong hoặc nhô ra ngoài** một chút — không cần khớp, miễn quân dân không đi lọt. Bản vẽ chạy thêm một lượt cho các lỗ rò: thử các vị trí BE quanh lỗ (±4 ô), giữ vị trí gần nhất mà sau khi chặn thì từ lỗ không còn đi được cả vào sâu bên trong lẫn ra ngoài (BFS trong 8 ô). Thử trên bản đồ giả: 2 khe 1 ô đều bị chặn, 0 lỗ rò. **Kiểm chứng arena gate16 (12/10/2026 13:46):** 4/4 AI chốt vòng, tường KÍN lúc 17:28 và 19:00 (23–26 BE), 41 lần xoá BE cho dân/quân qua và 18 lần xây lại trong 6 phút, 0 lỗi. Giới hạn sau đó: một lỗ mở mỗi lúc, mở ít nhất 15 s. Tiêu chí "kín" = bản vẽ tính lại trên bản đồ thật không còn lỗ/ô nào (BE đã xây là vật cản nên không đếm được theo ô).

### 3.9 Xe thánh tích (Artifact)

- Đi dò quanh nhà. Sau phút thứ 6 thì chạy dọc các mép bản đồ.



- **Câu voi / lùa hươu của người chơi (5 trận online 13/10, 4 người):** 38 voi bị giết, từ phát giáo đầu tới chết trung vị **27 s**, 11 phát, 4 dân quanh xác, chết cách nhà chính trung vị 3,8 ô (p90 53 ô = giết tại chỗ), dân mất máu trung vị 0. Hươu: dân tới 3–3,5 ô thì 66 % con nhảy trong 2 s; 51 % cú nhảy đưa nó gần nhà hơn; góc dân so với đường về nhà trung vị 81°.

### 3.8b Ruộng và nghiên cứu (13/10/2026, sau trận test của bạn)

- **Ruộng:** 28 "dân ruộng" cho 10 ruộng xong, 18 móng ruộng dở → bảng phân công giới hạn dân ruộng = ruộng xong + móng đang xây + 2; dư thì sang gỗ/vàng. (Luật một dân một ruộng vẫn giữ.)
- **Dành thực cho công nghệ (13/10 03:40):** trận thử 32 phút: 13 phút đời 3 chỉ 1 công nghệ dù có 1 879 vàng, vì BL và TC tiêu ngay từng 50–70 thực nên thực không bao giờ đủ 100–300 cho giáp/công ở BS. Nay ở đời 3, khi đã có ≥ 6 quân và không bị đánh, thực/vàng của công nghệ ưu tiên kế tiếp (nhà nghiên cứu đang rảnh) được **giữ lại**: ra ngựa, BY, cung và dân (từ dân thứ 35) chỉ dùng phần dư.
- **Nghiên cứu:** cả trận 45 phút mỗi bot chỉ 1–11 công nghệ vì mỗi lúc chỉ cho một nghiên cứu cho cả làng, mỗi lần thử hỏng chặn 6 s, và trừ sẵn 120 thực + 140 vàng ngoài giá. Nay mỗi loại nhà một nghiên cứu, các loại chạy song song (BS: giáp/công, BG: nông nghiệp, chợ: xe…); dự trữ chỉ 60–100 thực, 40–100 vàng (ít hơn khi quân đã đủ 12). Thứ tự ưu tiên: bánh xe, cung, công cụ, giáp ngựa, gỗ, vàng, thuần hoá, giáp vảy ngựa, luyện kim…

### 3.9b An toàn tiến trình game (13/10/2026)

- Trận 1v7 của bạn: một bot "mất kết nối" và game treo. Nhật ký lỗi Windows cho thấy AOEBOT.EXE của bot đó **crash truy cập bộ nhớ** trong hàm tạo lệnh xây (0x4EB8E3): bộ não ra lệnh xây cho con dân vừa chết (ảnh chụp cũ 1–4 s vì 7 bộ não chạy cùng lúc), game đọc bộ nhớ đã giải phóng. Host chờ người chơi rơi mãi → treo.
- Sửa: trước **mọi** lệnh (đi, đánh, dừng, xây, huấn luyện, nghiên cứu, xoá) bộ não đọc lại id tại con trỏ (+4) và máu (+0x30) của từng đối tượng; đối tượng không còn đúng thì bỏ khỏi lệnh, mục tiêu chết thì thành lệnh đi tới chỗ cũ.
- Lưu ý tải: 7 bot trên một máy làm tick bộ não 1–4 s (837 cảnh báo chậm trong trận); nên chơi ≤ 3–4 bot hoặc chờ tối ưu tick.

### 3.10 Tự đầu hàng

- Đầu hàng khi **tổng dân + quân của AI dưới 3/7 của người chơi, sau phút 5** (bạn giữ luật này: trận 11/10 AI bị thua là đúng, phải sửa kinh tế để lên đời sớm chứ không sửa luật).

