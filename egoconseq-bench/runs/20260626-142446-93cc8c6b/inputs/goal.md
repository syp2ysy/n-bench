# GOAL：EgoConseq-Bench
**一句话目标：** 造一个**单图 · 动作条件 · 身体归一化**的 ego-action consequence VQA benchmark，用来揭示——当前 MLLM 是否能**从当前可见的第一视角区域**中，预测"自己这个身体执行一个动作后会扫过哪里、会不会撞、能否通过"。并先落一个**轻量 demo** 判定这条线生死。

> 项目定位（一句话钉死）：**不是导航，不是空间关系，不是物体物理，而是"当前可见物理空间内的 ego-body swept-volume consequence reasoning"。**
> 本文件是北极星。后续 agent 据此讨论细节、迭代任务、实现 demo。所有取舍回到 §3 核心定义与 §4 焦点 7 条。

---

## 0. Context
- **判断**：MLLM 会输出动作、会描述场景，但未必懂"我这个身体动一下，物理世界/我自己会怎样"。这是 embodied agent 行动前最底层、却没人单独 isolate 测过的一格能力。
- **缺口**：现有 benchmark 各占一格但都不是这一格（§6）。需要受控诊断 benchmark 把它隔离出来单测。
- **产出**：(a) 可复现、sim 自动标注的 single-image action-consequence VQA；(b) 发现——前沿 VLM 系统性失败、且失败可被几何信息补救；(c) 可选接"几何监督注入"方法。
- **会场**：CVPR / ICLR。

---

## 1. 造什么
给模型 **一张第一视角 RGB + 身体描述 + 一个动作原语**，问这个动作的**物理后果**（碰撞/通行/哪边更安全/还能走几 body-width）。一张图、一个动作假设、一个答案。**不是导航。只评测当前可见/可推断区域。**

---

## 2. thesis & 三假设
**thesis**：MLLM 能"看懂空间事实"，但不能把 **自身朝向 + 身体形态 + 候选动作** 绑定到 **碰撞/通行后果**——其 action/空间能力很大程度是视觉-语义模式匹配，而非 embodied 几何 grounding。
- **H1 能力缺口**：前沿 VLM ≪ 几何 oracle。
- **H2 非语言捷径**：去图（只文字）≈ 随机。
- **H3 身体盲视**：同图只改 body，正确答案翻转；模型若不变 → 没把视觉空间与身体约束绑定。

---

## 3. ⭐ 统一核心定义
> **EgoConseq-Bench 评测：模型能否从单张 RGB，预测一个 ego 动作原语在身体约束下、且落在当前可见区域内的 *swept-volume 后果*。**

标签生成统一公式：
```
label = Intersect( Body ⊗ Action_trajectory ,  Scene_geometry )   # 仅取可见/可推断部分
```
5 个任务都是这条公式的不同读出口：

| Task | swept-volume 读出 |
|---|---|
| T1 | forward sweep 的**长度**（body-width 归一化） |
| T2 | 多方向 sweep 的**体积比较**（FOV 内小角度） |
| T3 | 复合 sweep（turn+forward）后果比较（±15°/±30°） |
| T4 | body 扰动下 sweep 的**可行性翻转**（do(body)） |
| T5 | sweep 能否穿过当前可见 free space |

> ⚠️ 诚实边界：swept-volume 求交=标准圆柱碰撞检测，**本身不是 novelty**；novelty 在"探测 MLLM 能否从单帧 RGB 做到"。它只作统一叙事+标签定义，不当技术贡献。

---

## 4. ⭐ 焦点死磕的问题（agent 每轮对照这 7 条）
1. **统一性 > 任务数**：新任务必须挂回 §3 公式，否则不加。宁可 4+1 干净任务，不要 8 个散任务。
2. **抗单目尺度攻击 = body-width 归一化**：所有"走多远"用 **body-width** 为单位，**`1 body-width = 2r`**（圆柱无 length，统一用宽度）。T1 用 `{<2 / 2–4 / 4–8 / >8 body-widths}`，不用米。答案无量纲，逼模型感知"空间相对我身体多大"。
3. **body = causal collision operator（不是 visual ruler）**：对外 headline 讲成**可干预因果算子** `do(body=r) → outcome flip`（H3）。它同时提供无量纲尺度归一化（机制层），但措辞用 "query-conditioned collision operator"，避免被说成 heuristic。
4. **反捷径三件套**：counterfactual 配对（换 body/换动作→flip）+ blind 控制（M5）+ 选项分布平衡。任务不满足"能造 flip 对"就降级。
5. **效度门是总开关**：oracle(M4)≈95%+ ∧ blind(M5)≈随机 ∧ 最强 VLM ≪ oracle ∧ **human/几何标注者 > VLM**。任一不过 → 改设计或砍任务。
6. **对近邻不可替代**：卖点统一收敛到 "single-image + counterfactual ego-body sweep + 仅可见区域"，一句话区分 CapNav（路线级/全局 video）、TouchSafeBench（多视角/观测当前碰撞）、ENACT（泛 affordance/场景演化）、PhysBench（object 物理，"physical world understanding"壳禁用）。
7. **【新】可见局部物理后果，而非隐藏空间推断**：只评测当前 egocentric RGB 中**可见或直接可推断**的局部 swept-volume 后果。若动作后果主要由图像外/遮挡后/转角后区域决定 → 不进核心测试，或标 `ambiguous`。保证测的是"对当前可见物理空间的 action-consequence grounding"，而非猜不可见世界。

---

## 5. 边界（不做）
- ❌ 无 rollout / path / SR / SPL / RL（严格 single-step）。
- ❌ 不做 object/scene 物理（PhysBench 地盘）。
- ❌ 不做绝对 metric 距离（用 body-width 替代）。
- ❌ 不要求预测图像外/遮挡后空间（见 §4-7）。
- ❌ 第一版不做室外/CARLA；**demo 先固定 height=1.5m**，只做 radius/width counterfactual（避开桌底/overhang 3D 复杂度）。

---

## 6. 撞车定位
| 近邻 | 它测什么 | 我们的差异 |
|---|---|---|
| PhysBench (ICLR'25) | object/scene 物理；video-image-text | 不问 ego 自身动作后果；禁用其壳 |
| CapNav (CVPR'26) | capability-conditioned **路线级**；tour video+graph | 我们 **单帧 ego-action 级**，body 当因果算子 |
| TouchSafeBench | VLM 碰撞 grounding；多视角 RGB-D，看**当前/即将**碰撞 | 我们 **单 RGB + counterfactual 假设动作** |
| ENACT | egocentric 泛 affordance / action-effect | 我们聚焦 **body-width ego-sweep 碰撞/通行** |
| EXPLORE-Bench | 单图+动作序列预测**场景状态**变化 | 我们预测 **ego 自身身体** sweep 后果 |

---

## 7. 任务族（统一化 4+1，含可见性/FOV 约束）
- **T1 Body-Width Forward Horizon**：向前走，第一次碰撞前还能走几 body-width？`{<2 / 2–4 / 4–8 / >8}`
- **T2 Visible Directional Sweep Ranking**：FOV 内 left-front / straight / right-front 哪个 collision-free sweep 最大？（核心用 ±15°/±30°，最多 ±45°）
- **T3 Composite Motion Consequence**：先转 ±15°/±30° 再前进，比直行更安全/更危险/差不多？（大角度仅 extension）
- **T4 Body Counterfactual Sweep**：小 body 能过的缝，大 body 能过吗？（含 no-flip 控制题防"总答不能"）
- **T5 Visible Passability**：这个 body 能否从**正前方可见 free space** 直接通过而不碰撞？（少用 semantic object，多用 physical constraint）

---

## 8. 输入模式 + 基线（含诊断升级）
| 代号 | 输入 | 作用 |
|---|---|---|
| **M1** | RGB + text（主设定） | 被测对象 |
| M2a | RGB + 动作箭头 overlay | 消融：是否懂动作方向 |
| **M2b** | RGB + **projected sweep corridor / footprint** overlay（画出身体会扫过的地面走廊，不给答案） | 区分"不懂方向 / 不懂空间碰撞 / 不懂 body width" |
| M3 | RGB + depth | 上界探针 |
| **M4** | 纯几何 oracle（GT depth+圆柱碰撞，非 MLLM） | 证任务可解、标签对（≈95%+） |
| **M5** | blind（只文字） | 证图必需、无语言捷径（≈随机） |
| **Human** | 少量人工（20–30 题，2–3 人） | 证"题对人可判定"，human > VLM |

---

## 9. Demo（第一阶段唯一交付，判生死）
- 场景：2–3 个 Habitat（HM3D/MP3D）。
- 题量：~60–100，**优先 T1/T2/T4**（直验 H1/H2/H3），T3/T5 附加；T3/T5 若可见性或语义歧义致效度门不过，不影响核心成立。
- body：radius `{0.10, 0.25, 0.40}`，**height 固定 1.5m**。
- 动作：forward；turn `±15°/±30°` + forward；direction ranking = left-front/straight/right-front。
- 标签：swept-cylinder collision → `max_safe_distance`（body-width）+ `visible_sweep_ratio` + `collision_point_visible` + `requires_hidden_geometry` + `ambiguous`。
- 每题存 RGB / depth / top-down / sweep-corridor 可视化。
- 基线：M1 (1–2 VLM) + M2b + M4 + M5 + human sanity。
- **效度门裁决**：oracle≈95%+ ∧ blind≈随机 ∧ best VLM≪oracle ∧ human>VLM → **线成立**，进正式版（finding 档 vs +method 档）；否则按失败模式修或停。同时在 counterfactual 对上验 H3。

### 9.5 数据生成 pipeline 规格
**原则**：几何 oracle 不是普通 baseline，而是数据引擎。它同时负责标签生成、歧义过滤、可见性判定和 M4 上界。整条 pipeline 必须是确定性几何/渲染代码，不能让 LLM 想象标签。第一版只处理静态场景，不含可移动目标。

**总流程**：
```
HM3D/MP3D 场景
→ 按身体半径重算 navmesh
→ 采样可导航 pose + yaw
→ 渲染 RGB / depth / pose
→ swept-cylinder oracle 标注碰撞、距离、通行性
→ depth+pose 投影做可见性判定
→ ambiguity filter
→ 中性 QA 实例化
→ 反事实配对与标签平衡
→ data_manifest.json 回灌 agent_loop
```

**取数**：
- 运行环境：`conda run -n qwen3vl_habitat ...`；已实测 `habitat_sim==0.2.4`。
- 默认 demo 数据：HM3D 0.2 val，路径 `/home/zhangshan/syp/datasets/versioned_data/hm3d-0.2/hm3d/val/`，优先使用 `hm3d_annotated_val_basis.scene_dataset_config.json`。MP3D 可作扩展，路径 `/home/zhangshan/syp/datasets/scene_datasets/mp3d/`。
- Habitat 坐标约定已实测：`FRONT=[0,0,-1]`，`UP=[0,1,0]`，`RIGHT=[1,0,0]`。marcher 在地面 navmesh 点 `(x,y,z)` 上运行；相机位置为该点加 `UP*1.5m`。
- Habitat-sim agent sensor height 固定 `1.5m`，RGB+Depth 必需，Semantic 可选。
- 默认分辨率 `640×480`，HFOV 约 `79°–90°`。
- 每个样本存 `position(x,y,z)`、`yaw`、相机内参 `K`、RGB、depth、top-down、sweep overlay。

**身体档位 = navmesh-per-radius**：
| 档位 | radius | width=2r | 机器人锚点 |
|---|---:|---:|---|
| small | 0.10m | 0.20m | 小型巡检/扫地机器人 |
| medium | 0.25m | 0.50m | 服务机器人 / Fetch、Stretch 级底盘 |
| large | 0.40m | 0.80m | 人形 / 大型轮式平台 / 人 |

每个 radius 用 Habitat `NavMeshSettings.agent_radius=r` 重新计算可行空间；不要把随包 navmesh 再配合 `clearance < r` 使用，否则会把默认 radius 内缩和目标 radius 再算一遍。已实测默认 navmesh 设置为 `agent_radius=0.10m`、`agent_height=1.5m`、`cell_size=0.05m`，所以 demo 中 small/medium/large 都统一重算 navmesh。T4/H3 的 same-image body counterfactual 由同一 pose、不同 radius 的几何结果给出。

**pose 采样**：
- 第一阶段先跑 survey mode：只采 pose/yaw 并计算每个 radius 的 forward max-safe-distance 分布，输出直方图，再最终冻结 T1 bin 阈值。
- 正式采样用拒绝/分层采样，而不是裸 `get_random_navigable_point()+random yaw`。目标是平衡 `{<2, 2-4, 4-8, >8}`、不同 radius、不同 scene、不同 yaw，并优先保留 T4 flip 对。
- 拒绝过近墙面导致的全 `<2`、大空地导致的全 `>8`、bin margin 太小、碰撞点在画外/遮挡后的 pose。

**oracle 标注**：
- 对每个身体 radius 先重算 navmesh，然后对 forward 或候选方向 `θ` 沿地面射线步进。
- 身体能占据某点当且仅当该点在对应 `r-navmesh` 上；首次 `pathfinder.is_navigable(point)==false` 即 swept-cylinder 首碰边界。
- 步长默认 `0.05m`，与 Habitat 默认 navmesh `cell_size=0.05m` 对齐；不需要更细粒度作为 demo 默认。
- 输出 `max_safe_distance_m`、`max_safe_distance_body_widths`、`collision_point_3d`、`oracle_trace_path`。
- T1 将 body-width 距离入 `{<2, 2-4, 4-8, >8}` bin；这些阈值在 survey 直方图后才冻结。
- T2 对 `{-30°, 0°, +30°}` 的 swept distance 排序。
- T3 比较 `turn θ + forward` 与 straight 的首碰距离。
- T4 同 pose/action 下改 radius，记录 flip/no-flip。
- T5 检查固定 horizon 内 swept corridor 是否全程无碰。

**可见性判定**：
- `collision_point_visible`：把 `collision_point_3d` 投影回当前相机，像素在画内且 depth buffer 与投影深度一致。
- `visible_sweep_ratio`：对 swept corridor footprint 采样，统计可被当前 depth 直接观测到的比例。
- `requires_hidden_geometry=true`：决定性碰撞/通行证据在画外、遮挡后、转角后或 depth 不可信区域。
- 核心样本保留条件：`visible_sweep_ratio >= 0.7`、适用时 `collision_point_visible=true`、`requires_hidden_geometry=false`、`fov_supported=true`、T1 `bin_margin >= 0.5 body-width`。

**中性 QA 模板**：
- prompt 只写身体参数、动作、答案选项。
- 场景描述、几何解释、可见证据说明只进入 display-only 字段，不进入模型 prompt。
- 禁止 prompt 中出现会泄答案的词：`clear`、`blocked`、`wider`、`narrower`、`solid face`、`open corridor`、`just ahead` 等。

**反捷径与平衡**：
- 同图换 radius / 动作自动生成 `flip_pair_id` 与 `counterfactual_group_id`。
- 按 task、body radius、action angle、scene、answer label、template 平衡。
- 必跑 blind M5、majority、radius-only、action-only、center-ray、largest-floor-patch / corridor-width heuristic。

**样本 schema**：
`case_id, task, scene_id, pose, intrinsics, rgb_path, depth_path, topdown_path, sweep_overlay_path, body_radius, body_width, body_height, action, answer_options, label, max_safe_distance_body_widths, collision_point_3d, collision_point_pixel, visible_sweep_ratio, collision_point_visible, requires_hidden_geometry, fov_supported, bin_margin_body_widths, ambiguous, ambiguity_reason, flip_pair_id, counterfactual_group_id, oracle_trace_path, geometric_explanation, visible_evidence_notes`。

---

## 10. Ambiguity filter（数据生成必过）
discard 或标 `ambiguous`：
- `visible_sweep_ratio` 太低（核心保留 `>0.7`）
- `collision_point` 不在当前可见区域 / `requires_hidden_geometry=true`
- `max_safe_distance` 距 bin 边界过近且图像证据弱
- 玻璃门/镜子/极细椅腿/被遮挡矮障碍/depth hole/图像外碰撞/3D overhang（height 固定下不入）
> 原则：要 hard boundary，但**不要 label-noisy / 视觉不可判定**的 boundary。难，但必须可判定。

---

## 11. 指标
精简（demo）：各任务 Acc、**False-Safe Rate**、Embodiment Sensitivity（H3）、Shortcut Gap=Acc(M1)−Acc(M5)（H2）、Oracle Gap=Acc(M4)−Acc(M1)（H1）。
补全（正式）：Collision Recall、序数 MAE/off-by-one、Monotonic Consistency、ECE、Counterfactual-Pair Consistency。
每样本 metadata：`{visible_sweep_ratio, collision_point_visible, requires_hidden_geometry, fov_supported, difficulty, ambiguous}`。

---

## 12. 开放问题（agent 讨论敲定）
1. body-width bin 阈值（`<2/2–4/...`）取多少最有区分度？demo 数据上扫。
2. T3 用比较式还是二值？两版各试。
3. body 档位几档够用又能稳定造 flip？
4. "边界"如何量化（距阈值多近算 boundary）？
5. counterfactual 对如何计分（配对一致性 vs 单题正确率）？

---

## 13. 第二幕（可选）
- **+method（PhysBench 模板）**：本 benchmark 暴露缺口 → 训练期把 forward-horizon/clearance/sweep-outcome/body-conditioned-collision 作辅助监督蒸进 MLLM（与当前 qwen3vl depth 注入实验同源）→ benchmark 分数↑ 且关联 R2R-CE/RxR-CE collision↓/SPL↑。
- **+室外**：CARLA，第二优先。

---

## Definition of Done（本阶段）
- [ ] Goal 定稿；§3 核心定义、§4 焦点 7 条获认可。
- [ ] 两个 HTML 交付：(a) 目标+分类+每类 10 case；(b) 设计理念+分类依据+能力考察。
- [ ] Demo 数据（~60–100 题，T1–T5，含 counterfactual 对、可见性 metadata）按 body-width 标签生成。
- [ ] M1/M2b/M4/M5/human 基线跑通，§9 效度门有数字裁决。
- [ ] 据裁决产出"进正式版 / 改设计 / 叫停"结论。
