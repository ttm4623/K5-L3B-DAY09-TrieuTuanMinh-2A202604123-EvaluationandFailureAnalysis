# Trace case: từ trace tới quyết định sai đầu tiên

Một trace case trả lời ba câu hỏi: **trial nào lỗi, event nào là bằng chứng sớm nhất, và test
nào sẽ ngăn lỗi tái diễn?** Không suy đoán ý định của model; mô tả sự kiện, ledger và nhãn
quan sát được.

## Chạy và đối chiếu

Chạy từ `src`. Lệnh trace case phát lại đúng một claim/seed trên shape được chọn trong một
SQLite tạm; lệnh này không đọc report có sẵn và không ghi vào DB của nhóm.

```powershell
python -m lab9.trace_case --shape seeded_regression --claim C-002 --seed 11
python -m lab9.trace_case --shape fixed --claim C-002 --seed 11
```

Lệnh hiện hỗ trợ claims trong `data/public_claims.jsonl`. Output có grader Lab 8, event theo
thứ tự (`kind` và payload), ledger so với label, trạng thái và số ledger row ngoài ý muốn.
Payload in ra bị rút gọn ở 110 ký tự và SQLite/trace tạm bị xóa sau lần chạy. Nếu phần bị cắt
là bằng chứng quan trọng, chưa kết luận từ output này; cần lưu/hiển thị đầy đủ trace trước khi
hoàn tất case.

Để gắn case với báo cáo, tìm cùng shape, claim/item và seed trong report tương ứng, rồi ghi
run ID và eval-set SHA từ report. `trace_case` tự nó không phát hành run ID. Adversarial claims
chỉ có trong pack v2; công cụ này chưa nạp pack đó, nên không ghi kết quả replay v1 như bằng
chứng cho claim adversarial.

## Mẫu ghi nhận

Mỗi case cần có một người phụ trách và bằng chứng tái hiện. Không điền kết quả chưa chạy.

| Trường | Nội dung |
|---|---|
| Trial | `<shape> <claim>@<seed>` |
| Báo cáo | Đường dẫn report, run ID, eval-set SHA; hoặc ghi “replay độc lập, chưa đối chiếu report” |
| Triệu chứng | Grader nào fail; reply nói gì, ledger ghi gì |
| Event sai đầu tiên | Số thứ tự + `kind` + phần payload liên quan (trích ngắn, đã loại secret) |
| Vì sao là sớm nhất | Các event trước đó đúng ở điểm nào; dẫn số event |
| Failure mode | Mã FM-xx và căn cứ trong [`failure_taxonomy.md`](./failure_taxonomy.md) |
| Đối chứng | Cùng claim/seed chạy `fixed`; nêu khác biệt quan sát được |
| Regression test | Tên test/grader/assertion; xác nhận fail trên variant lỗi và pass trên `fixed` |
| Giới hạn | Điều trace không chứng minh được hoặc chưa tái hiện được |

## Quy tắc phân tích

- Đọc ledger và policy trước khi kết luận từ reply: reply trôi chảy vẫn có thể báo sai khoản hoàn.
- “Event sai đầu tiên” là event sớm nhất vi phạm dữ kiện, policy hoặc invariant có thể quan sát;
  ghi số thứ tự cụ thể, không viết chung “agent bị nhầm”.
- Phân biệt triệu chứng với nguyên nhân: ví dụ reply sai số tiền là triệu chứng; kiểm tra quote,
  approval, host và ledger để xác định bước đầu tiên làm lệch kết quả.
- Không chép secret, token, header nhạy cảm hoặc dữ liệu cá nhân vào tài liệu.
- Case chỉ hoàn thành khi regression test chạy được: thêm test vào `tests/`, hoặc thêm item eval
  có FM tag và `provenance.from_trace` trỏ về trace đã được xem xét.
- Nếu chưa chạy đối chứng/test, đánh dấu rõ “chưa xác minh”; không suy ra PASS từ việc code có grader.
