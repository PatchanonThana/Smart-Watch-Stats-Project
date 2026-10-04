from pathlib import Path

import pandas as pd


project_dir = Path(__file__).resolve().parents[1]
raw_dir = project_dir / "Data" / "csv" / "Raw_data"
output_file = project_dir / "Data" / "csv" / "Preprocessed_data" / "merged" / "merged.csv"

brand_names = {
    "apple": "Apple",
    "samsung": "Samsung",
    "huawei": "Huawei",
}

model_names = {
    "apple-watch-series9": "Apple Watch Series 9",
    "apple-watch-series10": "Apple Watch Series 10",
    "apple-watch-ultra2": "Apple Watch Ultra 2",
    "galaxy-watch7": "Galaxy Watch7",
    "galaxy-watch8": "Galaxy Watch8",
    "galaxy-watch-ultra": "Galaxy Watch Ultra",
    "huawei-watch-gt4": "Huawei Watch GT 4",
    "huawei-watch-gt5": "Huawei Watch GT 5",
    "huawei-watch-ultimate": "Huawei Watch Ultimate",
}

platform_names = {
    "lazada": "Lazada",
    "shopee": "Shopee",
}

column_names = {
    "product_name": "product_name",
    "ชื่อรุ่น": "product_name",
    "price": "price_raw",
    "ราคา": "price_raw",
    "rating_score": "rating_raw",
    "rating": "rating_raw",
    "คะแนนรีวิว": "rating_raw",
}

csv_files = sorted(raw_dir.rglob("*.csv"))
dataframes = []

for file in csv_files:
    df = pd.read_csv(
        file,
        dtype=str,
        keep_default_na=False,
        encoding="utf-8-sig",
    )
    df.columns = df.columns.str.strip()
    df = df.rename(columns=column_names)
    df = df[["product_name", "price_raw", "rating_raw"]]

    brand, model, platform = file.relative_to(raw_dir).parts[:3]
    df.insert(0, "platform", platform_names[platform])
    df.insert(0, "model", model_names[model])
    df.insert(0, "brand", brand_names[brand])
    dataframes.append(df)

merged = pd.concat(dataframes, ignore_index=True)
output_file.parent.mkdir(parents=True, exist_ok=True)
merged.to_csv(output_file, index=False, encoding="utf-8-sig")

print(f"CSV files read: {len(csv_files)}")
print(f"Merged rows: {len(merged)}")
print(f"Output path: {output_file}")
