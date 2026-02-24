import unittest
from unittest.mock import MagicMock, patch
import json
from api import XiaoyuzhouAPI

class TestXiaoyuzhouAPI(unittest.TestCase):
    def setUp(self):
        self.api = XiaoyuzhouAPI()

    @patch('api.requests.Session.request')
    def test_get_episode_transcript_success(self, mock_request):
        # Mock successful response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "transcriptUrl": "https://transcript-highlight.xyzcdn.net/..."
            }
        }
        mock_request.return_value = mock_response

        eid = "test_eid"
        media_id = "test_media_id"
        result = self.api.get_episode_transcript(eid, media_id)

        self.assertTrue(result["success"])
        self.assertEqual(result["data"]["data"]["transcriptUrl"], "https://transcript-highlight.xyzcdn.net/...")
        
        # Verify call arguments
        args, kwargs = mock_request.call_args
        self.assertEqual(args[0], "POST")
        self.assertIn("/v1/episode-transcript/get", args[1])
        self.assertEqual(kwargs['json'], {"eid": eid, "mediaId": media_id})

    @patch('api.requests.Session.request')
    def test_get_episode_transcript_failure(self, mock_request):
        # Mock failed response
        mock_response = MagicMock()
        mock_response.status_code = 500
        # Correctly mock raise_for_status to raise an HTTPError
        import requests
        mock_response.raise_for_status.side_effect = requests.HTTPError("Server Error")
        mock_request.return_value = mock_response

        eid = "test_eid"
        media_id = "test_media_id"
        result = self.api.get_episode_transcript(eid, media_id)

        self.assertFalse(result["success"])
        self.assertIn("Server Error", result["error"])

if __name__ == '__main__':
    unittest.main()
