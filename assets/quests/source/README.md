# 无限任务百科

网站入口：<https://sduckyduck.github.io/wow-forever-talents/#/quests>。先交付任务百科，路线随后完善，按用户 2026-10-04 的优先级执行。

当前收录公开 Forever 任务目录的 5,372 个独立 ID，包括占位和未确认条目。客户端 1.60.1.70205 的 QuestV2 有 6,609 个 ID；这只用于对账，不能证明任务已开放，也不能提供完整服务器任务文本。默认隐藏仅 ID、旧资料与占位条目，仍可在高级选项查看。

## 给新人使用的入口

- 全部任务：按中英文名、ID、NPC、奖励搜索，筛选联盟/部落、职业、地区、任务等级、任务类型和版本改动。
- 副本出发准备：选择副本与阵营，展开副本关联任务和全部已知上游前置；清单列出接取 NPC、所在地区及坐标，可下载备份。任选分支需要按角色条件挑选，不能把所有分支当成必做。
- 完成记录：手动勾选、本机保存、JSON 导出和合并导入。尚未与游戏角色自动同步。
- 单条详情：目标、接取与交付、物品触发来源、怪物/物体分布、前后置、互斥、可选引导、职业种族专业声望等条件、固定/任选奖励、基础经验、金钱与声望。可复制独立链接并下载完整任务 JSON。

地图直接使用网站已有的客户端地形瓦片。接取 `!`、交付 `?`、怪物 `⚔`、物体 `◆`、其他目标 `●` 分层开关；不把副本内 `[-1,-1]` 哨兵当作室外坐标。地图上的多个点代表分布；没有坐标的副本目标仍保留所属副本。Leaflet 1.9.4 已在本地提供，不依赖外部 CDN 才能显示地图。

## 数据来源与覆盖

1. 本机客户端 DB2：产品 `wow_classic_beta`，build `1.60.1.70205`，locale `zhCN` / 64。导出文件在 `output/wow-cinema/index/<build>-quests-zhCN/db2`、`<build>-quest-entities-zhCN/db2`、`<build>-worldzh/db2`。每个使用文件记录 SHA-256；`.build.info` 核对实际版本。
2. [QuestieDB 固定快照](https://github.com/Questie/QuestieDB/tree/9d39232dab48e35811a7cc02473c2f4e42b62ab6)：Forever 原始库、六个继承修正、generated delta、社区 trace、手工 Forever 修正，按上游规定顺序合并。保留各字段来源；只组合静态层，不把某个角色的动态修正套给所有玩家。
3. [Wowhead Forever](https://www.wowhead.com/forever/quests)：分等级递归拆分有数量上限的公开目录，只提取结构化事实。收录 5,372 条目录，737 条标记新增、451 条标记改动。239 条当前详情快照补充任务地图实体、坐标和物品事实。之后收到 HTTP 403，已停止进一步请求；抓取脚本收到 403/429 时也会停止。未复制全文剧情或评论。
4. 本机 Questie 的 `QuestieForeverDB`：72 条任务的事实观察，只提取任务标题、目标和地图点，不发布账号、角色、完成进度或设置。

QuestieDB 的初始坐标转换基于 Forever 1.60.1.69893，保持继承的世界位置，不能发现 NPC 搬迁。本站再用当前 70205 的地图框投影。经典任务前置没有具体新版本修正时标为参考；未记载前置不等于没有前置。新增中文名称、目标数量、服务器条件、掉落率、全部装备属性和全部室内楼层坐标仍有缺项。缺项台账在本地 `missing-fields.json`，公开覆盖及逐文件来源在 `assets/quests/manifest.json`。

不能把上述来源混称为全部由本机解包或已经逐条实机验证。`QuestLineXQuest` 的剧情顺序不作为强制前置。

## 维护与重新生成

在 `D:/wow` 下执行；Python 3.11 和 Node.js，Lua 5.1 由 `lupa==2.8` 提供。

```powershell
python -m pip install --target .cache/quest-deps lupa==2.8
python -X utf8 talent/quests/fetch_questiedb.py
python -X utf8 talent/quests/fetch_catalog.py
# 可选详情补充；遇到 403/429 停止，不绕过来源限制
python -X utf8 talent/quests/fetch_details.py --limit 200
python -X utf8 talent/quests/fetch_vendor.py
python -X utf8 talent/quests/build_catalog.py
node talent/tier-model/build_page.cjs
node talent/tier-model/build_site.cjs
node talent/tests/quest-audit.cjs
```

抓取器重用本地快照；`fetch_questiedb.py` 保持 `raw/questiedb/snapshot.json` 中的提交，不会默默换成上游最新版本。下一版更新要另建快照、比对变化，再修改版本与 DB2 路径。保存每次来源与缺项台账，优先补新任务、改动任务和副本前置。

发布前运行浏览器检查，然后用 `talent/site/publish.cjs` 同步至 `talent/pages` 的独立仓库并提交推送。不要发布 `raw` HTML、账号 SavedVariables 或整个游戏客户端。

`catalog-full.json` 是本地共同数据模型，任务以 ID 为主键；网站发布轻量索引、分片任务详情和按需实体分片。页面真源为 `talent/tier-model/ui/quest-model.js`、`quest-views.js`、`quests.css`，路由 `#/quests/<ID>`；不要直接修改生成后的 `index.html`。

## 随后的路线与自己的插件

数据模型已经把“任务事实”和“路线步骤”分开。路线步骤以后只引用任务 ID、动作（接取/做目标/交付/交通）、目标实体、适用阵营/职业/等级、所需前置和可替代步骤。角色日志、已完成任务、地图位置与背包决定当前步骤是否可用；不会把路线里的文字顺序变成任务前置。

建议插件第一版提供中文任务卡、当前目标的怪物/物品来源图标、自动完成检测和副本出发清单。路线箭头与目标图层同时存在；点击某一步能显示本步全部目标，而非只有编号。先采用 Questie/QuestieDB 数据适配层，随后逐步独立实现目标图层，避免同时运行时重复画点。

网站可以导出任务包/角色进度文件，插件通过 SavedVariables 保存游戏事实；本地转换器在退出或 `/reload` 后生成网站可导入的 JSON。WoW 插件不能直接请求网站 API，不设计虚假的即时云同步。

RestedXP 先作为本机路线适配器的输入，公开网站使用自己编写的路线。其[公开代码许可证](https://raw.githubusercontent.com/RestedXP/RXPGuides/main/LICENSE)与购买的路线内容需要分别检查；现阶段没有把付费路线全文复制到网站。现有本地适配工具可参考 `tools/rxp_quest_probe/README.md`，此轮未更改玩家安装的插件。

## 许可与检查

Questie 继承任务数据及中文词条保留原作者归属和 GPLv3 通知。任务数据转换与任务百科模块的可修改源文件随网站放在 `assets/quests/source/`；本地 `raw/questiedb/snapshot.json` / 公开 manifest 链接至原始输入的固定提交。客户端资产、Wowhead 元数据与 Questie 数据分别标明来源，不能将整个网站所有素材统称为 GPL。Leaflet 保留 BSD 通知。

验证：前置 AND/OR、负数强制前置、替代任务与循环；全量实体引用与坐标合法性；桌面与 390px 手机的明暗主题；副本准备；任务深链接；怪物/物体图层；当前新增任务坐标；完成记录刷新、导出和非法导入；返回原有天赋模拟器。截图和结果保存 `output/quest-audit/`。这些验证证明网站行为，不能代替任务实机验证。
