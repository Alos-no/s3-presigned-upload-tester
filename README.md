# S3 Content-Length Enforcement Tester

**Automated compliance testing for S3-compatible storage providers.**

When you generate a presigned URL with a signed `Content-Length`, does your provider actually enforce it? This tool verifies that—continuously.

[**View Live Dashboard**](https://alos-no.github.io/s3-presigned-upload-tester/) · [**Why This Matters**](README-legacy.md)

---

## What It Tests

| Test | Expected | Purpose |
|------|----------|---------|
| Upload matches signed size | Accept | Baseline - valid uploads work |
| Body larger than signed | Reject | Prevents quota bypass |
| Body smaller than signed | Reject | Prevents truncation attacks |
| Header/body mismatch | Reject | Prevents header spoofing |

Tests run against both **multipart uploads** (`UploadPart`) and **single-part uploads** (`PutObject`).

---

## Providers Tested

| Provider | Status |
|----------|--------|
| AWS S3 | ![AWS](https://alos-no.github.io/s3-presigned-upload-tester/data/badges/aws.svg) |
| Cloudflare R2 | ![R2](https://alos-no.github.io/s3-presigned-upload-tester/data/badges/r2.svg) |
| Backblaze B2 | ![B2](https://alos-no.github.io/s3-presigned-upload-tester/data/badges/b2.svg) |
| Google Cloud Storage | ![GCS](https://alos-no.github.io/s3-presigned-upload-tester/data/badges/gcs.svg) |

---

## Quick Start

```bash
# Install
pip install -e .

# Configure (copy and edit)
cp config.example.json config.json

# Run tests
python run.py
```

---

## API

Results are available as JSON for integration into your own monitoring:

```
GET /data/latest.json    # Current test results
GET /data/history.json   # Historical data + changelog
GET /data/badges/*.svg   # Status badges per provider
```

---

## Architecture

```
src/
├── runner.py          # Test orchestration
├── test_cases.py      # Test definitions
├── s3_client.py       # Provider interactions
└── site_generator/    # Dashboard data generation

site/                  # Static dashboard (GitHub Pages)
```

---

## Background

This project validates the **Manifested Multipart Upload** pattern—a technique for enforcing upload quotas at the storage edge without proxying data through your servers.

For the full technical deep-dive, see [README-legacy.md](README-legacy.md).

---

## License

MIT
