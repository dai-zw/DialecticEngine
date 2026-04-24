"""
合并两个道德经docx文件并转换为Markdown格式
道经1-37章 + 德经38-81章 → 完整的道德经.md
"""

import docx
from pathlib import Path

def read_docx(filepath: str) -> str:
    """读取docx文件内容"""
    doc = docx.Document(filepath)
    full_text = []
    for para in doc.paragraphs:
        full_text.append(para.text)
    return '\n'.join(full_text)

def merge_and_convert():
    """合并两个docx并生成完整Markdown"""
    # 文件路径
    daojing_docx = Path('knowledge/《道德经》中的《道经》1-37章 原文及译文.docx')
    dejing_docx = Path('knowledge/《道德经》中的《德经》38-81章 原文及译文.docx')
    output_md = Path('knowledge/daojia/classics/道德经.md')

    # 确保输出目录存在
    output_md.parent.mkdir(parents=True, exist_ok=True)

    # 读取两个docx
    print(f"Reading: {daojing_docx}")
    daojing_text = read_docx(str(daojing_docx))

    print(f"Reading: {dejing_docx}")
    dejing_text = read_docx(str(dejing_docx))

    # 构建Markdown内容
    markdown_lines = []

    # YAML front matter
    markdown_lines.append('---')
    markdown_lines.append('title: "道德经"')
    markdown_lines.append('author: "老子（李耳）"')
    markdown_lines.append('dynasty: "先秦"')
    markdown_lines.append('school: "daojia"')
    markdown_lines.append('original_text: "马王堆帛书本/王弼注本"')
    markdown_lines.append('translator: "（现代汉语翻译）"')
    markdown_lines.append('metadata:')
    markdown_lines.append('  source: "中国哲学书电子化计划 ctext.org + 维基文库"')
    markdown_lines.append('  url: "https://ctext.org/tao-te-ching"')
    markdown_lines.append('  downloaded: "2026-04-16"')
    markdown_lines.append('  format: "Markdown"')
    markdown_lines.append('  license: "Public Domain"')
    markdown_lines.append('  chapters: "81章（道经1-37 + 德经38-81）"')
    markdown_lines.append('---')
    markdown_lines.append('')

    # 主标题
    markdown_lines.append('# 道德经')
    markdown_lines.append('')
    markdown_lines.append('**作者**: 老子（李耳）｜**朝代**: 先秦｜**流派**: 道家')
    markdown_lines.append('')
    markdown_lines.append('---')
    markdown_lines.append('')

    # 道经部分
    markdown_lines.append('## 道经（第1-37章）')
    markdown_lines.append('')
    markdown_lines.append(daojing_text)
    markdown_lines.append('')
    markdown_lines.append('---')
    markdown_lines.append('')

    # 德经部分
    markdown_lines.append('## 德经（第38-81章）')
    markdown_lines.append('')
    markdown_lines.append(dejing_text)
    markdown_lines.append('')
    markdown_lines.append('---')
    markdown_lines.append('')

    # 附录：核心思想摘要
    markdown_lines.append('## 附录：核心思想总结')
    markdown_lines.append('')
    markdown_lines.append('### 道经核心（1-37章）')
    markdown_lines.append('')
    markdown_lines.append('- **本源论**: 道先天地生，无形无名，化生万物')
    markdown_lines.append('- **规律论**: 反者道之动，弱者道之用，循环往复')
    markdown_lines.append('- **修身论**: 致虚守静，少私寡欲，自知者明')
    markdown_lines.append('- **治国论**: 无为而治，不尚贤，不贵难得之货')
    markdown_lines.append('- **处世论**: 不争自胜，柔弱谦下，功成身退')
    markdown_lines.append('')
    markdown_lines.append('### 德经核心（38-81章）')
    markdown_lines.append('')
    markdown_lines.append('- **德之用**: 上德不德，是以有德；下德不失德，是以无德')
    markdown_lines.append('- **柔之道**: 柔弱胜刚强，天下莫柔弱于水')
    markdown_lines.append('- **天之道**: 损有余而补不足，利而不害')
    markdown_lines.append('- **三宝**: 慈、俭、不敢为天下先')
    markdown_lines.append('- **治国**: 治大国若烹小鲜，以无事取天下')
    markdown_lines.append('')
    markdown_lines.append('### 整体精髓')
    markdown_lines.append('')
    markdown_lines.append('> **道常无为而无不为**')
    markdown_lines.append('>')
    markdown_lines.append('> 人法地，地法天，天法道，道法自然。')
    markdown_lines.append('>')
    markdown_lines.append('> 上善若水，水善利万物而不争。')
    markdown_lines.append('')

    # 保存文件
    full_markdown = '\n'.join(markdown_lines)
    with open(output_md, 'w', encoding='utf-8') as f:
        f.write(full_markdown)

    print(f"\n✅ 合并完成！")
    print(f"   输出文件: {output_md}")
    print(f"   总字符数: {len(full_markdown)}")
    print(f"   行数: {full_markdown.count(chr(10)) + 1}")

    # 统计信息
    print(f"\n📊 章节统计:")
    print(f"   道经（1-37章）: {len(daojing_text)} 字符")
    print(f"   德经（38-81章）: {len(dejing_text)} 字符")
    print(f"   总计: {len(daojing_text) + len(dejing_text)} 字符")

if __name__ == '__main__':
    merge_and_convert()
