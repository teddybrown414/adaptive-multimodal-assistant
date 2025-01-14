from sumy.parsers.plaintext import PlaintextParser
from sumy.nlp.tokenizers import Tokenizer
from sumy.summarizers.lex_rank import LexRankSummarizer
import nltk

async def summarize_text(text, num_sentences) -> str:
    """Summarizes text using the LexRank algorithm."""
    nltk.download('punkt_tab')

    parser = PlaintextParser.from_string(text, Tokenizer("english"))
    summarizer = LexRankSummarizer()
    summary = summarizer(parser.document, num_sentences)

    summary_text = ""
    for sentence in summary:
        summary_text += str(sentence) + " "

    return summary_text