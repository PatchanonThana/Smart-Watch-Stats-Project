import fs from "node:fs";
import path from "node:path";
import { TextDecoder } from "node:util";
import { fileURLToPath } from "node:url";

const EXPECTED_SOURCE_FILE_COUNT = 73;

const CANONICAL_COLUMNS = [
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
];

const BRAND_NAMES = new Map([
  ["apple", "Apple"],
  ["samsung", "Samsung"],
  ["huawei", "Huawei"],
]);

const MODEL_INFO = new Map([
  ["apple-watch-series9", { brand: "apple", name: "Apple Watch Series 9" }],
  ["apple-watch-series10", { brand: "apple", name: "Apple Watch Series 10" }],
  ["apple-watch-ultra2", { brand: "apple", name: "Apple Watch Ultra 2" }],
  ["galaxy-watch7", { brand: "samsung", name: "Galaxy Watch7" }],
  ["galaxy-watch8", { brand: "samsung", name: "Galaxy Watch8" }],
  ["galaxy-watch-ultra", { brand: "samsung", name: "Galaxy Watch Ultra" }],
  ["huawei-watch-gt4", { brand: "huawei", name: "Huawei Watch GT 4" }],
  ["huawei-watch-gt5", { brand: "huawei", name: "Huawei Watch GT 5" }],
  ["huawei-watch-ultimate", { brand: "huawei", name: "Huawei Watch Ultimate" }],
]);

const PLATFORM_NAMES = new Map([
  ["lazada", "Lazada"],
  ["shopee", "Shopee"],
]);

// The Thai aliases are present in the current files. The mojibake spellings are
// retained as aliases too because they were observed during schema reconnaissance.
const SOURCE_ALIASES = new Map([
  ["web_scraper_order", ["web_scraper_order"]],
  ["web_scraper_start_url", ["web_scraper_start_url"]],
  ["pagination", ["pagination"]],
  ["product_name", ["product_name", "ชื่อรุ่น", "เธเธทเนเธญเธฃเธธเนเธ"]],
  ["price_raw", ["price", "ราคา", "เธฃเธฒเธเธฒ"]],
  ["rating_raw", ["rating_score", "rating", "คะแนนรีวิว", "เธเธฐเนเธเธเธฃเธตเธงเธดเธง"]],
  ["historical_sold_raw", ["historical_sold"]],
  ["item_page_title", ["item_page_title"]],
  ["item_page_link", ["item_page_link"]],
]);

const REQUIRED_SOURCE_FIELDS = ["product_name", "price_raw", "rating_raw"];

const scriptDirectory = path.dirname(fileURLToPath(import.meta.url));
const projectRoot = path.resolve(scriptDirectory, "..");
const rawRoot = path.join(projectRoot, "Data", "csv", "Raw_data");
const outputDirectory = path.join(
  projectRoot,
  "Data",
  "csv",
  "Preprocessed_data",
  "merged",
);
const outputPath = path.join(outputDirectory, "merged.csv");
const reportPath = path.join(outputDirectory, "merge_validation.json");

function toPosixPath(value) {
  return value.split(path.sep).join("/");
}

function discoverCsvFiles(directory) {
  if (!fs.existsSync(directory)) {
    throw new Error(`Raw-data directory does not exist: ${directory}`);
  }

  const files = [];

  function visit(currentDirectory) {
    const entries = fs
      .readdirSync(currentDirectory, { withFileTypes: true })
      .sort((left, right) => left.name.localeCompare(right.name, "en"));

    for (const entry of entries) {
      const entryPath = path.join(currentDirectory, entry.name);
      if (entry.isDirectory()) {
        visit(entryPath);
      } else if (entry.isFile() && entry.name.toLowerCase().endsWith(".csv")) {
        files.push(entryPath);
      }
    }
  }

  visit(directory);
  return files.sort((left, right) =>
    toPosixPath(path.relative(directory, left)).localeCompare(
      toPosixPath(path.relative(directory, right)),
      "en",
    ),
  );
}

function readUtf8(filePath, sourceFile) {
  const bytes = fs.readFileSync(filePath);
  const hasBom =
    bytes.length >= 3 &&
    bytes[0] === 0xef &&
    bytes[1] === 0xbb &&
    bytes[2] === 0xbf;

  try {
    return new TextDecoder("utf-8", { fatal: true }).decode(
      hasBom ? bytes.subarray(3) : bytes,
    );
  } catch (error) {
    throw new Error(`${sourceFile}: invalid UTF-8 input (${error.message})`);
  }
}

function parseCsv(text, sourceFile) {
  const records = [];
  let record = [];
  let field = "";
  let insideQuotedField = false;
  let justClosedQuote = false;
  let justEndedRecord = false;
  let physicalLineNumber = 1;

  function finishField() {
    record.push(field);
    field = "";
    justClosedQuote = false;
  }

  function finishRecord() {
    finishField();
    records.push(record);
    record = [];
    justEndedRecord = true;
  }

  for (let index = 0; index < text.length; index += 1) {
    const character = text[index];
    justEndedRecord = false;

    if (insideQuotedField) {
      if (character === '"') {
        if (text[index + 1] === '"') {
          field += '"';
          index += 1;
        } else {
          insideQuotedField = false;
          justClosedQuote = true;
        }
      } else {
        field += character;
        if (character === "\n") {
          physicalLineNumber += 1;
        }
      }
      continue;
    }

    if (justClosedQuote) {
      if (character === ",") {
        finishField();
      } else if (character === "\r" || character === "\n") {
        if (character === "\r" && text[index + 1] === "\n") {
          index += 1;
        }
        finishRecord();
        physicalLineNumber += 1;
      } else {
        throw new Error(
          `${sourceFile}: unexpected character after a closing quote at physical line ${physicalLineNumber}`,
        );
      }
      continue;
    }

    if (character === ",") {
      finishField();
    } else if (character === "\r" || character === "\n") {
      if (character === "\r" && text[index + 1] === "\n") {
        index += 1;
      }
      finishRecord();
      physicalLineNumber += 1;
    } else if (character === '"') {
      if (field !== "") {
        throw new Error(
          `${sourceFile}: quote inside an unquoted field at physical line ${physicalLineNumber}`,
        );
      }
      insideQuotedField = true;
    } else {
      field += character;
    }
  }

  if (insideQuotedField) {
    throw new Error(`${sourceFile}: unterminated quoted field at end of file`);
  }

  if (!justEndedRecord && (justClosedQuote || field !== "" || record.length > 0)) {
    finishRecord();
  }

  if (records.length === 0) {
    throw new Error(`${sourceFile}: file is empty`);
  }

  return records;
}

function pathMetadata(filePath) {
  const sourceFile = toPosixPath(path.relative(rawRoot, filePath));
  const parts = sourceFile.split("/");
  if (parts.length !== 4) {
    throw new Error(
      `${sourceFile}: expected path <brand>/<model>/<platform>/<file>.csv`,
    );
  }

  const [brandDirectory, modelDirectory, platformDirectory] = parts;
  const brand = BRAND_NAMES.get(brandDirectory);
  const model = MODEL_INFO.get(modelDirectory);
  const platform = PLATFORM_NAMES.get(platformDirectory);

  if (!brand) {
    throw new Error(`${sourceFile}: unexpected brand directory '${brandDirectory}'`);
  }
  if (!model) {
    throw new Error(`${sourceFile}: unexpected model directory '${modelDirectory}'`);
  }
  if (model.brand !== brandDirectory) {
    throw new Error(
      `${sourceFile}: model '${modelDirectory}' is not mapped to brand '${brandDirectory}'`,
    );
  }
  if (!platform) {
    throw new Error(
      `${sourceFile}: unexpected platform directory '${platformDirectory}'`,
    );
  }

  return {
    brand,
    brandDirectory,
    model: model.name,
    modelDirectory,
    platform,
    platformDirectory,
    sourceFile,
  };
}

function buildColumnMapping(header, sourceFile) {
  const normalizedHeader = header.map((name) => name.trim());
  const headerIndexes = new Map();

  normalizedHeader.forEach((name, index) => {
    if (name === "") {
      throw new Error(`${sourceFile}: empty source header at column ${index + 1}`);
    }
    if (headerIndexes.has(name)) {
      throw new Error(
        `${sourceFile}: duplicate source header '${name}' after trimming surrounding whitespace`,
      );
    }
    headerIndexes.set(name, index);
  });

  const canonicalIndexes = new Map();
  const usedSourceIndexes = new Set();

  for (const [canonicalName, aliases] of SOURCE_ALIASES) {
    const matches = aliases
      .filter((alias) => headerIndexes.has(alias))
      .map((alias) => ({ alias, index: headerIndexes.get(alias) }));

    if (matches.length > 1) {
      throw new Error(
        `${sourceFile}: multiple headers map to '${canonicalName}': ${matches
          .map(({ alias }) => `'${alias}'`)
          .join(", ")}`,
      );
    }

    if (matches.length === 1) {
      canonicalIndexes.set(canonicalName, matches[0].index);
      usedSourceIndexes.add(matches[0].index);
    }
  }

  const missingRequiredFields = REQUIRED_SOURCE_FIELDS.filter(
    (name) => !canonicalIndexes.has(name),
  );
  if (missingRequiredFields.length > 0) {
    throw new Error(
      `${sourceFile}: source schema is missing required mapped field(s): ${missingRequiredFields.join(", ")}`,
    );
  }

  return {
    canonicalIndexes,
    ignoredHeaders: header.filter((_, index) => !usedSourceIndexes.has(index)),
    normalizedHeader,
  };
}

function csvCell(value) {
  if (/[",\r\n]/u.test(value)) {
    return `"${value.replaceAll('"', '""')}"`;
  }
  return value;
}

function csvRecord(values) {
  return values.map(csvCell).join(",");
}

function incrementBreakdown(breakdown, metadata) {
  const key = JSON.stringify([
    metadata.brand,
    metadata.model,
    metadata.platform,
  ]);
  const current = breakdown.get(key) ?? {
    brand: metadata.brand,
    model: metadata.model,
    platform: metadata.platform,
    row_count: 0,
  };
  current.row_count += 1;
  breakdown.set(key, current);
}

function main() {
  const sourcePaths = discoverCsvFiles(rawRoot);
  if (sourcePaths.length !== EXPECTED_SOURCE_FILE_COUNT) {
    throw new Error(
      `expected ${EXPECTED_SOURCE_FILE_COUNT} raw CSV files, discovered ${sourcePaths.length}`,
    );
  }

  const sourceReadCounts = new Map();
  const sources = [];
  const mergedRows = [];
  const breakdown = new Map();
  const encounteredModels = new Set();
  const encounteredPlatforms = new Set();

  for (const sourcePath of sourcePaths) {
    const metadata = pathMetadata(sourcePath);
    encounteredModels.add(metadata.modelDirectory);
    encounteredPlatforms.add(metadata.platformDirectory);

    const readCount = (sourceReadCounts.get(metadata.sourceFile) ?? 0) + 1;
    sourceReadCounts.set(metadata.sourceFile, readCount);
    if (readCount !== 1) {
      throw new Error(`${metadata.sourceFile}: source was read more than once`);
    }

    const records = parseCsv(
      readUtf8(sourcePath, metadata.sourceFile),
      metadata.sourceFile,
    );
    const header = records[0];
    const mapping = buildColumnMapping(header, metadata.sourceFile);

    for (let recordIndex = 1; recordIndex < records.length; recordIndex += 1) {
      const sourceRow = records[recordIndex];
      const sourceRowNumber = recordIndex;

      if (sourceRow.length !== header.length) {
        throw new Error(
          `${metadata.sourceFile}: data row ${sourceRowNumber} has ${sourceRow.length} fields; header has ${header.length}`,
        );
      }

      const sourceValue = (canonicalName) => {
        const sourceIndex = mapping.canonicalIndexes.get(canonicalName);
        return sourceIndex === undefined ? "" : sourceRow[sourceIndex];
      };

      const mergedRow = [
        metadata.brand,
        metadata.model,
        metadata.platform,
        metadata.sourceFile,
        String(sourceRowNumber),
        sourceValue("web_scraper_order"),
        sourceValue("web_scraper_start_url"),
        sourceValue("pagination"),
        sourceValue("product_name"),
        sourceValue("price_raw"),
        sourceValue("rating_raw"),
        sourceValue("historical_sold_raw"),
        sourceValue("item_page_title"),
        sourceValue("item_page_link"),
      ];

      if (mergedRow.slice(0, 5).some((value) => value === "")) {
        throw new Error(
          `${metadata.sourceFile}: data row ${sourceRowNumber} has empty provenance metadata`,
        );
      }

      mergedRows.push(mergedRow);
      incrementBreakdown(breakdown, metadata);
    }

    sources.push({
      source_file: metadata.sourceFile,
      read_count: readCount,
      data_row_count: records.length - 1,
      original_headers: header,
      normalized_headers: mapping.normalizedHeader,
      ignored_headers: mapping.ignoredHeaders,
    });
  }

  const expectedModels = [...MODEL_INFO.keys()].sort();
  const actualModels = [...encounteredModels].sort();
  if (JSON.stringify(actualModels) !== JSON.stringify(expectedModels)) {
    throw new Error(
      `model directories do not match the expected mappings; expected ${expectedModels.join(", ")}; encountered ${actualModels.join(", ")}`,
    );
  }

  const expectedPlatforms = [...PLATFORM_NAMES.keys()].sort();
  const actualPlatforms = [...encounteredPlatforms].sort();
  if (JSON.stringify(actualPlatforms) !== JSON.stringify(expectedPlatforms)) {
    throw new Error(
      `platform directories do not match the expected mappings; expected ${expectedPlatforms.join(", ")}; encountered ${actualPlatforms.join(", ")}`,
    );
  }

  const totalSourceRows = sources.reduce(
    (total, source) => total + source.data_row_count,
    0,
  );
  if (mergedRows.length !== totalSourceRows) {
    throw new Error(
      `merged row count ${mergedRows.length} does not equal source row count ${totalSourceRows}`,
    );
  }
  if (sourceReadCounts.size !== sourcePaths.length) {
    throw new Error(
      `read ${sourceReadCounts.size} unique sources but discovered ${sourcePaths.length}`,
    );
  }

  const rowCountsByBrandModelPlatform = [...breakdown.values()].sort(
    (left, right) =>
      left.brand.localeCompare(right.brand, "en") ||
      left.model.localeCompare(right.model, "en") ||
      left.platform.localeCompare(right.platform, "en"),
  );

  const outputText = [CANONICAL_COLUMNS, ...mergedRows]
    .map(csvRecord)
    .join("\r\n")
    .concat("\r\n");

  const outputRecords = parseCsv(outputText, "generated merged.csv");
  if (outputRecords.length !== mergedRows.length + 1) {
    throw new Error(
      `generated output contains ${outputRecords.length - 1} data rows; expected ${mergedRows.length}`,
    );
  }
  for (let index = 0; index < outputRecords.length; index += 1) {
    const expectedRecord = index === 0 ? CANONICAL_COLUMNS : mergedRows[index - 1];
    if (JSON.stringify(outputRecords[index]) !== JSON.stringify(expectedRecord)) {
      throw new Error(
        `generated output failed the CSV round-trip check at record ${index + 1}`,
      );
    }
  }

  const report = {
    source_csv_files_discovered: sourcePaths.length,
    source_csv_files_read: sourceReadCounts.size,
    total_source_rows: totalSourceRows,
    merged_rows: mergedRows.length,
    canonical_columns: CANONICAL_COLUMNS,
    encountered_model_directories: actualModels,
    encountered_platform_directories: actualPlatforms,
    row_counts_by_brand_model_platform: rowCountsByBrandModelPlatform,
    parse_failures: [],
    unexpected_schemas: [],
    path_exceptions: [],
    validations: {
      exactly_73_source_csv_files: sourcePaths.length === EXPECTED_SOURCE_FILE_COUNT,
      every_source_read_exactly_once: [...sourceReadCounts.values()].every(
        (count) => count === 1,
      ),
      merged_rows_equal_source_rows: mergedRows.length === totalSourceRows,
      no_source_rows_intentionally_dropped: true,
      provenance_fields_non_empty: true,
      output_csv_round_trip_preserves_values: true,
      exactly_expected_model_directories:
        JSON.stringify(actualModels) === JSON.stringify(expectedModels),
      exactly_expected_platform_directories:
        JSON.stringify(actualPlatforms) === JSON.stringify(expectedPlatforms),
    },
    sources,
  };

  fs.mkdirSync(outputDirectory, { recursive: true });
  fs.writeFileSync(outputPath, outputText, "utf8");
  fs.writeFileSync(reportPath, `${JSON.stringify(report, null, 2)}\n`, "utf8");

  console.log(`Source CSV files: ${sourcePaths.length}`);
  console.log(`Total source rows: ${totalSourceRows}`);
  console.log(`Merged rows: ${mergedRows.length}`);
  console.log(`Merged output: ${path.relative(projectRoot, outputPath)}`);
  console.log(`Validation report: ${path.relative(projectRoot, reportPath)}`);
  console.log("\nRow counts by brand / model / platform:");
  for (const item of rowCountsByBrandModelPlatform) {
    console.log(
      `${item.brand} | ${item.model} | ${item.platform} | ${item.row_count}`,
    );
  }
  console.log("\nPer-source data-row counts:");
  for (const source of sources) {
    console.log(`${source.data_row_count}\t${source.source_file}`);
  }
}

try {
  main();
} catch (error) {
  console.error(`Merge failed: ${error.message}`);
  process.exitCode = 1;
}
