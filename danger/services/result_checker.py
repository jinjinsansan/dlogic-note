"""危険人気馬の結果照合 — 翌日振り返り用"""
import json
import logging
import os
import re
from datetime import datetime, timedelta

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

NETKEIBA_NAR = "https://nar.netkeiba.com"
NETKEIBA_JRA = "https://race.netkeiba.com"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}


def _fetch_result_page(race_id: str, race_type: str) -> BeautifulSoup | None:
    """netkeibaから結果ページを取得"""
    base = NETKEIBA_NAR if race_type == "nar" else NETKEIBA_JRA
    url = f"{base}/race/result.html?race_id={race_id}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.encoding = "euc-jp"
        if resp.status_code != 200:
            return None
        return BeautifulSoup(resp.text, "html.parser")
    except Exception as e:
        logger.warning(f"結果取得失敗 {race_id}: {e}")
        return None


def _parse_finishing_order(soup: BeautifulSoup) -> list[dict]:
    """着順テーブルを解析"""
    table = soup.select_one("table.RaceTable01")
    if not table:
        return []

    rows = [tr for tr in table.select("tr") if tr.select("td.Result_Num")]
    if not rows:
        rows = table.select("tr.HorseList")

    results = []
    for tr in rows:
        tds = tr.select("td")
        if len(tds) < 4:
            continue
        try:
            position = int(tds[0].get_text(strip=True))
        except ValueError:
            position = 0
        try:
            horse_number = int(tds[2].get_text(strip=True))
        except ValueError:
            continue
        horse_name = tds[3].get_text(strip=True)
        results.append({
            "position": position,
            "horse_number": horse_number,
            "horse_name": horse_name,
        })

    results.sort(key=lambda x: (x["position"] == 0, x["position"]))
    return results


def _parse_win_payout(soup: BeautifulSoup) -> int:
    """単勝払戻金額を取得"""
    pay_back = soup.select_one(".Result_Pay_Back")
    if not pay_back:
        return 0
    for pt in pay_back.select("table.Payout_Detail_Table"):
        for tr in pt.select("tr"):
            th = tr.select_one("th")
            if th and "単勝" in th.get_text(strip=True):
                td = tr.select_one("td.Payout")
                if td:
                    m = re.search(r"([\d,]+)円", td.get_text(strip=True))
                    if m:
                        return int(m.group(1).replace(",", ""))
    return 0


def check_danger_results(date: str, race_type: str) -> list[dict]:
    """
    指定日の危険人気馬の結果を照合

    Returns:
        [{"horse_name", "race", "danger_level", "danger_score",
          "position", "win_payout", "result_label"}, ...]
    """
    output_dir = os.path.join("output", "danger", f"{date}_{race_type}")
    json_path = os.path.join(output_dir, "danger_rank.json")

    if not os.path.exists(json_path):
        logger.warning(f"危険人気馬データなし: {json_path}")
        return []

    with open(json_path, "r", encoding="utf-8") as f:
        danger_data = json.load(f)

    results = []
    for d in danger_data:
        race_id = d.get("race_id") or f"{date}-{d['track_name']}-{d['race_number']}"

        # netkeiba race_id に変換が必要だが、直接取得は困難
        # → dlogic-agentのprefetchデータからnetkeiba IDを探す
        # 簡易版: race_id そのものでは取れないので、結果は手動入力も可
        soup = _fetch_result_page(race_id, race_type)
        position = 0
        win_payout = 0

        if soup:
            finishing = _parse_finishing_order(soup)
            win_payout = _parse_win_payout(soup)
            for f_entry in finishing:
                if f_entry["horse_number"] == d["horse_number"]:
                    position = f_entry["position"]
                    break

        # 結果ラベル
        if position == 0:
            result_label = "結果未確定"
        elif position >= 4:
            result_label = "的中（馬券外）"
        elif position <= 3:
            result_label = "好走（3着以内）"
        else:
            result_label = f"{position}着"

        results.append({
            "rank": d.get("rank", 0),
            "horse_name": d["horse_name"],
            "race": f"{d['track_name']}{d['race_number']}R",
            "danger_level": d["danger_level"],
            "danger_score": d["danger_score"],
            "position": position,
            "win_payout": win_payout,
            "result_label": result_label,
        })

    # 結果を保存
    result_path = os.path.join(output_dir, "results.json")
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    return results


def load_accumulated_stats(base_dir: str = "output/danger") -> dict:
    """累積成績を集計"""
    stats = {"total": 0, "hit": 0, "miss": 0, "unknown": 0, "by_level": {}}

    if not os.path.exists(base_dir):
        return stats

    for dirname in os.listdir(base_dir):
        result_path = os.path.join(base_dir, dirname, "results.json")
        if not os.path.exists(result_path):
            continue
        with open(result_path, "r", encoding="utf-8") as f:
            results = json.load(f)

        for r in results:
            level = r.get("danger_level", "?")
            pos = r.get("position", 0)

            if level not in stats["by_level"]:
                stats["by_level"][level] = {"total": 0, "hit": 0, "miss": 0}

            stats["total"] += 1
            stats["by_level"][level]["total"] += 1

            if pos == 0:
                stats["unknown"] += 1
            elif pos >= 4:
                stats["hit"] += 1  # 馬券外 = 危険判定的中
                stats["by_level"][level]["hit"] += 1
            else:
                stats["miss"] += 1  # 3着以内 = 危険判定外れ
                stats["by_level"][level]["miss"] += 1

    return stats
