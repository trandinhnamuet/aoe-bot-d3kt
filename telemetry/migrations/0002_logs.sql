-- Logs gửi từ launcher (nút "Gửi log cho dev" và tự gửi sau trận / khi vào phòng lỗi), 02/11/2026.
CREATE TABLE IF NOT EXISTS logs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts INTEGER NOT NULL,            -- ms UTC lúc nhận
  install TEXT NOT NULL,          -- mã máy
  version TEXT NOT NULL,
  kind TEXT NOT NULL,             -- manual | match_end | setup_failed | ...
  name TEXT,                      -- tên người chơi
  ip TEXT,
  sys TEXT,                       -- JSON: cpu, ram, windows...
  note TEXT,                      -- ghi chú người chơi (nút gửi)
  raw_size INTEGER,               -- byte trước khi nén
  data BLOB NOT NULL              -- aoesolo.log của phiên, gzip
);
CREATE INDEX IF NOT EXISTS logs_ts ON logs(ts);
