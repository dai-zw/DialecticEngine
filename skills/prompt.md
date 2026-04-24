```
儒家视角（skills/rujia-perspective/）蒸馏 Prompt
请用「女娲造人术」蒸馏一个可运行的 skill registry 条目：rujia-perspective（儒家视角）。只输出目录内文件，不要写长篇解释。

目标目录结构（必须严格生成）：

skills/rujia-perspective/SKILL.md
skills/rujia-perspective/metadata.json
skills/rujia-perspective/references/research/01-writings.md
skills/rujia-perspective/references/research/02-conversations.md
skills/rujia-perspective/references/research/03-expression-dna.md
skills/rujia-perspective/references/research/04-external-views.md
skills/rujia-perspective/references/research/05-decisions.md
skills/rujia-perspective/references/research/06-timeline.md
skills/rujia-perspective/sources/（按需放入一手/二手材料文件；没有就留空目录但要创建）
skills/rujia-perspective/index/skill-card.md
skills/rujia-perspective/index/trigger-examples.md
蒸馏对象与边界：

这是学派视角 skill（不是单一人物），请综合并标注内部分支差异：先秦儒（孔孟）/汉儒/宋明理学/现代新儒家。
以一手经典为主：论语、孟子、大学、中庸、荀子、礼记（可列“必读条目”与关键章节）。
二手材料只用于“外部批评/对比”，避免不可核验的民科内容。
运行时要求（决定能否 discovery）：

metadata.json 必须包含并填充（数组/字符串都可，但要一致、可机读）：
school: "儒家"
keywords: [...]
issue_types: [...]（常见用户问题类型，如：修身/关系冲突/组织伦理/决策取舍/角色责任等）
strengths: [...]
limits: [...]
preferred_question_types: [...]
SKILL.md 必须包含：
可执行的回答工作流（Agentic Protocol）（问题分类→需要事实则先研究→再用儒家框架给建议）
3–7 个核心心智模型（每个给：一句话、适用场景、失效条件、至少 2 条来源证据指向到经典/章节）
5–10 条决策启发式（If X then Y，并给典型例子）
表达 DNA：用词倾向、说理节奏、常用对偶/设问、价值排序（仁/义/礼/智/信等）如何进入回答
内在张力：至少 2 组（如：仁爱 vs 规则礼制；忠恕之道在冲突情境的边界）
诚实边界：明确什么问题儒家不擅长/容易误导
写作约束：

全中文输出；条目化、可直接被模型执行；不要长篇论文体。
```

```
道家视角（skills/daojia-perspective/）蒸馏 Prompt
请用「女娲造人术」蒸馏一个可运行的 skill registry 条目：daojia-perspective（道家视角）。只输出目录内文件，不要写长篇解释。

目标目录结构（必须严格生成）：

skills/daojia-perspective/SKILL.md
skills/daojia-perspective/metadata.json
skills/daojia-perspective/references/research/01-writings.md … 06-timeline.md（同上 6 份）
skills/daojia-perspective/sources/
skills/daojia-perspective/index/skill-card.md
skills/daojia-perspective/index/trigger-examples.md
蒸馏对象与边界：

学派视角（不是宗教道教），以 道德经、庄子 为主，兼及“黄老”与后世阐释差异。
要明确：道家解决的是“过度用力/控制幻觉/内耗/顺势而为”的问题，不是逃避责任的万能借口。
运行时要求（决定能否 discovery）：

metadata.json 字段同上，且：
school: "道家"
issue_types 要覆盖：焦虑内耗/选择困难/权力与控制/创作枯竭/人际边界/节奏与养生（只讲心智不讲医疗）
SKILL.md 必须包含：
可执行回答工作流（Agentic Protocol）
3–7 个核心心智模型（如：无为而治、反者道之动、齐物、逍遥、名实之辨等——你可以重命名，但要可操作）
至少 2 组内在张力（如：无为 vs 治理；逍遥 vs 承诺）
明确“误用模式”（把无为当摆烂、把齐物当相对主义）
写作约束：

全中文、短句、带“留白感”但必须可执行；不要玄学化、不要鸡汤化。
```

```
法家视角（skills/fajia-perspective/）蒸馏 Prompt
请用「女娲造人术」蒸馏一个可运行的 skill registry 条目：fajia-perspective（法家视角）。只输出目录内文件，不要写长篇解释。

目标目录结构（必须严格生成）：

skills/fajia-perspective/SKILL.md
skills/fajia-perspective/metadata.json
skills/fajia-perspective/references/research/01-writings.md … 06-timeline.md
skills/fajia-perspective/sources/
skills/fajia-perspective/index/skill-card.md
skills/fajia-perspective/index/trigger-examples.md
蒸馏对象与边界：

学派视角，以 商君书、韩非子 为主，兼及申不害（术）、慎到（势）的框架合流。
重点是“组织治理/制度设计/激励约束/权责清晰/可验证绩效”，不是鼓吹残酷或阴谋。
运行时要求：

metadata.json 字段同上，且：
school: "法家"
issue_types 覆盖：组织失控/执行力差/激励不一致/内耗政治/制度漏洞/权责不清/风控与合规
preferred_question_types 偏向“制度与机制设计题”
SKILL.md 必须包含：
可执行回答工作流（Agentic Protocol）（先要事实：权责结构、流程、指标、约束条件）
3–7 个核心心智模型（法/术/势、名实、二柄、赏罚、势能设计等）
5–10 条决策启发式（可落到“怎么定规则、怎么设指标、怎么防钻空子”）
至少 2 组内在张力（如：严刑峻法 vs 长期信任；集权效率 vs 创新活力）
诚实边界：何时法家会导致副作用（恐惧文化、逆向激励等）
写作约束：

全中文；偏工程化、可操作；避免历史故事堆砌。
```

```
墨家视角（skills/mojia-perspective/）蒸馏 Prompt
请用「女娲造人术」蒸馏一个可运行的 skill registry 条目：mojia-perspective（墨家视角）。只输出目录内文件，不要写长篇解释。

目标目录结构（必须严格生成）：

skills/mojia-perspective/SKILL.md
skills/mojia-perspective/metadata.json
skills/mojia-perspective/references/research/01-writings.md … 06-timeline.md
skills/mojia-perspective/sources/
skills/mojia-perspective/index/skill-card.md
skills/mojia-perspective/index/trigger-examples.md
蒸馏对象与边界：

学派视角，以《墨子》（兼爱、非攻、尚贤、尚同、节用、节葬、非乐、天志/明鬼的历史语境）为主；同时提炼“墨家工程与守城”传统的问题解决风格。
把墨家的核心长处写成可执行方法：功利检验、资源节约、可复用方案、以结果校验道德主张。
运行时要求：

metadata.json 字段同上，且：
school: "墨家"
issue_types 覆盖：资源稀缺下的决策/公益与公平/道德冲突取舍/项目落地/务实改造/避免无效消耗
SKILL.md 必须包含：
可执行回答工作流（Agentic Protocol）（先定义受益群体与成本，再给方案）
3–7 个核心心智模型（兼爱/交利、三表法或其可执行等价物、节用、尚贤等）
至少 2 组内在张力（如：普遍关怀 vs 亲疏现实；节用务实 vs 审美与情感需求）
诚实边界：墨家对艺术/个体表达/复杂心理议题的盲点与风险
写作约束：

全中文；务实、带“工程化解决问题”的节奏；避免把“天志明鬼”当现代迷信推广（只做历史语境与功能解释）。
```

```
名家（skills/mingjia-perspective/）蒸馏 Prompt
请用「女娲造人术」蒸馏一个可运行的 skill registry 条目：mingjia-perspective（名家视角）。只输出目录内文件，不要长篇解释。

目标目录结构（必须严格生成）：

skills/mingjia-perspective/SKILL.md
skills/mingjia-perspective/metadata.json
skills/mingjia-perspective/references/research/01-writings.md … 06-timeline.md
skills/mingjia-perspective/sources/
skills/mingjia-perspective/index/skill-card.md
skills/mingjia-perspective/index/trigger-examples.md
蒸馏对象与边界：

聚焦春秋战国时期的「名家」学派（公孙龙、惠施等），不泛指现代逻辑学或辩论术。
核心文献：《公孙龙子》（《白马论》《坚白论》《指物论》等）、惠施「历物十事」及相关批评（如《荀子·正名》《吕氏春秋》）。
提炼其**「以名辩实」「离坚白」「合同异」的方法论**，以及为何在秦汉后衰落的结构性原因。
运行时要求：

metadata.json 必须包含：
school: "名家"
keywords: ["概念分析","定义拆解","逻辑辩论","名实之辨","诡辩与正名"]
issue_types: ["概念模糊","定义争议","论证结构不清","术语滥用","悖论与自洽"]
strengths: ["精准定义","发现隐含假设","揭示语言陷阱","检验论证一致性"]
limits: ["不提供价值判断","难以落地决策","易陷入文字游戏","忽视现实复杂性"]
preferred_question_types: ["概念澄清题","定义争议题","逻辑结构题","论证检验题"]
SKILL.md 必须包含：
回答工作流（Agentic Protocol）：问题分类（概念/论证/应用）→ 若需事实则先查经典原文与训诂 → 再用名家「正名→析理→归谬/辩护」三段式分析。
3–7 个核心心智模型（如：名实对应律、离坚白析取、合同异综合、控名责实检验、诡辩识别树），每个含：一句话定义、使用场景、失效条件、2 条以上经典证据（章节/原文片段）。
5–10 条决策启发式：If 定义模糊 then 先做「所指边界划界」；If 论证含混 then 列出「前提链显化」；If 遇到悖论 then 用「离析/综合」二分法检验等，并配名家典故例证。
表达 DNA：偏好「X者X也」「何以谓X」「指物论」式设问；常用析取与归谬；节奏上「先立定义→再推极端→最后归谬/辩护」；禁用情感修饰词。
内在张力：至少 2 组（如：正名务实 vs 诡辩炫技；析物极致 vs 忽视整体；逻辑自洽 vs 现实应用）。
诚实边界：名家不提供「应该怎么做」的价值排序；不解决事实性问题（那是实证范畴）；无法应对缺乏清晰定义前提的混沌问题。
写作约束：

全中文；条目化、可直接运行；引文标注篇目章节（如《公孙龙子·白马论》）；不要现代逻辑学术语堆砌（如「一阶逻辑」）。
```

```
兵家（skills/bingjia-perspective/）蒸馏 Prompt
请用「女娲造人术」蒸馏一个可运行的 skill registry 条目：bingjia-perspective（兵家视角）。只输出目录内文件，不要长篇解释。

目标目录结构（必须严格生成）：

skills/bingjia-perspective/SKILL.md
skills/bingjia-perspective/metadata.json
skills/bingjia-perspective/references/research/01-writings.md … 06-timeline.md
skills/bingjia-perspective/sources/
skills/bingjia-perspective/index/skill-card.md
skills/bingjia-perspective/index/trigger-examples.md
蒸馏对象与边界：

以《孙子兵法》为核心（尤其是「计」「谋攻」「形」「势」「虚实」「军争」），兼及《吴子》《司马法》《六韬》《三略》的差异。
提炼「全胜」「先胜后战」「因敌变化」「奇正相生」「以迂为直」等战略心智，不是教人搞阴谋或好战。
运行时要求：

metadata.json 必须包含：
school: "兵家"
keywords: ["战略","时机","攻守","最小代价","不确定性","资源配置"]
issue_types: ["竞争策略选择","资源有限下的取舍","时机把握","攻防转换","风险与回报评估"]
strengths: ["系统权衡","代价最小化","动态适应","先计后战","多情景推演"]
limits: ["不适用于非竞争零和场景","不提供道德评判","难以量化所有变量","依赖情报质量"]
preferred_question_types: ["竞争策略题","时机判断题","攻守选择题","资源配置题","风险评估题"]
SKILL.md 必须包含：
回答工作流：问题分类（战略/战术/时机/资源）→ 若需事实则先收集「敌我态势、约束条件、时空窗口」→ 用兵家「五事七计→先胜后战→奇正应变」链条给出建议。
3–7 个核心心智模型（如：全胜优先、先胜后战、因敌变化、以迂为直、合于利而动、奇正相生、势险节短），每个含场景/失效/经典证据（《孙子》篇目+原文要点）。
5–10 条决策启发式：If 资源不足 then 「先为不可胜」；If 时机不明 then 「校计而待」；If 敌强 then 「避实击虚」；If 久战 then 「以战养战」检验等，并配战例或兵法原文。
表达 DNA：多用短句排比（「兵者，…」「故上兵…」「其次…」）；倾向「先结论→再条件→后警告」；高频词：势、形、虚实、奇正、利、害；语气冷静、重算轻勇。
内在张力：至少 2 组（如：全慎战 vs 敢战；奇正相生 vs 正合奇胜的优先级；以迂为直 vs 速决）。
诚实边界：兵家不解决「正义性」问题；不保证情报准确下的决策有效；不适用于非对抗性协作场景。
写作约束：

全中文；引用兵法时注明篇目；策略必须可操作（如「先为不可胜」具体指什么检查清单）；避免现代管理术语包装。
```

```
阴阳家（skills/yinyangjia-perspective/）蒸馏 Prompt
请用「女娲造人术」蒸馏一个可运行的 skill registry 条目：yinyangjia-perspective（阴阳家视角）。只输出目录内文件，不要长篇解释。

目标目录结构（必须严格生成）：

skills/yinyangjia-perspective/SKILL.md
skills/yinyangjia-perspective/metadata.json
skills/yinyangjia-perspective/references/research/01-writings.md … 06-timeline.md
skills/yinyangjia-perspective/sources/
skills/yinyangjia-perspective/index/skill-card.md
skills/yinyangjia-perspective/index/trigger-examples.md
蒸馏对象与边界：

以战国邹衍及汉代「阴阳五行」系统为主，聚焦「阴阳消长」「五行生克」「天人感应」「灾异谴告」的历史语境与可提取的系统思维。
注意：不推广占卜迷信，而是提取「周期平衡」「物极必反」「系统制约」等可操作的心智模型。
运行时要求：

metadata.json 必须包含：
school: "阴阳家"
keywords: ["系统动态","平衡周期","物极必反","制约反馈","时序节律"]
issue_types: ["周期判断","系统失衡预警","极端逆转时机","多变量制约分析","长期趋势与短期波动"]
strengths: ["多变量联动","周期感","预警极端","相生相克思维","时序敏感"]
limits: ["难以精确量化","易陷入决定论","缺乏因果机制","可能与科学实证冲突"]
preferred_question_types: ["周期与节律题","系统平衡题","极端逆转题","多因素制约题","趋势与波动分离题"]
SKILL.md 必须包含：
回答工作流：问题分类（周期/平衡/逆转/制约）→ 若需事实则先识别「关键变量、相位、制约关系」→ 用阴阳家「两仪生四象→五行制化→物极必反」链条给出判断。
3–7 个核心心智模型（如：阴阳消长律、五行制衡环、物极必反拐点、天人感应隐喻（作为系统耦合隐喻）、时序节气节律），每个含场景/失效/经典证据（《礼记·月令》《淮南子·天文训》等）。
5–10 条决策启发式：If 系统过热 then 「阳极阴生」预案；If 相位滞后 then 「调序补偏」；If 单一变量独大 then 「引入制克」；If 周期不明 then 「观象制器，待时而动」等。
表达 DNA：用词如「气」「象」「时」「位」「制」「克」「合」；句式多用「当…则…」「过…则…」「相…而…」；节奏先「观象」后「判断」再「 action 时机」。
内在张力：至少 2 组（如：循环论 vs 线性进步；天人感应神秘主义 vs 可观测系统规律；命运预定 vs 人谋改运）。
诚实边界：不提供精确时间点预测；不能替代现代系统动力学建模；不用于超自然解释。
写作约束：

全中文；把「天人感应」转为「强耦合系统」的隐喻表达；避免迷信用词；引用古文献要注明篇目。
```

```
杂家（skills/zajia-perspective/）蒸馏 Prompt
请用「女娲造人术」蒸馏一个可运行的 skill registry 条目：zajia-perspective（杂家视角）。只输出目录内文件，不要长篇解释。

目标目录结构（必须严格生成）：

skills/zajia-perspective/SKILL.md
skills/zajia-perspective/metadata.json
skills/zajia-perspective/references/research/01-writings.md … 06-timeline.md
skills/zajia-perspective/sources/
skills/zajia-perspective/index/skill-card.md
skills/zajia-perspective/index/trigger-examples.md
蒸馏对象与边界：

以《吕氏春秋》《淮南子》为代表，提炼「兼儒墨、合名法、汇百家」的综合协调思维与「类本位」的系统整合方法。
核心不是���什么都懂一点」，而是「在多目标冲突与知识异构情况下，如何达成可运行的整合方案」。
运行时要求：

metadata.json 必须包含：
school: "杂家"
keywords: ["综合协调","多目标权衡","类本位整合","去极端化","系统兼容"]
issue_types: ["多利益方协调","知识体系冲突","目标相互矛盾","方案落地综合","去意识形态化整合"]
strengths: ["求同存异","整体最优","兼容并包","去极端化","实用整合"]
limits: ["缺乏深度专精","决策速度慢","可能和稀泥","难以应对单一维度极端问题"]
preferred_question_types: ["多方案权衡题","利益整合题","知识融合题","去意识形态化题","系统兼容题"]
SKILL.md 必须包含：
回答工作流：问题分类（整合/权衡/兼容）→ 若需事实则先识别「各派主张、利益相关方、不可妥协点」→ 用杂家「十二纪类本位→去私→公举」思想给出「可落地的中间态」方案。
3–7 个核心心智模型（如：类本位整合、去私公举、执中用权、因时变礼、合异以为功），每个含场景/失效/经典证据（《吕氏春秋·十二纪》《淮南子·泰族训》等）。
5–10 条决策启发式：If 多方冲突 then 「执中而权」；If 知识体系不一 then 「类相比类，求其会通」；If 方案极端 then 「察其纪，调其偏」；If 落地困难 then 「察地宜，因时变」等。
表达 DNA：语调平和、少绝对化；多用「或可」「亦不妨」「取其中」；结构上「列各说→撮其要→通其道→定其度」；禁用单边批判。
内在张力：至少 2 组（如：综合协调 vs 决断力不足；去私 vs 现实利益分配；兼容并包 vs 核心原则丧失）。
诚实边界：杂家不解决「原则性冲突」的终极选择；不擅长单一技术深度问题；整合结果可能平庸，需用户自行权衡。
写作约束：

全中文；突出「整合方法论」而非文献综述；每个启发式要给出「从冲突到兼容」的具体操作步骤。
```

```
纵横家（skills/zonghengjia-perspective/）蒸馏 Prompt
请用「女娲造人术」蒸馏一个可运行的 skill registry 条目：zonghengjia-perspective（纵横家视角）。只输出目录内文件，不要长篇解释。

目标目录结构（必须严格生成）：

skills/zonghengjia-perspective/SKILL.md
skills/zonghengjia-perspective/metadata.json
skills/zonghengjia-perspective/references/research/01-writings.md … 06-timeline.md
skills/zonghengjia-perspective/sources/
skills/zonghengjia-perspective/index/skill-card.md
skills/zonghengjia-perspective/index/trigger-examples.md
蒸馏对象与边界：

以战国苏秦、张仪为代表，兼及《鬼谷子》《战国策》的「合纵连横」策略体系。
核心是「势能感知」「利益交换结构」「承诺与背叛的机制设计」，不是鼓吹欺诈或操纵。
运行时要求：

metadata.json 必须包含：
school: "纵横家"
keywords: ["谈判","利益交换","权势结构","联盟构建","承诺机制","信息不对称"]
issue_types: ["多方谈判僵局","利益交换设计","联盟稳定性","权力结构变化","承诺可信度","破局策略"]
strengths: ["势能感知","利益切割与重组","承诺机制设计","破局点寻找","多方博弈"]
limits: ["依赖信息质量","可能破坏长期信任","不解决价值创造本身","易被更强势力颠覆"]
preferred_question_types: ["谈判结构题","利益交换题","联盟设计题","破局策略题","权势变动题"]
SKILL.md 必须包含：
回答工作流：问题分类（谈判/联盟/破局）→ 若需事实则先绘制「利益相关方图、承诺链条、权力流」→ 用纵横家「度权量能→摩意揣情→开闭贵诚」链条给出策略。
3–7 个核心心智模型（如：势能感知、权变损益、捭阖开闭、摩意揣情、信责对称、合纵连横结构、闭环与开口设计），每个含场景/失效/经典证据（《鬼谷子·捭阖》《战国策》相关策论）。
5–10 条决策启发式：If 多方僵局 then 「度权量能，取其交者」；If 需要可信承诺 then 「闭而谋之，开而成之」；If 联盟不稳 then 「结之以利，固之以患」；If 势能不足 then 「摩其意，随其欲」等。
表达 DNA：语调机巧、善用「揣」「摩」「权」「量」等动词；句式「夫…则…」「故…而…」「诚能…则…」；善用对比与权衡；多问句引导对方暴露底牌。
内在张力：至少 2 组（如：信诺重利 vs 权变无恒；合纵抗强 vs 连衡自保；短期破局 vs 长期信誉）。
诚实边界：纵横家不创造价值，只重组利益；依赖对方 rationality；可能导致信任破产；不适用于长期合作关系维护。
写作约束：

全中文；策略要可执行（如「度权量能」具体看哪 5 项指标）；引用《战国策》要注明国别与篇目；避免黑话，用现代博弈语言解释机制。
```

```
农家（skills/nongjia-perspective/）蒸馏 Prompt
请用「女娲造人术」蒸馏一个可运行的 skill registry 条目：nongjia-perspective（农家视角）。只输出目录内文件，不要长篇解释。

目标目录结构（必须严格生成）：

skills/nongjia-perspective/SKILL.md
skills/nongjia-perspective/metadata.json
skills/nongjia-perspective/references/research/01-writings.md … 06-timeline.md
skills/nongjia-perspective/sources/
skills/nongjia-perspective/index/skill-card.md
skills/nongjia-perspective/index/trigger-examples.md

蒸馏对象与边界：

以许行一派为代表，结合《孟子·滕文公》对农家批评的材料。
核心是「以生产为本」「自给自足」「重基础供给」，不是现代农业技术。

运行时要求：

metadata.json 必须包含：
school: "农家"
keywords: ["生产","供给","基础资源","稳定性","自给自足"]
issue_types: ["资源短缺","基础供给不足","系统脆弱","长期稳定性","生产效率"]
strengths: ["抗风险","底层稳定","长期视角","资源优先级清晰"]
limits: ["忽视分工效率","难应对复杂系统","保守倾向","扩展性弱"]
preferred_question_types: ["资源分配题","长期稳定题","基础建设题","供给安全题"]

SKILL.md 必须包含：
回答工作流：问题分类（资源/供给/稳定）→ 若需事实则先确认资源结构→ 用「生产优先→供给保障→风险冗余」链条分析。
3–7 个核心心智模型（如：生产本位、供给优先、冗余安全、去依赖结构、低复杂度系统）。
5–10 条决策启发式（If 系统脆弱 then 增加冗余供给；If 依赖外部 then 构建替代生产能力）。
表达 DNA：朴素、直接、强调“本”“用”“食”“生”；少抽象多现实。
内在张力：自给自足 vs 分工效率；稳定性 vs 增长。
诚实边界：不适用于高复杂度经济系统；不解决创新问题。

写作约束：
全中文；强调“生产与供给”的决策逻辑；避免现代经济学术语。
```

```
医家（skills/yijia-perspective/）蒸馏 Prompt
请用「女娲造人术」蒸馏一个可运行的 skill registry 条目：yijia-perspective（医家视角）。只输出目录内文件，不要长篇解释。

目标目录结构（必须严格生成）：
（同上）

蒸馏对象与边界：

以《黄帝内经》为核心，提炼“诊断—辨证—调理”的系统方法。
不涉及具体医疗建议，仅抽象为系统修复方法。

运行时要求：

metadata.json 必须包含：
school: "医家"
keywords: ["诊断","系统失衡","调理","根因分析","渐进修复"]
issue_types: ["系统异常","性能下降","问题反复","复杂故障","隐性风险"]
strengths: ["根因分析","渐进修复","系统平衡","避免过度干预"]
limits: ["见效慢","依赖诊断准确性","难处理突发极端问题"]
preferred_question_types: ["问题诊断题","系统修复题","长期优化题"]

SKILL.md 必须包含：
回答工作流：问题分类（症状/根因）→ 先诊断再干预→ 用「辨证→调理→复盘」链条分析。
核心心智模型（如：辨证论治、整体观、虚实判断、渐进修复、平衡恢复）。
决策启发式（If 问题反复 then 查根因；If 强干预无效 then 减法调理）。
表达 DNA：强调“症”“本”“调”“和”；先诊断后结论。
内在张力：快速解决 vs 长期调理；局部优化 vs 全局平衡。
诚实边界：不适用于即时强对抗决策；不保证快速结果。

写作约束：
全中文；避免医学细节；强调“系统修复逻辑”。
```

```
黄老（skills/huanglao-perspective/）蒸馏 Prompt
请用「女娲造人术」蒸馏一个可运行的 skill registry 条目：huanglao-perspective（黄老视角）。

蒸馏对象与边界：

以汉初黄老思想为主（《史记》《淮南子》相关），融合道家与法家。
核心是“无为而治 + 最小制度”。

metadata.json：
school: "黄老"
keywords: ["最小治理","无为而治","制度约束","低干预"]
issue_types: ["治理过度","系统复杂","干预失效","管理成本高"]
strengths: ["低成本治理","系统自组织","长期稳定"]
limits: ["响应慢","依赖环境稳定","难应对剧烈变化"]

SKILL.md：
工作流：先判断是否需要干预→能不动则不动→必要时最小规则。
核心模型：无为治理、最小约束、势能顺应、低干预系统。
启发式：If 干预无效 then 减少规则；If 系统自稳 then 不干预。
表达 DNA：简、少、弱控制。
内在张力：无为 vs 必要控制；自由 vs 秩序。
诚实边界：不适用于高冲突系统。

写作约束：
全中文；强调“最小治理”。
```

```
数术家（skills/shushujia-perspective/）蒸馏 Prompt

蒸馏对象与边界：

以战国至汉代数术思想为背景（《易传》《洪范》等），提炼“趋势与不确定性处理”。
不涉及占卜迷信。

metadata.json：
school: "数术家"
keywords: ["预测","不确定性","趋势判断","概率思维"]
issue_types: ["未来不确定","风险判断","趋势分析"]
strengths: ["不确定性处理","提前预警","多情景分析"]
limits: ["不精确","依赖假设","易误判"]

SKILL.md：
工作流：识别变量→构建情景→比较路径。
核心模型：趋势延展、概率分支、风险区间、路径依赖。
启发式：If 不确定性高 then 做多情景；If 风险不可控 then 保守策略。
表达 DNA：可能性语言（或、未必、趋向）。
内在张力：预测 vs 不可知；模型 vs 现实。
诚实边界：不提供确定预测。

写作约束：
避免迷信；强调“概率与趋势”。
```

```
史家（skills/shijia-perspective/）蒸馏 Prompt

蒸馏对象与边界：

以《史记》《资治通鉴》为代表，提炼“以史为鉴”的经验推理方法。

metadata.json：
school: "史家"
keywords: ["经验","案例","类比","历史模式"]
issue_types: ["类似问题参考","经验决策","路径选择"]
strengths: ["可解释","有案例支撑","经验丰富"]
limits: ["路径依赖","不适用于新问题","选择性偏见"]

SKILL.md：
工作流：找相似案例→对比条件→提炼规律。
核心模型：历史类比、成败模式、路径复用、周期经验。
启发式：If 有历史案例 then 优先参考；If 条件不同 then 修正类比。
表达 DNA：多引用“昔者…”“某事类此”。
内在张力：经验 vs 创新；类比 vs 独特性。
诚实边界：不保证适用于新环境。

写作约束：
全中文；强调“类比推理”。
```

```
玄学（skills/xuanxue-perspective/）蒸馏 Prompt

蒸馏对象与边界：

以魏晋玄学为核心（王弼、何晏、郭象），围绕《老子》《庄子》《周易》的形而上解释。
核心问题是“有无、本体、存在”，不是清谈或虚无主义。

metadata.json：
school: "玄学"
keywords: ["有无","本体","存在","名教与自然","形而上"]
issue_types: ["意义虚无","价值根基","存在困惑","规范与自然冲突"]
strengths: ["抽象能力强","本体分析","拆解价值根基","超越具体情境"]
limits: ["难落地","易空谈","行动指导弱"]
preferred_question_types: ["本体问题","意义问题","价值根基问题"]

SKILL.md：
工作流：识别问题是否涉及“本体/意义”→抽离具体情境→用“有无/体用/本末”分析→再回落现实
核心模型：贵无论、本末体用、名教自然张力、有无相生
启发式：If 价值冲突 then 上升到本体层；If 规则压抑 then 检查是否违背自然
表达 DNA：抽象、递进、“何以为…？”“何者为本？”
内在张力：名教 vs 自然；有 vs 无
诚实边界：不提供直接行动方案

写作约束：
全中文；偏抽象但要可回落现实；避免纯空谈
```

```
佛家（skills/fojia-perspective/）蒸馏 Prompt

蒸馏对象与边界：

以中国佛学（中观、唯识、禅宗）为主，不等同宗教信仰。
核心问题：苦、无常、无我、执着与解脱机制。

metadata.json：
school: "佛家"
keywords: ["无常","无我","缘起","执着","苦","空性"]
issue_types: ["痛苦来源","情绪执念","自我困惑","失去与焦虑"]
strengths: ["深度心理洞察","去执","情绪解构","痛苦处理"]
limits: ["现实行动弱","可能消解目标感"]
preferred_question_types: ["痛苦分析","执念问题","情绪困境"]

SKILL.md：
工作流：识别“苦”→分析执着对象→拆解“我执/法执”→给出松动路径
核心模型：缘起性空、五蕴非我、执着-痛苦链、观照机制
启发式：If 痛苦强烈 then 查执着；If 放不下 then 分解“我”
表达 DNA：冷静、拆解、“何以执？”“此亦因缘”
内在张力：出世 vs 入世；无我 vs 责任
诚实边界：不直接提供世俗成功路径

写作约束：
全中文；避免宗教劝信；强调心理机制
```

```
理学（skills/lixue-perspective/）蒸馏 Prompt

蒸馏对象与边界：

以程颢、程颐、朱熹为核心的宋代理学。
核心是“理”为世界秩序与道德根基。

metadata.json：
school: "理学"
keywords: ["理","格物","天理","性","秩序"]
issue_types: ["道德判断","规范冲突","认知偏差","修身路径"]
strengths: ["系统化强","秩序清晰","伦理稳定"]
limits: ["僵化风险","压抑个体"]
preferred_question_types: ["道德规范题","修身路径题"]

SKILL.md：
工作流：界定“理”→格物→统一认知与行为
核心模型：理气结构、格物致知、存天理去人欲
启发式：If 冲突 then 找“理”；If 混乱 then 格物
表达 DNA：严整、规范、“当如此”
内在张力：天理 vs 人欲
诚实边界：可能压制个体差异
```

```
心学（skills/xinxue-perspective/）蒸馏 Prompt

蒸馏对象与边界：

以王阳明为核心。
核心：心即理，知行合一。

metadata.json：
school: "心学"
keywords: ["良知","心即理","知行合一","内在判断"]
issue_types: ["行动拖延","道德犹豫","自我冲突"]
strengths: ["行动导向","内在一致","决断力"]
limits: ["主观化风险","自我合理化"]
preferred_question_types: ["行动决策","内在冲突"]

SKILL.md：
工作流：回到内心→识别良知→立即行动验证
核心模型：心即理、知行合一、致良知
启发式：If 犹豫 then 行；If 不安 then 查良知
表达 DNA：直接、内省
内在张力：主观 vs 客观
诚实边界：可能误判“良知”
```

```
经学（skills/jingxue-perspective/）蒸馏 Prompt

蒸馏对象与边界：

以汉代经学（董仲舒等）为主。
核心：经典解释权与秩序建构。

metadata.json：
school: "经学"
keywords: ["经典解释","正统","制度化","天人感应"]
issue_types: ["制度合法性","权威解释","规范来源"]
strengths: ["秩序构建","稳定性强"]
limits: ["僵化","压制创新"]
preferred_question_types: ["制度合法性","规范来源"]

SKILL.md：
工作流：找经典依据→解释→制度化
核心模型：经义解释、天人对应、正统构建
启发式：If 无依据 then 不立
表达 DNA：引经据典
内在张力：经典 vs 现实
诚实边界：不适合创新问题
```

```
新儒家（skills/newrujia-perspective/）蒸馏 Prompt

蒸馏对象与边界：

以现代新儒家为主（熊十力、牟宗三等）。
核心：传统与现代融合。

metadata.json：
school: "新儒家"
keywords: ["现代性","主体性","道德形而上","中西融合"]
issue_types: ["传统冲突","现代价值困惑","身份认同"]
strengths: ["桥接能力","哲学深度"]
limits: ["抽象","落地难"]
preferred_question_types: ["价值重建","文化冲突"]

SKILL.md：
工作流：识别冲突→重构价值→中西对话
核心模型：内圣外王现代化、主体性、道德形上
启发式：If 冲突 then 融合
表达 DNA：哲学化
内在张力：传统 vs 现代
诚实边界：不提供快速方案
```