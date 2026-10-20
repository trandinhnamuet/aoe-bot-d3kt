# Thống kê sử dụng AoE Bot D3KT (telemetry)

Cloudflare Worker + D1 nhận thống kê từ launcher (launcher/telemetry.py). Chép từ AoE-MapCap/telemetry, thêm số bot,
quân người chơi và kích thước bản đồ cho mỗi trận.

## Tài khoản Cloudflare (RIÊNG, không chung quota với AoE-MapCap)

| App          | Gmail                      | Account ID                       | Worker / trang thống kê |
|--------------|----------------------------|----------------------------------|-------------------------|
| AoE-MapCap   | trandinhnamuet@gmail.com   | 0e94c764717751df22419cf08ffcbf2b | https://aoe-mapcap-telemetry.aoemapcap.workers.dev/stats |
| AoE Bot D3KT | minhtuan90959095@gmail.com | 628734c2276f1bf92534091a36cc2d58 | https://aoesolo-telemetry.aoebotd3kt.workers.dev/stats |

Quota gói miễn phí (100 000 request/ngày, D1 100 000 dòng ghi/ngày) tính theo tài khoản, nên hai app ở hai tài khoản
không ảnh hưởng nhau. Tạo ngày 20/10/2026.

Đăng nhập wrangler của tài khoản AoE Bot D3KT lưu riêng ở `C:\Users\Admin\.cf-aoesolo` (biến `XDG_CONFIG_HOME`), để không
ghi đè đăng nhập MapCap ở `~/.config/.wrangler`. Mật khẩu trang /stats: `C:\Users\Admin\.cf-aoesolo\stats_password.txt`
(không đưa vào repo). D1: `aoesolo-telemetry`, APAC, id 657ead74-5e56-49be-a532-7c30fb194f7e. Subdomain workers.dev
`aoebotd3kt` (đăng ký qua API vì wrangler không hỏi được trong shell không tương tác).

## Lệnh

    python deploy.py            # wrangler deploy với đúng tài khoản
    python deploy.py secret     # đổi mật khẩu trang /stats (đọc từ stats_password.txt)
    python deploy.py sql "SELECT COUNT(*) FROM events"     # chạy SQL trên D1 thật
    python deploy.py schema     # tạo bảng lần đầu (schema.sql)

Đăng nhập lại khi token hết hạn: `set XDG_CONFIG_HOME=C:\Users\Admin\.cf-aoesolo` rồi `npx wrangler login`, đăng nhập bằng
Gmail minhtuan90959095@gmail.com.

## Giao thức

- `POST /v1/e` body JSON: `id` (UUID máy), `app` = "aoesolo", `v` (phiên bản), `ev` = "open" | "match", `name` (tên trong
  phòng, có thể rỗng); với `match` thêm `bots` (1..7), `civ` ("Random" nếu để game rút), `size` (Large/Huge/...).
- `GET /stats` trang thống kê (mật khẩu STATS_PASSWORD), `GET /api/stats?range=7d&page=1&q=` với `Authorization: Bearer`.
- Bỏ trùng cùng máy + loại trong 5 s; một IP quá 120 lượt/phút bị bỏ.

Launcher: gửi `open` khi mở AoESolo.exe, `match` khi bấm Start trong phòng (trận vs bot bắt đầu). Tắt bằng ô "Gửi thống kê
sử dụng" trong Cài đặt trận hoặc `AOESOLO_TELEMETRY=0`. Chạy từ mã nguồn không gửi trừ khi `AOESOLO_TELEMETRY=1`;
`AOESOLO_TELEMETRY_URL` đổi địa chỉ nhận để kiểm thử.
