# Eval card — LogiX-VN refund agent

Card này đi kèm mỗi báo cáo và được dùng lại ở Day 10.

- **Run ID / eval set SHA:**
- **Phiên bản:** code (commit) … · eval set v1 (sha …) · metric_spec … · grader (commit) … · seeds 11/22/33/44/55
- **Eval set:** v1, 14 item × 5 seed, nguồn lab8_public; nhãn: labels_v1.json
- **Metric & ngưỡng:** (trích metric_spec.yaml)
- **Kết quả baseline vs PR:** bảng + paired CI
- **Judge:** tone_ok κ=…, P=…, R=…; helpful bị loại vì …
- **Trace case:** link `docs/trace_case.md`, bước sai đầu tiên, regression test
- **Gate owner:** ai xử lý khi gate exit 1
- **Phạm vi pilot:** …
- **Giới hạn / bằng chứng còn thiếu:** MockLLM, 14 item, judge replay; không đo trên người dùng thật
- **Khi nào tăng eval-set version:** …

## M6 — Độ tin cậy trên v2

- **Metric blocking:** `pass_hat_5` ≥ 0.80. `pass_hat_5` là tỉ lệ item có cả 5 lần chạy đều
  pass; do đó một lỗi chập chờn 1/5 lần vẫn làm item đó không đạt, dù `pass_rate` trung bình
  có thể còn trên sàn.
- **A/A:** với MockLLM cố định, cùng agent chạy hai bộ seed `[11,22,33,44,55]` và
  `[66,77,88,99,110]` cho Δ=0. Không nên suy ra LLM thật cũng có nhiễu bằng 0: sampling,
  khác biệt backend/model version, tải dịch vụ và biến thiên thời gian chạy có thể làm kết quả
  cùng prompt khác nhau.
- **Chọn sàn:** `pass_hat_5` ≥ 0.80 là sàn blocking của bài lab; Δ=0 cho biết hai lần chạy
  MockLLM không cho thấy nhiễu trên phép so sánh đó. Khi dùng LLM thật, lặp nhiều A/A trên cùng
  phiên bản và cấu hình, ước lượng dải biến thiên của chính metric; đặt sàn thấp hơn biên dưới
  của dải nhiễu bình thường, không đặt bên trong dải đó, nếu không PR trung thực có thể bị chặn
  ngẫu nhiên.

## M7 — Integrity và giới hạn

Gate từ chối report có dòng `(item_id, seed)` trùng/lệch baseline, số dòng không khớp manifest,
metric không khớp aggregate từ rows, grader bị lỗi (kể cả khi metric tổng trông xanh), metric
grader bị null, slice bị đổi nhãn, hoặc spec bị nới trên cùng eval-set version. Một report bị
chỉnh đồng bộ cả rows lẫn aggregates vẫn cần nguồn chạy độc lập để xác thực; vì vậy CI phải tự
chạy eval trên PR thay vì tin report do PR cung cấp.
