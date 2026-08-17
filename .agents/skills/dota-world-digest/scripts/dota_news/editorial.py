from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any

from .collectors import fetch_json
from .models import NewsItem


HEROES_ZH = {
    "Axe": "斧王", "Bane": "祸乱之源", "Crystal Maiden": "水晶室女",
    "Drow Ranger": "卓尔游侠", "Earthshaker": "撼地者", "Juggernaut": "主宰",
    "Mirana": "米拉娜", "Morphling": "变体精灵", "Shadow Fiend": "影魔",
    "Phantom Lancer": "幻影长矛手", "Puck": "帕克", "Pudge": "帕吉",
    "Razor": "剃刀", "Sand King": "沙王", "Storm Spirit": "风暴之灵",
    "Sven": "斯温", "Tiny": "小小", "Vengeful Spirit": "复仇之魂",
    "Windranger": "风行者", "Zeus": "宙斯", "Kunkka": "昆卡",
    "Lina": "莉娜（火女）", "Lion": "莱恩", "Shadow Shaman": "暗影萨满",
    "Slardar": "斯拉达", "Tidehunter": "潮汐猎人", "Witch Doctor": "巫医",
    "Riki": "力丸", "Enigma": "谜团", "Tinker": "修补匠",
    "Sniper": "狙击手", "Necrophos": "瘟疫法师", "Warlock": "术士",
    "Beastmaster": "兽王", "Queen of Pain": "痛苦女王", "Venomancer": "剧毒术士",
    "Faceless Void": "虚空假面", "Wraith King": "冥魂大帝", "Death Prophet": "死亡先知",
    "Phantom Assassin": "幻影刺客", "Pugna": "帕格纳", "Templar Assassin": "圣堂刺客",
    "Viper": "冥界亚龙", "Luna": "露娜", "Dragon Knight": "龙骑士",
    "Dazzle": "戴泽", "Clockwerk": "发条技师", "Leshrac": "拉席克",
    "Nature's Prophet": "先知", "Lifestealer": "噬魂鬼", "Dark Seer": "黑暗贤者",
    "Clinkz": "克林克兹", "Omniknight": "全能骑士", "Enchantress": "魅惑魔女",
    "Huskar": "哈斯卡", "Night Stalker": "暗夜魔王", "Broodmother": "育母蜘蛛",
    "Bounty Hunter": "赏金猎人", "Weaver": "编织者", "Jakiro": "杰奇洛",
    "Batrider": "蝙蝠骑士", "Chen": "陈", "Spectre": "幽鬼",
    "Ancient Apparition": "远古冰魄", "Doom": "末日使者", "Ursa": "熊战士",
    "Spirit Breaker": "裂魂人", "Gyrocopter": "矮人直升机", "Alchemist": "炼金术士",
    "Invoker": "祈求者", "Silencer": "沉默术士", "Outworld Destroyer": "殁境神蚀者",
    "Lycan": "狼人", "Brewmaster": "酒仙", "Shadow Demon": "暗影恶魔",
    "Lone Druid": "德鲁伊", "Chaos Knight": "混沌骑士", "Meepo": "米波",
    "Treant Protector": "树精卫士", "Ogre Magi": "食人魔魔法师", "Undying": "不朽尸王",
    "Rubick": "拉比克", "Disruptor": "干扰者", "Nyx Assassin": "司夜刺客",
    "Naga Siren": "娜迦海妖", "Keeper of the Light": "光之守卫", "Io": "艾欧",
    "Visage": "维萨吉", "Slark": "斯拉克", "Medusa": "美杜莎",
    "Troll Warlord": "巨魔战将", "Centaur Warrunner": "半人马战行者", "Magnus": "马格纳斯",
    "Timbersaw": "伐木机", "Bristleback": "钢背兽", "Tusk": "巨牙海民",
    "Skywrath Mage": "天怒法师", "Abaddon": "亚巴顿", "Elder Titan": "上古巨神",
    "Legion Commander": "军团指挥官", "Techies": "工程师", "Ember Spirit": "灰烬之灵",
    "Earth Spirit": "大地之灵", "Underlord": "孽主", "Terrorblade": "恐怖利刃",
    "Phoenix": "凤凰", "Oracle": "神谕者", "Winter Wyvern": "寒冬飞龙",
    "Arc Warden": "天穹守望者", "Monkey King": "齐天大圣", "Dark Willow": "邪影芳灵",
    "Pangolier": "石鳞剑士", "Grimstroke": "天涯墨客", "Hoodwink": "森海飞霞",
    "Void Spirit": "虚无之灵", "Snapfire": "电炎绝手", "Mars": "玛尔斯",
    "Dawnbreaker": "破晓辰星", "Marci": "玛西", "Primal Beast": "獸",
    "Muerta": "琼英碧灵", "Ringmaster": "百戏大王", "Kez": "凯斯"
}


def _team_matches(name: str, candidates: list[str]) -> bool:
    normalized = name.casefold().strip()
    return any(candidate.casefold() in normalized or normalized in candidate.casefold() for candidate in candidates if candidate)


def china_relation(item: NewsItem, policy: dict[str, Any]) -> tuple[int, str]:
    if item.metadata.get("kind") != "match":
        return 0, ""
    teams = [str(item.metadata.get("radiant", "")), str(item.metadata.get("dire", ""))]
    clubs = policy.get("china_clubs", [])
    for team in teams:
        if _team_matches(team, clubs):
            return 100, f"中国俱乐部：{team}"
    for team, players in policy.get("tracked_overseas_teams", {}).items():
        if any(_team_matches(candidate, [team]) for candidate in teams):
            return 95, f"中国选手旅外：{'、'.join(players)}（{team}）"
    return 0, ""


def merge_match_series(items: list[NewsItem], policy: dict[str, Any]) -> list[NewsItem]:
    groups: dict[str, list[NewsItem]] = {}
    passthrough: list[NewsItem] = []
    for item in items:
        if item.metadata.get("kind") != "match":
            passthrough.append(item)
            continue
        series_id = str(item.metadata.get("series_id") or "")
        key = f"series:{series_id}" if series_id and series_id != "0" else f"match:{item.item_id}"
        groups.setdefault(key, []).append(item)

    merged: list[NewsItem] = []
    for key, games in groups.items():
        games.sort(key=lambda game: game.published_at)
        if len(games) == 1:
            result = games[0]
        else:
            wins = Counter(str(game.metadata.get("winner", "")) for game in games)
            winner, winner_wins = wins.most_common(1)[0]
            teams = []
            for game in games:
                for field in ("radiant", "dire"):
                    name = str(game.metadata.get(field, ""))
                    if name and name not in teams:
                        teams.append(name)
            loser = next((team for team in teams if team != winner), "对手")
            loser_wins = wins.get(loser, 0)
            league = str(games[0].metadata.get("league") or "职业赛事")
            ids = [str(game.metadata.get("match_id") or game.item_id) for game in games]
            result = NewsItem(
                item_id=key,
                title=f"{league}：{winner} {winner_wins}–{loser_wins} {loser}",
                url=games[-1].url,
                published_at=games[-1].published_at,
                source_id=games[0].source_id,
                source_name=games[0].source_name,
                source_tier=games[0].source_tier,
                trust=games[0].trust,
                summary=f"{winner} 以 {winner_wins}–{loser_wins} 赢下系列赛。",
                category="esports",
                tags=[league],
                metadata={
                    "kind": "match", "series_id": key.removeprefix("series:"), "match_ids": ids,
                    "league": league, "winner": winner, "loser": loser,
                    "series_score": f"{winner_wins}–{loser_wins}",
                    "radiant": teams[0] if teams else "", "dire": teams[1] if len(teams) > 1 else "",
                },
            )
        relation_score, relation = china_relation(result, policy)
        result.metadata["china_relation_score"] = relation_score
        result.metadata["china_relation"] = relation
        result.priority_group = "china_match" if relation_score else "global_match"
        merged.append(result)
    return passthrough + merged


def circle_category(item: NewsItem, policy: dict[str, Any]) -> str:
    text = f"{item.title} {item.summary}".casefold()
    china = any(word in text for word in ("china", "chinese", "中国", "lgd", "xtreme", "tidebound", "vici", "aster", "emo", "ame", "somnus"))
    transfer = any(word in text for word in ("roster", "transfer", "signs", "joins", "leaves", "disband", "阵容", "转会", "解散"))
    player = any(word in text for word in ("retire", "comeback", "interview", "ban", "penalty", "退役", "复出", "采访", "禁赛"))
    event = any(word in text for word in ("the international", " ti ", "ti202", "major", "esl one", "dreamleague"))
    patch = any(word in text for word in ("patch", "gameplay update", "版本", "补丁"))
    ecosystem = any(word in text for word in ("academy", "youth", "青训", "生态", "联赛"))
    legendary = any(name.casefold() in text for name in policy.get("legendary_players", []))
    if china and transfer:
        return "china_roster"
    if china and player:
        return "china_player"
    if event:
        return "top_event_offstage"
    if transfer and (legendary or not china):
        return "elite_transfer"
    if patch:
        return "pro_patch"
    if china and ecosystem:
        return "china_ecosystem"
    return ""


def apply_editorial_priority(items: list[NewsItem], policy: dict[str, Any], now: datetime) -> None:
    category_values = policy.get("interest_categories", {})
    for item in items:
        if item.metadata.get("kind") == "match":
            relation = int(item.metadata.get("china_relation_score") or 0)
            item.score += relation
            continue
        category = circle_category(item, policy)
        item.metadata["interest_category"] = category
        if not category:
            continue
        item.priority_group = "circle"
        age_hours = max(0.0, (now - item.published_at.astimezone(timezone.utc)).total_seconds() / 3600)
        credibility = min(30.0, item.trust * 0.30)
        china_score = 25.0 if category.startswith("china_") else 0.0
        impact = min(20.0, category_values.get(category, 0) * 0.20)
        recency = max(0.0, 10.0 - age_hours / 12)
        interest = min(10.0, category_values.get(category, 0) * 0.10)
        heat = min(5.0, len(item.corroborating_sources) * 2.5)
        item.metadata["circle_score"] = round(credibility + china_score + impact + recency + interest + heat, 2)


def compose_digest(items: list[NewsItem], policy: dict[str, Any]) -> list[NewsItem]:
    china = [item for item in items if item.priority_group == "china_match"]
    global_matches = [item for item in items if item.priority_group == "global_match"]
    circle = []
    official = []
    legends = []
    sensitive_terms = [term.casefold() for term in policy.get("sensitive_terms", [])]
    for item in items:
        text = f"{item.title} {item.summary}".casefold()
        if item.priority_group == "circle":
            sensitive = any(term in text for term in sensitive_terms)
            trustworthy = item.trust >= int(policy.get("circle_trust_floor", 65))
            confirmed = item.source_tier == "official" or len(item.corroborating_sources) >= 2
            if trustworthy and (not sensitive or confirmed):
                circle.append(item)
        if item.category in {"official", "patch"} and item not in circle:
            item.priority_group = "official"
            official.append(item)
        if any(name.casefold() in text for name in policy.get("legendary_players", [])) and item not in circle:
            item.priority_group = "legend"
            legends.append(item)

    china.sort(key=lambda value: (value.published_at, value.score), reverse=True)
    global_matches.sort(key=lambda value: value.score, reverse=True)
    circle.sort(key=lambda value: (value.metadata.get("circle_score", 0), value.score), reverse=True)
    official.sort(key=lambda value: value.score, reverse=True)
    legends.sort(key=lambda value: value.score, reverse=True)
    result = (
        china[: int(policy.get("china_match_limit", 8))]
        + global_matches[: int(policy.get("global_match_limit", 2))]
        + circle[: int(policy.get("circle_limit", 2))]
        + legends[:1]
        + official[:2]
    )
    seen: set[str] = set()
    return [item for item in result if not (item.item_id in seen or seen.add(item.item_id))]


def _role(player: dict[str, Any], team_players: list[dict[str, Any]]) -> str:
    lane = int(player.get("lane_role") or 0)
    net_rank = sorted(team_players, key=lambda value: int(value.get("net_worth") or 0), reverse=True).index(player)
    if lane == 2:
        return "二号位（中路）"
    if lane == 1 and net_rank <= 2:
        return "一号位（优势路核心）"
    if lane == 3 and net_rank <= 2:
        return "三号位（劣势路核心）"
    return "四号位（游走辅助）" if net_rank == 3 else "五号位（辅助）"


def _hero_name(hero_id: Any, heroes: dict[str, Any]) -> str:
    hero = heroes.get(str(hero_id), {})
    english = str(hero.get("localized_name") or f"英雄#{hero_id}")
    return HEROES_ZH.get(english, english)


def enrich_match_reports(items: list[NewsItem]) -> list[str]:
    warnings: list[str] = []
    matches = [item for item in items if item.metadata.get("kind") == "match"]
    if not matches:
        return warnings
    try:
        heroes = fetch_json("https://api.opendota.com/api/constants/heroes")
    except Exception as exc:
        warnings.append(f"英雄名称表读取失败：{type(exc).__name__}: {exc}")
        heroes = {}
    for item in matches:
        details = []
        for match_id in item.metadata.get("match_ids", [])[-3:]:
            try:
                details.append(fetch_json(f"https://api.opendota.com/api/matches/{match_id}", timeout=20))
            except Exception as exc:
                warnings.append(f"比赛 {match_id} 详情读取失败：{type(exc).__name__}: {exc}")
        if not details:
            continue
        narratives = []
        candidate_performances: list[tuple[float, dict[str, Any], list[dict[str, Any]]]] = []
        series_winner = str(item.metadata.get("winner") or "")
        for index, detail in enumerate(details, 1):
            duration = round(int(detail.get("duration") or 0) / 60)
            radiant = str(detail.get("radiant_name") or "天辉")
            dire = str(detail.get("dire_name") or "夜魇")
            winner = radiant if detail.get("radiant_win") else dire
            r_score, d_score = detail.get("radiant_score"), detail.get("dire_score")
            winner_score = r_score if detail.get("radiant_win") else d_score
            loser_score = d_score if detail.get("radiant_win") else r_score
            narratives.append(f"第{index}局 {winner} 以 {winner_score}–{loser_score} 取胜（{duration}分钟）")
            game_players = detail.get("players") or []
            series_winner_radiant = _team_matches(radiant, [series_winner])
            for player in game_players:
                is_series_winner = bool(player.get("isRadiant")) == series_winner_radiant
                if not is_series_winner:
                    continue
                value = int(player.get("kills") or 0) * 3 + int(player.get("assists") or 0) - int(player.get("deaths") or 0) * 2 + int(player.get("hero_damage") or 0) / 5000
                team_players = [candidate for candidate in game_players if bool(candidate.get("isRadiant")) == bool(player.get("isRadiant"))]
                candidate_performances.append((value, player, team_players))
        item.summary = "；".join(narratives) + "。"
        last = details[-1]
        gold = [int(value or 0) for value in (last.get("radiant_gold_adv") or [])]
        sign_changes = sum(1 for left, right in zip(gold, gold[1:]) if (left < 0 < right) or (left > 0 > right))
        duration = round(int(last.get("duration") or 0) / 60)
        if duration >= 55 or sign_changes >= 3:
            item.editorial_note = f"决胜局打了约 {duration} 分钟，经济领先至少 {sign_changes} 次易手，是一场拉扯明显的长局。"
        else:
            item.editorial_note = f"决胜局约 {duration} 分钟结束；胜负转折应结合录像中的团战与关键技能进一步复盘。"
        if candidate_performances:
            _, best, team_players = max(candidate_performances, key=lambda value: value[0])
            alias = str(best.get("name") or best.get("personaname") or "关键选手")
            item.spotlights = [{
                "label": "本报MVP",
                "player": alias,
                "team": series_winner,
                "role": _role(best, team_players),
                "hero": _hero_name(best.get("hero_id"), heroes),
                "kda": f"{best.get('kills', 0)}/{best.get('deaths', 0)}/{best.get('assists', 0)}",
                "hero_damage": int(best.get("hero_damage") or 0),
            }]
        last_players = last.get("players") or []
        last_radiant = str(last.get("radiant_name") or "天辉")
        loser_is_radiant = _team_matches(last_radiant, [str(item.metadata.get("loser") or "")])
        losing_players = [player for player in last_players if bool(player.get("isRadiant")) == loser_is_radiant]
        if losing_players:
            key_player = max(
                losing_players,
                key=lambda player: (int(player.get("hero_damage") or 0), int(player.get("kills") or 0) + int(player.get("assists") or 0)),
            )
            alias = str(key_player.get("name") or key_player.get("personaname") or "关键选手")
            hero = _hero_name(key_player.get("hero_id"), heroes)
            role = _role(key_player, losing_players)
            item.spotlights.append({
                "label": "末局关键选手", "player": alias, "team": str(item.metadata.get("loser") or ""),
                "role": role, "hero": hero,
                "kda": f"{key_player.get('kills', 0)}/{key_player.get('deaths', 0)}/{key_player.get('assists', 0)}",
                "hero_damage": int(key_player.get("hero_damage") or 0),
            })
            if "三号位" in role:
                item.editorial_note += f" {alias} 在末局用三号位{hero}打出 {key_player.get('kills', 0)}/{key_player.get('deaths', 0)}/{key_player.get('assists', 0)}，但仍未能帮助队伍赢下系列赛。"
        relation = str(item.metadata.get("china_relation") or "")
        if relation:
            item.impact = f"本系列赛涉及{relation}，因此进入中国 Dota 全量追踪。晋级或淘汰结论仅在赛事官方赛程能够确认时写入。"
        else:
            item.impact = "该场进入全球焦点赛事栏；后续影响以赛事官方积分、分组或淘汰赛程为准。"
    return warnings
