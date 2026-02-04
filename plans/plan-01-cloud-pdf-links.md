# Cloud PDF Link Enhancement Plan

## Problem Statement
Currently, opening a cloud-hosted PDF (Google Drive, Dropbox, etc.) from an email requires 5+ clicks through a dialog picker. Users want a streamlined, one-click experience similar to regular file attachments.

## Goals
1. **Fewer clicks** - One-click to view any cloud PDF
2. **Consistent UI** - Match the existing attachment row style
3. **Persistent caching** - Downloaded PDFs cached permanently for instant re-access
4. **Keep existing batch flow** - "Select & Open PDFs" dialog remains for power users

## Current State

```
email_app_v2.py
├── _render_cloud_pdf_links() → Shows summary + "Select & Open PDFs" button
├── _open_cloud_pdf_links() → Opens CloudPdfLinkDialog picker
├── _download_linked_pdf_bytes() → Downloads via requests
└── _open_pdf_in_tab() → Loads into PdfViewerFrame

genimail/domain/link_tools.py
├── collect_cloud_pdf_links() → Extracts links from email HTML/text
├── normalize_cloud_download_url() → Converts to direct download URLs
└── is_supported_cloud_link() → Validates provider support

genimail/ui/dialogs.py
└── CloudPdfLinkDialog → Multi-select checkbox dialog
```

## Proposed Changes

### Phase 1: Individual Link Rows with One-Click View
- [ ] Refactor `_render_cloud_pdf_links()` to render each link as its own row
- [ ] Add "View" button per row (like `_render_attachments()` does)
- [ ] Add "Save" button per row for downloading to disk
- [ ] Create `_view_cloud_pdf()` method for single-link download + open
- [ ] Keep "Select & Open PDFs" button at bottom for batch operations

**Target UI:**
```
LINKED CLOUD FILES
┌──────────────────────────────────────────────────────────────┐
│ 📄 Google Drive: floorplan.pdf              [View] [Save]   │
│ 📄 Dropbox: measurements.pdf                [View] [Save]   │
│ 📄 Google Drive: quote_v2.pdf               [View] [Save]   │
├──────────────────────────────────────────────────────────────┤
│ [Select & Open Multiple...]                                  │
└──────────────────────────────────────────────────────────────┘
```

### Phase 2: Persistent PDF Cache
- [ ] Add `cloud_pdf_cache` table to SQLite (`email_cache.db`)
  - Schema: `(url_hash TEXT PRIMARY KEY, download_url TEXT, name TEXT, content BLOB, created_at INT)`
- [ ] Add `EmailCache.get_cloud_pdf(url_hash)` method
- [ ] Add `EmailCache.save_cloud_pdf(url_hash, url, name, content)` method
- [ ] Modify `_view_cloud_pdf()` to check cache before downloading
- [ ] Show visual indicator for cached vs uncached links (e.g., ✓ icon)

### Phase 3: Loading State & Polish
- [ ] Add loading indicator when downloading (spinner or "Loading..." text in row)
- [ ] Show download progress in status bar
- [ ] Handle download failures gracefully with retry option
- [ ] Add tooltip showing full URL on hover

### Phase 4: Testing & Edge Cases
- [ ] Test with Google Drive public + shared links
- [ ] Test with Dropbox public + shared links  
- [ ] Test with OneDrive links
- [ ] Test large PDFs (>10MB)
- [ ] Test expired/invalid links
- [ ] Test offline behavior (cache hits)
- [ ] Add unit tests for new cache methods

## Files to Modify

| File | Changes |
|------|---------|
| `email_app_v2.py` | Refactor `_render_cloud_pdf_links()`, add `_view_cloud_pdf()` |
| `genimail/infra/cache_store.py` | Add cloud PDF cache table + methods |
| `genimail/ui/dialogs.py` | Minor - keep CloudPdfLinkDialog for batch |
| `tests/test_cache_store.py` | Add tests for cloud PDF cache (new file or extend) |

## Non-Goals (Out of Scope)
- Thumbnail previews (too complex)
- Auto-open PDFs without user action
- Additional cloud providers beyond current (Google, Dropbox, OneDrive)
- Inline buttons in email body HTML

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Large PDFs bloat SQLite | Add size limit (e.g., 50MB max cached) |
| Stale cached PDFs | Show "Re-download" option; cache is convenience not source of truth |
| Google Drive auth walls | Already handled by `normalize_cloud_download_url()` |
| Rate limiting by providers | Add retry with backoff |

## Success Criteria
- [ ] Can open any cloud PDF with 1 click
- [ ] Second open of same PDF is instant (cached)
- [ ] Existing batch dialog still works
- [ ] All 64+ existing tests still pass
- [ ] New cache methods have test coverage

## Estimated Effort
- Phase 1: ~45 min (UI refactor)
- Phase 2: ~30 min (cache layer)
- Phase 3: ~20 min (polish)
- Phase 4: ~25 min (testing)

---

*Plan created: 2026-02-04*
*Status: Ready for implementation*
