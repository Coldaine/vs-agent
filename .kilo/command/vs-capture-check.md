---
description: Verify WGC game capture and OCR
agent: code
---

From the repository root, use `.venv\Scripts\python.exe` with `spine.io_adapter.IOAdapter`
to capture one WGC frame and print JSON containing backend, frame dimensions, mean pixel value,
and treat invalid dimensions as a failure.
