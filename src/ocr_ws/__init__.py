from __future__ import annotations

import re
from pathlib import Path

from rapidocr_onnxruntime import RapidOCR


TRANSPORTATION_CELL_PATTERN = re.compile(
    r"(?<![A-Za-z0-9])(?:QZ|[QWTZ])[A-Z0-9]*\d+(?:[.](?:R|B|Y))?(?:\+(?:QZ|[QWTZ])[A-Z0-9]*\d+(?:[.](?:R|B|Y))?)*(?![A-Za-z0-9])"
)
PROJECT_ID_PATTERN = re.compile(r"(?<!\d)(\d{6})(?!\d)")
BAY_ID_PATTERN = re.compile(r"(?<![A-Za-z0-9])((?!(?:QZ|Q|W|T|Z))[A-Z][A-Z0-9]*\d+)(?![A-Za-z0-9])")


def extract_cell_symbol(text: str) -> str | None:
    """Extract the first transportation cell string like W83, Q2+Q51+W90, W1+Q9+Q8, QZ3+W8, or W7.R+W7.B+W8.Y."""
    if not text:
        return None

    normalized = text.replace("＋", "+")
    match = TRANSPORTATION_CELL_PATTERN.search(normalized)
    return match.group(0) if match else None


def extract_project_id(text: str) -> str | None:
    match = PROJECT_ID_PATTERN.search(text)
    return match.group(1) if match else None


def extract_bay_id(text: str) -> str | None:
    match = BAY_ID_PATTERN.search(text)
    return match.group(1) if match else None


def extract_fields(text: str) -> dict[str, str | None]:
    normalized = text.replace("＋", "+")

    return {
        "project_id": extract_project_id(normalized),
        "bay_id": extract_bay_id(normalized),
        "transportation_cell_symbol": extract_cell_symbol(normalized),
    }


def main() -> None:
    project_root = Path(__file__).resolve().parents[2]
    assets_dir = project_root / "assets"

    if not assets_dir.exists():
        print(f"未找到 assets 目录: {assets_dir}")
        return

    ocr = RapidOCR()
    image_files = sorted(
        p for p in assets_dir.iterdir() if p.is_file() and p.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}
    )

    if not image_files:
        print(f"在 {assets_dir} 下没有发现图片文件")
        return

    fallback_index = 0
    last_good_project_id: str | None = None
    last_good_bay_id: str | None = None
    last_good_cell_symbol: str | None = None

    for img_path in image_files:
        result, elapse = ocr(str(img_path))

        if result is None:
            if last_good_project_id is None or last_good_bay_id is None or last_good_cell_symbol is None:
                print(f"{img_path.name}: 未识别到内容，且还没有上一条成功记录，跳过重命名")
                continue

            fallback_index += 1
            new_name = f"{last_good_project_id}_{last_good_bay_id}_{last_good_cell_symbol}_{fallback_index}"
            target_path = img_path.with_name(new_name + img_path.suffix)
            print(f"{img_path.name}: 未识别到内容，按上一条成功记录重命名为 {target_path.name}")
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
                new_name = f"{project_id}_{bay_id}_{transportation_cell_symbol}"
                target_path = img_path.with_name(new_name + img_path.suffix)
                print(f"{img_path.name}: 识别成功，准备重命名为 {target_path.name}")
            elif last_good_project_id is not None and last_good_bay_id is not None and last_good_cell_symbol is not None:
                fallback_index += 1
                new_name = f"{last_good_project_id}_{last_good_bay_id}_{last_good_cell_symbol}_{fallback_index}"
                target_path = img_path.with_name(new_name + img_path.suffix)
                print(f"{img_path.name}: 识别字段不完整，按上一条成功记录重命名为 {target_path.name}")
            else:
                print(f"{img_path.name}: 识别字段不完整，且还没有上一条成功记录，跳过重命名")
                continue

        if img_path != target_path:
            try:
                img_path.rename(target_path)
                print(f"重命名: {img_path.name} -> {target_path.name}")
            except OSError as exc:
                print(f"重命名失败: {img_path.name} -> {target_path.name}: {exc}")

        if result is not None:
            elapsed_value = sum(elapse) if elapse is not None else 0.0
            print(f"{img_path.name} 识别耗时: {elapsed_value:.3f}s")
            print(f"OCR 文本: {full_text[:200]}...")
            print(f"提取字段: {fields}")
        print("-" * 60)


if __name__ == "__main__":
    main()