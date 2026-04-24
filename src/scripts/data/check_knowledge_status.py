"""
知识库状态检查脚本
显示knowledge目录的结构、文件统计、待下载列表
"""

from pathlib import Path
from collections import defaultdict

def count_files_by_type(base_dir):
    """统计各目录文件数量"""
    stats = defaultdict(lambda: {'total': 0, 'md': 0, 'other': 0})

    knowledge = Path(base_dir)
    if not knowledge.exists():
        print(f'[ERROR] {base_dir} not found')
        return

    for item in knowledge.rglob('*'):
        if item.is_file():
            rel = item.relative_to(knowledge)
            parts = rel.parts

            if len(parts) >= 2:
                category = parts[0]  # rujia/daojia等
                subdir = parts[1] if len(parts) > 1 else ''

                stats[category]['total'] += 1
                if item.suffix == '.md':
                    stats[category]['md'] += 1
                else:
                    stats[category]['other'] += 1

    return stats

def list_placeholder_files(base_dir):
    """列出所有占位符文件（需要下载原文的）"""
    knowledge = Path(base_dir)
    placeholders = []

    for md_file in knowledge.rglob('*.md'):
        rel = md_file.relative_to(knowledge)

        # 跳过converted_markdown和README
        if 'converted_markdown' in str(md_file) or md_file.name in ['README.md', 'INDEX.md', 'milvus_import_guide.md']:
            continue

        # 检查是否为占位符（包含"待下载"关键词）
        try:
            with open(md_file, 'r', encoding='utf-8') as f:
                content = f.read()
                if '待下载' in content or 'placeholder' in content.lower():
                    placeholders.append(str(rel))
        except:
            pass

    return placeholders

def main():
    print('=' * 70)
    print('DialecticEngine Knowledge Base Status')
    print('=' * 70)
    print()

    knowledge_dir = Path('knowledge')
    if not knowledge_dir.exists():
        print('[ERROR] knowledge/ directory not found!')
        return

    # 统计文件
    stats = count_files_by_type(knowledge_dir)

    print('[DIRECTORY STRUCTURE]')
    print('-' * 70)

    schools_order = [
        ('rujia', '儒家 (Confucianism)'),
        ('daojia', '道家 (Daoism)'),
        ('mojia', '墨家 (Mohism)'),
        ('fajia', '法家 (Legalism)'),
        ('bingjia', '兵家 (Military Strategy)'),
        ('mingjia', '名家 (School of Names)'),
        ('yinyangjia', '阴阳家 (Yin-Yang)'),
        ('zonghengjia', '纵横家 (Diplomacy)'),
        ('nongjia', '农家 (Agrarianism)'),
        ('zajia', '杂家 (Syncretism)'),
        ('xiaoshuojia', '小说家 (Minor Schools)'),
        ('yijia', '医家 (Medicine)'),
        ('shijia', '史家 (Historiography)'),
        ('shushujia', '术数家 (Astrology)'),
        ('huanglao', '黄老家 (Huang-Lao)'),
    ]

    total_md = 0
    total_all = 0

    for key, name in schools_order:
        if key in stats:
            s = stats[key]
            total_all += s['total']
            total_md += s['md']
            status = 'OK' if s['md'] > 0 else 'EMPTY'
            print(f'  [{status}] {name:<40} {s["md"]:>3} md files')
        else:
            print(f'  [MISS] {name:<40}   0 md files')

    # 其他目录
    print()
    print('[OTHER FILES]')
    converted = list(knowledge_dir.glob('converted_markdown/*.md'))
    print(f'  Converted (from docx): {len(converted)} files')
    print(f'    - {", ".join(f.name for f in converted)}')

    # 检查占位符
    print()
    print('[PLACEHOLDER FILES]')
    placeholders = list_placeholder_files(knowledge_dir)
    if placeholders:
        print(f'  Need to download: {len(placeholders)} files')
        for ph in placeholders[:10]:  # 只显示前10个
            print(f'    - {ph}')
        if len(placeholders) > 10:
            print(f'    ... and {len(placeholders)-10} more')
    else:
        print('  No placeholders found (all files have content)')

    print()
    print('=' * 70)
    print(f'SUMMARY: {total_md} markdown files, {total_all} total files')
    print(f'TODO: {len(placeholders)} files need to be downloaded')
    print('=' * 70)

    # 建议下一步
    print()
    print('NEXT STEPS:')
    if placeholders:
        print('1. Download original texts from ctext.org to placeholder files')
        print('   See: knowledge/milvus_import_guide.md for download instructions')
    else:
        print('1. Run preprocessing: python scripts/preprocess_for_milvus.py')
        print('2. Import to Milvus: python scripts/import_to_milvus.py')

    print('3. Verify retrieval: Use scripts/test_retrieval.py')
    print('4. Integrate with skills: Update huashu-nuwa skill to use Milvus')

if __name__ == '__main__':
    main()
