from pathlib import Path
import pdfplumber

try:
    import fitz  # pymupdf 的导入名
    HAS_PYMUPDF = True
except ImportError:
    HAS_PYMUPDF = False

try:
    from rapidocr_onnxruntime import RapidOCR
    HAS_RAPIDOCR = True
except ImportError:
    HAS_RAPIDOCR = False


def extract_text_from_pdf_pymupdf(pdf_path, max_pages=40):
    """使用 pymupdf 提取文本（处理复杂 PDF 更强）"""
    text = ""
    try:
        doc = fitz.open(pdf_path)
        for i, page in enumerate(doc):
            if i >= max_pages:
                break
            page_text = page.get_text()
            if page_text:
                text += page_text + "\n"
        doc.close()
    except Exception as e:
        print(f"pymupdf 解析失败: {e}")
    return text


def extract_text_from_pdf(pdf_path, max_pages=40):
    """优先使用 pymupdf，失败则退回 pdfplumber"""
    if HAS_PYMUPDF:
        text = extract_text_from_pdf_pymupdf(pdf_path, max_pages)
        if len(text) > 100:
            return text

    print("pymupdf 提取为空，改用 pdfplumber 尝试...")
    full_text = ""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages[:max_pages]:
                t = page.extract_text()
                if t:
                    full_text += t + "\n"
    except Exception as e:
        print(f"pdfplumber 解析失败: {e}")
    return full_text


def extract_text_from_scanned_pdf(pdf_path, max_pages=15):
    """
    用 RapidOCR 识别图片型 PDF。
    只处理前 max_pages 页，避免耗时过久。
    """
    if not HAS_RAPIDOCR:
        print("未安装 rapidocr-onnxruntime，无法 OCR")
        return ""

    if not HAS_PYMUPDF:
        print("未安装 pymupdf，无法将 PDF 转为图片")
        return ""

    print(f"启动 OCR，正在识别前 {max_pages} 页，请耐心等待...")
    ocr_engine = RapidOCR()
    full_text = ""

    try:
        doc = fitz.open(pdf_path)
        for i, page in enumerate(doc):
            if i >= max_pages:
                break

            # 把 PDF 页面渲染成图片（200 DPI 兼顾清晰度和速度）
            pix = page.get_pixmap(dpi=200)
            img_bytes = pix.tobytes("png")

            # OCR 识别
            result, _ = ocr_engine(img_bytes)
            if result:
                for line in result:
                    # line 结构：[坐标框, 文本, 置信度]
                    text = line[1]
                    full_text += text + "\n"
            full_text += "\n"  # 页面之间加空行
            print(f"  已识别第 {i + 1} 页，累计 {len(full_text)} 字符")

        doc.close()
        print(f"OCR 完成，共识别 {len(full_text)} 个字符")
    except Exception as e:
        print(f"OCR 处理失败: {e}")

    return full_text


def extract_text_from_file(file_path: str, max_pages=40) -> str:
    """根据文件后缀名自动选择解析方式，返回纯文本"""
    suffix = Path(file_path).suffix.lower()

    if suffix == ".pdf":
        # 第一步：尝试普通文本提取
        text = extract_text_from_pdf(file_path, max_pages)

        # 第二步：如果提取出的文字太少，判定为图片型 PDF，自动启动 OCR
        if len(text.strip()) < 100 and HAS_RAPIDOCR:
            print("检测到图片型 PDF，正在启动 OCR 识别...")
            ocr_text = extract_text_from_scanned_pdf(file_path, max_pages=15)
            if len(ocr_text.strip()) > len(text.strip()):
                return ocr_text

        return text

    elif suffix == ".docx":
        import docx2txt
        return docx2txt.process(file_path)

    elif suffix in [".txt", ".md"]:
        return Path(file_path).read_text(encoding="utf-8", errors="ignore")

    elif suffix == ".csv":
        import pandas as pd
        return pd.read_csv(file_path).to_string()

    elif suffix in [".xlsx", ".xls"]:
        import pandas as pd
        xls = pd.ExcelFile(file_path)
        text = ""
        for sheet in xls.sheet_names:
            text += f"\n--- Sheet: {sheet} ---\n" + pd.read_excel(file_path, sheet_name=sheet).to_string()
        return text

    elif suffix in [".html", ".htm"]:
        from bs4 import BeautifulSoup
        return BeautifulSoup(Path(file_path).read_text(encoding="utf-8", errors="ignore"), "html.parser").get_text(separator="\n")

    return ""


if __name__ == "__main__":
    import os
    # 改成你要测试的 PDF 路径
    pdf_path = "data/tencent.pdf"
    print(f"1. 文件是否存在: {os.path.exists(pdf_path)}")
    if os.path.exists(pdf_path):
        text = extract_text_from_file(pdf_path, max_pages=5)
        print(f"\n2. 解析前5页总字符数: {len(text)}")
        print("\n=== 前 1500 字符 ===")
        print(text[:1500])
