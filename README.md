# AoESolo — AI đánh AoE 1 theo luật D3KT, chơi giống người

AoESolo là một launcher cho **Age of Empires 1: The Rise of Rome (bản "AoE-HD")**: bạn bấm "Chơi", launcher tự mở thêm các bản game chạy ẩn cho từng máy (bot), cho chúng vào phòng LAN với bạn và điều khiển từng con dân, từng đơn vị quân của bot **từ bên ngoài game**, như một người chơi thật ngồi trước máy. Bot chơi theo **luật D3KT** ("Đời 3 không thành") của cộng đồng AoE Việt Nam và theo lối chơi của người chơi giỏi.

**Tải về:** xem mục [Releases](https://github.com/trandinhnamuet/aoe-bot-d3kt/releases).

---

## 1. Vấn đề của AI trong AoE xưa nay

Ai chơi AoE 1 lâu năm đều biết máy (computer player) có sẵn trong game không phải là đối thủ để luyện:

1. **Không chơi theo luật D3KT.** Luật D3KT mà người Việt chơi với nhau gồm: không xây thành, chòi; không tấn công trước khi kích lên đời 3; không có quá 1 quân trước khi lên xong đời 3; không dùng dân đánh dân. Máy của game không biết những luật này: nó xây chòi, đem quân và dân đánh sớm, nên một trận "đánh máy" không giống một trận D3KT thật.
2. **"Hack" tài nguyên để lên đời.** Ở các mức khó cao, máy được game cho lợi thế tài nguyên mà người chơi không có, nên nó lên đời nhanh và ra quân đông mà không cần kinh tế giỏi. Thắng hay thua máy vì thế không phản ánh trình độ quản lý kinh tế.
3. **Hành vi không giống người.** Máy không câu voi, không lùa hươu về nhà, không bo nhà bằng BE, đi dân lộn xộn, để dân đứng chơi, đánh quân từng con một, không biết rút dân khi bị cướp, không chọn lính theo quân địch. Người chơi quen với nó sẽ học phải những phản xạ sai.

## 2. Vì sao lại như vậy: cơ chế game và giới hạn thời điểm làm game

- **AI của AoE 1 là hệ luật viết tay** (file chiến lược `.ai` liệt kê thứ tự xây, file luật `.per` kiểu "nếu … thì …"). Một luật chỉ nhìn được vài con số tổng (số dân, số tài nguyên, đời hiện tại), không nhìn thấy bản đồ, không điều khiển được từng con dân theo từng giây. Những việc người chơi giỏi làm hằng giây — câu một con voi bằng một phát lao rồi chạy, đứng sau đàn hươu đúng góc để chúng nhảy về nhà, chọn chỗ đặt BE nối các mảng rừng — không viết được bằng loại luật đó.
- **Máy tính năm 1997** (Pentium 100–200 MHz, vài chục MB RAM) phải chạy cùng lúc đồ hoạ, tìm đường cho hàng trăm đơn vị và tối đa 7 máy. Ngân sách tính toán cho mỗi máy rất nhỏ, nên AI được thiết kế đơn giản, và chỗ thiếu khôn ngoan được bù bằng **lợi thế tài nguyên** — cách rẻ nhất để máy "khó" hơn.
- **Cơ chế vi mô của game rất khó cho máy.** Lệnh trong game nhiều người chạy theo kiểu lockstep: một lệnh tới game trễ ~1 giây ở tốc độ x1, ~2 giây ở x2. Hươu sợ người ở ~2 ô và nhảy 2,75 ô ngẫu nhiên; voi bỏ đuổi sau vài giây; giáo có tầm 3 ô, nạp 1,5 s. Lùa hay câu cho tốt phải tính trước cả độ trễ lệnh lẫn phản ứng ngẫu nhiên của con vật, việc mà người chơi học bằng cảm giác qua hàng nghìn trận.
- **Luật D3KT ra đời sau, trong cộng đồng**, không phải luật của game, nên AI gốc không có lý do gì để biết nó.
- **Thiết kế một AI "giống người"** cần dữ liệu về cách người chơi thật đánh (thứ tự dân, cách chia việc, khi nào lên đời, cách bo nhà…). Thời đó không có dữ liệu ấy, cũng không có các kỹ thuật như học từ bản ghi trận hay mô phỏng để thử hàng nghìn lần.

## 3. AoESolo làm khác thế nào

- **Không cộng tài nguyên, không nhìn xuyên sương mù để gian lận**: bot chỉ dùng lệnh như người chơi (chọn dân, chuột phải, xây, huấn luyện, nghiên cứu, xoá nhà) qua cùng hàng đợi lệnh của game.
- **Luật D3KT là luật cứng**: không thành/chòi, không quá 1 quân trước đời 3, không đánh trước khi kích đời 3, không dùng dân đánh dân; đối phương phạm luật trước thì bot được đáp trả. Tự đầu hàng khi lực lượng còn dưới 3:7 sau 5 phút.
- **Kinh tế theo tư duy người chơi**: 6 dân quả, 2 dân dò, dân thứ 8 gỗ, BS sớm, câu voi về nhà chính/BS gần nhất, lùa đàn hươu, 25 dân trước đời 2, ruộng một người một ruộng, nâng công nghệ song song.
- **Vi mô có tính trễ lệnh**: câu voi (một phát lao rồi chạy, đứng chờ khi voi bỏ đuổi, dân chờ sẵn ở nhà để kết liễu), lùa hươu (chọn điểm bước vào để mọi con nhảy về phía nhà chính, phi từ phía ngoài đồng khi giết), chạy dân khi bị cướp.
- **Bo nhà theo địa hình**: tìm lát cắt nhỏ nhất giữa khu nhà và vùng ngoài, rừng / vực / nước / mép bản đồ là tường có sẵn, BE (và BM, BL phải xây để lên đời) chỉ nối các mảng địa hình; dân/quân cần ra vào thì xoá một BE rồi xây lại.
- **Đời 3**: chọn quân theo quân địch (ngựa, cung, BY cho Hy Lạp / Macedonia), quân ra ở nhà lính ngoài bo, 2 quân là đi đánh, bị đánh thì về thủ.
- **Đo được, kiểm chứng được**: mỗi bài toán con có điều kiện pass do người chơi đặt và được đo trong mô phỏng lẫn trong trận thật (xem `RL_BAI_TOAN_CON.md`).

## 4. Cài và chơi

1. Cần có sẵn game **AoE 1 Rise of Rome bản AoE-HD** trên máy (ví dụ bản cài qua XArena). Repo này **không** kèm game.
2. Tải `AoESolo.zip` ở Releases, giải nén ở đâu cũng được, chạy `AoESolo.exe`.
3. Launcher **tự tìm thư mục game** (thư mục đã chọn lần trước, khoá registry do bộ cài game ghi — XArena ghi `C:\Program Files\XArena\Game\AoE-HD` —, các đường dẫn hay gặp, rồi dò nhanh các ổ đĩa). Không thấy thì bấm **"Chọn..."** để trỏ tới thư mục có `EMPIRESX.EXE`; lựa chọn được nhớ cho lần sau.
4. Nếu thư mục game nằm trong `Program Files` (cần quyền admin để ghi), launcher hỏi để **chép bản game trên máy đó** sang `%LOCALAPPDATA%\AoESolo\AoE-HD` và dùng bản chép.
5. Nhập tên, chọn số máy và phe, bấm "Chơi". Các bot chạy ẩn, không chiếm bàn phím, chuột. Khuyến nghị tốc độ x2, máy yếu nên để 1–4 bot.

## 5. Cấu trúc mã

| Thư mục / file | Nội dung |
|---|---|
| `launcher/main.py`, `orchestrator.py`, `lobby.py`, `dplobby.py` | giao diện, mở game, phòng LAN qua DirectPlay |
| `launcher/inject.py`, `aoemem.py`, `gamestate.py` | đọc bộ nhớ game, gọi hàm lệnh của game qua hook |
| `launcher/d3kt.py` | bộ não chính: kinh tế, săn, bo nhà, lên đời, quân |
| `launcher/brain/` | bảng phân công dân, các task vi mô (câu voi, lùa hươu), chiến thuật đời 3 |
| `launcher/walling.py` | lập kế hoạch bo nhà (lát cắt nhỏ nhất theo địa hình) |
| `launcher/sim/` | mô phỏng 2D để thử câu voi / lùa hươu hàng nghìn lần |
| `launcher/rl/` | thử nghiệm học tăng cường cho lùa hươu (đã dừng, giữ lại mã) |
| `hook/` | DLL nạp vào game để gọi lệnh, công cụ mở game ẩn |
| `tools/` | arena (cho các bot đấu nhau để đo), học từ bản ghi trận, chẩn đoán |
| `LUAT_D3KT.md` | toàn bộ luật và quy tắc lối chơi bot đang theo |
| `KIEN_TRUC_AI.md`, `RL_BAI_TOAN_CON.md`, `RL_LUA_HUOU.md` | kiến trúc, bảng bài toán con và tiến độ |

Build exe: `python build.py --no-game` (cần Python 3.10 + PyInstaller trong `.venv`).

## 6. Giới hạn hiện tại

- Lùa hươu còn chậm hơn người (đàn tiến ~0,25 ô/s); câu voi ở x2 đạt ~85 % theo chuẩn chặt (voi chết ≤ 4 ô mép nhà, không dân chết, ≤ 150 s).
- Bo nhà theo địa hình mới thay vòng BE, đang được kiểm chứng trong trận thật.
- Chỉ chạy trên Windows, với đúng bản AoE-HD đã dò địa chỉ hàm.
