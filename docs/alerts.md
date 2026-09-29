# Alert và Runbook

Mỗi alert phải dựa trên triệu chứng người dùng hoặc SLO, không dựa trực tiếp vào tên implementation nội bộ.

## Alert 1

- Tên: `HighTailLatency`
- Severity: warning
- Duration: 5 phút
- Kênh thông báo: Slack `#llmops-alerts`
- SLI/SLO liên quan: P95 latency và SLO request thành công trong 3000 ms.
- Điều kiện và thời gian duy trì: `latency_p95_ms > 3000` liên tục 5 phút.
- Ảnh hưởng tới người dùng: Người dùng phải chờ lâu dù request cuối cùng có thể vẫn thành công.
- Ba bước kiểm tra đầu tiên: (1) xác nhận cửa sổ và P95/P99 trên dashboard; (2) lọc các `response_sent` chậm và lấy correlation ID; (3) mở trace tương ứng, so sánh span retrieval với generation.
- Mitigation tạm thời: Tắt incident/feature gây chậm, giảm concurrency hoặc chuyển về prompt/model ổn định gần nhất.
- Owner: `llm-platform-oncall`

## Alert 2

- Tên: `HighRequestErrorRate`
- Severity: critical
- Duration: 5 phút
- Kênh thông báo: Slack `#llmops-alerts`
- SLI/SLO liên quan: Error rate tối đa 2% và SLO successful requests.
- Điều kiện và thời gian duy trì: `error_rate_pct > 2` liên tục 5 phút.
- Ảnh hưởng tới người dùng: Request trả lỗi hoặc không nhận được câu trả lời.
- Ba bước kiểm tra đầu tiên: (1) kiểm tra breakdown theo `error_type`; (2) lấy correlation ID từ `request_failed`; (3) mở trace và xác định observation lỗi gần nhất.
- Mitigation tạm thời: Rollback thay đổi gần nhất, vô hiệu hóa incident và dùng fallback an toàn nếu dependency ngoài đang lỗi.
- Owner: `llm-platform-oncall`

## Alert 3

- Tên: `LowRetrievalSuccessRate`
- Severity: warning
- Duration: 10 phút
- Kênh thông báo: Slack `#llmops-alerts`
- SLI/SLO liên quan: Retrieval success rate tối thiểu 90% và quality score trung bình tối thiểu 0.75.
- Điều kiện và thời gian duy trì: `retrieval_success_rate_pct < 90` liên tục 10 phút.
- Ảnh hưởng tới người dùng: Câu trả lời thiếu ngữ cảnh, kém chính xác hoặc không trả lời được câu hỏi.
- Ba bước kiểm tra đầu tiên: (1) kiểm tra `tool_success` và quality panel; (2) lấy correlation ID của request retrieval thất bại; (3) mở trace để xem trạng thái và thời gian của span `retrieval`.
- Mitigation tạm thời: Dùng nguồn retrieval dự phòng, giảm phạm vi truy vấn hoặc trả thông báo an toàn thay vì sinh câu trả lời không có grounding.
- Owner: `rag-oncall`
