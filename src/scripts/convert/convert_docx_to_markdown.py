"""
将docx文件转换为Markdown格式的脚本
为RAG检索准备文档
"""

import os
import sys
from docx import Document
from pathlib import Path

# 设置控制台编码
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

def convert_docx_to_markdown(docx_path, output_path):
    """
    将docx文件转换为Markdown格式

    Args:
        docx_path: docx文件路径
        output_path: 输出的markdown文件路径
    """
    doc = Document(docx_path)
    markdown_content = []

    # 获取文件名作为标题
    filename = os.path.basename(docx_path)
    title = filename.replace('.docx', '').replace('《', '').replace('》', '')
    markdown_content.append(f'# {title}\n')
    markdown_content.append(f'**来源文件**: {filename}\n')
    markdown_content.append('---\n')

    # 处理段落
    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue

        # 检测标题样式
        if para.style.name.startswith('Heading'):
            level = int(para.style.name[-1])
            markdown_content.append(f'{"#" * level} {text}\n')
        elif para.style.name == 'Title':
            markdown_content.append(f'# {text}\n')
        elif para.style.name == 'Subtitle':
            markdown_content.append(f'## {text}\n')
        elif para.style.name.startswith('List'):
            markdown_content.append(f'- {text}\n')
        else:
            # 普通段落
            markdown_content.append(f'{text}\n\n')

    # 保存文件
    with open(output_path, 'w', encoding='utf-8') as f:
        f.writelines(markdown_content)

    print(f'[OK] Converted: {docx_path} -> {output_path}')

def process_knowledge_base(knowledge_dir='knowledge'):
    """
    处理knowledge目录中的所有docx文件
    """
    knowledge_path = Path(knowledge_dir)
    if not knowledge_path.exists():
        print(f'❌ 目录不存在: {knowledge_dir}')
        return

    # 创建输出目录
    output_dir = knowledge_path / 'converted_markdown'
    output_dir.mkdir(exist_ok=True)

    # 查找所有docx文件
    docx_files = list(knowledge_path.glob('*.docx'))
    print(f'[INFO] Found {len(docx_files)} docx files')

    for docx_file in docx_files:
        output_file = output_dir / f'{docx_file.stem}.md'
        try:
            convert_docx_to_markdown(str(docx_file), str(output_file))
        except Exception as e:
            print(f'转换失败 {docx_file}: {e}')

if __name__ == '__main__':
    process_knowledge_base()
