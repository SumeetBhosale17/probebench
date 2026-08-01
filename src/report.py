import pandas as pd
import logging
from src.generator import load_filler, load_needles, create_haystack, count_tokens
from src.tester import MODEL, run_query, evaluate_accuracy

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    logger.info("Loading data files...")
    filler = load_filler("data/filler_text.txt")
    needles = load_needles("data/needles.txt")

    if not filler:
        logging.error("Filler text is empty! Check data/filler_text.txt")
        return

    results = []

    target_tokens = [4000, 8000, 16000, 32000]
    depths = [0.0, 0.5, 1.0]

    logger.info(f"Starting benchmark for {MODEL}...")
    logger.info(f"Total filler size: {len(filler)} chars")

    for tokens in target_tokens:
        for depth in depths:
            for needle in needles[:3]:
                logger.info(f"Generating haystack: {tokens} tokens, depth {depth}...")

                try:
                    context = create_haystack(filler, needle, tokens, depth)
                    actual_tokens = count_tokens(context)

                    if actual_tokens > 35000:
                        logger.warning(f"Skipping test: Generated {actual_tokens} tokens (Limit: 35k)")
                        continue

                    question = "What is the important secret mentioned in the text?"
                    logger.info(f"Sending query (Tokens: {actual_tokens})...")
                    
                    answer, latency = run_query(context, question)
                    success = evaluate_accuracy(answer, needle)

                    results.append({
                        "context_tokens": actual_tokens,
                        "depth": depth,
                        "needle": needle,
                        "predicted": answer,
                        "success": success,
                        "latency_sec": latency
                    })

                    status = "✅" if success else "❌"
                    logger.info(f"[{status}] Tokens: {actual_tokens}, Depth: {depth}, Latency: {latency:.2f}s")

                except Exception as e:
                    logger.error(f"Test failed completely: {e}")
                    continue

    if results:
        df = pd.DataFrame(results)
        df['context_tokens_binned'] = (df['context_tokens'] / 1000).round() * 1000
        df.to_csv("results/benchmarking_raw.csv", index=False)

        summary = df.pivot_table(
            index="context_tokens_binned", 
            columns="depth", 
            values="success", 
            aggfunc="mean"
        ).fillna(0)
        summary.to_markdown("results/summary_report.md")
        logger.info("\nReport saved to results/summary_report.md")
        print(summary)
    else:
        logger.error("No results generated. Check logs for errors.")


if __name__ == '__main__':
    main()