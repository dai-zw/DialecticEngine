"""
创建知识库目录结构
"""

import os
from pathlib import Path

# 定义所有流派目录名（从skills中提取）
schools = [
    'daojia',        # 道家
    'rujia',         # 儒家
    'mojia',         # 墨家
    'fajia',         # 法家
    'bingjia',       # 兵家
    'mingjia',       # 名家
    'yinyangjia',    # 阴阳家
    'zonghengjia',   # 纵横家
    'nongjia',       # 农家
    'zajia',         # 杂家
    'xiaoshuojia',   # 小说家
    'yijia',         # 医家
    'shijia',        # 史家
    'shushujia',     # 术数家
    'huanglao',      # 黄老家
]

knowledge_root = Path('knowledge')

# 创建目录
for school in schools:
    school_dir = knowledge_root / school / 'classics'
    school_dir.mkdir(parents=True, exist_ok=True)
    print(f'[OK] Created: {school_dir}')

# 创建sources目录
(knowledge_root / 'sources').mkdir(exist_ok=True)
print(f'[OK] Created: knowledge/sources/')

print(f'\n✅ Total directories created: {len(schools)}')
