import csv


def csv_to_markdown(csv_file="results/benchmarking_raw.csv", md_file="bench.md"):
    with open(csv_file, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        rows = list(reader)

    if not rows:
        print("CSV file is empty.")
        return

    with open(md_file, "w", encoding="utf-8") as f:
        # Header
        header = rows[0]
        f.write("| " + " | ".join(header) + " |\n")
        f.write("| " + " | ".join(["---"] * len(header)) + " |\n")

        # Data rows
        for row in rows[1:]:
            # Pad short rows if necessary
            row += [""] * (len(header) - len(row))
            f.write("| " + " | ".join(row[: len(header)]) + " |\n")

    print(f"Markdown table written to {md_file}")


if __name__ == "__main__":
    csv_to_markdown()
