import unittest
from fastapi.testclient import TestClient
from scrollarr.app import app

class TestApiDocs(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_api_docs_endpoint(self):
        response = self.client.get("/api-docs")
        self.assertEqual(response.status_code, 200)
        self.assertIn("API Documentation", response.text)
        self.assertIn("Interactive Documentation", response.text)
        self.assertIn("Open Swagger UI", response.text)

if __name__ == '__main__':
    unittest.main()
