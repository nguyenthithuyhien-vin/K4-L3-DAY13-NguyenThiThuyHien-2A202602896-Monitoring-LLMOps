# Báo cáo cá nhân — K4-L3B Day 13 Monitoring & LLMOps

> Mỗi học viên hoàn thiện một file duy nhất này. Khi dẫn evidence, dùng đường dẫn tương đối, ví dụ `evidence/07-trace-waterfall.png`.

## 1. Thông tin học viên

- **Họ và tên:** Nguyen Thi Thuy Hien
- **MSSV:** 2A202602896
- **Lớp:** K4-L3B
- **Repository URL:** https://github.com/nguyenthithuyhien-vin/K4-L3-DAY13-NguyenThiThuyHien-2A202602896-Monitoring-LLMOps
- **Commit SHA cuối:** *(điền sau khi commit cuối)*
- **Challenge ID:** day13-k4-l3b-monitoring-llmops-v1
- **Tên project Langfuse cá nhân:** `day13-k4-l3b-2A202602896`

## 2. Evidence index

| Evidence | Đường dẫn |
|---|---|
| Pytest cuối | `evidence/01-pytest.txt` |
| Log validator | `evidence/02-log-validator.txt` |
| Dashboard validator | `evidence/03-dashboard-validator.txt` |
| Structured log | `evidence/04-structured-log.txt` |
| PII redaction | `evidence/05-pii-redaction.txt` |
| Trace list | `evidence/06-trace-list.txt` |
| Trace waterfall | `evidence/07-trace-waterfall.txt` |
| Trace metadata | `evidence/08-trace-metadata.txt` |
| Prompt versions | `evidence/09-prompt-versions.txt` |
| Prompt rollback | `evidence/10-prompt-rollback.txt` |
| Dashboard runtime | `evidence/11-dashboard-overview.png` |
| Incident metric | `evidence/12-incident-metric.png` / `evidence/12-incident-metric.txt` |
| Incident log | `evidence/13-incident-log.txt` |
| Incident trace | `evidence/14-incident-trace.txt` |

## 3. Kết quả kỹ thuật

| Nội dung | Baseline | Kết quả cuối | Nhận xét |
|---|---|---|---|
| `validate_logs.py` | chưa đạt (TODO chưa làm, correlation_id=MISSING) | 100/100 | Sau CP1: schema, enrichment, PII đều PASS |
| `validate_dashboard.py` | contract 6/6 (YAML sẵn) | 6/6 panel | Runtime dashboard Streamlit đọc `data/logs.jsonl` |
| `pytest` | một số fail do TODO | 22 passed | Đã cập nhật mock `update_current_generation` |
| Số traces hợp lệ | 0 | 25 | Project `day13-k4-l3b-2A202602896` |
| Số PII leak | N/A | 0 | Scrub trước khi ghi JSONL |
| Latency P95 / TTFT P95 | ~892ms / ~55ms (trước challenge) | P95 challenge ~2665ms / TTFT ~55ms | TTFT ổn; latency tăng vì retrieval |
| Retrieval success rate | ~100% | ~100% trong challenge `rag_slow` | Incident làm chậm, không fail tool |

## 4. Logging và PII

- **Cách tạo/nhận và truyền correlation ID:** Middleware `CorrelationIdMiddleware` gọi `clear_contextvars()`, nhận `x-request-id` hợp lệ dạng `req-<8-hex>` hoặc sinh mới bằng `uuid4().hex[:8]`, bind vào structlog context, gắn `request.state.correlation_id`, rồi trả lại qua header `x-request-id` và `x-response-time-ms`.
- **Các metadata được ghi vào structured log:** Trước `request_received`, `chat()` bind `user_id_hash`, `session_id`, `feature`, `model`, `env`. Các event API kế thừa context này; `response_sent` thêm `latency_ms`, `ttft_ms`, tokens, cost, `quality_score`, `tool_name`, `tool_success`.
- **Cách bảo đảm PII được scrub trước khi ghi:** Processor `scrub_event` đăng ký trong `structlog.configure` **trước** `JsonlFileProcessor` và `JSONRenderer`. Pattern trong `app/pii.py` cover email, phone VN, CCCD, thẻ, passport, địa chỉ VN.
- **Cách kiểm chứng kết quả:** `python scripts/validate_logs.py` → 100/100; evidence `04`/`05`.

## 5. Tracing và prompt versioning

- **Cách xác nhận traces do chính tôi tạo trong project cá nhân:** Workload chạy local với key project `day13-k4-l3b-2A202602896`; danh sách trace IDs trong `evidence/06-trace-list.txt` (25 traces).
- **Cấu trúc root/retrieval/generation observations:** `@observe` trên `LabAgent.run` (agent) + child `retrieve_with_trace` (retriever) + `_generate_with_trace` (generation với usage/cost đã scrub). Xem `evidence/07-trace-waterfall.txt`.
- **Cách nối trace với log:** Cùng `correlation_id` trong log và metadata observation; khi điều tra challenge còn join thêm `session_id`.
- **Prompt name:** `day13-chat`
- **Version/label baseline:** version 1 / label `baseline` (+ `production` sau rollback)
- **Version/label candidate:** version 2 / label `candidate` (promote tạm thời tạo version 3 rồi rollback ra version 4)
- **Trace ID của mỗi version:** correlation `req-base0001` (baseline), `req-cand0001` (candidate), `req-prod0002` (production sau promote), `req-prod0001` (production sau rollback). Ví dụ waterfall: `3b47ed59d02fb9984b8149969c8eb102`.
- **Cách promote và rollback `production`:** Dùng Langfuse `create_prompt` gắn label `production` sang nội dung v2, chạy request, rồi gắn lại `production` về nội dung v1. Evidence `09`/`10`.

## 6. Dashboard, SLO và alerts

- **Dashboard và sáu panel:** Streamlit app `scripts/dashboard_app.py` + PNG overview `evidence/11-dashboard-overview.png`: latency (+TTFT), traffic, errors/retrieval, cost, tokens, quality — đúng contract `config/dashboard.yaml`.
- **SLO và lý do chọn:** `config/slo.yaml` — 99.5% request thành công với `latency_ms <= 3000` trong 28 ngày. Baseline mock LLM ổn định vài trăm ms nên ngưỡng 3000ms còn room cho biến động nhưng vẫn bắt được incident `rag_slow`.
- **Cách tính error budget:** `100 - 99.5 = 0.5%`. Với 10,000 request thì tối đa 50 request được phép lỗi hoặc chậm hơn 3000ms.
- **Ba alert và runbook tương ứng:** `HighLatencyP95` (5m), `HighErrorRate` (5m), `LowRetrievalSuccess` (10m) trong `config/alert_rules.yaml`; runbook chi tiết tại `docs/alerts.md`.

## 7. Điều tra challenge

- **Challenge ID:** day13-k4-l3b-monitoring-llmops-v1
- **Khoảng thời gian điều tra:** khoảng `2026-09-30T11:45:22Z` → `2026-09-30T11:45:36Z` (UTC)
- **Triệu chứng từ metrics:** Trước inject: latency P95 ≈ 892ms. Sau `rag_slow`: nhiều request ≥ 2000ms, P95/P99 ≈ 2665ms trong log; client wall-clock lên tới ~13s khi concurrency 5. TTFT gần như không đổi (~55ms). Xem `evidence/12-incident-metric.png`.
- **Log line và correlation ID liên quan:** `response_sent` `correlation_id=req-1cb1f08b`, `latency_ms=2665`, `session_id=k4-l3b-challenge-s04`, `ts=2026-09-30T11:45:27.908081Z` — `evidence/13-incident-log.txt`.
- **Trace ID và span gây ảnh hưởng:** Trace `2a0cbd535b73febc96abcec7dcbe4075`; span `retrieval` ~2505ms, `generation` ~159ms, agent total ~2665ms — `evidence/14-incident-trace.txt`.
- **Root cause:** Incident `rag_slow` khiến bước retrieval sleep ~2.5s; bottleneck nằm ở retriever, không phải LLM generation.
- **Fix action:** Tắt incident (`inject_incident.py --disable` / `/incidents/rag_slow/disable`); trong production sẽ rollback cấu hình retrieval/timeout và phục hồi vector store.
- **Preventive measure:** Alert `HighLatencyP95` + runbook Metrics→Logs→Traces; theo dõi riêng duration span `retrieval`; thêm guardrail retrieval latency trong dashboard.

## 8. Giải thích và tự đánh giá

- **Một quyết định kỹ thuật quan trọng và lý do:** Instrument child observations bằng `@observe` trên hàm riêng thay vì chỉ root span, để waterfall tách được retrieval vs generation — bắt buộc cho điều tra CP3.
- **Một lỗi/blocker đã gặp:** Python 3.14 không build được `pydantic-core` (PyO3); phải tạo lại venv bằng Python 3.12.
- **Cách tìm nguyên nhân và xử lý:** Đọc lỗi maturin/PyO3, chuyển sang `/opt/homebrew/bin/python3.12 -m venv .venv` rồi cài lại dependencies.
- **Cách hiểu luồng Metrics → Logs → Traces:** Metrics báo latency tăng và khoảng thời gian; logs cung cấp `correlation_id`/`session_id` của request chậm; traces cùng ID cho thấy span `retrieval` chiếm hầu hết thời gian → kết luận root cause có bằng chứng.
- **Vai trò của prompt version, token/cost, SLO hoặc rollback trong vận hành LLM:** Prompt version gắn trên trace giúp biết regression đến từ prompt mới; token/cost theo dõi chi phí; SLO/error budget đặt ngưỡng “đủ tốt”; rollback label `production` là cách phục hồi nhanh không cần redeploy code.
- **Điều quan trọng nhất đã học:** Không đoán root cause — luôn đi Metrics → Logs → Traces và nối bằng `correlation_id`.
- **Hạn chế hoặc phần chưa hoàn thành, nếu có:** Evidence Langfuse nộp dạng export JSON/text (đã redacted) kèm PNG dashboard; nên bổ sung screenshot UI Langfuse nếu grader yêu cầu ảnh chụp màn hình trực tiếp.

## 9. Checklist trước khi nộp

- [x] Kết quả và evidence thuộc commit SHA cuối.
- [x] `validate_logs.py` ≥ 80/100 và `validate_dashboard.py` = 6/6.
- [x] Có ≥10 traces, waterfall, metadata, prompt rollback.
- [x] Dashboard 6 panel + SLO/error budget + 3 alert/runbook.
- [x] Incident nối metric → log → trace.
- [x] Không commit `.env`, secret, `config/challenge.json`, PII thô.
