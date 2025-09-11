Below are two stand-alone implementation blueprints that an agentic-coder model can consume top-to-bottom.  
Each file contains:

- Exact API surface (request/response schemas, error codes)  
- OpenRouter prompt engineering & parsing strategy  
- Bulk vs. single-file flow (re-using existing job dispatcher)  
- CSV / Excel export logic (streaming, memory-safe)  
- Security, rate-limit, retry, test and observability specs  
- File-level checklist that can be converted into GitHub issues or code patches

Save them in `docs/ai_features/` so they live next to the guides you already have.

--------------------------------------------------
docs/ai_features/invoice_extraction_impl.md
--------------------------------------------------
# Invoice Extraction – Implementation Blueprint  
**Status**: design | **Owner**: AI squad | **Target**: v2.4.0

## 1. User Stories
- AS AN accountant I want to upload one or many invoices and receive an Excel file with extracted fields so that I can reconcile in SAP.  
- AS AN ERP integrator I want to call a single endpoint and get JSON back so that I can map fields automatically.

## 2. API Surface
### 2.1 Single-file – synchronous shortcut
`POST /ai/invoice/extract`  
form-data: `file: PDF/JPG/PNG`  
query params:  
- `output_format=json|csv|xlsx` (default `json`)  
- `filename` (optional, used in export)  

**Response 200**  
```json
{
  "invoice_number": "INV-12345",
  "vendor_name": "Acme Corp.",
  "issue_date": "2024-07-01",
  "due_date": "2024-07-31",
  "currency": "USD",
  "total": 1050.00,
  "line_items": [
    {"description": "Widget A", "quantity": 2, "unit_price": 500.0, "amount": 1000.0}
  ],
  "vat_amount": 50.0,
  "confidence": 0.94
}
```
**Attachment headers**  
`Content-Disposition: attachment; filename="invoice_result.xlsx"`

### 2.2 Bulk – async (re-uses job engine)
`POST /jobs`  
```json
{
  "type": "invoice_extraction",
  "output_format": "xlsx",
  "files": [
    {"file_id": "u123_1.pdf"},
    {"file_id": "u123_2.pdf"}
  ]
}
```
**Response 201**  
`{ "job_id": "j_abc123" }`

Poll `GET /jobs/j_abc123` → when `status=done`  
`GET /jobs/j_abc123/download` returns zip containing:  
- `invoice_summary.xlsx` (all rows aggregated)  
- individual `{original_name}_result.json` for traceability

## 3. OpenRouter Integration
### 3.1 Prompt template (`src/ai/prompts/invoice_extraction.txt`)
```
You are an expert invoice parser.  
Extract the following JSON keys:  
invoice_number, vendor_name, vendor_address, vendor_tax_id,  
issue_date (YYYY-MM-DD), due_date (YYYY-MM-DD), currency,  
line_items (array: description, quantity, unit_price, amount),  
sub_total, vat_rate, vat_amount, total, iban, swift.  
If a field is missing use null.  
Return ONLY valid JSON, no markdown block.
```
Tokens: ~220 input + variable OCR text.  
Model: `openrouter/openai/gpt-4o-mini` (cost ≈ $0.06 / 1k pages).

### 3.2 Client wrapper (`src/ai/openrouter_client.py`)
- `async def complete(prompt: str, max_tokens: 1200) -> str`  
- Retry: 3× exponential backoff on 429/5xx  
- Timeout: 30 s  
- Inject `X-Title: pdf-smaller-backend` for OpenRouter analytics

### 3.3 Parser (`src/ai/extractors/invoice.py`)
- Use `pydantic` model `InvoiceSchema` for validation  
- On JSON decode error → second prompt “Fix the following invalid JSON: …” (once)  
- Return `ExtractResult[InvoiceSchema]` with `.confidence` = avg of per-field softmax (when OpenRouter supplies logprobs)

## 4. Export Logic
### 4.1 CSV (`src/ai/exporters/csv_exporter.py`)
- Streaming write via `io.StringIO` → `StreamingResponse`  
- Headers in English; localisable via `gettext`

### 4.2 Excel (`src/ai/exporters/excel_exporter.py`)
- `openpyxl` – constant-memory mode (`write_only=True`)  
- Sheet 1 “Invoices” – one row per file  
- Sheet 2 “Line items” – flattened, foreign key = filename  
- Auto-filter + number formats (`#,##0.00`)

## 5. Security & Compliance
- OpenRouter API key stored in `k8s secret` `openrouter-api-key`, mounted as env `OPENROUTER_API_KEY`  
- NetworkPolicy egress allow `api.openrouter.ai:443` only  
- Prompts never logged at DEBUG; only token counts  
- Retention: exported files follow same TTL as compressed PDFs (S3 lifecycle 7 days)

## 6. Rate-limiting
- Per-org: 100 invoice pages / minute (configurable)  
- HTTP 429 returned when exceeded; retry-after header

## 7. Observability
- Prometheus counters:  
  `ai_invoice_pages_total{status="success|error"}`  
  `ai_invoice_tokens_sent_total`  
  `ai_invoice_first_token_latency_seconds`  
- Logs: `invoice_id` (hashed) for traceability

## 8. Test Plan
- Unit: prompt → JSON parsing edge cases (missing date, multi-currency)  
- Mock OpenRouter with `pytest-httpx`  
- Golden set: 50 real invoices (anonymised) in `tests/ai/fixtures/invoices/`  
- Assert Excel checksum for regression

## 9. File-level Task List (convert to issues)
- [ ] `src/ai/prompts/invoice_extraction.txt`  
- [ ] `src/ai/openrouter_client.py`  
- [ ] `src/ai/extractors/invoice.py`  
- [ ] `src/ai/exporters/csv_exporter.py`  
- [ ] `src/ai/exporters/excel_exporter.py`  
- [ ] `src/api/routes/ai_invoice.py` (single sync endpoint)  
- [ ] extend `src/jobs.py` for bulk flow  
- [ ] update `helm/values.yaml` (secrets, network-policy)  
- [ ] add tests under `tests/ai/invoice/`  
- [ ] update public `api_documentation.md`

--------------------------------------------------
docs/ai_features/bank_statement_extraction_impl.md
--------------------------------------------------
# Bank Statement Extraction – Implementation Blueprint  
**Status**: design | **Owner**: AI squad | **Target**: v2.4.0

## 1. User Stories
- AS A bookkeeper I want to upload bank statements (PDF/CSV scans) and receive an Excel ledger so that I can import it into QuickBooks.  
- AS A developer I want JSON so that I can push transactions via API to my accounting SaaS.

## 2. API Surface
### 2.1 Single-file
`POST /ai/bank/extract`  
form-data: `file: PDF/PNG/JPG`  
query params:  
- `output_format=json|csv|xlsx` (default `json`)  
- `start_date` / `end_date` (optional filter, ISO-8601)  
- `account_suffix` (optional, last 4 digits for verification)

**Response 200 JSON**
```json
{
  "bank_name": "Example Bank",
  "account_number_suffix": "1234",
  "statement_period": {"start": "2024-06-01", "end": "2024-06-30"},
  "opening_balance": 5000.00,
  "closing_balance": 4700.00,
  "currency": "USD",
  "transactions": [
    {
      "date": "2024-06-02",
      "description": "PAYPAL *SHOP",
      "debit": 50.00,
      "credit": null,
      "balance": 4950.00
    }
  ]
}
```
Excel/CSV columns: Date, Description, Debit, Credit, Balance, Category (inferred)

### 2.2 Bulk
`POST /jobs`
```json
{
  "type": "bank_statement_extraction",
  "output_format": "xlsx",
  "account_suffix": "1234",
  "files": [{"file_id": "u456_stmt1.pdf"}]
}
```
Returns job_id; download zip with `ledger.xlsx` (all txns) + individual JSON for audit.

## 3. LLM Prompt Design
Prompt template (`src/ai/prompts/bank_extraction.txt`)
```
You are an OCR post-processor specialising in bank statements.  
Output valid JSON with keys:  
bank_name, statement_period_start (YYYY-MM-DD), statement_period_end,  
opening_balance, closing_balance, currency,  
transactions (array: date, description, debit, credit, balance).  
Debits positive, credits positive, balance running.  
If a transaction line is unclear, mark as {"date": null, "description": "<raw>", debit: null, credit: null, balance: null}  
Return ONLY JSON.
```
Model same as invoice: `gpt-4o-mini` (cost ≈ $0.04 / 1k txns).

## 4. Post-processing
- Detect currency symbol → ISO-4217 code  
- Strip IBAN from description to separate column  
- Auto-infer category using keyword map (config yaml)  
- Validate running balance; warn on mismatch > 0.01

## 5. Export
Excel template identical to invoice exporter (separate sheet for txns).  
CSV includes extra column `source_file` for bulk traceability.

## 6. Security & Compliance
- Bank statements are PCI-adjacent – apply same encryption-at-rest as PDFs (S3 SSE-KMS)  
- Account numbers redacted to last 4 digits in logs  
- OpenRouter key reuse; no additional egress rules needed

## 7. Rate-limiting
- Per-org: 200 pages / minute (higher than invoice – statements often 1 page)

## 8. Observability
Counters:  
`ai_bank_pages_total`, `ai_bank_txns_extracted_total`, `ai_bank_balance_mismatch_total`

## 9. Test Dataset
- 30 anonymised statements (PDF scans + CSV ground truth) in `tests/ai/fixtures/bank/`  
- Golden checksum on closing balance & txn count

## 10. File-level Task List
- [ ] `src/ai/prompts/bank_extraction.txt`  
- [ ] `src/ai/extractors/bank.py`  
- [ ] `src/ai/exporters/excel_exporter.py` (extend with `BankSheetBuilder`)  
- [ ] `src/api/routes/ai_bank.py`  
- [ ] extend `src/jobs.py` (bulk flow)  
- [ ] keyword-category yaml `src/ai/config/bank_categories.yml`  
- [ ] tests `tests/ai/bank/`  
- [ ] update `api_documentation.md`

--------------------------------------------------
End of blueprints – agentic coder can now generate pull-requests issue-by-issue.