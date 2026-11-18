# Judge audit (M2)

Calibration lệnh:

```powershell
python -m lab9.judge --csv data/eval/judge_tone_public.csv --audit 5
python -m lab9.judge --csv data/eval/judge_helpful_public.csv --audit 5
```

`FAIL` là lớp dương. Ma trận dưới đây theo thứ tự TP / FP / FN / TN; helpful được tính
trên nhãn CSV hiện tại, trước khi xử lý bất đồng nhãn ở HL-081.

| Tiêu chí | n | TP/FP/FN/TN | κ | Precision | Recall | Đạt floors (κ≥0.6, P≥0.8, R≥0.7)? | Quyết định |
|---|---:|---|---:|---:|---:|---|---|
| tone (`judge_tone_public.csv`) | 100 | 24 / 4 / 6 / 66 | 0.757 | 0.857 | 0.800 | Có | Dùng có giới hạn cho giọng điệu |
| helpful (`judge_helpful_public.csv`) | 100 | 9 / 1 / 21 / 69 | 0.353 | 0.900 | 0.300 | Không | Không dùng làm gate |

`judge_helpful` bỏ sót 21/30 lỗi theo nhãn hiện tại (recall 0.300, dưới floor 0.700) và
κ=0.353, thấp hơn mức đồng thuận tối thiểu. Precision 0.900 không bù được việc judge thường
cho PASS những câu trả lời trôi chảy nhưng sai dữ kiện. Tỉ lệ FAIL quan sát được là 0.100;
Rogan–Gladen hiệu chỉnh thành 0.300 với sensitivity 0.300, specificity 69/70. Vì vậy dùng
judge này làm gate sẽ để lọt phần lớn câu trả lời không hữu ích. `judge_tone` đạt floors trên
bộ replay này, nhưng chỉ nên đánh giá tiêu chí tone đã hiệu chỉnh; không dùng nó để chấm tiền
hoặc approval.

## Audit bất đồng

| Case | Judge nói | Người nói | Ai đúng? | Hành động sửa rubric / nhãn |
|---|---|---|---|---|
| HL-015 | PASS | FAIL | Người đúng: reply hứa 55.000đ, ghi chú cho biết ledger chỉ có 40.000đ. | Không để độ lịch sự che lấp sai kết quả; so số tiền reply với ledger bằng code. |
| HL-016 | PASS | FAIL | Người đúng: reply báo 55.000đ, ledger 35.000đ. | Thêm ví dụ phản chứng: câu dài, xin lỗi nhiều nhưng sai số tiền vẫn FAIL. |
| HL-020 | PASS | FAIL | Người đúng: reply báo 90.000đ, ledger 120.000đ. | Đối chiếu khoản đã ghi, không chấm theo sự tự tin hay cách diễn đạt. |
| HL-028 | PASS | FAIL | Người đúng: reply báo 50.000đ, ledger 35.000đ. | Tách `helpful` khỏi `polite`; tiền sai là lỗi factual, nên code grader quyết định. |
| HL-035 | PASS | FAIL | Người đúng: reply báo 50.000đ, ledger 35.000đ. | Cùng loại lỗi lặp lại: thêm quy tắc “sai số tiền => không helpful” và kiểm tra tự động. |
| HL-047 | PASS | FAIL | Người đúng: “Ok bạn … nhé” dùng xưng hô quá suồng sã theo nhãn audit. | Nêu rõ cách xưng hô phù hợp; không coi riêng từ “Dạ” là đủ để PASS. |
| HL-081 | FAIL | PASS | Judge đúng theo ghi chú của bộ dữ liệu: nhãn người đọc nhầm ticket. | Sửa/đối soát nhãn gold bằng người thứ hai; không đổi rubric để khớp một nhãn sai. |

## Rubric sau audit

1. Chấm riêng từng tiêu chí: liên quan yêu cầu, bước tiếp theo hữu ích, đúng trạng thái, giọng
   điệu/xưng hô phù hợp. Văn phong lịch sự hoặc dài không thể bù cho thông tin sai.
2. Không giao cho LLM judge quyền xác nhận số tiền hay approval. Dùng code so reply/ledger và
   policy; judge chỉ xét chất lượng giao tiếp sau khi kết quả đã được xác minh.
3. Với helpfulness, FAIL nếu lạc đề, không hỏi thông tin thiết yếu, ra lệnh/xưng hô không phù
   hợp, hứa vượt kết quả thật, hoặc làm người dùng hiểu sai việc đã xử lý. Bổ sung các case
   HL-015/016/020/028/035 làm ví dụ sai tiền; adjudicate lại HL-081 và các nhãn mơ hồ.
4. Chạy lại calibration trên nhãn đã adjudicate và tập held-out mới trước khi cân nhắc gate.

Kết quả hiện tại chỉ đo replay công khai, không chứng minh độ khái quát sang judge/model hoặc
phân phối reply mới. Các bất đồng phải được người audit quyết định trước khi dùng làm nhãn sửa
rubric.
