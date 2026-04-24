# DialecticEngine 策略系统

> 基于中国古代哲学经典的政策推理引擎

## 系统概述

DialecticEngine Skills 是一个**认知策略运行时**，将传统中国哲学编译为可执行的推理框架。系统不模拟角色——它加载带有显式约束、操作边界和评估指标的结构化决策策略。

**核心抽象**：每个 Skill 是一个**推理策略**——元组 `(mental_models, heuristics, constraints, trigger_conditions)`。

---

## 架构

### 策略模块结构

```
{school}-perspective/
├── SKILL.md                    # 策略定义：模型 + 启发式 + 约束
├── metadata.json               # 路由元数据：触发器、问题类型、能力
├── README.md                   # 模块级规范
├── references/
│   └── research/               # 证据库（6类）
│       ├── 01-writings.md      # 原典分析
│       ├── 02-conversations.md # 论辩模式
│       ├── 03-expression-dna.md # 输出格式约束
│       ├── 04-external-views.md # 范围限制 + 批评
│       ├── 05-decisions.md     # 决策轨迹示例
│       └── 06-timeline.md      # 策略演变历史
├── sources/                    # 原始语料（可选）
└── index/
    ├── skill-card.md          # 快速参考
    └── trigger-examples.md    # 路由示例
```

### 可用策略模块

| 策略 | 领域 | 优势 | 局限 |
|------|------|------|------|
| **rujia** | 角色伦理、义利取舍 | 关系冲突、品德修养 | 法律判决、量化决策 |
| **daojia** | 无为边界、顺势而为 | 控制幻觉、选择困难 | 行动方案、危机干预 |
| **fajia** | 激励设计、制度系统 | 组织治理、风控合规 | 人文关怀、长期信任 |
| **mojia** | 功利计算、资源运营 | 项目落地、效率优先 | 审美、个体表达 |
| **bingjia** | 竞争策略、时机把握 | 谈判博弈、风险评估 | 合作场景、道德判断 |
| **mingjia** | 概念分析、定义澄清 | 术语争议、逻辑检验 | 价值判断、行动建议 |
| **yinyangjia** | 系统平衡、周期判断 | 多变量、趋势分析 | 精确预测、因果机制 |
| **zajia** | 综合协调、多方权衡 | 利益整合、冲突调解 | 单一深度问题 |
| **zonghengjia** | 联盟构建、利益交换 | 复杂谈判、破局策略 | 长期信任、价值创造 |
| **nongjia** | 生产稳定、底层保障 | 资源分配、风险冗余 | 复杂系统、创新 |
| **yijia** | 诊断修复、系统平衡 | 问题识别、渐进优化 | 突发事件、快速决策 |
| **huanglao** | 最小治理、无为而治 | 过度管理、干预失效 | 高冲突、急剧变化 |
| **shushujia** | 趋势推演、不确定性 | 情景规划、风险区间 | 精确预测、因果判断 |
| **shijia** | 历史类比、经验推理 | 路径选择、模式识别 | 新问题、创新场景 |
| **xuanxue** | 本体论（有无）、意义 | 价值虚无、规范冲突 | 落地实施、行动指导 |
| **fojia** | 执着、苦之根源 | 情绪困境、执念分析 | 世俗成功、行动导向 |
| **lixue** | 天理秩序、格物致知 | 道德规范、认知统一 | 灵活性、创新 |
| **xinxue** | 良知本体、知行合一 | 行动决策、内在冲突 | 客观分析 |
| **jingxue** | 经典解释、正统建构 | 制度合法性、权威来源 | 创新、现实适应 |
| **newrujia** | 传统现代、主体性重建 | 文化冲突、价值重建 | 快速方案、具体操作 |
| **xiaoshuojia** | 叙事结构 | 故事分析 | 抽象推理 |

---

## 策略推导框架

### 编译流水线

```
原典 → 六维研究 → 模型提取 → 策略编译 → 验证
```

**阶段一：证据收集（六维度）**
1. 原典分析（核心命题、论证结构）
2. 论辩模式（论辩逻辑、问答场景）
3. 输出格式约束（表达DNA）
4. 外部批评 + 范围限制（局限性）
5. 决策轨迹（历史决策案例）
6. 演变历史（思想演变）

**阶段二：模型提取**

每个策略包含 3-7 个**心智模型**：

```json
{
  "name": "model_id",
  "definition": "现代语言表述",
  "applies_to": ["issue_type_a", "issue_type_b"],
  "fails_when": ["condition_x", "condition_y"],
  "evidence": [{"source": "text_name", "chapter": "n"}]
}
```

**阶段三：启发式编译**

```python
# 模式：If <条件> then <行动>
# 示例：
if resource_insufficient: "先为不可胜"
if timing_uncertain: "校计而待"
if opponent_strong: "避实击虚"
```

**阶段四：约束定义**

每个策略显式定义：
- **边界条件**：策略范围外的问题
- **内在张力**：已知矛盾（如：仁爱 vs 礼制）
- **失败模式**：已知失败模式及缓解措施

---

## 执行运行时

### 策略加载协议

```
用户输入
    ↓
路由器：匹配 trigger_conditions → 选择策略
    ↓
分类器：映射到 issue_type (A-E)
    ↓
证据检索器：获取相关原典（如需要）
    ↓
策略引擎：应用 mental_models → 生成启发式
    ↓
约束检查器：验证输出是否符合策略边界
    ↓
张力解析器：显式呈现内在矛盾
    ↓
输出：决策 + 启发式 + 警告 + 范围声明
```

### 问题类型映射

| 类型 | 特征 | 策略动作 |
|------|------|----------|
| **A** | 角色/关系冲突 | 角色定位（伦常定位） |
| **B** | 资源/利益冲突 | 代价收益分析 |
| **C** | 规则/变通冲突 | 经权区分判断 |
| **D** | 意义/价值困惑 | 本体澄清 |
| **E** | 修身/心性困境 | 反求诸己 |

---

## 路由规范

### 触发匹配

**显式路由**：直接策略调用
- 「用儒家分析」
- 「切换到法家模式」
- 「从道家角度」

**隐式路由**：概念/场景匹配
- 关键词：五伦, 义利之辨, 舍生取义, 修身
- 场景标签：relationship conflict, ethical dilemma, organizational governance

**无匹配路由**：回退到通用推理或请求澄清。

### 策略选择启发式

```python
def select_policy(issue_type, context):
    if issue_type == "A" and "relationship" in context:
        return ["rujia", "xinxue"]
    if issue_type == "B" and "efficiency" in context:
        return ["mojia", "fajia"]
    if issue_type == "A" and "competition" in context:
        return ["bingjia", "zonghengjia"]
    # ... 其他规则
    return []
```

---

## 评估框架

### 策略验证指标

| 指标 | 定义 | 目标 |
|------|------|------|
| **Coverage** | 有适用模型的问题类型占比 | >80% |
| **Coherence** | 内在张力显式解析 | Yes |
| **Scope Clarity** | 边界条件已声明 | Yes |
| **Evidence Density** | 每个模型的原典引用数 | ≥2 |
| **Heuristic Count** | 每个策略的操作规则数 | 5-10 |

### 比较协议

策略可比：
- **决策分歧度**：同问题 → 不同建议
- **约束重叠度**：共享 vs 独占应用域
- **历史准确性**：轨迹 vs 实际历史决策
- **失败模式对齐度**：已知弱点 vs 测试用例

### 蒸馏协议

从新语料推导新策略：

1. 执行六维研究框架
2. 提取候选心智模型（≥3, ≤10）
3. 编译启发式规则（5-10）
4. 定义约束 + 内在张力
5. 与现有策略交叉验证（检测冗余）
6. 在路由表中注册触发条件
7. 用留出决策案例进行单元测试

---

## 元数据 Schema

```json
{
  "name": "policy_id",
  "description": "操作摘要",
  "school": "哲学流派",
  "issue_types": ["A", "B", "C"],
  "preferred_conditions": ["context_1", "context_2"],
  "triggers": {
    "keywords": [],
    "scenes": []
  },
  "capabilities": ["reasoning_1", "reasoning_2"],
  "constraints": {
    "inapplicable": ["case_1"],
    "internal_tensions": [{"tension": "X vs Y", "resolution": "Z"}]
  },
  "evidence_base": ["source_1", "source_2"],
  "version": "1.0.0",
  "validation": {
    "coverage": 0.85,
    "coherence": true,
    "scope_clarity": true
  }
}
```

---

## 系统集成

### 知识库（RAG 语料）

`knowledge/` 包含用于证据检索的原典语料。每个策略有显式映射：

| 策略 | 语料库 |
|------|--------|
| rujia | 论语, 孟子, 礼记, 荀子 |
| daojia | 道德经, 庄子 |
| fajia | 韩非子, 商君书 |
| bingjia | 孙子兵法 |
| ... | ... |

### 策略组合

可加载多个策略用于：
- **比较分析**：同问题 → 多策略输出
- **约束传播**：策略 A 的约束影响策略 B 的范围
- **蒸馏**：从父策略派生混合策略

组合示例：
```python
composite_policy = ensemble([
    load_policy("rujia"),  # 伦理框架
    load_policy("fajia"),  # 激励约束
    load_policy("bingjia") # 竞争边界
])
```

---

## 扩展协议

### 添加新策略

1. 收集原典 + 二手研究
2. 执行六维框架 → 生成6份参考文档
3. 提取3-7个带证据的��智模型
4. 编译5-10条启发式规则
5. 定义约束 + 张力
6. 填充 metadata.json
7. 在路由表中注册触发器
8. 用测试用例验证

### 策略更新

1. 更新受影响的参考文档
2. 修订心智模型（如解释有变）
3. 递增版本号，更新验证指标

---

## 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| v2.0 | 2026-04-16 | 21个策略，覆盖先秦至宋明 |
| v1.0 | 2026-04-15 | 核心4个：rujia/daojia/fajia/bingjia |

---

## 来源

- **原典**：维基文库, ctext.org
- **版本**：中华书局点校本, 上海古籍出版社
- **推导框架**：女娲策略编译协议