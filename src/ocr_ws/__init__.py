from __future__ import annotations

import re
from pathlib import Path

from PIL import Image
from pillow_heif import register_heif_opener
from rapidocr_onnxruntime import RapidOCR

register_heif_opener()


# TRANSPORTATION_CELL_PATTERN = re.compile(
#     r"(?<![A-Za-z0-9])(?:QZ|[QWTZ])[A-Z]*\d{1,2}(?:[.](?:R|B|Y)|(?:R|B|Y))?(?:\+(?:QZ|[QWTZ])[A-Z]*\d{1,2}(?:[.](?:R|B|Y)|(?:R|B|Y))?)*(?![A-Za-z0-9])"
# )
TRANSPORTATION_CELL_PATTERN = re.compile(
    r"(?<![A-Za-z0-9])(?:QZ|[QWTZ])[A-Z]*\d{1,2}(?:\.\s*(?:R|B|Y|\d{1,2})|(?:R|B|Y))?(?:\s*\+\s*(?:QZ|[QWTZ])[A-Z]*\d{1,2}(?:\.\s*(?:R|B|Y|\d{1,2})|(?:R|B|Y))?)*(?![A-Za-z0-9])"
)
PROJECT_ID_PATTERN = re.compile(r"(?<![A-Za-z0-9-])(\d{6})(?![A-Za-z0-9-])")
BAY_ID_PATTERN = re.compile(
    r"(?<![A-Za-z0-9])([A-M]+\d{1,2}(?:[.\-_]\d)?(?:-[A-M]+\d+)?)(?![A-Za-z0-9])"
)


def normalize_ocr_text(text: str) -> str:
    return text.replace("＋", "+").replace("O", "0").replace("o", "0")


def extract_cell_symbol(text: str) -> str | None:
    """Extract the first transportation cell string like W83, Q2+Q51+W90, W1+Q9+Q8, QZ3+W8, or W7.R+W7.B+W8.Y."""
    if not text:
        return None

    normalized = normalize_ocr_text(text)
    match = TRANSPORTATION_CELL_PATTERN.search(normalized)
    return match.group(0) if match else None


def extract_project_id(text: str) -> str | None:
    match = PROJECT_ID_PATTERN.search(normalize_ocr_text(text))
    return match.group(1) if match else None


def extract_bay_id(text: str) -> str | None:
    match = BAY_ID_PATTERN.search(normalize_ocr_text(text))
    return match.group(1) if match else None


def extract_fields(text: str) -> dict[str, str | None]:
    normalized = normalize_ocr_text(text)

    return {
        "project_id": extract_project_id(normalized),
        "bay_id": extract_bay_id(normalized),
        "transportation_cell_symbol": extract_cell_symbol(normalized),
    }


def convert_heic_to_png(img_path: Path) -> Path:
    png_path = img_path.with_name(f"{img_path.stem}__ocr.png")
    with Image.open(img_path) as image:
        image.convert("RGB").save(png_path, format="PNG")
    return png_path


def main() -> None:
    project_root = Path(__file__).resolve().parents[2]
    assets_dir = project_root / "assets"

    if not assets_dir.exists():
        print(f"未找到 assets 目录: {assets_dir}")
        return

    ocr = RapidOCR()
    image_files = sorted(
        p
        for p in assets_dir.iterdir()
        if p.is_file()
        and p.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".heic"}
        and not p.name.endswith("__ocr.png")
    )

    if not image_files:
        print(f"在 {assets_dir} 下没有发现图片文件")
        return

    fallback_index = 0
    last_good_project_id: str | None = None
    last_good_bay_id: str | None = None
    last_good_cell_symbol: str | None = None

    for source_path in image_files:
        ocr_path = source_path
        if source_path.suffix.lower() == ".heic":
            try:
                ocr_path = convert_heic_to_png(source_path)
                print(f"转换: {source_path.name} -> {ocr_path.name}")
            except (OSError, ValueError) as exc:
                print(f"转换失败: {source_path.name}: {exc}")
                continue

        result, elapse = ocr(str(ocr_path))

        if result is None:
            if last_good_project_id is None or last_good_bay_id is None or last_good_cell_symbol is None:
                print(f"{source_path.name}: 未识别到内容，且还没有上一条成功记录，跳过归类")
                continue

            fallback_index += 1
            project_id = last_good_project_id
            bay_id = last_good_bay_id
            transportation_cell_symbol = last_good_cell_symbol
            print(f"{source_path.name}: 未识别到内容，按上一条成功记录归类到 {project_id}/{bay_id}/{transportation_cell_symbol}")
        else:
            full_text = " ".join(line[1] for line in result if len(line) > 1)
            fields = extract_fields(full_text)

            project_id = fields.get("project_id")
            bay_id = fields.get("bay_id")
            transportation_cell_symbol = fields.get("transportation_cell_symbol")

            if project_id and bay_id and transportation_cell_symbol:
                fallback_index = 0
                last_good_project_id = project_id
                last_good_bay_id = bay_id
                last_good_cell_symbol = transportation_cell_symbol
                print(f"{source_path.name}: 识别成功，准备归类到 {project_id}/{bay_id}/{transportation_cell_symbol}")
            elif last_good_project_id is not None and last_good_bay_id is not None and last_good_cell_symbol is not None:
                fallback_index += 1
                project_id = last_good_project_id
                bay_id = last_good_bay_id
                transportation_cell_symbol = last_good_cell_symbol
                print(f"{source_path.name}: 识别字段不完整，按上一条成功记录归类到 {project_id}/{bay_id}/{transportation_cell_symbol}")
            else:
                print(f"{source_path.name}: 识别字段不完整，且还没有上一条成功记录，跳过归类")
                continue

        target_dir = assets_dir / project_id / bay_id / transportation_cell_symbol
        target_dir.mkdir(parents=True, exist_ok=True)

        target_path = source_path
        organized_path = target_dir / target_path.name
        if target_path != organized_path:
            duplicate_index = 0
            while organized_path.exists():
                duplicate_index += 1
                organized_path = target_dir / (
                    f"{target_path.stem}({duplicate_index}){target_path.suffix}"
                )

            try:
                target_path.rename(organized_path)
                print(f"归类: {target_path.name} -> {organized_path}")
            except OSError as exc:
                print(f"归类失败: {target_path.name} -> {organized_path}: {exc}")

        if ocr_path != source_path and ocr_path.exists():
            try:
                ocr_path.unlink()
                print(f"删除临时 OCR 文件: {ocr_path.name}")
            except OSError as exc:
                print(f"删除临时 OCR 文件失败: {ocr_path.name}: {exc}")

        if result is not None:
            elapsed_value = sum(elapse) if elapse is not None else 0.0
            print(f"{source_path.name} 识别耗时: {elapsed_value:.3f}s")
            print(f"OCR 文本: {full_text[:200]}...")
            print(f"提取字段: {fields}")
        print("-" * 60)


if __name__ == "__main__":
    main()