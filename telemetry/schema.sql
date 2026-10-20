-- Thống kê sử dụng AoE Bot D3KT / AoESolo (Cloudflare D1, tài khoản riêng - xem README.md). Giờ lưu theo ms UTC;
-- trang thống kê gom ngày theo giờ Việt Nam.
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts INTEGER NOT NULL,            -- ms UTC lúc nhận
  install TEXT NOT NULL,          -- mã máy (UUID ngẫu nhiên tạo lần đầu chạy, %APPDATA%\AoESolo\install_id)
  app TEXT NOT NULL,              -- aoesolo
  version TEXT NOT NULL,          -- launcher/version.py
  ev TEXT NOT NULL,               -- open (mở launcher) | match (bấm Start, trận vs bot bắt đầu)
  ip TEXT,                        -- IP người gọi (CF-Connecting-IP; app kết nối bằng IPv4)
  country TEXT,                   -- mã nước theo Cloudflare
  name TEXT,                      -- tên người chơi trong phòng (cho phép trùng, có thể rỗng)
  bots INTEGER,                   -- match: số AI trong phòng (1..7)
  civ TEXT,                       -- match: quân người chơi chọn ("Random" nếu để game rút)
  size TEXT                       -- match: kích thước bản đồ
);
CREATE INDEX IF NOT EXISTS events_ts ON events(ts);
CREATE INDEX IF NOT EXISTS events_install_ts ON events(install, ts);

CREATE TABLE IF NOT EXISTS installs (
  install TEXT PRIMARY KEY,
  first_ts INTEGER NOT NULL,
  last_ts INTEGER NOT NULL,
  first_ip TEXT,
  last_ip TEXT,
  country TEXT,
  app TEXT,
  version TEXT,
  opens INTEGER NOT NULL DEFAULT 0,
  matches INTEGER NOT NULL DEFAULT 0,
  name TEXT                       -- tên người chơi gần nhất của máy
);
CREATE INDEX IF NOT EXISTS installs_last ON installs(last_ts);
