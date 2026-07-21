"""Round-trip tests for lossless plan-document synchronization."""

from lib.pulse.scripts.plan_sync import parse_document, patch_document


DOCUMENT = """---\n# Keep this frontmatter comment.\nowner: docs-team\ncustom: # Unknown keys must survive sync patches.\n  review: required\nsync:\n  issue: {repo: acme/widgets, number: 42}\n  base:\n    blob: deadbeef\n    title: Original title\n---\n# Original title\n\nThis body must remain exactly as written.  \n"""


def test_parse_document_preserves_frontmatter_comments_unknown_keys_and_body_bytes():
    document = parse_document(DOCUMENT)

    assert document.frontmatter["owner"] == "docs-team"
    assert document.frontmatter["custom"]["review"] == "required"
    assert document.binding is document.frontmatter["sync"]
    assert document.title == "Original title"
    assert document.body == "# Original title\n\nThis body must remain exactly as written.  \n"


def test_parse_document_allows_unbound_documents():
    source = "---\nowner: docs-team\n---\n# Standalone plan\n\nNo sync block.\n"

    document = parse_document(source)

    assert document.frontmatter["owner"] == "docs-team"
    assert document.binding is None
    assert document.title == "Standalone plan"
    assert document.body == "# Standalone plan\n\nNo sync block.\n"


def test_noop_patch_returns_byte_identical_document():
    assert patch_document(DOCUMENT, {}, {}) == DOCUMENT


def test_sync_base_patch_preserves_frontmatter_comments_unknown_keys_and_body_bytes():
    patched = patch_document(DOCUMENT, {}, {"blob": "cafebabe"})

    assert patched == DOCUMENT.replace("blob: deadbeef", "blob: cafebabe")


def test_patch_preserves_crlf_line_endings_and_untouched_body_bytes():
    document = DOCUMENT.replace("\n", "\r\n")

    patched = patch_document(document, {}, {"blob": "cafebabe"})

    assert patched == document.replace("blob: deadbeef", "blob: cafebabe")
    assert "\n" not in patched.replace("\r\n", "")


def test_retitle_changes_only_the_first_h1_line():
    document = "# Old title\n\n# Later H1 stays\n"

    patched = patch_document(document, {"title": "New title"}, {})

    assert patched == "# New title\n\n# Later H1 stays\n"


def test_body_patch_uses_the_replacement_verbatim():
    replacement = "# Replacement\r\n\r\nBody with CRLF.\r\n"

    patched = patch_document(DOCUMENT, {"body": replacement}, {})

    assert patched == DOCUMENT[:DOCUMENT.index("# Original title")] + replacement
