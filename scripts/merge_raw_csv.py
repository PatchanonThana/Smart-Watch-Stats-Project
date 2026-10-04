from __future__ import annotations

import csv
import io
import json
import sys
from collections import Counter
from pathlib import Path

import pandas as pd


EXPECTED_SOURCE_FILE_COUNT = 73

CANONICAL_COLUMNS = [
    "brand",
    "model",
    "platform",
    "source_file",
    "source_row_number",
    "web_scraper_order",
    "web_scraper_start_url",
    "pagination",
    "product_name",
    "price_raw",
    "rating_raw",
    "historical_sold_raw",
    "item_page_title",
    "item_page_link",
]

BRAND_NAMES = {
    "apple": "Apple",
    "samsung": "Samsung",
    "huawei": "Huawei",
}

MODEL_INFO = {
    "apple-watch-series9": {
        "brand": "apple",
        "name": "Apple Watch Series 9",
    },
    "apple-watch-series10": {
        "brand": "apple",
        "name": "Apple Watch Series 10",
    },
    "apple-watch-ultra2": {
        "brand": "apple",
        "name": "Apple Watch Ultra 2",
    },
    "galaxy-watch7": {"brand": "samsung", "name": "Galaxy Watch7"},
    "galaxy-watch8": {"brand": "samsung", "name": "Galaxy Watch8"},
    "galaxy-watch-ultra": {
        "brand": "samsung",
        "name": "Galaxy Watch Ultra",
    },
    "huawei-watch-gt4": {"brand": "huawei", "name": "Huawei Watch GT 4"},
    "huawei-watch-gt5": {"brand": "huawei", "name": "Huawei Watch GT 5"},
    "huawei-watch-ultimate": {
        "brand": "huawei",
        "name": "Huawei Watch Ultimate",
    },
}

PLATFORM_NAMES = {
    "lazada": "Lazada",
    "shopee": "Shopee",
}

# The Thai aliases are present in the current files. The mojibake spellings are
# retained as aliases too because they were observed during schema reconnaissance.
SOURCE_ALIASES = {
    "web_scraper_order": ["web_scraper_order"],
    "web_scraper_start_url": ["web_scraper_start_url"],
    "pagination": ["pagination"],
    "product_name": [
        "product_name",
        "\u0e0a\u0e37\u0e48\u0e2d\u0e23\u0e38\u0e48\u0e19",
        (
            "\u0e40\u0e18\x8a\u0e40\u0e18\u0e17\u0e40\u0e19\x88"
            "\u0e40\u0e18\u0e0d\u0e40\u0e18\u0e03\u0e40\u0e18\u0e18"
            "\u0e40\u0e19\x88\u0e40\u0e18\x99"
        ),
    ],
    "price_raw": [
        "price",
        "\u0e23\u0e32\u0e04\u0e32",
        "\u0e40\u0e18\u0e03\u0e40\u0e18\u0e12\u0e40\u0e18\x84\u0e40\u0e18\u0e12",
    ],
    "rating_raw": [
        "rating_score",
        "rating",
        "\u0e04\u0e30\u0e41\u0e19\u0e19\u0e23\u0e35\u0e27\u0e34\u0e27",
        (
            "\u0e40\u0e18\x84\u0e40\u0e18\u0e10\u0e40\u0e19\x81"
            "\u0e40\u0e18\x99\u0e40\u0e18\x99\u0e40\u0e18\u0e03"
            "\u0e40\u0e18\u0e15\u0e40\u0e18\u0e07\u0e40\u0e18\u0e14"
            "\u0e40\u0e18\u0e07"
        ),
    ],
    "historical_sold_raw": ["historical_sold"],
    "item_page_title": ["item_page_title"],
    "item_page_link": ["item_page_link"],
}

REQUIRED_SOURCE_FIELDS = ["product_name", "price_raw", "rating_raw"]

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_ROOT = PROJECT_ROOT / "Data" / "csv" / "Raw_data"
OUTPUT_DIRECTORY = PROJECT_ROOT / "Data" / "csv" / "Preprocessed_data" / "merged"
OUTPUT_PATH = OUTPUT_DIRECTORY / "merged.csv"
REPORT_PATH = OUTPUT_DIRECTORY / "merge_validation.json"


def discover_csv_files(directory: Path) -> list[Path]:
    if not directory.exists():
        raise ValueError(f"Raw-data directory does not exist: {directory}")

    files = [
        path
        for path in directory.rglob("*")
        if path.is_file() and path.suffix.lower() == ".csv"
    ]
    return sorted(files, key=lambda path: path.relative_to(directory).as_posix())


def path_metadata(file_path: Path) -> dict[str, str]:
    source_file = file_path.relative_to(RAW_ROOT).as_posix()
    parts = source_file.split("/")
    if len(parts) != 4:
        raise ValueError(
            f"{source_file}: expected path <brand>/<model>/<platform>/<file>.csv"
        )

    brand_directory, model_directory, platform_directory, _ = parts
    brand = BRAND_NAMES.get(brand_directory)
    model = MODEL_INFO.get(model_directory)
    platform = PLATFORM_NAMES.get(platform_directory)

    if brand is None:
        raise ValueError(
            f"{source_file}: unexpected brand directory '{brand_directory}'"
        )
    if model is None:
        raise ValueError(
            f"{source_file}: unexpected model directory '{model_directory}'"
        )
    if model["brand"] != brand_directory:
        raise ValueError(
            f"{source_file}: model '{model_directory}' is not mapped to brand "
            f"'{brand_directory}'"
        )
    if platform is None:
        raise ValueError(
            f"{source_file}: unexpected platform directory '{platform_directory}'"
        )

    return {
        "brand": brand,
        "brand_directory": brand_directory,
        "model": model["name"],
        "model_directory": model_directory,
        "platform": platform,
        "platform_directory": platform_directory,
        "source_file": source_file,
    }


def read_source_csv(file_path: Path, source_file: str) -> pd.DataFrame:
    try:
        with file_path.open(
            "r", encoding="utf-8-sig", errors="strict", newline=""
        ) as source:
            source_text = source.read()
    except UnicodeDecodeError as error:
        raise ValueError(f"{source_file}: invalid UTF-8 input ({error})") from error

    try:
        records = csv.reader(io.StringIO(source_text, newline=""), strict=True)
        header = next(records)
        header_width = len(header)
        for source_row_number, record in enumerate(records, start=1):
            if len(record) != header_width:
                raise ValueError(
                    f"{source_file}: data row {source_row_number} has "
                    f"{len(record)} fields; header has {header_width}"
                )
    except StopIteration as error:
        raise ValueError(f"{source_file}: file is empty") from error
    except csv.Error as error:
        raise ValueError(f"{source_file}: invalid CSV input ({error})") from error

    try:
        frame = pd.read_csv(
            io.StringIO(source_text, newline=""),
            header=None,
            dtype=str,
            keep_default_na=False,
            na_filter=False,
            skip_blank_lines=False,
            on_bad_lines="error",
        )
    except pd.errors.EmptyDataError as error:
        raise ValueError(f"{source_file}: file is empty") from error
    except pd.errors.ParserError as error:
        raise ValueError(f"{source_file}: invalid CSV input ({error})") from error

    if frame.empty:
        raise ValueError(f"{source_file}: file is empty")
    if frame.isna().to_numpy().any():
        raise ValueError(
            f"{source_file}: pandas produced missing values despite raw-string settings"
        )
    return frame


def build_column_mapping(
    header: list[str], source_file: str
) -> tuple[dict[str, int], list[str], list[str]]:
    normalized_header = [name.strip() for name in header]
    header_counts = Counter(normalized_header)

    for index, name in enumerate(normalized_header, start=1):
        if name == "":
            raise ValueError(f"{source_file}: empty source header at column {index}")
    for name, count in header_counts.items():
        if count > 1:
            raise ValueError(
                f"{source_file}: duplicate source header '{name}' after trimming "
                "surrounding whitespace"
            )

    header_indexes = {name: index for index, name in enumerate(normalized_header)}
    canonical_indexes: dict[str, int] = {}
    used_source_indexes: set[int] = set()

    for canonical_name, aliases in SOURCE_ALIASES.items():
        matches = [
            (alias, header_indexes[alias])
            for alias in aliases
            if alias in header_indexes
        ]
        if len(matches) > 1:
            matched_aliases = ", ".join(f"'{alias}'" for alias, _ in matches)
            raise ValueError(
                f"{source_file}: multiple headers map to '{canonical_name}': "
                f"{matched_aliases}"
            )
        if matches:
            _, source_index = matches[0]
            canonical_indexes[canonical_name] = source_index
            used_source_indexes.add(source_index)

    missing_required_fields = [
        name for name in REQUIRED_SOURCE_FIELDS if name not in canonical_indexes
    ]
    if missing_required_fields:
        raise ValueError(
            f"{source_file}: source schema is missing required mapped field(s): "
            f"{', '.join(missing_required_fields)}"
        )

    ignored_headers = [
        name for index, name in enumerate(header) if index not in used_source_indexes
    ]
    return canonical_indexes, ignored_headers, normalized_header


def canonical_frame(
    source_frame: pd.DataFrame,
    metadata: dict[str, str],
    canonical_indexes: dict[str, int],
) -> pd.DataFrame:
    data = source_frame.iloc[1:].reset_index(drop=True)
    row_count = len(data)
    frame = pd.DataFrame(index=range(row_count))

    frame["brand"] = metadata["brand"]
    frame["model"] = metadata["model"]
    frame["platform"] = metadata["platform"]
    frame["source_file"] = metadata["source_file"]
    frame["source_row_number"] = [str(index) for index in range(1, row_count + 1)]

    for canonical_name in CANONICAL_COLUMNS[5:]:
        source_index = canonical_indexes.get(canonical_name)
        if source_index is None:
            frame[canonical_name] = ""
        else:
            frame[canonical_name] = data.iloc[:, source_index].tolist()

    frame = frame[CANONICAL_COLUMNS]
    if frame.iloc[:, :5].eq("").to_numpy().any():
        raise ValueError(
            f"{metadata['source_file']}: generated empty provenance metadata"
        )
    return frame


def dataframe_records(frame: pd.DataFrame) -> list[list[str]]:
    return [[str(value) for value in row] for row in frame.itertuples(index=False)]


def main() -> None:
    source_paths = discover_csv_files(RAW_ROOT)
    if len(source_paths) != EXPECTED_SOURCE_FILE_COUNT:
        raise ValueError(
            f"expected {EXPECTED_SOURCE_FILE_COUNT} raw CSV files, discovered "
            f"{len(source_paths)}"
        )

    source_read_counts: Counter[str] = Counter()
    sources: list[dict[str, object]] = []
    source_frames: list[pd.DataFrame] = []
    breakdown: Counter[tuple[str, str, str]] = Counter()
    encountered_models: set[str] = set()
    encountered_platforms: set[str] = set()

    for source_path in source_paths:
        metadata = path_metadata(source_path)
        source_file = metadata["source_file"]
        encountered_models.add(metadata["model_directory"])
        encountered_platforms.add(metadata["platform_directory"])

        source_read_counts[source_file] += 1
        if source_read_counts[source_file] != 1:
            raise ValueError(f"{source_file}: source was read more than once")

        raw_frame = read_source_csv(source_path, source_file)
        header = raw_frame.iloc[0].tolist()
        canonical_indexes, ignored_headers, normalized_header = build_column_mapping(
            header, source_file
        )
        merged_source = canonical_frame(raw_frame, metadata, canonical_indexes)
        source_frames.append(merged_source)

        row_count = len(merged_source)
        breakdown[(metadata["brand"], metadata["model"], metadata["platform"])] += (
            row_count
        )
        sources.append(
            {
                "source_file": source_file,
                "read_count": source_read_counts[source_file],
                "data_row_count": row_count,
                "original_headers": header,
                "normalized_headers": normalized_header,
                "ignored_headers": ignored_headers,
            }
        )

    expected_models = sorted(MODEL_INFO)
    actual_models = sorted(encountered_models)
    if actual_models != expected_models:
        raise ValueError(
            "model directories do not match the expected mappings; expected "
            f"{', '.join(expected_models)}; encountered {', '.join(actual_models)}"
        )

    expected_platforms = sorted(PLATFORM_NAMES)
    actual_platforms = sorted(encountered_platforms)
    if actual_platforms != expected_platforms:
        raise ValueError(
            "platform directories do not match the expected mappings; expected "
            f"{', '.join(expected_platforms)}; encountered "
            f"{', '.join(actual_platforms)}"
        )

    merged = pd.concat(source_frames, ignore_index=True)[CANONICAL_COLUMNS]
    total_source_rows = sum(int(source["data_row_count"]) for source in sources)
    if len(merged) != total_source_rows:
        raise ValueError(
            f"merged row count {len(merged)} does not equal source row count "
            f"{total_source_rows}"
        )
    if len(source_read_counts) != len(source_paths):
        raise ValueError(
            f"read {len(source_read_counts)} unique sources but discovered "
            f"{len(source_paths)}"
        )

    row_counts_by_brand_model_platform = [
        {
            "brand": brand,
            "model": model,
            "platform": platform,
            "row_count": breakdown[(brand, model, platform)],
        }
        for brand, model, platform in sorted(breakdown)
    ]

    output_text = merged.to_csv(
        index=False,
        lineterminator="\r\n",
        quoting=csv.QUOTE_MINIMAL,
    )
    output_records = pd.read_csv(
        io.StringIO(output_text),
        header=None,
        dtype=str,
        keep_default_na=False,
        na_filter=False,
        skip_blank_lines=False,
        on_bad_lines="error",
    )
    expected_output_records = [CANONICAL_COLUMNS, *dataframe_records(merged)]
    if dataframe_records(output_records) != expected_output_records:
        raise ValueError("generated output failed the CSV round-trip check")

    report = {
        "source_csv_files_discovered": len(source_paths),
        "source_csv_files_read": len(source_read_counts),
        "total_source_rows": total_source_rows,
        "merged_rows": len(merged),
        "canonical_columns": CANONICAL_COLUMNS,
        "encountered_model_directories": actual_models,
        "encountered_platform_directories": actual_platforms,
        "row_counts_by_brand_model_platform": row_counts_by_brand_model_platform,
        "parse_failures": [],
        "unexpected_schemas": [],
        "path_exceptions": [],
        "validations": {
            "exactly_73_source_csv_files": (
                len(source_paths) == EXPECTED_SOURCE_FILE_COUNT
            ),
            "every_source_read_exactly_once": all(
                count == 1 for count in source_read_counts.values()
            ),
            "merged_rows_equal_source_rows": len(merged) == total_source_rows,
            "no_source_rows_intentionally_dropped": True,
            "provenance_fields_non_empty": True,
            "output_csv_round_trip_preserves_values": True,
            "exactly_expected_model_directories": actual_models == expected_models,
            "exactly_expected_platform_directories": (
                actual_platforms == expected_platforms
            ),
        },
        "sources": sources,
    }

    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", encoding="utf-8", newline="") as output_file:
        output_file.write(output_text)
    with REPORT_PATH.open("w", encoding="utf-8", newline="\n") as report_file:
        json.dump(report, report_file, ensure_ascii=False, indent=2)
        report_file.write("\n")

    print(f"Source CSV files: {len(source_paths)}")
    print(f"Total source rows: {total_source_rows}")
    print(f"Merged rows: {len(merged)}")
    print(f"Merged output: {OUTPUT_PATH.relative_to(PROJECT_ROOT)}")
    print(f"Validation report: {REPORT_PATH.relative_to(PROJECT_ROOT)}")
    print("\nRow counts by brand / model / platform:")
    for item in row_counts_by_brand_model_platform:
        print(
            f"{item['brand']} | {item['model']} | {item['platform']} | "
            f"{item['row_count']}"
        )
    print("\nPer-source data-row counts:")
    for source in sources:
        print(f"{source['data_row_count']}\t{source['source_file']}")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"Merge failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error
