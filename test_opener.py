import unittest
from unittest.mock import patch

import app
from website import Evidence, WebsiteError, evidence_from, fetch_homepage, normalize_url


class OpenerTests(unittest.TestCase):
    def test_nested_hidden_heading_does_not_leak_duplicate_text(self):
        expected = "The product development system for teams and agents"
        html = f'<h1><span aria-hidden="true"><span>duplicate</span> noise</span>{expected}</h1>'
        self.assertEqual(evidence_from(html), [Evidence(expected)])

    def test_format_keeps_the_selected_excerpt_and_three_lines(self):
        html = "<p>Automate shift handoffs so the next support agent knows which tickets need a reply.</p>"
        with patch.object(app, "MODEL", "test-model"), patch.object(app, "model_choice", return_value=(0, "workflow")):
            draft = app.make_draft("https://example.com/", html)
        self.assertEqual(len(draft["lines"]), 3)
        self.assertTrue(all(line and "\n" not in line for line in draft["lines"]))
        self.assertIn(draft["source"]["excerpt"], draft["lines"][0])
        self.assertEqual(draft["source"]["url"], "https://example.com/")
        self.assertEqual(draft["method"], "Ollama · test-model")

    def test_model_failure_falls_back(self):
        with patch.object(app, "MODEL", "test-model"), patch.object(app, "model_choice", return_value=None):
            draft = app.make_draft("/example", "<p>Plan and schedule email newsletters from one shared dashboard.</p>")
        self.assertTrue(draft["fallback"])

    def test_example_only_offers_product_copy_as_evidence(self):
        html = (app.WEB / "example.html").read_text(encoding="utf-8")
        excerpts = evidence_from(html)
        self.assertEqual(len(excerpts), 1)
        self.assertIn("Automate shift handoffs", excerpts[0].text)

    def test_uses_metadata_when_page_has_no_readable_product_copy(self):
        html = ('<head><meta property="og:description" content="Schedule group lessons and collect payments online.">'
                '</head><body><p>Please enable JavaScript to view this website.</p></body>')
        draft = app.make_draft("https://example.com/", html)
        self.assertEqual(draft["source"]["metadata_field"], "og:description")
        self.assertIn("your homepage description", draft["lines"][0])
        self.assertIn("Schedule group lessons", draft["lines"][0])

    def test_prefers_visible_copy_to_metadata(self):
        html = ('<head><meta name="description" content="Track support tickets from one shared inbox."></head>'
                '<body><h1>Automate the handoff between support shifts.</h1></body>')
        self.assertEqual(evidence_from(html), [Evidence("Automate the handoff between support shifts.")])

    def test_normalizes_domains_and_rejects_local_addresses(self):
        self.assertEqual(normalize_url("  Example.COM  "), "https://example.com/")
        with self.assertRaisesRegex(WebsiteError, "public website"):
            fetch_homepage("http://127.0.0.1")


if __name__ == "__main__":
    unittest.main()
