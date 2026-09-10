# Pokémon 动作审视 — 2026-09-10 当前版本

本文件取代旧动作笔记中“喷火龙转身飞远”的描述。当前方向：离地后向左前方飞来、逐渐放大、从左侧出画。Hero 和动作研究页使用同一份骨骼与轨迹代码。

| Before | After | Why |
| --- | --- | --- |
| 喷火龙离地后旋转约 197°，缩小并飞远 | 身体向左缓转约 41°，提前看向左前方，放大后从左边离场 | 视线、朝向、移动方向一致；移除无缘由的空中自转。[轨迹](../apps/web/scripts/scene-parts/pokemon-choreography.js.txt#L42) |
| 接触时只渐变脚踝目标；膝盖弯曲平面立即切换 | 整条髋—膝—踝关节链一起渐变接管；完全承重时继续固定脚趾 | 新增真实骨骼边界检查确实捕获了这个跳变；修复落地和离地的接缝。[关节接管](../apps/web/scripts/scene-parts/pokemon-characters.js.txt#L106) |
| 蹬地时，独立翼拍时钟可能恰好处于上收阶段 | 起飞阶段翼拍与腿部伸展共享进度，随后平滑恢复持续飞行翼拍 | 发力动作需要协调，不能双脚蹬地而翅膀随机反向。[翼拍](../apps/web/scripts/scene-parts/pokemon-characters.js.txt#L225) |
| 卡比兽触碰支撑后立即往上弹；下坠手脚重复摆动过多 | 先沉入软支撑，再回稳；肩、肘、腕依次回摆并衰减 | 保留沉重、柔软的身体反应，减少主动游泳般的挥动。[接触](../apps/web/scripts/scene-parts/pokemon-choreography.js.txt#L32) |
| 研究页只有两只角色，且每帧重设 canvas 大小 | 三只角色共用预览；¼ 倍播放、前后逐帧；仅尺寸变化时调整画布 | 能完整检查，而不会把连续动作仅当几个静态姿势验收。[研究页](../apps/web/scripts/scene-parts/pokemon-motion-review.html) |
| 卡片 hover 动画包含阴影重绘；CTA hover 未限制指针类型 | 卡片只过渡 transform；CTA 仅在精细指针 hover 时移动，减少动态偏好下静止 | 减少无必要绘制，并避免触屏粘滞 hover。[样式](../apps/web/scripts/scene-parts/pokemon-showcase.css#L17) |

## 当前判断

- **Feel-breaking regressions：** 旧离场方向和 IK 接管跳变已修复。不是单纯调慢播放来掩盖。
- **Performance：** 主 Hero 继续共用原时钟；角色投影大小改变的是 WebGL viewport，不是 DOM 布局。研究页不再每帧重置画布。喷火龙飞近时才将离屏纹理升到手机 768 / 桌面 1024，采用不同的进入/退出阈值避免反复分配。图表保持 transform/opacity 渐变。
- **Interruptibility & timing：** 滚动路径是无历史依赖函数；反向滚动返回相同进度的同一姿势。翼拍和呼吸仍随场景时钟继续，暂停会冻结。Hero 叙事由滚动控制，250/300 ms 的普通按钮预算不套用到跑动和飞行动作。
- **Origin, physicality & cohesion：** 皮卡丘保留已接受的原始跑步 clip；卡比兽保留“手先伸出 → 肩膀跟随 → 身体转动 → 越过支撑 → 下坠”；喷火龙保留伸腿、卸力、蓄力、蹬地顺序；根据后续反馈，离地改为腿部伸展后向后摆，脚尖随后朝后。靠近镜头时降低投影中心，避免高处卡片旁的脸过早藏进导航。
- **Accessibility：** 主 Hero 的暂停、减少动态偏好和隐藏页面暂停保持有效；研究页默认尊重减少动态偏好，循环播放需要主动开启。

**Approve — 通过本次本地动作审视。** 这是参考自然运动规律的角色动画，不是物理求解器或动作捕捉复刻；下表明确参考与创作之间的界线。本次没有发布、提交或 push。

## 自然参考与动作对应

| 角色 / 阶段 | 可回看的自然参考 | 用于本页的规律与边界 |
| --- | --- | --- |
| 皮卡丘：跑入、腾空、落脚、减速 | [Harvard Concord Field Station：跳鼠 500 fps 摄影](https://cfs.mcz.harvard.edu/news-media/jerboa)；[跳鼠步态研究](https://www.frontiersin.org/journals/bioengineering-and-biotechnology/articles/10.3389/fbioe.2022.804826/full) | 双足推进存在不同落脚与腾空组合。用来审视已有原始 run clip 的躯干、后肢与行进配合；没有把四足松鼠跑法硬套进皮卡丘，也没有宣称逐帧复刻跳鼠。现有 clip 保留。 |
| 卡比兽：伸手触碰身体、带动侧身 | [Jordan，1979：American Black Bear observational study，第 5 章](https://trace.tennessee.edu/server/api/core/bitstreams/b4d87b2e-dc2a-409a-b366-9705316ddb69/content) | 黑熊会用前爪和不同姿势清理、抓挠身体。“因为挠痒而滑落”是创作的因果段落，文献没有记录这一整段剧情。 |
| 卡比兽：翻滚、越过支点、着地回摆 | [Smithsonian：Bei Bei Plays in the Snow](https://nationalzoo.si.edu/animals/news/bei-bei-plays-snow)，[原始视频](https://www.youtube.com/watch?v=DANW0kPoy9s)，约 16–22 秒 | 原视频可见身体越过横木、四肢姿态随翻落改变，落下后继续滚动。参考接触顺序与身体重量；没有复制熊猫体型。原始睡眠 clip 保留，摆幅与阻尼属于动画调校。 |
| 喷火龙：接近、伸腿、接触、卸力、回稳 | [Roderick 等，eLife 2019，Video 2](https://elifesciences.org/articles/46415#video2) | 研究及九种落栖条件的慢动作区分空中、吸收冲量、锚定与调整阶段。翼的制动与腿部承重相接；应用到伸腿、接触渐变、下蹲卸力和尾部跟随。 |
| 喷火龙：看向目的地、接近路线 | [Harris's hawk 落栖轨迹研究，Nature 2022](https://www.nature.com/articles/s41586-022-04861-4) | 参考连续的接近路径和接近时保持视觉目标的需要。头先看左、身体稍后跟随，是服务用户指定左前方路线的动画设计，不是该论文测得的固定角度。 |
| 喷火龙：蓄力、蹬地、离地伸展 | [Chin & Lentink，鸟类起飞与降落的气动力研究](https://www.nature.com/articles/s41467-019-13347-3) | 起飞与减速不是同一种翼拍状态。离地前安排腿部发力和翼的下压；离地后保持伸展，再从髋部向后摆。阶段长度随滚动压缩，未声称对应真实速度。 |
| 喷火龙：飞行时后伸的双腿与脚尖 | [Cornell Lab：大蓝鹭飞行姿态](https://www.allaboutbirds.org/guide/great_blue_heron/id)；[Abourachid 等：鸟类起飞的三维腿部运动](https://pubmed.ncbi.nlm.nih.gov/29330588/) | 大蓝鹭飞行时双腿向后拖曳；起飞研究说明后肢关节伸展参与推进。不同鸟类巡航腿姿不同，本版选择后伸轮廓作角色参考。保留原始短腿比例和轻微膝弯，髋部先后摆，踝部延迟跟随，避免僵直锁膝。 |
| 喷火龙：下拍、折翼回收、翼尖滞后 | [Brown University：蝙蝠翼研究与视频](https://engineering.brown.edu/news/2013-02-20/brown-researchers-build-robotic-bat-wing) | 区分展开下拍与折叠回收；分配到原始翼根、肘部和翼尖骨骼。38% 下拍 / 62% 回收是本项目艺术参数，不是引用的实验数值。 |
| 喷火龙：重心变化时的尾巴与手臂 | [Lacava 等，JEB 2024：鼠尾平衡研究](https://journals.biologists.com/jeb/article/227/21/jeb247552/362590/The-role-of-mouse-tails-in-response-to-external) | 尾巴既可配重也可通过运动帮助稳定身体。应用为反向平衡、分段滞后，双臂则跟随胸部发力和卸力；六肢喷火龙没有可一对一套用的真实动物，全套配合是参考后的推演。 |

文字与视频参考均来自研究者或机构。未下载、重新分发参考影片。模型文件保持原始哈希和等比缩放。

## 验证与复看

- `pnpm --filter @pokecrack/web lint`、`typecheck` 通过。
- 三个 Hero 相关测试文件：22 项通过。覆盖左移、连续放大、保持前向、淡出前离开左边界、离地位置/速度连续、倒放、暂停及数据呈现。
- `node apps/web/scripts/verify-pokemon-characters.mjs` 通过：真实 r149 GLB、哈希、克隆骨架、脚趾承重位置、约 20 个阶段边界的逐节点连续性与反向一致性，以及完整动作范围的模型裁切检查。
- 浏览器检查包括研究页三只角色的关键姿势与逐帧；完整 Hero 的趋势章节、前进/反向滚动，桌面与 539 px 小屏构图。自动化检查能发现跳变、方向和裁切错误，不能替代对动物动作质感的判断。
- 本次变更位于工作树 `/Users/nixon/.codex/worktrees/bb70/PokeCrack`，分支 `codex/pokemon-kage-hero-local`。编辑了 choreography、characters、motion-review、showcase CSS、相关验证代码，以及构建生成的静态预览文件。

[完整 Hero](http://127.0.0.1:3017/) · [动作研究：慢放 / 逐帧 / 自然参考](http://127.0.0.1:3017/landing-pages/pokemon-motion-review.html)

## 后续腿姿修订验证

真实骨骼新增检查：进场飞行与离场飞行在三个翼拍时刻，左右踝都在髋部后方、脚尖都指向后方、上下腿夹角接近伸展；脚趾承重与阶段边界检查仍通过。浏览器检查已恢复，逐段复看了 0.43 离地、0.49 后伸与 0.53 飞近的姿态。主 Hero 与研究页均由相同片段重新生成。本次仍未提交或 push。

## 全身惯性与尾焰修订

这次将惯性补到全身，同时保留已经接受的跑动、抓挠滑落和左前方飞行路线：

- **皮卡丘**：原始 run clip 继续负责步幅与落脚；胸、头、手腕、三段耳骨与三段尾骨共享步态节奏，末端延迟。跑停和重新起步各有短促、衰减的回摆；站稳后不留下冻结的刹车倾斜。
- **卡比兽**：已有肩→肘→腕的落地反应继续向躯干、头、耳、脚趾和放松的手指传递。核心摆幅小、末端稍晚，抓挠的左手仍领先身体翻转。
- **喷火龙**：翼拍带动胸部，颈部稳定视线，手臂、腕、后伸的腿与脚尖稍后跟随。七段尾骨共享翼拍、卸力、蹬地和转向信号，逐段延迟，形成回摆；不再使用与发力无关的独立尾巴正弦摆动。
- **尾焰**：使用原模型自带的三段 `center_feeler` 骨骼，根部连在尾尖。依据分段尾骨的角速度与力臂估计尾尖运动，并叠加向后的相对气流、世界坐标向上的浮力方向和小幅尖端扰动。根部限制较多，尖端弯曲更自由。没有替换、拉伸或重导出模型，没有新增粒子计时器。

尾焰参考补充：[NASA — Studying Combustion and Fire Safety](https://www.nasa.gov/missions/station/iss-research/studying-combustion-and-fire-safety/)，说明浮力对火焰形状和闪烁的影响。尾部配重与平衡沿用上表 JEB 研究。延迟、幅度、气流强度均为角色动画参数；滚动映射使用确定性的节奏采样，不是实时流体求解或对动物运动的定量复现。

附加偏转在角色局部坐标内计算，移除外围 turntable 后再分解骨骼父变换，避免展示角度改变惯性方向。所有姿势由当前滚动进度和共享时钟求出；正向、倒放、重复停在同一帧均不积累偏转。

验证记录：

- 原始 GLB 哈希、运行中源骨骼与网格不变；角色克隆相互独立。
- 真实骨骼检查涵盖全身关节、尾焰三段、火焰根部与长度、空中上升方向、同一时刻站立/飞行时尾焰形状差异，以及暂停冻结。
- 脚趾承重、后伸双腿、阶段边界连续性、倒放与完整动作范围裁切检查通过；新增外围旋转下局部姿势不变的检查通过。
- 浏览器导出三只角色各 12 个连续阶段姿势复看，并检查小屏动作研究页与完整 Hero。研究页“自然动作参考”补入尾部平衡和 NASA 火焰资料。
- `lint`、`typecheck` 与 22 项 Hero 相关测试通过。静态 Hero、模型研究页和动作研究页均从同一角色源重新生成。

本次编辑：`apps/web/scripts/scene-parts/pokemon-characters.js.txt`、`pokemon-motion-review.html`、`apps/web/scripts/verify-pokemon-characters.mjs`、本记录，以及对应生成的三个 `apps/web/public/landing-pages/pokemon-*.html` 文件。工作树仍为 `/Users/nixon/.codex/worktrees/bb70/PokeCrack`，分支 `codex/pokemon-kage-hero-local`；没有 commit、push 或部署。
