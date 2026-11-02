#!/usr/bin/env python3
"""
WeChat 发布前敏感词扫描器
----------------------------
微信审核红线「不得不当使用国家机关、国家机关工作人员的名义或形象」的预检工具。
在任何文章发布到微信公众号草稿箱之前运行本脚本，拦截可能触发内容安全拦截的表述。

用法：
    python3 sensitive_scan.py --md <文件.md>
    python3 sensitive_scan.py --md <文件.md> --strict   # 连广义词也标黄(仅为提示，不阻止)

判定分级（读取 --html 可同时导出 HTML 报告用于人工复核）：
    🔴 REQUIRED 高置信红线 —— 直接触发「国家机关/国家机关工作人员名义或形象」拦截，必须处理
    🟡 WARN      需人工判断 —— 可能是正常商业/地缘叙述，也可能触发，建议复核
    🟡 IDEOLOGY  意识形态语境词 —— 不触发草稿接口拦截，但正式发布审核有不确定性，
                 提示评估是否按发布指南 §6.4 中性化改写微信构建文件（2026-09-04 新增）

退出码：
    0 = 无红线词
    1 = 发现 🔴 红线词（发布前必须处理）
    2 = 运行错误

注：本脚本只做文本预检，不负责替换；发现红线词后按发布指南的建议改写。
"""

import argparse
import sys
import re
import os

# -----------------------------------------------------------------------------
# 1. 高置信红线词（🔴 REQUIRED）
#    出现即基本必然触发微信「不当使用国家机关/国家机关工作人员名义或形象」拦截。
#    涵盖国家领导人姓名（正式姓名）、常见称呼、以及具体国家机关实名。
# -----------------------------------------------------------------------------
REQUIRED_WORDS = [
    # 国家领导人姓名（按可维护性分组；均为现任/近年公开领导人）
    # 中国共产党中央及国家领导人（常见误用为调侃对象）
    "习近平", "XI JINPING", "Xi Jinping", "xi jinping", "XI JIN PING",
    "李强", "赵乐际", "王沪宁", "丁薛祥", "李希", "韩正",
    "胡锦涛", "温家宝", "李克强", "朱镕基", "江泽民", "华国锋",
    "毛泽东", "邓小平", "薄熙来", "周永康", "令计划", "徐才厚",
    # 常见国家机关实名（提及即属「以国家机关名义」）
    "国务院", "国务院办公厅", "全国人大常委会", "全国政协", "中央军委",
    "中共中央", "中纪委", "中央纪委", "国家监察委", "最高人民法院", "最高人民检察院",
    "解放军", "中国人民解放军", "武警部队", "公安机关", "以习近平",
    "中南海", "天安门", "人民大会堂", "中办", "国办",
]

# -----------------------------------------------------------------------------
# 2. 广义词（🟡 WARN）
#    本身属中性商业/地缘叙述（如"中国市场""中国政府""地缘政治"），
#    单独出现通常不触发红线，但需人工判断是否在语境中构成对国家机关的影射。
#    列出来仅为「看一眼」，不判定为必须处理。
# -----------------------------------------------------------------------------
WARN_WORDS = [
    "中国政府", "国家领导人", "国家主席", "政府机构", "政府部门",
    "国务院", "部委", "机关单位", "国家机关", "官方媒体", "党媒",
    "国家形象", "政府形象", "中央号令", "政治局", "国务院国资委",
]

# -----------------------------------------------------------------------------
# 3. 意识形态语境词（🟡 WARN，2026-09-04 CI457 期沉淀，用户明确决策）
#    不触发草稿接口拦截，但正式发布审核有不确定性；出现即提示评估是否需要
#    按发布指南 §6.4「意识形态词汇中性化改写」处理（只改微信临时构建文件，
#    源文件保持忠实原文）。官方文本常用词（如"社会主义"）只提示、不拦截。
# -----------------------------------------------------------------------------
IDEOLOGY_WORDS = [
    "共产主义", "共产党", "社会主义", "斯大林", "波尔布特", "齐奥塞斯库",
]

# 键名映射：英文大小写变体归一后指向中文标签（用于输出）
DISPLAY_MAP = {
    "习近平": "国家领导人 · 习近平",
    "XI JINPING": "国家领导人 · XI JINPING",
    "Xi Jinping": "国家领导人 · Xi Jinping",
    "xi jinping": "国家领导人 · xi jinping",
    "XI JIN PING": "国家领导人 · XI JIN PING",
    "李强": "国家领导人 · 李强",
    "赵乐际": "国家领导人 · 赵乐际",
    "王沪宁": "国家领导人 · 王沪宁",
    "丁薛祥": "国家领导人 · 丁薛祥",
    "李希": "国家领导人 · 李希",
    "韩正": "国家领导人 · 韩正",
    "胡锦涛": "国家领导人 · 胡锦涛",
    "温家宝": "国家领导人 · 温家宝",
    "李克强": "国家领导人 · 李克强",
    "朱镕基": "国家领导人 · 朱镕基",
    "江泽民": "国家领导人 · 江泽民",
    "华国锋": "国家领导人 · 华国锋",
    "毛泽东": "国家领导人 · 毛泽东",
    "邓小平": "国家领导人 · 邓小平",
    "薄熙来": "落马官员 · 薄熙来",
    "周永康": "落马官员 · 周永康",
    "令计划": "落马官员 · 令计划",
    "徐才厚": "落马官员 · 徐才厚",
    "国务院": "国家机关 · 国务院",
    "国务院办公厅": "国家机关 · 国务院办公厅",
    "全国人大常委会": "国家机关 · 全国人大常委会",
    "全国政协": "国家机关 · 全国政协",
    "中央军委": "国家机关 · 中央军委",
    "中共中央": "机关 · 中共中央",
    "中纪委": "机关 · 中纪委",
    "中央纪委": "机关 · 中央纪委",
    "国家监察委": "机关 · 国家监察委",
    "最高人民法院": "机关 · 最高人民法院",
    "最高人民检察院": "机关 · 最高人民检察院",
    "解放军": "机关 · 解放军",
    "中国人民解放军": "机关 · 中国人民解放军",
    "武警部队": "机关 · 武警部队",
    "公安机关": "机关 · 公安机关",
    "以习近平": "机关用语 · 以习近平",
    "中南海": "场所 · 中南海",
    "天安门": "场所 · 天安门",
    "人民大会堂": "场所 · 人民大会堂",
    "中办": "机关 · 中办",
    "国办": "机关 · 国办",
}


# 已知误报形态：词是另一词汇的子串时按语境剔除。
# 「X国办公室/办事处/办学」里的「国办」不是国家机关（2026-09-28 实测“美国办公室”误报）。
FALSE_POSITIVE_PATTERNS = {
    "国办": re.compile(r"[一-龥]国办" + "(?:公|事|学)"),
}


def scan(text):
    """扫描文本，返回 (required_hits, warn_hits, ideology_hits)。"""
    required = []
    warn = []
    ideology = []
    for w in REQUIRED_WORDS:
        if w in text:
            fp = FALSE_POSITIVE_PATTERNS.get(w)
            n = text.count(w) - (len(fp.findall(text)) if fp else 0)
            if n <= 0:
                continue
            label = DISPLAY_MAP.get(w, w)
            required.append({"word": w, "label": label, "count": n})
    for w in WARN_WORDS:
        if w in text:
            n = text.count(w)
            warn.append({"word": w, "label": w, "count": n})
    for w in IDEOLOGY_WORDS:
        if w in text:
            n = text.count(w)
            ideology.append({"word": w, "label": w, "count": n})
    return required, warn, ideology


def context(text, word, radius=60):
    """返回某个词首次出现处的一段上下文。"""
    idx = text.find(word)
    if idx == -1:
        return ""
    start = max(0, idx - radius)
    end = min(len(text), idx + len(word) + radius)
    return text[start:end].replace("\n", " ")


def report(fname, required, warn, ideology, strict=False):
    """打印人类可读报告。"""
    print(f"\n扫描目标: {fname}")
    print("-" * 60)

    if not required and not warn and not ideology:
        print("✅ 未发现敏感词。")
        return 0

    if required:
        print(f"\n🔴 红线词（{len(required)} 类）— 发布前必须处理:\n")
        for h in required:
            print(f"  [{h['label']}] 出现 {h['count']} 次")
            print(f"    语境: …{context(text_raw, h['word'])}…")
        print("\n  → 改写建议: 用" + "「国家/官方/通用主体」" + "等中性词替代领导人姓名或具名机构；")
        print("    删除整句调侃或改用无具体指向的表述。见发布指南「敏感词」节。")

    if ideology:
        print(f"\n🟡 意识形态语境词（{len(ideology)} 类）— 仅提示，评估是否需按 §6.4 中性化改写微信构建文件:\n")
        for h in ideology:
            print(f"  [{h['label']}] 出现 {h['count']} 次")
            if strict:
                print(f"    语境: …{context(text_raw, h['word'])}…")

    if warn:
        if strict:
            print(f"\n🟡 广义敏感词（{len(warn)} 类）— 请人工判断:\n")
            for h in warn:
                print(f"  [{h['label']}] 出现 {h['count']} 次")
                print(f"    语境: …{context(text_raw, h['word'])}…")
        else:
            print(f"\n🟡 广义敏感词（{len(warn)} 类）— 仅提示，需人工判断是否涉国家机关影射:\n")
            for h in warn:
                print(f"  [{h['label']}] 出现 {h['count']} 次")

    return 1 if required else 0


def main():
    p = argparse.ArgumentParser(description="WeChat 发布前敏感词扫描")
    p.add_argument("--md", required=True, help="要扫描的 Markdown 文件路径")
    p.add_argument("--strict", action="store_true", help="连广义词也打印完整语境")
    args = p.parse_args()

    if not os.path.isfile(args.md):
        print(f"❌ 找不到文件: {args.md}", file=sys.stderr)
        return 2

    global text_raw
    try:
        text_raw = open(args.md, encoding="utf-8").read()
    except Exception as e:
        print(f"❌ 读取失败: {e}", file=sys.stderr)
        return 2

    required, warn, ideology = scan(text_raw)
    code = report(args.md, required, warn, ideology, strict=args.strict)
    return code


if __name__ == "__main__":
    sys.exit(main())
