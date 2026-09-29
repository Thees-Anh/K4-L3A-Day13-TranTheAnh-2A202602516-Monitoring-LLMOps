# Báo cáo cá nhân — K4-L3A Day 13 Monitoring & LLMOps

> Mỗi học viên hoàn thiện một file duy nhất này. Khi dẫn evidence, dùng đường dẫn tương đối, ví dụ `evidence/07-trace-waterfall.png`.

## 1. Thông tin học viên

- **Họ và tên:** Trần Thế Anh
- **MSSV:** 2A202602516
- **Lớp:** K4-L3A
- **Repository URL:** https://github.com/Thees-Anh/K4-L3A-Day13-TranTheAnh-2A202602516-Monitoring-LLMOps
- **Commit SHA cuối:**
- **Challenge ID:** `day13-k4-l3a-monitoring-llmops-v1`
- **Tên project Langfuse cá nhân:** `day13-k4-l3a-2A202602516`

## 2. Evidence index

Điền đúng đường dẫn tới evidence thực tế. Có thể đổi tên hoặc dùng nhiều ảnh nếu cần.

| Evidence | Đường dẫn |
|---|---|
| Pytest cuối | `evidence/01-pytest.png` |
| Log validator | `evidence/02-log-validator.png` |
| Dashboard validator | `evidence/03-dashboard-validator.png` |
| Structured log | `evidence/04-structured-log.png` |
| PII redaction | `evidence/05-pii-redaction.png` |
| Trace list | `evidence/06-trace-list.png` |
| Trace waterfall | `evidence/07-trace-waterfall.png` |
| Trace metadata | `evidence/08-trace-metadata.png` |
| Prompt versions | `evidence/09-prompt-versions.png` |
| Prompt rollback | `evidence/10-prompt-rollback.png` |
| Dashboard runtime | `evidence/11-dashboard-overview.png` |
| Incident metric | `evidence/12-incident-metric.png` |
| Incident log | `evidence/13-incident-log.png` |
| Incident trace | `evidence/14-incident-trace.png` |

## 3. Kết quả kỹ thuật

| Nội dung | Baseline | Kết quả cuối | Nhận xét |
|---|---|---|---|
| `validate_logs.py` | 30/100 | 100/100 | Evidence cuối ghi nhận 148 log records, 0 bản ghi thiếu field/enrichment, 70 correlation ID hợp lệ và 0 PII leak. |
| `validate_dashboard.py` | HỢP LỆ: 6/6 panel | HỢP LỆ: 6/6 panel | Dashboard runtime local hiển thị đủ sáu panel từ `data/logs.jsonl`. |
| `pytest` | 22 passed in 2.81s | 26 passed in 6.20s | Bao gồm test child observations và dashboard runtime. |
| Số traces hợp lệ | Chưa xác minh | 12 | Evidence `06-trace-list.png` hiển thị đúng project cá nhân và tổng 12 root observations. |
| Số PII leak | 0 | 0 | Không phát hiện email, số điện thoại Việt Nam, CCCD hoặc thẻ thanh toán nguyên văn. |
| Latency P95 / TTFT P95 | 1121.7 ms / 50 ms | 2655 ms / 50 ms | Giá trị cuối trên dashboard runtime trong cửa sổ 60 phút có chứa workload challenge; P50 là 152 ms và P99 là 2655 ms. |
| Retrieval success rate | 100% (10/10) | 100% | Tính từ các event có `tool_success` trong cửa sổ dashboard. |

## 4. Logging và PII

- **Cách tạo/nhận và truyền correlation ID:** Middleware xóa context cũ ở đầu mỗi request, nhận `x-request-id` nếu đúng mẫu `req-<8-hex>`; nếu thiếu hoặc sai mẫu thì sinh ID mới từ UUID. ID được bind vào `structlog.contextvars`, lưu trong `request.state`, trả lại qua header `x-request-id` và được dùng khi gọi agent.
- **Các metadata được ghi vào structured log:** Trước event `request_received`, endpoint `/chat` bind `user_id_hash` (SHA-256 rút gọn 12 ký tự), `session_id`, `feature`, `model` và `env`. Vì dùng contextvars, cả `request_received`, `response_sent` và `request_failed` của cùng request nhận chung metadata và correlation ID.
- **Cách bảo đảm PII được scrub trước khi ghi:** Processor `scrub_event` duyệt đệ quy các chuỗi trong event, dictionary, list và tuple, thay email, số điện thoại Việt Nam, CCCD và thẻ thanh toán bằng marker `[REDACTED_*]`. Processor được đặt trước `JsonlFileProcessor` và `JSONRenderer`, nên dữ liệu đã được che trước khi serialize hoặc ghi xuống file.
- **Cách kiểm chứng kết quả:** Đã lưu log CP0 tại `data/logs.baseline-cp0.jsonl`, tạo lại workload và chạy `python scripts/validate_logs.py`. Lần kiểm tra cuối trong evidence ghi nhận 148 records, 0 thiếu required fields, 0 thiếu enrichment, 70 correlation ID duy nhất, 0 PII leak, điểm 100/100. Toàn bộ test cuối đạt 26 passed.

## 5. Tracing và prompt versioning

- **Cách xác nhận traces do chính tôi tạo trong project cá nhân:** Credential đã xác thực thành công với host `https://jp.cloud.langfuse.com`. Evidence `06-trace-list.png` hiển thị project `day13-k4-l3a-2A202602516`, trace name `day13-agent-request` và tổng 12 root observations do workload cá nhân tạo.
- **Cấu trúc root/retrieval/generation observations:** Root `lab-agent-run` loại agent chứa hai child: `retrieval` loại retriever ghi query preview đã scrub, doc count và success; `llm-generation` loại generation ghi model, managed prompt, preview đã scrub, input/output/total tokens và input/output/total cost.
- **Cách nối trace với log:** Middleware sinh correlation ID và bind vào structured log; `LabAgent.run` truyền cùng ID vào trace metadata. Có thể tìm log theo `correlation_id`, sau đó lọc metadata trên Langfuse bằng đúng ID đó.
- **Prompt name:** `day13-chat`
- **Version/label baseline:** v1 — labels `baseline`, `production`
- **Version/label candidate:** v2 — label `candidate`
- **Trace ID của mỗi version:** baseline/production v1: `9f7f7f223074e79b682d13336e242a46`; candidate v2: `00c58eca4c946b450ca7a9966df0350a`.
- **Cách promote và rollback `production`:** Đã chuyển `production` sang v2 và xác minh API trả `production=v2`, sau đó chuyển lại về v1 và xác minh trạng thái cuối `production=v1`. V1 tiếp tục giữ label `baseline`, v2 giữ label `candidate`.

## 6. Dashboard, SLO và alerts

- **Dashboard và sáu panel:** Dashboard local tại `python scripts/dashboard.py` đọc `data/logs.jsonl`, dùng time range 60 phút và auto-refresh 30 giây. Sáu panel gồm latency P50/P95/P99 + TTFT P95, traffic, error + retrieval success, cost, input/output tokens và quality proxy. Evidence: `evidence/11-dashboard-overview.png`.
- **SLO và lý do chọn:** 99.5% request trong cửa sổ 28 ngày phải có `response_sent` và latency không quá 3000 ms. Baseline P95 khoảng 1.1 giây nên ngưỡng 3 giây có khoảng đệm nhưng vẫn phát hiện tail latency ảnh hưởng người dùng.
- **Cách tính error budget:** `100% - 99.5% = 0.5%`; tức tối đa 500 bad requests trên 100,000 request. Nếu quy đổi theo thời gian: `28 × 24 × 60 × 0.5% = 201.6 phút` trong 28 ngày.
- **Ba alert và runbook tương ứng:** `HighTailLatency` (warning, P95 > 3000 ms trong 5m), `HighRequestErrorRate` (critical, error rate > 2% trong 5m), `LowRetrievalSuccessRate` (warning, retrieval success < 90% trong 10m). Tất cả gửi Slack `#llmops-alerts`, có owner và runbook trong `docs/alerts.md`.

## 7. Điều tra challenge

> Challenge chính thức dùng file riêng do Lab Coach cung cấp; `config/challenge.json` được Git ignore và không được commit.

- **Challenge ID:** `day13-k4-l3a-monitoring-llmops-v1`
- **Khoảng thời gian điều tra:** `2026-09-29T09:09:30Z`–`2026-09-29T09:09:44Z` (16:09:30–16:09:44 Asia/Bangkok).
- **Triệu chứng từ metrics:** Cả 5/5 request feature `monitoring` vượt ngưỡng điều tra challenge 2000 ms; latency nằm trong 2652–2655 ms, P95 workload chính thức khoảng 2655 ms. TTFT vẫn 50 ms, error rate 0% và retrieval vẫn success, nên triệu chứng là tail latency chứ không phải request lỗi. Ngưỡng 2000 ms dùng để khoanh vùng challenge; threshold SLO vận hành hiển thị trên dashboard là P95 ≤ 3000 ms.
- **Log line và correlation ID liên quan:** `response_sent` của `req-db7d9878` tại `2026-09-29T09:09:33.122739Z` có `latency_ms=2655`, `ttft_ms=50`, `tool_name=retrieval`, `tool_success=true`, model `claude-sonnet-4-5`.
- **Trace ID và span gây ảnh hưởng:** Trace `ab344863fe75c80cc55276faf781cd44`; root `lab-agent-run` 2.657 s, child `retrieval` 2.500 s, child `llm-generation` 0.152 s. Cả ba observations có correlation ID `req-db7d9878`.
- **Root cause:** Incident `rag_slow` làm bước retrieval chậm khoảng 2.5 giây. Retrieval chiếm gần toàn bộ thời gian root trong khi generation chỉ khoảng 0.15 giây, khớp metric và log.
- **Fix action:** Tắt incident `rag_slow` (đã thực hiện ngay sau workload), kiểm tra backend/index retrieval và áp timeout/circuit breaker để request không chờ retrieval quá lâu.
- **Preventive measure:** Theo dõi riêng retrieval latency/success, cảnh báo P95 request và retrieval, đặt latency budget cho từng span, thêm regression/load test retrieval trước khi promote thay đổi.

## 8. Giải thích và tự đánh giá

- **Một quyết định kỹ thuật quan trọng và lý do:** Dùng context manager và cập nhật trực tiếp object `root_observation` thay vì chỉ dựa vào current span. Cách này bảo đảm metadata request/prompt được gắn đúng root, còn retrieval và generation vẫn giữ quan hệ cha-con rõ ràng.
- **Một lỗi/blocker đã gặp:** Python 3.14 không có wheel phù hợp cho `pydantic-core==2.33.2`; Langfuse ban đầu trả 401 do key/host không khớp, sau đó kết nối region Japan đôi lúc bị timeout; metadata của trace cũ không xuất hiện vì instrumentation cập nhật root chưa đủ trực tiếp.
- **Cách tìm nguyên nhân và xử lý:** Đổi virtual environment sang Python 3.11; kiểm tra `.env` ở dạng che secret và dùng lời gọi đọc prompt để phân biệt 401 với 404; sửa root tracing sang `start_as_current_observation(... ) as root_observation` và `root_observation.update(metadata=...)`; luôn tạo trace mới vì observation cũ không được sửa hồi tố.
- **Cách hiểu luồng Metrics → Logs → Traces:** Metrics cho biết loại triệu chứng và cửa sổ thời gian; structured log trong cửa sổ đó cho một request cụ thể cùng `correlation_id`; trace có cùng ID cho thấy child retrieval hay generation chậm/lỗi; chỉ sau khi ba lớp bằng chứng khớp mới kết luận root cause.
- **Vai trò của prompt version, token/cost, SLO hoặc rollback trong vận hành LLM:** Prompt version giúp tái hiện hành vi và rollback mà không sửa code; token/cost giúp phát hiện mức sử dụng bất thường; SLO biến kỳ vọng người dùng thành mục tiêu đo được; error budget quyết định mức rủi ro thay đổi có thể chấp nhận.
- **Điều quan trọng nhất đã học:** Observability hữu ích khi cùng một correlation ID nối được metric, log và trace, đồng thời telemetry phải tránh PII và chứa đủ metadata để điều tra.
- **Hạn chế hoặc phần chưa hoàn thành, nếu có:** Source, CP3 và bộ evidence PNG đã được hoàn thiện. Evidence rollback ghi nhận trạng thái cuối `production=v1`; thao tác promote sang v2 rồi rollback về v1 được kiểm tra qua Langfuse API và mô tả trong mục 5. Commit SHA cuối chỉ được điền sau khi tạo commit nộp bài.

## 9. Checklist trước khi nộp

- [ ] Kết quả và evidence thuộc commit SHA cuối.
- [x] Tất cả ảnh/output mở được bằng đường dẫn tương đối.
- [x] Incident evidence nối đúng metric → log → trace.
- [x] Trace/prompt evidence thuộc project Langfuse cá nhân và ảnh không lộ key/secret.
- [x] Repository chạy lại được theo README.
- [x] Không có secret, API key, PII thô hoặc evidence của người khác/lớp khác.
- [ ] URL repo và commit SHA cuối đã được nộp trên LMS/Codelabs.
