import pdfplumber

def extract_text_from_pdf(pdf_path, max_pages=15):
    """提取PDF文本，默认读前15页"""
    full_text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages[:max_pages]:
            text = page.extract_text()
            if text:
                full_text += text + "\n"
    return full_text

if __name__ == "__main__":
    pdf_path = "data/annual_report.pdf"
    text = extract_text_from_pdf(pdf_path, max_pages=15)
    
    target_keyword = "主要会计数据"
    
    if target_keyword in text:
        print(f"\n✅ 成功找到 '{target_keyword}'！以下是核心财务数据：\n")
        start_idx = text.find(target_keyword)
        # 从关键词开始打印3000个字符
        print(text[start_idx : start_idx + 3000])
    else:
        print(f"\n❌ 未找到关键词，打印前3000字符：\n")
        print(text[:3000])