from pathlib import Path
import re
import unicodedata

import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[1]
INPUT_FILE = PROJECT_DIR / "Data" / "csv" / "Preprocessed_data" / "merged" / "merged.csv"
OUTPUT_FILE = PROJECT_DIR / "Data" / "csv" / "Preprocessed_data" / "cleaned" / "cleaned.csv"

SOURCE_COLUMNS = [
    "brand",
    "model",
    "platform",
    "product_name",
    "price_raw",
    "rating_raw",
]
FINAL_COLUMNS = ["brand", "model", "platform", "product_name", "price", "rating"]

TARGET_PATTERNS = {
    "Apple Watch Series 9": r"\bapple\s+watch\s+(?:series\s*9|s9)\b",
    "Apple Watch Series 10": r"\bapple\s+watch\s+(?:series\s*10|s10)\b",
    "Apple Watch Ultra 2": r"\bapple\s+watch\s+ultra\s*2\b",
    "Galaxy Watch7": r"\b(?:samsung\s+)?galaxy\s+watch\s*7\b",
    "Galaxy Watch8": r"\b(?:samsung\s+)?galaxy\s+watch\s*8\b",
    "Galaxy Watch Ultra": r"\b(?:samsung\s+)?galaxy\s+watch\s+ultra\b",
    "Huawei Watch GT 4": r"\bhuawei\s+watch\s+gt\s*4\b",
    "Huawei Watch GT 5": r"\bhuawei\s+watch\s+gt\s*5\b",
    "Huawei Watch Ultimate": r"\bhuawei\s+watch\s+ultimate\b",
}

ACCESSORY_PATTERN = re.compile(
    r"screen\s*protector|tempered\s+glass|protective\s+film|"
    r"watch\s*(?:strap|band)|watchstrap|watchband|"
    r"replacement\s+(?:strap|band|part)|charging\s+(?:cable|dock|stand)|"
    r"\bcharger\b|case\s+cover|protective\s+case|\bbumper\b|\badapter\b|"
    r"\bconnector\b|\baccessor(?:y|ies)\b|"
    r"^(?:case|strap|band|film|cover)\b|"
    r"(?:case|strap|band|film|glass|cover).{0,30}\bfor\b|"
    r"\b(?:silicone|leather|metal|nylon|titanium|stainless\s+steel)\s+"
    r"(?:watch\s*)?(?:strap|band)\b|"
    r"(?:\bfor\b|สำหรับ|สําหรับ|สำหรบ|สําหรบ)\s+"
    r"(?:apple|samsung|huawei|galaxy)\b|"
    r"(?:ฟิล์ม|กระจกกันรอย|กระจกนิรภัย|ฟิล์มกระจก|สายนาฬิกา|สายรัด|"
    r"(?<!ไร้)สายชาร์จ|ที่ชาร์จ|แท่นชาร์จ|เคส|กรอบ|กันชน|อะไหล่|อุปกรณ์เสริม|"
    r"ฟลมกนรอย|กนรอยหนาจอ)|"
    r"^(?:สายซิลิโคน|สายยาง|สายหนัง|สายโลหะ|สายไนลอน|สายสแตนเลส)|"
    r"(?:สายซิลิโคน|สายหนัง|สายโลหะ|สายไนลอน|สายสแตนเลส).{0,40}"
    r"(?:สำหรับ|สําหรับ)|"
    r"(?:สแตนเลส|ซิลิโคน|หนัง|โลหะ).{0,80}(?:สร้อยข้อมือ|สายคล้อง)",
    re.IGNORECASE,
)

CONDITION_PATTERN = re.compile(
    r"(?<!be )\bused\b|second[ -]hand|refurbished|\bdemo\b|showpiece|open[ -]box|"
    r"\b\d{1,2}\s*%\s*new\b|"
    r"มือสอง|เครื่องโชว์|เครื่องสาธิต|รีเฟอร์บิช|แกะกล่อง",
    re.IGNORECASE,
)

CLONE_PATTERN = re.compile(
    r"\b(?:clone|replica|copy)\b|\b1\s*:\s*1\b",
    re.IGNORECASE,
)


def normalize_for_matching(value):
    text = unicodedata.normalize("NFKC", str(value)).casefold()
    return re.sub(r"\s+", " ", text).strip()


def has_conflicting_model(model, title):
    if model.startswith("Apple Watch"):
        series = {int(number) for number in re.findall(r"\bseries\s*(\d{1,2})\b", title)}
        short = {int(number) for number in re.findall(r"\bs\s*(\d{1,2})\b", title)}
        if model == "Apple Watch Series 9":
            return bool((series | short) - {9} or re.search(r"\b(?:ultra|se)\b", title))
        if model == "Apple Watch Series 10":
            return bool((series | short) - {10} or re.search(r"\b(?:ultra|se)\b", title))
        ultra_numbers = re.findall(r"\bultra\s*(\d+)", title)
        return bool(series or short or re.search(r"\bse\b", title)) or any(
            int(number) != 2 for number in ultra_numbers
        )

    if model.startswith("Galaxy Watch"):
        numbered_models = {
            int(number) for number in re.findall(r"\bwatch\s*(\d+)\b", title)
        }
        if model == "Galaxy Watch7":
            return bool(
                numbered_models - {7}
                or re.search(r"\b(?:classic|ultra|fe|mini|max)\b", title)
                or re.search(r"\b(?:46|47|49)\s*mm\b", title)
            )
        if model == "Galaxy Watch8":
            return bool(
                numbered_models - {8}
                or re.search(r"\b(?:classic|ultra|fe|mini|max)\b", title)
                or re.search(r"\b(?:46|47|49)\s*mm\b", title)
            )
        return bool(
            numbered_models
            or re.search(r"\bultra\s*2\b|\bultra\s*/\s*s?\d+\b", title)
        )

    if model in {"Huawei Watch GT 4", "Huawei Watch GT 5"}:
        target_number = 4 if model.endswith("4") else 5
        gt_models = {
            int(number) for number in re.findall(r"\bgt\s*(\d+)\b", title)
        }
        is_pro = re.search(rf"\bgt\s*{target_number}\s*pro\b", title)
        watch_4_pro = target_number == 4 and re.search(r"\bhuawei\s+watch\s*4\s*pro\b", title)
        return bool(gt_models - {target_number} or is_pro or watch_4_pro)

    return bool(
        re.search(r"\bultimate\s*2\b|\bultimate\s+design\b", title)
        or re.search(r"\bhuawei\s+(?:watch\s+(?:gt|fit)|band)\b", title)
    )


def is_relevant_product(row):
    title = normalize_for_matching(row["product_name"])
    target_pattern = TARGET_PATTERNS.get(row["model"])
    if target_pattern is None:
        raise ValueError(f"No product rule exists for model: {row['model']}")
    return bool(
        re.search(target_pattern, title, re.IGNORECASE)
        and not ACCESSORY_PATTERN.search(title)
        and not CONDITION_PATTERN.search(title)
        and not CLONE_PATTERN.search(title)
        and not has_conflicting_model(row["model"], title)
    )


def parse_rating(value):
    text = str(value).strip()
    if not text:
        return float("nan")
    match = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)\s*(?:คะแนน)?", text)
    if not match:
        return float("nan")
    rating = float(match.group(1))
    return rating if 0 <= rating <= 5 else float("nan")


def main():
    data = pd.read_csv(INPUT_FILE, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    missing_columns = [column for column in SOURCE_COLUMNS if column not in data.columns]
    if missing_columns:
        raise ValueError(f"Missing expected columns: {', '.join(missing_columns)}")

    input_rows = len(data)
    data = data.drop_duplicates(subset=SOURCE_COLUMNS, keep="first").copy()
    duplicates_removed = input_rows - len(data)
    model_order = data["model"].drop_duplicates()
    platform_order = data["platform"].drop_duplicates()

    relevant = data.apply(is_relevant_product, axis=1)
    irrelevant_removed = int((~relevant).sum())
    data = data.loc[relevant].copy()

    price_text = data["price_raw"].str.strip().str.replace("฿", "", regex=False)
    data["price"] = pd.to_numeric(price_text.str.replace(",", "", regex=False), errors="coerce")
    invalid_price_rows = int(data["price"].isna().sum())
    data = data.loc[data["price"].notna()].copy()

    data["rating"] = data["rating_raw"].map(parse_rating)
    cleaned = data[FINAL_COLUMNS]

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    cleaned.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")

    print(f"Input rows: {input_rows}")
    print(f"Exact duplicates removed: {duplicates_removed}")
    print(f"Irrelevant/non-target rows removed: {irrelevant_removed}")
    print(f"Invalid-price rows removed: {invalid_price_rows}")
    print(f"Final cleaned rows: {len(cleaned)}")
    print(f"Final rows with missing rating: {int(cleaned['rating'].isna().sum())}")
    print("\nFinal rows by model x platform:")
    counts = cleaned.groupby(["model", "platform"], sort=False).size().unstack(fill_value=0)
    counts = counts.reindex(index=model_order, columns=platform_order, fill_value=0)
    print(counts.to_string())
    print(f"\nOutput path: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
