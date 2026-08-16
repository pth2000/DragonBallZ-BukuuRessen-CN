# 术语表

本表收录《DRAGON BALL Z 舞空烈戦》本地化使用的 199 条专有名词，并按日文原名、官方英文版名称和项目简体中文译名对照。

同一招式可能同时出现在剧情获得提示、角色状态页和资料模式角色卡中；角色名也会跨路线与界面复用。术语表用于约束这些位置使用同一译名。

数据源文件为 [`data/glossary/terms.tsv`](../data/glossary/terms.tsv)，可用 `tools/check_glossary.py` 校验，见[校验](#校验)。

## 译名原则

**沿用官方简体中文常用译名。** 对已有稳定中文译法的角色和概念，优先采用读者熟悉的形式，不因日文读音差异另造译名。

**不跟随官方英文版的改名。** 官方英文版对部分专有名词做了本地化改动，中文版不跟随。例如，`ミスター・サタン` 在英文版中改为 `Hercule`，中文仍按原名译为“撒旦先生”。

**保留原文中已有的英文。** 日版本身使用英文或罗马字的部分（栏目名、角色名牌、通关横幅）不译，详见[界面资源盘点](tech/ui/resource-audit.md)。

**优先保证低分辨率可辨识度。** 正文字号仅 12 像素，笔画密集的字符可能连成大面积像素。同义表达可选时，优先采用笔画较少、结构较清晰的写法。

## 角色

共 41 条，取自剧情对白中的说话人字段。

| 日文 | 官方英文 | 简体中文 |
| --- | --- | --- |
| １６号 | Android #16 | 16号 |
| １７号 | Android #17 | 17号 |
| １８号 | Android #18 | 18号 |
| クリリン | Krillin | 克林 |
| ネイズ | Neize | 内兹 |
| リクーム | Recoome | 利库姆 |
| グルド | Guldo | 古尔多 |
| クウラ | Cooler | 古拉 |
| ジース | Jeice | 吉斯 |
| ギニュー | Ginyu | 基纽 |
| ドドリア | Dodoria | 多多利亚 |
| 天津飯 | Tien | 天津饭 |
| バビディ | Babidi | 巴比迪 |
| バータ | Burter | 巴特 |
| バーダック | Bardock | 巴达克 |
| ブルマ | Bulma | 布尔玛 |
| ミスター・ブウ | Buu | 布欧先生 |
| ブロリー | Broly | 布罗利 |
| パラガス | Baragus | 帕拉伽斯 |
| コルド大王 | King Cold | 库尔德王 |
| フリーザ | Frieza | 弗利萨 |
| 悟天 | Goten | 悟天 |
| ゴテンクス | Gotenks | 悟天克斯 |
| 悟空 | Goku | 悟空 |
| 悟飯 | Gohan | 悟饭 |
| ミスター・サタン | Hercule | 撒旦先生 |
| メカフリーザ | Frieza | 机械弗利萨 |
| ドクター・ゲロ | Dr.Gero | 格罗博士 |
| ピッコロ | Piccolo | 比克 |
| ビーデル | Videl | 比迪丽 |
| サウザー | Sauzer | 沙维扎 |
| セル | Cell | 沙鲁 |
| トランクス | Trunks | 特兰克斯 |
| 界王 | Kai | 界王 |
| 神龍 | Syenron | 神龙 |
| ザーボン | Zarbon | 萨博 |
| ベジータ | Vegeta | 贝吉塔 |
| ダーブラ | Dabura | 达普拉 |
| メタルクウラ | Metal Cooler | 金属古拉 |
| ヤムチャ | Yamcha | 雅木茶 |
| 魔人ブウ | Buu | 魔人布欧 |

## 招式

共 97 条，取自资料模式角色卡与角色状态页。

| 日文 | 官方英文 | 简体中文 |
| --- | --- | --- |
| ＭＡＸバスター | MAX Buster | MAX爆裂炮 |
| ハイドラスマッシャー | Hydra Smasher | 九头蛇粉碎击 |
| ２０倍界王拳 | Level 20 Kaioken | 二十倍界王拳 |
| 余裕 | Relax! | 从容 |
| ギャリック砲 | Galick Gun | 伽力克炮 |
| ギャリックファイヤー | Garlic Fire | 伽力克烈焰 |
| 元気玉 | Spirit Bomb | 元气弹 |
| フォトンウェイブ | Photon Wave | 光子波 |
| フォトンブラスト | Photon Blast | 光子爆破 |
| フォトンストライク | Photon Strike | 光子突袭 |
| フォトンブリッツ | Photon Blitz | 光子闪击 |
| フルパワーラッシュ | Full Power Rush | 全力猛攻 |
| ネイズサイクロン | Neize Electron | 内兹旋风 |
| ネストアイス | Nest Ice | 冰巢 |
| リクームイレイザーガン | Recoome Boom | 利库姆毁灭炮 |
| アトミックブラスト | Atomic Burst | 原子爆裂 |
| ダブルバスター | Double Buster | 双重爆裂 |
| 双龍弾 | Twin Dragon Shot | 双龙弹 |
| 吸収 | Absorption | 吸收 |
| ナイトメアブラスト | Nightmare Blast | 噩梦爆破 |
| ヘルブレス | Hell Bless | 地狱吐息 |
| ビッグバンアタック | Big Bang Attack | 大爆炸攻击 |
| ビッグバンバースト | Big Bang Burst | 大爆炸爆裂 |
| イノセンスキャノン | Innocence Cannon | 天真加农炮 |
| セルジュニア乱舞 | Cell Junior Vance | 小沙鲁乱舞 |
| ギガンティックスパイク | Gigantic Spike | 巨型尖刺 |
| コルドスマッシュ | Ghost King | 库尔德重击 |
| アークブラスト | Arc Blast | 弧光爆破 |
| アサルトレイン | Assault Rain | 强袭骤雨 |
| ドーレプレッシャー | Doray Pressure | 德雷重压 |
| サイコトライアングル | Psycho Triangle | 念力三角阵 |
| サイコブラスト | Psycho Blast | 念力爆破 |
| アングリーエクスプロージョン | Angry Explosion | 愤怒爆炸 |
| 操気弾 | Soukidan | 操气弹 |
| クレセントソード | Crescent Sword | 新月剑 |
| ファイナルエクスプロージョン | Final Explosion | 最终爆炸 |
| ファイナルブラスター | Final Blaster | 最终爆破 |
| ファイナルブリッド | Final Bleed | 最终连弹 |
| マシーナリーレイン | Machine Rain | 机械暴雨 |
| コア・スマッシュ | Core Smash | 核心重击 |
| ハッピースウィーツ | Happy Sweets | 欢乐甜点 |
| デスビーム | Death Beam | 死亡光束 |
| デスボール | Death Ball | 死亡弹 |
| デスジャンク | Death Junk | 死亡残骸 |
| デスウェーブ | Death Wave | 死亡波 |
| デスブラスター | Death Blaster | 死亡爆破 |
| 気合連弾 | Super Shots | 气合连弹 |
| 気円連斬 | Kienrenzan | 气圆连斩 |
| ゼクスブレイカー | Zex Breaker | 泽克斯破坏击 |
| 流星気功弾 | Ryuuseikikoudan | 流星气功弹 |
| メテオバースト | Meteor Burst | 流星爆裂 |
| 激烈光弾 | Gekiretsukoudan | 激烈光弹 |
| 激烈破弾 | Gekiretsuhadan | 激烈破弹 |
| 激烈魔閃弾 | Gekiretsumasendan | 激烈魔闪弹 |
| 激絶乱魔 | Gekizeturama | 激绝乱魔 |
| バスターブレード | Buster Blade | 爆裂剑 |
| バスターキャノン | Buster Cannon | 爆裂加农炮 |
| ブラスターメテオ | Blaster Meteor | 爆裂流星 |
| ブラスターシェル | Blaster Shell | 爆裂炮弹 |
| クラッカーフォーメーション | Cracker Formation | 爆裂阵形 |
| 特戦隊ストーム | Ginyu Storm | 特战队风暴 |
| レイジングラッシュ | Raging Rush | 狂怒连击 |
| マッドキルダイブ | Mad Kill Dive | 狂杀俯冲 |
| ラッシュブレード | Rush Blade | 疾冲剑 |
| ラピッドショット | Rapid Shot | 疾速气弹 |
| アイビーム | Eye Beam | 眼部光线 |
| 神魔伏滅 | Shinmafukumetsu | 神魔伏灭 |
| アルティメットウェーブ | Ultimate Wave | 究极冲击波 |
| ウルトラ超サイヤ人 | Ultra Super Saiyan | 究极超级赛亚人 |
| アルティメットブリッツ | Ultimate Blitz | 究极闪击 |
| クラッシャーボール | Crasher Ball | 粉碎球 |
| ファイナルフラッシュ | Final Flash | 终极闪光 |
| フィニッシュバスター | Finish Buster | 终结爆裂 |
| 勝利のＶサイン | V For Victory | 胜利V字手势 |
| ビクトリーキャノン | V Cannon | 胜利加农炮 |
| エナジードレイン | Energy Drain | 能量吸收 |
| エネルギー吸収バリア | Absorbtion Barrier | 能量吸收屏障 |
| エナジーマイン | Energy Mine | 能量地雷 |
| サウザーブレード | Sauzer Blade | 沙维扎利刃 |
| プラネットゲイザー | Planet Geyser | 行星喷泉 |
| プラネットバースト | Planet Burst | 行星爆裂 |
| Ｓ．Ｇ．Ｋ．Ｂ． | Super Ghost Bomber | 超级幽灵炸弹 |
| Ｓ．Ｇ．Ｋ．Ａ． | S.G.K.A. | 超级幽灵神风攻击 |
| 超サイヤ人３ | Super Saiyan 3 | 超级赛亚人3 |
| 超かめはめ波 | Super Kamehameha | 超级龟派气功 |
| 超龍撃弾 | Super Shot | 超龙击弹 |
| 連続気合弾 | Continuous Shots | 连续气合弹 |
| エビルダンス | Evil Dance | 邪恶之舞 |
| イノシシアタック | Boar Attack | 野猪突击 |
| フラッシュセーバー | Flash Saber | 闪光剑 |
| 魔撃弾 | Magekidan | 魔击弹 |
| 魔激閃光弾 | Magekisenkoudan | 魔激闪光弹 |
| 魔空包囲弾 | Makankuuhouidan | 魔空包围弹 |
| 魔貫光殺砲 | Special Beam Cannon | 魔贯光杀炮 |
| 魔閃光 | Demon Flash | 魔闪光 |
| 魔閃烈弾 | Masenretsudan | 魔闪烈弹 |
| かめはめ波 | Kamehameha | 龟派气功 |

## 特殊能力

共 36 条。

| 日文 | 官方英文 | 简体中文 |
| --- | --- | --- |
| １００％発動 | 100% Activation | 100%全力 |
| １６号 | Android #16 | 16号 |
| １７号 | Android #17 | 17号 |
| デンデ | Dende | 丹迪 |
| 余裕 | Relax | 从容 |
| 再生能力 | Regeneration Ability | 再生能力 |
| ライバル意識 | Rival Awareness | 劲敌意识 |
| 復活 | Revive | 复活 |
| ドドリア | Dodoria | 多多利亚 |
| 天津飯 | Tien | 天津饭 |
| プライド | Pride | 尊严 |
| セルジュニア | Cell Jr. | 小沙鲁 |
| バーダック | Bardock | 巴达克 |
| 強撃打 | Power Shot | 强力击打 |
| 怒り | Angry | 愤怒 |
| 打倒カカロット！ | Defeat Kakarot! | 打倒卡卡罗特！ |
| ミスターサタン | Hercule | 撒旦先生 |
| 逆上 | Frenzy | 暴怒 |
| 永久エネルギー炉 | Infinite Energy Type | 永久能量炉 |
| 汚名返上 | Honor Redeemed | 洗刷污名 |
| 潜在能力開放 | True Potential | 潜在能力解放 |
| スペシャルファイティングポーズ | Special Pose | 特别战斗姿势 |
| ネコマジンＺ | Neko Majin Z | 猫魔人Z |
| 界王拳 | Kaioken | 界王拳 |
| 真の力の開放 | True Power Unleashed | 真力解放 |
| 瞬間移動 | Instant Transmission | 瞬间移动 |
| 神龍 | Shenron | 神龙 |
| 勝利のＶサイン | V for Victory | 胜利V字手势 |
| エナジー吸収バリア | Absorption Barrier | 能量吸收屏障 |
| 自爆 | Self-Destruct | 自爆 |
| ザーボン | Zarbon | 萨博 |
| 超サイヤ人 | Super Saiyan | 超级赛亚人 |
| 超サイヤ人１．５ | Super Saiyan 1.5 | 超级赛亚人1.5 |
| ダーブラ | Dabura | 达普拉 |
| ヤムチャ | Yamcha | 雅木茶 |
| 魔導師バビディ | Babidi | 魔导师巴比迪 |

## 团队必杀技

共 25 条。

| 日文 | 官方英文 | 简体中文 |
| --- | --- | --- |
| ギャリックバスター | Garlic Buster | 伽力克爆裂 |
| フリーズストーム | Freeze Storm | 冰冻风暴 |
| ツインソードスラッシュ | Twin Sword Slash | 双剑斩 |
| ツインドレイン | Twin Drain | 双重吸收 |
| ダブルアタック | Double Attack | 双重攻击 |
| ダブル気円斬 | Dual Destructo-Disk | 双重气圆斩 |
| ヘルズスパイラル | Hell Spiral | 地狱螺旋 |
| 地球の戦士たち | Warriors of Earth | 地球战士们 |
| セルジュニア乱舞 | Cell Junior Dance | 小沙鲁乱舞 |
| アウトサイダーショット | Outsider Shot | 异端冲击 |
| バレーボールアタック | Volleyball Attack | 排球攻击 |
| サタン大活躍 | Hercule Attack | 撒旦大显身手 |
| ダークソードスラッシュ | Dark Sword Slash | 暗黑剑斩 |
| 気の開放 | Energy Unleashed | 气之解放 |
| クラッカー・フォーメーション | Cracker Formation | 爆裂阵形 |
| 親子かめはめ波 | Family Kamehameha | 父子龟派气功 |
| 絶対悪 | Absolute Evil | 绝对邪恶 |
| ブラインドメテオ | Blind Meteor | 致盲流星 |
| 超元気玉 | Super Spirit Bomb | 超级元气弹 |
| 超ベジットソード | Super Bajit Sword | 超级贝吉特剑 |
| 超絶かめはめ波 | Ultimate Kamehameha | 超绝龟派气功 |
| ボディチェンジスペシャル | Body Change Special | 身体互换特别版 |
| ギャラクティカドーナツ | Galactic Donuts | 银河甜甜圈 |
| 魔連撃 | Evil Shot | 魔连击 |
| 魔閃光殺砲 | Special Beam Cannon | 魔闪光杀炮 |

## 原文的拼写差异

游戏原文本身在几处存在拼写不一致，中文统一为同一译名：

| 简体中文 | 日文原文的两种写法 |
| --- | --- |
| 撒旦先生 | `ミスターサタン` / `ミスター・サタン` |
| 爆裂阵形 | `クラッカーフォーメーション` / `クラッカー・フォーメーション` |
| 能量吸收屏障 | `エナジー吸収バリア` / `エネルギー吸収バリア` |

官方英文版同样存在此类差异，例如 `Special Beam Cannon` 与 `Special Beam Canon`、`Absorption` 与 `Absorbtion`、`Android #16` 与 `#16`。表中各取其一。

## 已修正的一致性问题

`サウザー` 在剧情中译作“沙维扎”，但其招式 `サウザーブレード` 曾在资料模式角色卡中译作“萨乌扎利刃”，导致角色名在复合词中出现两种写法。

完整词条的一对一比较无法识别此类问题，因为角色名和招式名是不同原文。招式已统一为“沙维扎利刃”，并在校验器中增加复合词一致性检查。

## 校验

```powershell
uv run python tools/check_glossary.py
```

检查内容：

1. 同一日文原名没有对应多个中文译名；
2. 表中每个译名仍被至少一张翻译表引用；
3. 角色名出现在招式名内部时，写法与角色条目一致。

## 扩充

新增译名时，先查本表是否已有同一原名的既定译法；确无先例再新拟，并同时更新 `data/glossary/terms.tsv` 和相应的翻译表。文本规则见[翻译规范](TRANSLATION.md)，新增用字还需按[字体工作流](tech/FONTS.md)确认字形与编码槽。
