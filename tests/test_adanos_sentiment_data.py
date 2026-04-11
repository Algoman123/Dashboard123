import sys
import types
import unittest
from unittest.mock import Mock, patch


def _cache_data_stub(*args, **kwargs):
    def decorator(func):
        func.clear = lambda: None
        return func

    return decorator


sys.modules.setdefault(
    "streamlit",
    types.SimpleNamespace(cache_data=_cache_data_stub),
)
sys.modules.setdefault("yfinance", types.SimpleNamespace())

from services.sentiment_data import fetch_adanos_sentiment, _normalize_adanos_tickers


class AdanosSentimentDataTests(unittest.TestCase):
    def setUp(self):
        fetch_adanos_sentiment.clear()

    def tearDown(self):
        fetch_adanos_sentiment.clear()

    def test_normalizes_tickers_for_compare_request(self):
        self.assertEqual(
            ("TSLA", "NVDA", "BRK.B"),
            _normalize_adanos_tickers(" $tsla, NVDA ^GSPC TSLA BRK.B BTC-USD "),
        )

    def test_skips_network_request_without_api_key(self):
        with (
            patch("services.sentiment_data.get_adanos_key", return_value=None),
            patch("services.sentiment_data.requests.get") as mock_get,
        ):
            result = fetch_adanos_sentiment(("TSLA",), platforms=("reddit",))

        self.assertTrue(result.empty)
        mock_get.assert_not_called()

    def test_fetches_and_parses_compare_rows(self):
        response = Mock()
        response.status_code = 200
        response.json.return_value = {
            "period_days": 30,
            "stocks": [
                {
                    "ticker": "TSLA",
                    "company_name": "Tesla, Inc.",
                    "buzz_score": 72.5,
                    "sentiment_score": 0.31,
                    "bullish_pct": 61,
                    "bearish_pct": 19,
                    "mentions": 180,
                    "trend": "rising",
                }
            ],
        }

        with (
            patch("services.sentiment_data.get_adanos_key", return_value="sk_live_test"),
            patch("services.sentiment_data.requests.get", return_value=response) as mock_get,
        ):
            result = fetch_adanos_sentiment(("TSLA",), days=30, platforms=("reddit",))

        self.assertEqual(1, len(result))
        self.assertEqual("TSLA", result.iloc[0]["Ticker"])
        self.assertEqual("Reddit", result.iloc[0]["Platform"])
        self.assertEqual(72.5, result.iloc[0]["Buzz Score"])

        mock_get.assert_called_once()
        request_url = mock_get.call_args.args[0]
        request_kwargs = mock_get.call_args.kwargs
        self.assertEqual("https://api.adanos.org/reddit/stocks/v1/compare", request_url)
        self.assertEqual({"tickers": "TSLA", "days": 30}, request_kwargs["params"])
        self.assertEqual("sk_live_test", request_kwargs["headers"]["X-API-Key"])


if __name__ == "__main__":
    unittest.main()
