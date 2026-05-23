import unittest

from src import literature_hunter


class LiteratureHunterTest(unittest.TestCase):
    def test_hunter_returns_only_verifiable_openalex_works(self):
        original_search = literature_hunter._openalex_search

        def fake_search(query, per_page=12, timeout=12):
            return [
                {
                    "id": "https://openalex.org/W1",
                    "doi": "https://doi.org/10.1000/example",
                    "display_name": "Knowledge management capability and sales team performance",
                    "publication_year": 2022,
                    "cited_by_count": 42,
                    "authorships": [
                        {"author": {"display_name": "Jane Smith"}},
                        {"author": {"display_name": "John Doe"}},
                    ],
                    "primary_location": {
                        "source": {"display_name": "Journal of Knowledge Management"},
                        "landing_page_url": "https://doi.org/10.1000/example",
                    },
                    "abstract_inverted_index": {
                        "knowledge": [0],
                        "management": [1],
                        "sales": [2],
                        "team": [3],
                        "training": [4],
                        "performance": [5],
                    },
                    "concepts": [{"display_name": "Knowledge management"}],
                },
                {
                    "id": "",
                    "display_name": "Unverifiable generated looking title",
                },
            ]

        try:
            literature_hunter._openalex_search = fake_search
            result = literature_hunter.hunt_real_literature(
                {
                    "topic": "AI赋能知识管理与销售团队培训能力提升",
                    "direction_name": "知识管理",
                    "methods": ["案例研究法"],
                    "project_context": "销售团队培训、知识共享、绩效提升",
                },
                limit=3,
            )
        finally:
            literature_hunter._openalex_search = original_search

        self.assertEqual("found", result["status"])
        self.assertEqual(1, len(result["citations"]))
        citation = result["citations"][0]
        self.assertEqual("real_literature_hunter", citation["source"])
        self.assertIn("OpenAlex", citation["verify_status"])
        self.assertTrue(citation["doi"] or citation["openalex_id"] or citation["url"])
        self.assertIn("Knowledge management", citation["formatted"])


if __name__ == "__main__":
    unittest.main()
