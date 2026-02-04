from genimail.domain.link_tools import (
    collect_cloud_pdf_links,
    extract_urls,
    normalize_cloud_download_url,
)


def test_extract_urls_dedupes_and_strips_punctuation():
    text = "See https://example.com/a.pdf, and https://example.com/a.pdf."
    assert extract_urls(text) == ["https://example.com/a.pdf"]


def test_normalize_dropbox_link_to_download():
    src = "https://www.dropbox.com/s/abc123/file.pdf?dl=0"
    out = normalize_cloud_download_url(src)
    assert "dropbox.com" in out
    assert "dl=1" in out


def test_normalize_google_drive_file_link():
    src = "https://drive.google.com/file/d/FILEID123/view?usp=sharing"
    out = normalize_cloud_download_url(src)
    assert out == "https://drive.google.com/uc?export=download&id=FILEID123"


def test_collect_cloud_pdf_links_filters_and_labels():
    html = """
    <a href="https://drive.google.com/file/d/FILEID123/view?usp=sharing">Drive</a>
    <a href="https://www.dropbox.com/s/abc123/report.pdf?dl=0">Dropbox</a>
    <a href="https://example.com/ignore">Ignore</a>
    """
    links = collect_cloud_pdf_links(html, "")
    assert len(links) == 2
    assert links[0]["source"] == "Google Drive"
    assert links[1]["source"] == "Dropbox"
