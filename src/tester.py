import ollama
import time
import logging
from typing import Tuple

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

MODEL = "llama3.1-32k"

client = ollama.Client(host='http://localhost:11434', timeout=600.0)

def run_query(context: str, question: str) -> Tuple[str, float]:
    start_time = time.time()

    logger.info(f"Sending request with context length: {len(context)} chars")

    messages = [
        {"role": "system", "content": "You are a precise extraction engine. Answer ONLY with the secret code found in the text. Do not add any explanation."},
        {"role": "user", "content": f"{context}\n\nQuestion: {question}"}
    ]

    try:
        response = client.chat(model=MODEL, messages=messages, options={"num_ctx": 8192})
        elapsed = time.time() - start_time
        answer = response['message']['content'].strip()

        logger.info(f"Response received in {elapsed:.2f}s: {answer[:50]}...")
        return answer, elapsed

    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"Request failed after {elapsed:.2f}s: {str(e)}")
        return f"ERROR: {str(e)}", elapsed


def evaluate_accuracy(predicted: str, expected: str) -> bool:
    if "ERROR" in predicted:
        return False

    expected_code = expected.split("'")[1] if "'" in expected else expected.split("is ")[-1].strip(".")
    return expected_code.lower() in predicted.lower()