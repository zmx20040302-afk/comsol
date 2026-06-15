import tempfile
import unittest
from pathlib import Path

from comsol_docs_kb import clean_page_text, module_boost, similarity, tokenize


class ComsolDocumentationKnowledgeBaseTest(unittest.TestCase):
    def test_tokenizes_english_and_chinese_operations(self):
        tokens = tokenize("Build mesh and 求解器设置")
        self.assertIn("mesh", tokens)
        self.assertIn("求解", tokens)

    def test_cleans_pdf_page_text(self):
        self.assertEqual(clean_page_text("A   B\n\n\nC\x00"), "A B\n\nC")

    def test_similarity_prefers_matching_operation(self):
        idf = {"mesh": 1.0, "solver": 1.0}
        self.assertGreater(
            similarity("mesh", idf, {"mesh": 1.0}),
            similarity("mesh", idf, {"solver": 1.0}),
        )

    def test_module_boost_prefers_matlab_documentation(self):
        page = {"module": "LiveLink_for_MATLAB", "document": "LiveLinkForMATLABUsersGuide.pdf"}
        self.assertGreater(module_boost("How to use mphstart in MATLAB?", page), 0)


if __name__ == "__main__":
    unittest.main()
