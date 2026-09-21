from pathlib import Path
import pdfplumber

def extract_text_from_pdf(pdf_path, max_pages=15):
    full_text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages[:max_pages]:
            text = page.extract_text()
            if text:
                full_text += text + "\n"
    return full_text

def extract_text_from_file(file_path: str, max_pages=15) -> str:
    """根据后缀名自动选择解析方式，返回纯文本"""
    suffix = Path(file_path).suffix.lower()
    
    if suffix == ".pdf":
        return extract_text_from_pdf(file_path, max_pages)
    
    elif suffix == ".docx":
        import docx2txt
        return docx2txt.process(file_path)
    
    elif suffix in [".txt", ".md"]:
        return Path(file_path).read_text(encoding="utf-8", errors="ignore")
    
    elif suffix == ".csv":
        import pandas as pd
        df = pd.read_csv(file_path)
        return df.to_string()
    
    elif suffix in [".xlsx", ".xls"]:
        import pandas as pd
        xls = pd.ExcelFile(file_path)
        text = ""
        for sheet in xls.sheet_names:
            df = pd.read_excel(file_path, sheet_name=sheet)
            text += f"\n--- Sheet: {sheet} ---\n" + df.to_string()
        return text
    
    elif suffix in [".html", ".htm"]:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(Path(file_path).read_text(encoding="utf-8", errors="ignore"), "html.parser")
        return soup.get_text(separator="\n")
    
    else:
        return ""
