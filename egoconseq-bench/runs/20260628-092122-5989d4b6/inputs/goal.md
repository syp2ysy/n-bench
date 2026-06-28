# GOAL: EgoConseq-Bench

**一句话目标：** 构建一个 **single-image + action-conditioned + ego-body swept-volume consequence** benchmark，用来诊断 MLLM 是否能从一张第一视角 RGB 中，把 **当前可见几何、自己的身体尺寸、候选动作** 绑定成局部物理后果判断：会不会撞、还能走多远、哪边更安全、同图换身体答案是否翻转。

> **项目定位钉死：不是导航，不是空间关系，不是物体物理，不是泛 affordance；而是当前可见局部空间内的 ego-body swept-volume consequence reasoning。**
>
> 模型输入恒为 `egocentric RGB image + question`。Depth / pose / navmesh 只用于离线 GT、过滤和可视化，不进入被测模型 prompt。

---

## 0. Context

MLLM 能描述场景、识别障碍、输出动作文字，但这不等于它真的理解：

```text
我这个身体，如果照这个方向动一下，身体扫过的空间会发生什么？
```

现有 benchmark 覆盖 physical understanding、affordance、navigation、collision grounding、egocentric world modeling，但没有一个完全隔离下面这个切片：

```text
single-image + hypothetical ego action + body-conditioned swept volume + visible local consequence
```

因此本项目的贡献不能包装成“又一个 physical / affordance / navigation benchmark”。真正能站住的点只有一个：**MLLM 是否能预测局部 ego 动作的 body-conditioned swept-volume 后果**。

安全表述：

> Existing benchmarks study physical understanding, affordance, navigation, collision grounding, or egocentric world modeling, but they do not isolate single-image, action-conditioned, ego-body swept-volume consequence reasoning within the currently visible space.

---

## 1. 论文主张

英文主张：

> We test whether MLLMs can predict the local physical consequence of an ego action by binding the visible egocentric geometry, the agent body, and the action-induced swept volume.

中文主张：

> 我们不测导航、不测泛 affordance、不测物体物理；我们测 embodied agent 行动前最底层的局部能力：**我这个身体照这个方向动一下，身体扫过的空间会不会碰、还能走多远、哪边更安全。**

---

## 2. Thesis & Hypotheses

**Thesis：** 当前 MLLM 可能能描述自由空间、障碍、门、走廊，但不能稳定地把 **自身朝向 + 身体形态 + 候选动作** 绑定到 **碰撞 / 通行 / 安全距离后果**。其“空间能力”很可能是视觉-语义模式匹配，而不是 embodied geometry grounding。

- **H1 能力缺口：** MLLM 在局部 swept-volume 后果判断上显著低于几何 oracle / human。
- **H2 非语言捷径：** blind text-only、majority、radius-only、action-only 等捷径 baseline 接近随机或明显低于 RGB 模型。
- **H3 身体盲视：** 同一 RGB 只改变 **ground-plane body footprint radius / 宽度**（v1 相机高度固定，不改身高/视点），GT 答案发生翻转；若模型答案不翻转，说明它没有把 body 当 collision operator。

---

## 3. 统一核心定义

EgoConseq-Bench 的标签统一由一个函数派生：

```text
rollout_outcome(s, r, a_1..a_k) =
  simulator feedback after executing a 1-10 step action sequence
  from start state s with a radius-r body
```

更抽象地写：

```text
label = Consequence( Body(r), StartState(s), ActionSequence(a_1..a_k), Simulator )
```

其中：

- `Body(r)` 是圆柱身体 footprint，`1 body-width = 2r`。
- `ActionSequence(a_1..a_k)` 是 1 到 10 个离散动作（move_forward / turn_left / turn_right）的短序列。
- `Simulator` 离线提供 collision、实际位移、height change、semantic context、rollout trace。
- 模型仍只看起始 RGB + question；rollout 结果只用于 GT、过滤和可视化。
- 如果问题需要隐藏未来视觉证据才能回答，样本必须丢弃或标 `ambiguous`，不能作为核心题。

**诚实边界：** swept-volume collision 本身不是技术 novelty；它是标准几何 oracle。Novelty 在于用它构造一个受控诊断 benchmark，测试 MLLM 是否能从单帧 RGB 进行 body-conditioned action consequence reasoning。

---

## 4. 分类体系（v1 主线 + v2 扩展）

分类**按能力轴**组织，不按房间 / 物体。每个类别必须绑定：一个明确能力缺口 + 一个「低分能授权的结论」。结果按类别报告，**绝不只报总 accuracy**。

分类设计要参考已有 benchmark 的方法，而不是照抄它们的任务：

- 借 VSI-Bench / Thinking in Space 的 `measurement / configurational` 思路，把粗距离估计和方向关系拆开。
- 借 SpatialBench 的分层思想，把 observation / relation / action consequence 区分开。
- 借 A4Bench 的 affordance 切分思想，把静态可供性和情境动作后果区分开。
- 借 CapNav 的 capability-conditioned 评测思想，把身体半径作为局部通行能力条件。
- 借 TouchSafeBench 的 collision grounding 思想，但保持 single RGB + hypothetical local action。

v1 **不做厘米级精确几何问答**，而做粗粒度 3D 后果判断：距离范围、动作是否可完成、方向粗排序、身体反事实、局部风险类型。

### 4.1 v1 主线分类（Habitat / MP3D simulator-in-the-loop）

第一版不追求类多，主打能在 Habitat simulator 中**真实执行短动作序列并拿到反馈**的能力族：**4 个核心能力 + 1 个 hazard / grounding 诊断**。每个 case 从一个 MP3D/R2R-CE 起始状态渲染起始 RGB，然后离线执行 1、2、3、5、10 步动作序列，记录 collision、actual distance、height change、semantic context 和 rollout trace。Action-Horizon Collision 是核心（它最直接对应机器人执行一个具体 action 前的安全判断，本项目自称 action-conditioned，它不能降为附加）；Local Hazard / First-Contact 类是诊断附加，不进生死门核心（见 §10）。

| 分类 | 参考的 benchmark 设计原则 | 假设 | QA 形式 | GT 读出 | 诊断的能力缺口 / 低分结论 |
|---|---|---|---|---|---|
| **Local Progress Estimation** | VSI-Bench measurement-style 粗空间估计 | H1 | 自然短答 / 粗范围：如果前进 N 步或约 M 米，大概能推进多少、会不会很快停下 | rollout `actual_distance_m / intended_distance_m / progress_ratio` | body-relative progress 感知：能说「前面有空间」但估不出执行后实际推进范围 |
| **Action-Horizon Collision** | ENACT / EXPLORE 的 action consequence，收窄到短时局部动作 | H1 | yes/no 或短答：执行 1/2/3/5/10 步动作后会撞、停住、下落，还是正常推进 | rollout `collision / stopped_early / height_delta_m / hazard_type` | action-conditioned projection：能感知自由空间但不能把动作序列投到未来状态 |
| **Directional Rollout Comparison** | VSI-Bench configurational / relative direction | H1 | 自然问答：左转后前进、直行、右转后前进，哪个实际推进更远 | 同起点分别 rollout 左/直/右，比较 `actual_distance_m` | 多候选动作比较 + 方向绑定；总偏 straight = center / semantic prior |
| **Body Counterfactual Flip** | CapNav capability-conditioned feasibility 的局部化版本 | H3 | 同图同动作，small/large body 谁能完成或谁更早失败 | 同起点同动作、不同 body radius 的 rollout outcome | body 是否被当 collision operator；同图换 radius 答案翻转而模型不翻 = body 盲视 |
| **Local Hazard Explanation / First-Contact**（诊断） | TouchSafeBench collision grounding，扩展为局部风险解释 | H1 | 开放短答 / hazard 类型：最先出现的风险是什么，发生在视野哪个大致区域 | rollout `collision / height_delta_m / semantic context / trace` | 答案是否 grounded 到真实局部风险，而非语言猜 yes/no |

> **Body Counterfactual Flip 是最强武器（见 §7、§10）。其余四类一般、只要它成立，论文仍有价值。** 任何便宜诊断都不得挤占它的样本预算或污染它的干净性。

### 4.2 v2 扩展分类（需更细 mesh / 多视角 / profile 重渲染）

以下三类需要比 v1 rollout 更细的 3D 控制或额外渲染，列为正式版扩展，且**只在 v1 生死门（§10）通过后启动**：

| 分类 | 为什么必须落到 v2 底座 |
|---|---|
| **Height/Viewpoint Counterfactual** | 同 base pose / yaw，按 P1/P2/P3 不同相机高度**重渲染**单图。注意它换了图，模型答错会和「普通跨图感知方差」混淆，是比 Body Counterfactual Flip **更弱**的 claim，不得顶替它当 headline |
| **Vertical Envelope Clearance**（桌下 / 横梁 / 悬空） | 需完整 3D swept volume 求交；v1 只主打 ground-plane footprint 和短动作后果 |
| **First-Contact (含 overhead)** | 上方碰撞需 3D；v1 的 First-Contact Region 只做地面三区 |

### 4.3 分析轴（tag，不是顶层类别）

profile 与 geometry 只作为 case 的**分析维度**（打 tag 后分桶切片），**不增设独立顶层类别**——否则 类别 × profile × geometry 组合爆炸，每个组合单元都得独立过效度门（§10），现阶段连单类都未干净，广度不是约束。

- **agent profile（v1 仅 radius 轴）**：v1 只变 `body_radius`；`camera_height` / `body_height` 多 profile 属 v2。`instantiation_spec` v1 **禁止**把多相机高度当主贡献。
- **geometry tag**：`open` / `frontal-barrier` / `narrow-gap` / `corner-branch` / `clutter`，仅用于结果分桶。

注意：论文和 HTML 使用 human-readable category names，不把 `T1/T2/T4` 当最终 taxonomy；它们只是内部 probe shorthand。

---

## 5. 数据与 GT 路线

### 5.1 v1 路线：Habitat simulator-in-the-loop GT

第一版实现目标固定为 **Habitat + MP3D/R2R-CE simulator rollout**：

```text
选择 MP3D/R2R-CE 起始状态
→ 渲染 egocentric RGB / depth / semantic / pose
→ 采样 1-10 步短动作序列
→ 在 simulator 中真实执行 rollout
→ 记录 collision、actual_distance_m、intended_distance_m、progress_ratio、height_delta_m、hazard_type、semantic context、rollout_trace
→ 生成 GT + 可视化 overlay + HTML case
```

Simulator-GT 的最低及格线：

1. 模型输入只保存起始 RGB + question。
2. GT 来自同一 simulator 内真实执行的 action sequence，而不是单帧 depth 启发式。
3. 输出连续 rollout 字段，同时对外生成粗标签：`distance_range_m`、`direction_bucket`、`action_feasibility`、`hazard_type`、`scoring_rule`、`rollout_trace_path`。
4. 语义 sensor 只用于离线 scene context、case 合理性和 HTML 展示，不进入模型 prompt。
5. 采样必须覆盖多个 scan / episode / action horizon，不能单场景填满。

**禁止再使用固定矩形框 depth quantile 当 GT。** 这类启发式会把楼梯、边缘、负空间、天花板或无关墙面误当成 clearance，不够格做 oracle。

**v1 可以使用粗语义上下文，但不做精细 object grounding。** MP3D/Habitat semantic 只用于“楼梯/门口/走廊/开阔区”等场景语境和 HTML 分析；核心 GT 仍由 rollout outcome 决定。不要问精细 instance/bbox 级 object QA，除非已有可靠 semantic source。

### 5.2 备选 / v2 路线：depth-corridor 或 navmesh 诊断

如果后续需要更细的几何诊断，可以补两个后端：

```text
depth-corridor backend: 用 depth/pose 反投影估局部走廊求交，只作可见几何诊断
navmesh backend: 按 radius 重算 navmesh，做更硬的 swept-cylinder / passability oracle
```

但当前 v1 的主线是 simulator rollout：它直接解决“站在楼梯口往前走会掉下去吗”这类 depth-corridor 难以可靠标注的问题。所有路线对模型都只暴露 RGB + question。

---

## 6. 可见性与 ambiguity 过滤

核心题只问“当前可见局部空间”的后果，不问完整真实世界安全性。

必须保存并过滤：

```text
start_pose_valid = true for the chosen body profile
rollout_trace_path exists and is replayable
collision / stopped_early / height_delta_m / progress_ratio fields are present
ambiguous = false
question uses coarse labels, not exact centimeter-level distance

# 阈值题/排序题专属 margin gate（yes/no 与 ranking 最怕阈值噪声）
Action-Horizon Collision:  progress_ratio / stopped_early / hazard_type must be stable under repeat rollout
Directional Rollout Comparison: top1 actual_distance_m - top2 actual_distance_m must exceed a coarse margin
Body Counterfactual Flip: small-body rollout progress must be >= large-body rollout progress under the same start/action
```

> **v1 oracle 的诚实边界（必须写进论文）：** simulator rollout 是离线 GT，不代表模型看到了 rollout 后的未来图像。题目必须问“从当前图像判断这个短动作序列大概会怎样”，不能把隐藏长程导航能力伪装成单图能力。

discard / mark ambiguous：

- simulator 起点对当前 body profile 不合法。
- rollout trace 缺失或不可复算。
- yes/no、排序或粗距离标签贴近阈值，重复 rollout 或扰动后不稳定。
- depth hole、玻璃/镜面、极细障碍、overhang 或图像证据不足。
- 楼梯 / 台阶 / 下行落差 / 无地面支撑不应被当成普通“前方畅通”；simulator rollout 若显示 height drop / stopped early，应进入 hazard 或 feasibility 类。
- 方向排序中两个方向距离近似 tie，除非 QA 显式包含 “about the same” 选项。

原则：可以难，但必须视觉可判定；不能把隐藏空间预测伪装成单图能力。

### 6.1 数据集级 answer-balance gate（防盲猜捷径）

上面是 per-case 过滤；还须一道 **dataset 级**闸门，否则 blind/majority 会高（违反 H2 与 §10 生死门第 2 条）：

```text
每个类别内，单一答案占比 <= 1 / n_options + 0.15
  Forward Body Clearance: 4 选项，单选占比 <= 0.40
  Action-Horizon Collision: yes/no，单类占比 <= 0.65
  Directional Sweep Ranking: 3 选项，单选占比 <= 0.48
  Body Counterfactual Flip: 3 选项（both-safe / small-only / neither-safe）三类均衡，单选占比 <= 0.48
  First-Contact Region: 4 选项（lower-left / center / right / no-contact），单选占比 <= 0.40
```

> **不设 `only large can pass`：** 同 pose / 同 action / 同相机、只变 radius 的圆柱设定下，large 能过则 small 必能过（radius monotonicity，见 §7）。强行要求该选项有样本 = 制造不物理的标签。它只能作为干扰项考语言先验，不进平衡要求。

不达标必须**继续采样或下采样多数类**，不能直接交付。Body Counterfactual Flip 还须满足 §7 的 no-flip controls。

---

## 7. Body Counterfactual 规则

T4 / Body Counterfactual 是最强武器，但必须干净。

Flip case 应满足：

```text
start pose 对 small/medium/large body 都合法
small body rollout completes or makes high progress
large body rollout collides, stops early, or triggers visible hazard
the action sequence, start state, and initial RGB are identical
rollout trace and semantic context are saved for both bodies
```

必须同时采 no-flip controls：

- small 能过，large 也能过；
- small 不能过，large 也不能过；
- large 更短但 label bin 不翻转；
- direction ranking 不因 radius 改变。

否则模型可以学到 `large body -> blocked`、`small body -> pass` 的分布捷径，H3 不干净。

**Radius monotonicity sanity check（同时是 oracle 自检）：** v1 只变 radius，GT 必须满足

```text
r_small <= r_large  =>  progress(small) >= progress(large) or small no worse than large   (容差内)
```

即小身体不应比大身体更早失败。违反单调性的配对一律丢弃或标 `oracle_error`——它要么是 simulator/body 配置 bug，要么是不物理的标签。这条 check 既保证 H3 干净，也是 paper-level 的 GT 质量证据。

---

## 8. QA Prompt 原则

模型 prompt 只包含：

- body 参数：radius / width / height；
- 动作假设：前进几步、左转/右转多少度、是否继续前进；
- 粗 3D 参数：约多少米 / 多少 body-widths / 左右约多少度；
- 可确定性评分的回答格式：二值、粗范围、方向短答、body counterfactual、hazard 短答。选择题可以用，但不是默认唯一形式。

禁止把场景答案写进文字：

- 禁用 `clear`、`blocked`、`wider`、`narrower`、`solid face`、`open corridor`、`just ahead` 等泄答案词。
- 场景解释、几何解释、可见证据说明只能进入 display-only metadata / HTML，不进入被测 prompt。

示例模板：

**Forward Body Clearance**

```text
机器人半径约 0.25 米，高 1.5 米。
只看这张第一视角图，如果它从当前位置直接向前移动约 1 米，
它大概会顺利推进、很快停住，还是出现明显风险？请用一句话回答。
```

**Directional Sweep Ranking**

```text
机器人半径约 0.25 米。
从当前视角出发，比较三个动作：左转约 15 度后前进、直接前进、右转约 15 度后前进。
哪一个方向在实际执行后能推进得更远？
```

**Body Counterfactual**

```text
同一张图、同一个起点、同样向前移动约 1 米。
半径 0.10 米的小机器人和半径 0.40 米的宽机器人，哪个更可能完成这个动作？
可以回答：两个都可以 / 只有小机器人可以 / 两个都不适合。
```

> v1 中 height 固定，counterfactual 只变 ground-plane footprint radius；prompt 不得暗示在测身高。三选一（去掉物理上不可能的 `only Robot L` 作为强制平衡项，见 §6.1）。

**Action-Horizon Collision**

```text
机器人半径约 0.25 米。
如果它先左转约 30 度，再连续前进 3 步，
这个短动作序列大概率能完成吗？如果不能，主要会因为什么失败？
```

**Local Hazard Recognition**

```text
机器人半径约 0.25 米。
如果它从这里继续向前走几步，最需要担心的局部风险是什么？
请回答：碰撞、下台阶/落差、地面支撑不足，或没有明显风险。
```

**First-Contact Region**

```text
机器人半径约 0.25 米。
如果它从当前视角继续向前移动并发生第一次接触，
这个接触大概会出现在画面左下、中下、右下，还是这个短动作内没有明显接触？
```

> 加 `no visible contact` 选项，否则 “until first physical contact” 的措辞会泄露“这题一定撞”。该类是诊断附加（见 §10），不进生死门核心。

---

## 9. Baselines & Diagnostics

不要只跑 MLLM。至少保留：

| Baseline | 作用 |
|---|---|
| random / majority | 基础下限 |
| blind text-only | 验证 prompt 没泄露答案 |
| radius-only | 验证 body 分布没有捷径 |
| action-only | 验证方向分布没有捷径 |
| center-ray depth heuristic | 检查是否只看中心深度就够 |
| floor-patch / corridor-width heuristic | 检查传统几何启发式能否解 |
| M1 RGB+text VLM | 主结果 |
| M2b RGB+sweep overlay VLM | 诊断是否不懂 footprint / 碰撞 |
| M3 RGB+depth VLM | depth 是否补救 |
| M4 geometry oracle | 标签上界 |
| human small set | 证明题目对人可判定 |

核心指标：

- Accuracy；
- **False-Safe Rate**：危险动作被判断为安全的比例；
- Embodiment Sensitivity：同图换 body 后模型是否翻转；
- Shortcut Gap：`Acc(M1)-Acc(M5/blind)`；
- Oracle Gap：`Acc(M4)-Acc(M1)`；
- Counterfactual Pair Consistency。

M2b sweep overlay 是诊断，不是主任务。主结果必须是 M1：RGB + body/action text。

---

## 10. Demo 生死门槛

第一版 demo 的目的不是把任务铺满，而是判断这条线是否成立。

建议裁决标准：

```text
1. Simulator rollout label stability >= 95%
   例如同 seed / 同 start state / 同 action sequence 可复算，轻微采样扰动不改变粗标签。

2. Blind / radius-only / action-only 接近随机或明显低于 M1
   如果 blind 很高，说明模板或 label 分布泄露。

3. Human 明显高于最强 MLLM
   如果人也做不好，说明题视觉不可判定。

4. MLLM 与 oracle/human 有明显 gap
   至少 15-25 points，才有诊断价值。

5. T4 / body counterfactual 上模型明显不敏感
   同图换 body 后，模型答案不随 GT 翻转。
```

**生死门核心只看 4 个核心类**：Forward Body Clearance / Action-Horizon Collision / Directional Sweep Ranking / Body Counterfactual Flip。**First-Contact Region 是 optional diagnostic**——region bin 在透视和稀疏 depth 下抖动大、首碰常是身体侧边擦边而非点接触，它可以进 HTML 展示，但不得决定项目生死。

如果 T4（Body Counterfactual Flip）成立，即使其余核心类一般，也有论文价值：主打 **body counterfactual failure**。如果只 Forward/Action-Horizon 成立而 T4 不成立，论文会弱很多。

---

## 11. Related Work 定位

| 近邻 | 它测什么 | 我们的差异 |
|---|---|---|
| TouchSafeBench | VLM collision grounding；Habitat 3.0，多视角 RGB-D，episode / trajectory / contact label | 我们是 single RGB + hypothetical ego action + body counterfactual swept-volume |
| CapNav | capability-conditioned route-level indoor navigation；tour video + graph + mobility profile | 我们没有 route/goal/SR/SPL，只问当前图一个局部 action sweep 后果 |
| ENACT | egocentric action consequence / world modeling，偏长程交互和 scene/action sequence | 我们只预测当前可见局部空间内 ego-body collision sweep |
| EXPLORE-Bench | 初始图 + 长动作序列预测最终场景状态 | 我们预测 ego 自身身体扫掠后果，不预测场景状态变化 |
| COPILOT | egocentric video collision prediction/localization | 我们是 MLLM VQA，single-frame，body-radius counterfactual |
| PhysBench | 泛 physical world understanding | 我们不做 object physics，只做 ego-body swept-volume consequence |
| A4Bench / affordance benchmarks | 泛 affordance perception | 我们定义明确几何算子 `Intersect(Body ⊗ Action, Scene_geometry)`，不是语义 affordance |

审稿安全说法：

> We do not claim novelty in collision checking. We use deterministic geometry to create a controlled diagnostic benchmark for single-image, action-conditioned, ego-body swept-volume consequence reasoning.

---

## 12. Agent 设计目标

Agent 的任务不是自己写 case，也不是替 pipeline 想象标签。Agent 只做两件事：

1. **设计共识**：讨论并冻结 `design.json`，包括分类、motivation 映射、QA 类型、反捷径原则。
2. **实例化共识**：讨论并冻结 `instantiation_spec.json`，包括 Habitat start-state 采样、动作序列、QA 模板、rollout GT 字段、semantic context policy、scoring rule、flip/balance gate。

随后由确定性 pipeline 执行：

```text
design.json + instantiation_spec.json
→ Habitat simulator-rollout generator
→ candidate manifest
→ validity gate
→ accepted manifest
→ HTML
```

硬约束：

- Subagent 之间不能看 hidden think，只能看 public JSON。
- 批评必须带 `proposed_fix`。
- 改完必须 re-review。
- `design.json` / `instantiation_spec.json` 是唯一事实源。
- LLM 不许发明最终 image-backed case。

---

## 13. Definition of Done（当前阶段）

- [ ] `goal.md` 定稿，定位收敛到：single-image, action-conditioned, ego-body swept-volume consequence reasoning within visible local space。
- [ ] Agent 能冻结 `design.json`：分类逐条对应 H1/H3，不复用 T1/T2/T4 作为最终 taxonomy 名字。
- [ ] Agent 能冻结 `instantiation_spec.json`：Habitat rollout GT、QA 模板、action horizons、semantic context、scoring、flip/balance gates 明确。
- [ ] Habitat demo 数据生成（两级标准，含 RGB / depth / semantic preview / rollout overlay / trace / oracle metadata）：
  - **HTML 定性 demo**：§4.1 五类每类 >= 10 accepted case（First-Contact Region 为 optional 诊断）。
  - **定量 sanity demo**（跑 baseline 才有统计意义）：4 个核心类每类 >= 30 accepted case，Body Counterfactual >= 30 pairs。
- [ ] 通过 §6.1 answer-balance gate（每类无单一答案超阈、Body Counterfactual 三类均衡）+ §7 no-flip controls + radius monotonicity check + §6 margin gate；样本跨多个 scan/episode，不是单场景。
- [ ] 两个中文 HTML 交付：
  - 设计页：目标、分类、每类测什么、GT 如何获得、如何防捷径；
  - case 页：每类真实 case，展示 image、QA、GT、rollout trace/overlay、semantic context、oracle metadata。
- [ ] 至少跑通 sanity baselines：random / majority / blind / geometry oracle；正式版再补 VLM、M2b、M3、human。
- [ ] 用生死门槛判断：进正式版 / 改设计 / 停止。

---

## 14. 后续可选

- **Evaluator loop**：跑 M1/M2b/M3/M4/M5/human，并生成效度门数字裁决。
- **Navmesh / 3D swept backend**：用 radius-conditioned navmesh 得到更硬 passability oracle 和更稳定的 body flip。
- **Geometry-supervised method**：用 sweep/collision/horizon 辅助监督改善 MLLM，在 benchmark 分数和下游 embodied collision 指标上验证。
