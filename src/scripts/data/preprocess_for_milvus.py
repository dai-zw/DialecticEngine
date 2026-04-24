"""
知识库数据预处理脚本
将Markdown文档转换为Milvus可导入的chunks
"""

import re
import json
import yaml
from pathlib import Path
from typing import List, Dict
import frontmatter

class ClassicPreprocessor:
    def __init__(self,
                 chunk_size: int = 500,
                 chunk_overlap: int = 50,
                 school_mapping: Dict = None):
        """
        Args:
            chunk_size: 每个chunk的最大字符数
            chunk_overlap: chunk之间的重叠字符数
            school_mapping: 流派映射表
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.school_mapping = school_mapping or {}

    def parse_front_matter(self, file_path: Path) -> Dict:
        """解析Markdown文件的YAML front matter"""
        post = frontmatter.load(file_path)
        metadata = post.metadata

        # 自动推断流派和经典名
        relative = file_path.relative_to(Path('knowledge'))
        parts = relative.parts

        if len(parts) >= 2:
            metadata.setdefault('school', parts[0])
            metadata.setdefault('classic', file_path.stem)

        return metadata

    def split_by_chapters(self, content: str) -> List[str]:
        """
        按章节拆分（适用于经典著作）
        检测"第X章"、"卷一"等模式
        """
        # 常见章节标记模式
        patterns = [
            r'^#{1,3} 第[一二三四五六七八九十百千零]+章',
            r'^#{1,3} 第[一二三四五六七八九十百千零]+卷',
            r'^#{1,3} [一二三四五六七八九十]+[.、]',
            r'^#{1,3} [第]?[一二三四五六七八九十]+[章篇节]',
            r'^#{1,3} [上中下初终]',
        ]

        chapters = []
        current_chapter = []
        in_chapter = False

        for line in content.split('\n'):
            # 检测章节标题
            is_chapter_header = any(re.match(p, line) for p in patterns)

            if is_chapter_header and current_chapter:
                chapters.append('\n'.join(current_chapter))
                current_chapter = [line]
            else:
                current_chapter.append(line)

        if current_chapter:
            chapters.append('\n'.join(current_chapter))

        return chapters if chapters else [content]

    def split_into_chunks(self, text: str, metadata: Dict) -> List[Dict]:
        """
        将文本分割为固定大小的chunks

        Returns:
            List of {text, metadata}
        """
        text = text.strip()
        if len(text) <= self.chunk_size:
            return [{
                'text': text,
                'metadata': metadata
            }]

        chunks = []
        start = 0

        while start < len(text):
            end = start + self.chunk_size

            # 尝试在句子/段落边界分割
            if end < len(text):
                # 寻找最近的句号、换行或空格
                for sep in ['。', '！', '？', '\n\n', '\n', ' ']:
                    pos = text.rfind(sep, start, end)
                    if pos > start + self.chunk_size // 2:
                        end = pos + len(sep)
                        break

            chunk_text = text[start:end].strip()
            if chunk_text:
                chunk_meta = metadata.copy()
                chunk_meta['chunk_id'] = len(chunks)
                chunk_meta['char_start'] = start
                chunk_meta['char_end'] = end

                chunks.append({
                    'text': chunk_text,
                    'metadata': chunk_meta
                })

            start = end - self.chunk_overlap
            if start >= len(text):
                break

        return chunks

    def process_file(self, file_path: Path) -> List[Dict]:
        """处理单个Markdown文件"""
        # 解析front matter
        metadata = self.parse_front_matter(file_path)

        # 读取正文
        post = frontmatter.load(file_path)
        content = post.content

        # 按章节拆分
        chapters = self.split_by_chapters(content)

        all_chunks = []
        for chapter_text in chapters:
            # 提取章节标题（如果有）
            chapter_title = ""
            lines = chapter_text.split('\n')
            if lines and lines[0].startswith('#'):
                chapter_title = lines[0].lstrip('#').strip()
                chapter_text = '\n'.join(lines[1:])

            chapter_meta = metadata.copy()
            if chapter_title:
                chapter_meta['chapter'] = chapter_title

            # 拆分为chunks
            chunks = self.split_into_chunks(chapter_text, chapter_meta)
            all_chunks.extend(chunks)

        return all_chunks

    def process_directory(self, dir_path: Path) -> List[Dict]:
        """处理整个目录"""
        all_chunks = []

        md_files = list(dir_path.rglob('*.md'))
        print(f'[INFO] Found {len(md_files)} markdown files in {dir_path}')

        for file_path in md_files:
            # 跳过converted_markdown和索引文件
            if 'converted_markdown' in str(file_path) or file_path.name in ['README.md', 'INDEX.md', 'chunks.jsonl', 'BOOK_MAPPING.md']:
                continue

            print(f'  Processing: {file_path.relative_to(dir_path)}')
            try:
                chunks = self.process_file(file_path)
                all_chunks.extend(chunks)
                print(f'    → {len(chunks)} chunks generated')
            except Exception as e:
                print(f'    [ERROR] {e}')

        return all_chunks

def main():
    knowledge_dir = Path('knowledge')

    preprocessor = ClassicPreprocessor(
        chunk_size=500,
        chunk_overlap=50
    )

    # 处理所有文件
    all_chunks = preprocessor.process_directory(knowledge_dir)

    print(f'\n✅ Total chunks generated: {len(all_chunks)}')

    # 保存为JSONL格式（每行一个JSON对象）
    output_file = knowledge_dir / 'chunks.jsonl'
    with open(output_file, 'w', encoding='utf-8') as f:
        for chunk in all_chunks:
            f.write(json.dumps(chunk, ensure_ascii=False) + '\n')

    print(f'✅ Saved to: {output_file}')

    # 统计信息
    schools = {}
    classics = {}
    for chunk in all_chunks:
        school = chunk['metadata'].get('school', 'unknown')
        classic = chunk['metadata'].get('classic', 'unknown')
        schools[school] = schools.get(school, 0) + 1
        classics[classic] = classics.get(classic, 0) + 1

    print('\n📊 Distribution by school:')
    for school, count in sorted(schools.items()):
        print(f'  {school}: {count} chunks')

    print('\n📚 Distribution by classic:')
    for classic, count in sorted(classics.items()):
        print(f'  {classic}: {count} chunks')

    print('\n🎯 Ready for Milvus import!')
    print('   Next step: python scripts/import_to_milvus.py')

if __name__ == '__main__':
    main()
