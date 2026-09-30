# Alert Runbook — Day 13 Monitoring & LLMOps

Mỗi alert dựa trên triệu chứng người dùng hoặc SLO, không dựa trực tiếp vào tên implementation nội bộ.

## Alert mẫu để tham khảo

- Tên: `HighLatencyP95`
- Severity: `warning`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: latency P95 của `response_sent.latency_ms`
- Điều kiện và thời gian duy trì: `p95(latency_ms) > 3000ms` trong 5 phút
- Ảnh hưởng tới người dùng: người dùng phải chờ lâu hơn trước khi nhận câu trả lời
- Ba bước kiểm tra đầu tiên:
  1. Mở dashboard latency để xác nhận P95/P99 và khoảng thời gian tăng.
  2. Lọc `data/logs.jsonl` trong khoảng đó, lấy một `correlation_id` có `latency_ms` cao.
  3. Mở trace cùng `correlation_id` trên Langfuse, so sánh các span chính để xác định bước nào bất thường.
- Mitigation tạm thời: dựa trên evidence thực tế để rollback prompt, khôi phục cấu hình liên quan, tắt practice scenario hoặc giảm tải khi demo.
- Owner: `student-2A202602896`

## Alert 1

- Tên: `HighLatencyP95`
- Severity: `warning`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: latency P95 của `response_sent.latency_ms` so với SLO `fast_successful_requests` (≤ 3000ms)
- Điều kiện và thời gian duy trì: `p95(latency_ms) > 3000ms` trong 5 phút
- Ảnh hưởng tới người dùng: phần lớn request chậm hơn mục tiêu; người dùng chờ lâu trước khi nhận câu trả lời
- Ba bước kiểm tra đầu tiên:
  1. Mở dashboard panel Latency, xác nhận P95/P99/TTFT và khoảng thời gian tăng.
  2. Lọc `data/logs.jsonl` theo `event=response_sent` và `latency_ms > 3000`, lấy một `correlation_id`.
  3. Mở Langfuse trace cùng `correlation_id`, so sánh span `retrieval` và `generation` để khoanh vùng bước chậm.
- Mitigation tạm thời: rollback prompt `production` nếu version mới gây regression; tắt incident practice; giảm concurrency nếu đang load test.
- Owner: `student-2A202602896`

## Alert 2

- Tên: `HighErrorRate`
- Severity: `critical`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: error rate = `count(request_failed) / count(request_received)`; guardrail `error_rate_pct_max: 2`
- Điều kiện và thời gian duy trì: `error_rate_pct > 2` trong 5 phút
- Ảnh hưởng tới người dùng: tỷ lệ request thất bại tăng; người dùng nhận lỗi 500 thay vì câu trả lời
- Ba bước kiểm tra đầu tiên:
  1. Mở dashboard panel Errors, xem error rate và breakdown theo `error_type`.
  2. Lọc log `event=request_failed`, lấy `correlation_id` và `error_type`.
  3. Mở trace cùng `correlation_id` để xem span nào fail (retrieval timeout, generation, ...).
- Mitigation tạm thời: tắt incident `tool_fail` nếu đang inject; kiểm tra dependency retrieval; rollback prompt nếu lỗi liên quan format.
- Owner: `student-2A202602896`

## Alert 3

- Tên: `LowRetrievalSuccess`
- Severity: `warning`
- Duration: `10m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: `tool_success` trên retrieval; guardrail `retrieval_success_rate_pct_min: 90`
- Điều kiện và thời gian duy trì: `retrieval_success_rate_pct < 90` trong 10 phút
- Ảnh hưởng tới người dùng: RAG không tìm được context phù hợp; chất lượng câu trả lời giảm
- Ba bước kiểm tra đầu tiên:
  1. Mở dashboard panel Errors, kiểm tra retrieval success rate.
  2. Lọc log có `tool_name=retrieval` và `tool_success=false` (hoặc `request_failed` với Vector store timeout).
  3. Mở trace cùng `correlation_id`, kiểm tra span `retrieval` có lỗi/timeout.
- Mitigation tạm thời: tắt incident `tool_fail`/`rag_slow`; kiểm tra corpus và query; thêm alert/runbook để bắt sớm hơn.
- Owner: `student-2A202602896`
