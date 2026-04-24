"""
批量下载诸子百家经典文本 - 简化版
从中国哲学书电子化计划(ctext.org)下载
为Milvus RAG准备格式化的Markdown文件
"""

import os
import time
from pathlib import Path

# 经典书籍清单
CLASSICS_TO_DOWNLOAD = {
    # 儒家
    'rujia/classics/论语.md': ('Confucianism', '论语', 'Analects', 'https://ctext.org/analects/zh'),
    'rujia/classics/孟子.md': ('Confucianism', '孟子', 'Mencius', 'https://ctext.org/mengzi/zh'),
    'rujia/classics/大学.md': ('Confucianism', '大学', 'Great Learning', 'https://ctext.org/liji/da-xue/zh'),
    'rujia/classics/中庸.md': ('Confucianism', '中庸', 'Doctrine of the Mean', 'https://ctext.org/liji/zhong-yong/zh'),
    'rujia/classics/诗经.md': ('Confucianism', '诗经', 'Book of Songs', 'https://ctext.org/shijing/zh'),
    'rujia/classics/尚书.md': ('Confucianism', '尚书', 'Book of Documents', 'https://ctext.org/shang-shu/zh'),
    'rujia/classics/礼记.md': ('Confucianism', '礼记', 'Book of Rites', 'https://ctext.org/liji/zh'),
    'rujia/classics/周易.md': ('Confucianism', '周易', 'I Ching', 'https://ctext.org/zhou-yi/zh'),
    'rujia/classics/春秋.md': ('Confucianism', '春秋', 'Spring and Autumn Annals', 'https://ctext.org/chun-qiu/zh'),

    # 道家
    'daojia/classics/道德经.md': ('Daoism', '道德经', 'Tao Te Ching', 'https://ctext.org/dao-de-jing/zh'),
    'daojia/classics/庄子.md': ('Daoism', '庄子', 'Zhuangzi', 'https://ctext.org/zhuangzi/zh'),
    'daojia/classics/列子.md': ('Daoism', '列子', 'Liezi', 'https://ctext.org/liezi/zh'),
    'daojia/classics/文子.md': ('Daoism', '文子', 'Wenzi', 'https://ctext.org/wenzi/zh'),

    # 墨家
    'mojia/classics/墨子.md': ('Mohism', '墨子', 'Mozi', 'https://ctext.org/mozi/zh'),

    # 法家
    'fajia/classics/韩非子.md': ('Legalism', '韩非子', 'Han Feizi', 'https://ctext.org/han-fei-zi/zh'),
    'fajia/classics/商君书.md': ('Legalism', '商君书', 'Shangjunshu', 'https://ctext.org/shang-jun-shu/zh'),
    'fajia/classics/管子.md': ('Legalism', '管子', 'Guanzi', 'https://ctext.org/guan-zi/zh'),

    # 兵家
    'bingjia/classics/孙子兵法.md': ('Military Strategy', '孙子兵法', 'Art of War', 'https://ctext.org/sun-tzu-bing-fa/zh'),
    'bingjia/classics/孙膑兵法.md': ('Military Strategy', '孙膑兵法', 'Sun Bin Bing Fa', 'https://ctext.org/sun-bin-bing-fa/zh'),
    'bingjia/classics/吴子.md': ('Military Strategy', '吴子', 'Wuzi', 'https://ctext.org/wu-zi/zh'),
    'bingjia/classics/六韬.md': ('Military Strategy', '六韬', 'Six Secret Teachings', 'https://ctext.org/liu-tao/zh'),
    'bingjia/classics/三略.md': ('Military Strategy', '三略', 'Three Strategies', 'https://ctext.org/san-lue/zh'),
    'bingjia/classics/尉缭子.md': ('Military Strategy', '尉缭子', 'Weiliaozi', 'https://ctext.org/wei-liao-zi/zh'),

    # 名家
    'mingjia/classics/公孙龙子.md': ('School of Names', '公孙龙子', 'Gongsun Longzi', 'https://ctext.org/gongsun-long-zi/zh'),
    'mingjia/classics/邓析子.md': ('School of Names', '邓析子', 'Dengxizi', 'https://ctext.org/deng-xi-zi/zh'),
    'mingjia/classics/尹文子.md': ('School of Names', '尹文子', 'Yin Wenzi', 'https://ctext.org/yin-wen-zi/zh'),

    # 阴阳家
    'yinyangjia/classics/邹子.md': ('Yin-Yang', '邹子', 'Zouzi', 'https://ctext.org/zou-zi/zh'),

    # 纵横家
    'zonghengjia/classics/鬼谷子.md': ('Diplomacy', '鬼谷子', 'Guiguzi', 'https://ctext.org/gui-gu-zi/zh'),
    'zonghengjia/classics/战国策.md': ('Diplomacy', '战国策', 'Zhan Guo Ce', 'https://ctext.org/zhan-guo-ce/zh'),

    # 农家
    'nongjia/classics/神农.md': ('Agrarianism', '神农', 'Shennong', 'https://ctext.org/shen-nong/zh'),

    # 杂家
    'zajia/classics/吕氏春秋.md': ('Syncretism', '吕氏春秋', 'Lüshi Chunqiu', 'https://ctext.org/lv-shi-chun-qiu/zh'),
    'zajia/classics/淮南子.md': ('Syncretism', '淮南子', 'Huainanzi', 'https://ctext.org/huai-nan-zi/zh'),
    'zajia/classics/尸子.md': ('Syncretism', '尸子', 'Shizi', 'https://ctext.org/shi-zi/zh'),

    # 小说家
    'xiaoshuojia/classics/汉书艺文志.md': ('Minor Schools', '汉书艺文志', 'Han Shu Yi Wen Zhi', 'https://ctext.org/han-shu-yi-wen-zhi/zh'),

    # 医家
    'yijia/classics/黄帝内经.md': ('Medicine', '黄帝内经', 'Huangdi Neijing', 'https://ctext.org/huang-di-nei-jing/zh'),
    'yijia/classics/伤寒论.md': ('Medicine', '伤寒论', 'Shanghan Lun', 'https://ctext.org/shang-han-lun/zh'),
    'yijia/classics/难经.md': ('Medicine', '难经', 'Nanjing', 'https://ctext.org/nan-jing/zh'),
    'yijia/classics/神农本草经.md': ('Medicine', '神农本草经', 'Shennong Bencao Jing', 'https://ctext.org/shen-nong-ben-cao-jing/zh'),

    # 史家
    'shijia/classics/史记.md': ('Historiography', '史记', 'Records of the Grand Historian', 'https://ctext.org/shi-ji/zh'),
    'shijia/classics/汉书.md': ('Historiography', '汉书', 'Book of Han', 'https://ctext.org/han-shu/zh'),
    'shijia/classics/左传.md': ('Historiography', '左传', 'Zuo Zhuan', 'https://ctext.org/zuo-zhuan/zh'),
    'shijia/classics/国语.md': ('Historiography', '国语', 'Guo Yu', 'https://ctext.org/guo-yu/zh'),

    # 术数家
    'shushujia/classics/易传.md': ('Astrology', '易传', 'Yizhuan', 'https://ctext.org/yi-zhuan/zh'),

    # 黄老家
    'huanglao/classics/黄帝四经.md': ('Huang-Lao', '黄帝四经', 'Huangdi Sijing', 'https://ctext.org/huang-di-si-jing/zh'),
}

def create_front_matter(chinese_title, english_title, school_en, url):
    """创建YAML front matter元数据"""
    return f"""---
title: "{chinese_title} (${english_title})"
chinese_title: "{chinese_title}"
english_title: "{english_title}"
school: "{school_en}"
source: "中国哲学书电子化计划"
url: "{url}"
downloaded: "2026-04-16"
format: "Markdown"
description: "诸子百家核心经典 - {chinese_title}"
---

"""

def create_placeholder_file(file_path, chinese_title, english_title, school_en, school_zh, url):
    """创建占位符文件，包含下载说明"""
    content = create_front_matter(chinese_title, english_title, school_en, url)

    content += f"""# {chinese_title}

**流派**: {school_zh} ({school_en})
**英文名**: {english_title}
**来源**: [中国哲学书电子化计划]({url})

---

## 待下载说明

本文档为占位符文件。请按以下步骤获取原文：

### 方法1: 使用ctext.org API（推荐）

ctext.org提供结构化数据接口：

```bash
# 获取JSON格式数据
curl "https://ctext.org/{url.split('/')[-2]}/{url.split('/')[-1]}?format=json" \\
     -H "User-Agent: DialecticEngine/1.0" \\
     -o original.json
```

### 方法2: 手动复制

1. 访问 [{url}]({url})
2. 选择文本版本（如" Plaincat"）
3. 复制原文粘贴到此文件

### 方法3: Python爬虫（示例）

```python
import requests
from bs4 import BeautifulSoup

def download_classic(url, output_file):
    response = requests.get(url, headers={{'User-Agent': 'Mozilla/5.0'}})
    soup = BeautifulSoup(response.text, 'html.parser')

    # ctext页面结构较复杂，建议使用ctext的JSON API
    # 或查看network请求找到text数据

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(extracted_content)
```

## 文件结构建议

下载完成后，请整理为���下格式：

```markdown
---
title: "{chinese_title}"
school: "{school_en}"
source: "ctext.org"
url: "{url}"
---

# {chinese_title}

## 第一章

**原文**: ...
**译文**: ...（如有）
**注释**: ...（如有）
```

## 用于Milvus RAG

导入Milvus时的分块建议：

1. **按章节分块**: 每章/篇作为一个chunk
2. **块大小**: 200-500字（中文）
3. **元数据字段**:
   - `school`: "{school_en}"
   - `classic`: "{chinese_title}"
   - `chapter`: "第一章"等
   - `dynasty`: "先秦"等
   - `source_url`: "{url}"

4. **嵌入模型建议**: 使用中文embedding模型，如：
   - BAAI/bge-large-zh-v1.5
   - M3E-large
   - sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2

---

**待下载链接**: {url}
**创建时间**: 2026-04-16
**状态**: 待手动下载原文
"""

    file_path.parent.mkdir(parents=True, exist_ok=True)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f'[OK] Created placeholder: {file_path}')

def main():
    print('============================================================')
    print('DialecticEngine Knowledge Downloader - Simplified')
    print('============================================================')
    print()

    total = len(CLASSICS_TO_DOWNLOAD)
    processed = 0

    for i, (rel_path, (school_en, chinese_title, english_title, url)) in enumerate(CLASSICS_TO_DOWNLOAD.items(), 1):
        file_path = Path(rel_path)
        school_zh = {
            'daojia': '道家', 'rujia': '儒家', 'mojia': '墨家', 'fajia': '法家',
            'bingjia': '兵家', 'mingjia': '名家', 'yinyangjia': '阴阳家',
            'zonghengjia': '纵横家', 'nongjia': '农家', 'zajia': '杂家',
            'xiaoshuojia': '小说家', 'yijia': '医家', 'shijia': '史家',
            'shushujia': '术数家', 'huanglao': '黄老家'
        }.get(file_path.parent.parent.name, file_path.parent.parent.name)

        print(f'[{i:02d}/{total:02d}] {chinese_title} ({school_zh})')

        try:
            create_placeholder_file(file_path, chinese_title, english_title, school_en, school_zh, url)
            processed += 1
        except Exception as e:
            print(f'[ERROR] {rel_path}: {e}')

        time.sleep(0.05)

    print()
    print('============================================================')
    print(f'Completed: {processed}/{total} files created')
    print()
    print('Next steps:')
    print('1. 手动从 ctext.org 下载原文到对应的 .md 文件')
    print('2. 或实现完整的自动下载脚本（需要处理ctext反爬）')
    print('3. 删除占位符文件中的"待下载"部分')
    print('4. 参考 milvus_import_guide.md 导入Milvus')
    print('============================================================')

if __name__ == '__main__':
    main()
