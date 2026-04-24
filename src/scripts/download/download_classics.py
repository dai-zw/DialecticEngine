# 下载脚本 - 从维基文库和ctext.org下载诸子百家经典

"""
用于自动下载诸子百家经典文献
数据来源：维基文库 zh.wikisource.org
"""

import requests
from pathlib import Path
from typing import Dict, List
import time

# 经典列表（URL映射）
CLASSICS = {
    # 道家
    "daojia": {
        "name": "道家",
        "books": {
            "道德经": {
                "url": "https://zh.wikisource.org/wiki/道德經",
                "status": "已有"
            },
            "庄子": {
                "url": "https://zh.wikisource.org/wiki/莊子_(郭象註)",
                "status": "待下载"
            },
            "列子": {
                "url": "https://zh.wikisource.org/wiki/列子",
                "status": "待下载"
            },
            "文子": {
                "url": "https://zh.wikisource.org/wiki/文子",
                "status": "待下载"
            }
        }
    },
    # 儒家
    "rujia": {
        "name": "儒家",
        "books": {
            "论语": {
                "url": "https://zh.wikisource.org/wiki/論語",
                "status": "待下载"
            },
            "孟子": {
                "url": "https://zh.wikisource.org/wiki/孟子",
                "status": "待下载"
            },
            "大学": {
                "url": "https://zh.wikisource.org/wiki/大學",
                "status": "待下载"
            },
            "中庸": {
                "url": "https://zh.wikisource.org/wiki/中庸",
                "status": "待下载"
            },
            "诗经": {
                "url": "https://zh.wikisource.org/wiki/詩經",
                "status": "待下载"
            },
            "尚书": {
                "url": "https://zh.wikisource.org/wiki/尚書",
                "status": "待下载"
            },
            "周易": {
                "url": "https://zh.wikisource.org/wiki/周易",
                "status": "待下载"
            },
            "礼记": {
                "url": "https://zh.wikisource.org/wiki/禮記",
                "status": "待下载"
            },
            "春秋": {
                "url": "https://zh.wikisource.org/wiki/春秋_(杜預註)",
                "status": "待下载"
            }
        }
    },
    # 墨家
    "mojia": {
        "name": "墨家",
        "books": {
            "墨子": {
                "url": "https://zh.wikisource.org/wiki/墨子",
                "status": "已有"
            }
        }
    },
    # 法家
    "fajia": {
        "name": "法家",
        "books": {
            "韩非子": {
                "url": "https://zh.wikisource.org/wiki/韓非子",
                "status": "待下载"
            },
            "商君书": {
                "url": "https://zh.wikisource.org/wiki/商君書",
                "status": "待下载"
            },
            "管子": {
                "url": "https://zh.wikisource.org/wiki/管子",
                "status": "待下载"
            }
        }
    },
    # 兵家
    "bingjia": {
        "name": "兵家",
        "books": {
            "孙子兵法": {
                "url": "https://zh.wikisource.org/wiki/孫子兵法",
                "status": "已有"
            },
            "孙膑兵法": {
                "url": "https://zh.wikisource.org/wiki/孫臏兵法",
                "status": "待下载"
            },
            "吴子": {
                "url": "https://zh.wikisource.org/wiki/吳子",
                "status": "待下载"
            },
            "六韬": {
                "url": "https://zh.wikisource.org/wiki/六韜",
                "status": "待下载"
            },
            "三略": {
                "url": "https://zh.wikisource.org/wiki/三略",
                "status": "待下载"
            },
            "尉缭子": {
                "url": "https://zh.wikisource.org/wiki/尉繚子",
                "status": "待下载"
            }
        }
    },
    # 名家
    "mingjia": {
        "name": "名家",
        "books": {
            "公孙龙子": {
                "url": "https://zh.wikisource.org/wiki/公孫龍子",
                "status": "待下载"
            },
            "邓析子": {
                "url": "https://zh.wikisource.org/wiki/鄧析子",
                "status": "待下载"
            },
            "尹文子": {
                "url": "https://zh.wikisource.org/wiki/尹文子",
                "status": "待下载"
            }
        }
    },
    # 纵横家
    "zonghengjia": {
        "name": "纵横家",
        "books": {
            "鬼谷子": {
                "url": "https://zh.wikisource.org/wiki/鬼谷子",
                "status": "待下载"
            },
            "战国策": {
                "url": "https://zh.wikisource.org/wiki/戰國策",
                "status": "待下载"
            }
        }
    },
    # 杂家
    "zajia": {
        "name": "杂家",
        "books": {
            "吕氏春秋": {
                "url": "https://zh.wikisource.org/wiki/呂氏春秋",
                "status": "待下载"
            },
            "淮南子": {
                "url": "https://zh.wikisource.org/wiki/淮南子",
                "status": "待下载"
            },
            "尸子": {
                "url": "https://zh.wikisource.org/wiki/尸子",
                "status": "待下载"
            }
        }
    },
    # 医家
    "yijia": {
        "name": "医家",
        "books": {
            "黄帝内经": {
                "url": "https://zh.wikisource.org/wiki/黃帝內經",
                "status": "待下载"
            },
            "伤寒论": {
                "url": "https://zh.wikisource.org/wiki/傷寒論",
                "status": "待下载"
            },
            "难经": {
                "url": "https://zh.wikisource.org/wiki/難經",
                "status": "待下载"
            },
            "神农本草经": {
                "url": "https://zh.wikisource.org/wiki/神農本草經",
                "status": "待下载"
            }
        }
    },
    # 史家
    "shijia": {
        "name": "史家",
        "books": {
            "史记": {
                "url": "https://zh.wikisource.org/wiki/史記",
                "status": "待下载"
            },
            "汉书": {
                "url": "https://zh.wikisource.org/wiki/漢書",
                "status": "待下载"
            },
            "左传": {
                "url": "https://zh.wikisource.org/wiki/春秋左氏傳",
                "status": "待下载"
            },
            "国语": {
                "url": "https://zh.wikisource.org/wiki/國語_(韋昭註)",
                "status": "待下载"
            }
        }
    },
    # 农家
    "nongjia": {
        "name": "农家",
        "books": {
            "神农": {
                "url": "https://zh.wikisource.org/wiki/神農",
                "status": "已有"
            },
            "野老": {
                "url": "",
                "status": "难获取"
            }
        }
    },
    # 阴阳家
    "yinyangjia": {
        "name": "阴阳家",
        "books": {
            "邹子": {
                "url": "https://zh.wikisource.org/wiki/鄒子",
                "status": "待下载"
            }
        }
    },
    # 术数家
    "shushujia": {
        "name": "术数家",
        "books": {
            "周易": {
                "url": "https://zh.wikisource.org/wiki/周易",
                "status": "已有"
            },
            "易传": {
                "url": "https://zh.wikisource.org/wiki/易傳",
                "status": "待下载"
            }
        }
    },
    # 黄老家
    "huanglao": {
        "name": "黄老家",
        "books": {
            "黄帝四经": {
                "url": "https://zh.wikisource.org/wiki/黃帝四經",
                "status": "待下载"
            }
        }
    },
    # 小说家
    "xiaoshuojia": {
        "name": "小说家",
        "books": {
            "汉书艺文志": {
                "url": "https://zh.wikisource.org/wiki/漢書藝文志",
                "status": "待下载"
            }
        }
    }
}

def get_wikisource_content(url: str, timeout: int = 30) -> str:
    """从维基文库获取内容"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    try:
        response = requests.get(url, headers=headers, timeout=timeout)
        if response.status_code == 200:
            return response.text
        else:
            return f"Error: HTTP {response.status_code}"
    except Exception as e:
        return f"Error: {str(e)}"

def generate_markdown(book_name: str, school: str, url: str, content: str = "") -> str:
    """生成带YAML front matter的Markdown文件"""
    dynasty = "先秦" if school not in ["yijia"] else "汉"
    author_map = {
        "道家": "老子/庄周等",
        "儒家": "孔子/孟子等",
        "墨家": "墨子",
        "法家": "韩非等",
        "兵家": "孙武等",
        "名家": "公孙龙等",
        "纵横家": "鬼谷子等",
        "杂家": "吕不韦等",
        "医家": "张仲景等",
        "史家": "司马迁等",
        "农家": "神农等",
        "阴阳家": "邹衍等",
        "术数家": "伏羲等",
        "黄老家": "黄老学派",
        "小说家": "刘向等"
    }
    
    author = author_map.get(school, "未知")
    
    return f'''---
title: "{book_name}"
author: "{author}"
dynasty: "{dynasty}"
school: "{school}"
original_text: "维基文库公有领域版本"
metadata:
  source: "维基文库 zh.wikisource.org"
  url: "{url}"
  downloaded: "2026-04-16"
  format: "Markdown"
  license: "Public Domain"
---

# {book_name}

**作者**: {author}｜**朝代**: {dynasty}｜**流派**: {school}

---

## 内容

{content if content else "（待下载）"}


'''

def check_status():
    """检查各经典的下载状态"""
    print("=" * 60)
    print("诸子百家经典下载状态")
    print("=" * 60)
    
    total = 0
    downloaded = 0
    
    for school, data in CLASSICS.items():
        print(f"\n【{data['name']}】({school})")
        for book, info in data['books'].items():
            status = info['status']
            total += 1
            if status == "已有":
                downloaded += 1
            print(f"  {'✅' if status == '已有' else '⬜'} {book}: {status}")
    
    print("\n" + "=" * 60)
    print(f"总计: {downloaded}/{total} 已下载")
    print("=" * 60)

def main():
    print("""
╔═══════════════════════════════════════════════════════════╗
║         诸子百家经典下载工具                              ║
║         数据来源: 维基文库 + ctext.org                    ║
╚═══════════════════════════════════════════════════════════╝
    """)
    
    check_status()
    
    print("""
使用说明：
1. 运行 check_status() 查看当前下载状态
2. 手动从维基文库下载内容，保存到各流派的classics文件夹
3. 确保文件格式为: knowledge/{school}/classics/{book_name}.md
4. 已下载文件带有YAML front matter，包含完整metadata
""")

if __name__ == "__main__":
    main()