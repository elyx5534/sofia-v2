# thirdparty_stubs/vaderSentiment/__init__.py
class SentimentIntensityAnalyzer:
    def __init__(self):
        pass

    def polarity_scores(self, text):
        return {"neg": 0.0, "neu": 0.5, "pos": 0.5, "compound": 0.5}


__all__ = ["SentimentIntensityAnalyzer"]
