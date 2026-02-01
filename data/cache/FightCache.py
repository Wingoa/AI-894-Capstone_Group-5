from __future__ import annotations
from typing import Dict, List, Optional
from data_model.FightStatLine import FightStatLine
import csv
import os
import BaseCsvCache as BaseCsvCache


class FightCache(BaseCsvCache[str, List[FightStatLine]]):
    """
    Key: fight_id
    Value: list of FightStatLine rows (usually 2 rows per fight)
    """

    FIELDS = [
        "fight_id", "fighter_id", "fighter", "kd", "sig_str", "sig_str_pct",
        "total_str", "td", "td_pct", "sub_att", "rev", "ctrl", "head", "body",
        "leg", "distance", "clinch", "ground",
    ]

    def key_of(self, value: List[FightStatLine]) -> str:
        if not value:
            raise ValueError("Cannot cache an empty list of FightStatLine")
        return value[0].fight_id

    # Override because BaseCsvCache.upsert expects a single object per key,
    # while this cache stores list-per-key.
    def upsert_line(self, line: FightStatLine) -> None:
        """
        Add/append a single FightStatLine into the fight_id bucket.
        """
        self.load()
        with self._lock:
            self._data.setdefault(line.fight_id, []).append(line)

    def get_fight(self, fight_id: str) -> List[FightStatLine]:
        """
        Convenience wrapper: returns [] if fight_id not found.
        """
        self.load()
        with self._lock:
            return list(self._data.get(fight_id, []))

    def _load_from_csv(self, csv_path: str) -> None:
        with open(csv_path, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)

            fieldnames = set(reader.fieldnames or [])
            missing = set(self.FIELDS) - fieldnames
            if missing:
                raise ValueError(f"CSV missing required columns: {sorted(missing)}")

            for row in reader:
                fight_id = (row.get("fight_id") or "").strip()
                if not fight_id:
                    continue
                line = self._row_to_line(row)
                self._data.setdefault(fight_id, []).append(line)

    def append_to_csv(self, value: List[FightStatLine]) -> None:
        """
        Append a batch of stat lines to the CSV (append-only).
        """
        self.load()
        with self._lock:
            file_exists = os.path.exists(self._csv_path)
            file_empty = (not file_exists) or (os.path.getsize(self._csv_path) == 0)

            with open(self._csv_path, "a", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=self.FIELDS)
                if file_empty:
                    writer.writeheader()

                for line in value:
                    writer.writerow(self._line_to_row(line))

    def append_line_to_csv(self, line: FightStatLine) -> None:
        """
        Convenience: append a single line to the CSV (append-only).
        """
        self.load()
        with self._lock:
            file_exists = os.path.exists(self._csv_path)
            file_empty = (not file_exists) or (os.path.getsize(self._csv_path) == 0)

            with open(self._csv_path, "a", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=self.FIELDS)
                if file_empty:
                    writer.writeheader()
                writer.writerow(self._line_to_row(line))

    def saveAll(self, fights: List[Dict]) -> None:
        for fight in fights:
            print(f"Saving fight {fight} to FightCache")
            self.save(fight)

    # -------- helpers --------

    @staticmethod
    def _clean_str(v) -> str:
        return "" if v is None else str(v).strip()

    @staticmethod
    def _clean_int(v) -> Optional[int]:
        if v is None:
            return None
        s = str(v).strip()
        if s == "" or s.lower() == "nan":
            return None
        try:
            return int(float(s))
        except ValueError:
            return None

    @classmethod
    def _row_to_line(cls, row: Dict) -> FightStatLine:
        return FightStatLine(
            fight_id=cls._clean_str(row.get("fight_id")),
            fighter_id=cls._clean_str(row.get("fighter_id")),
            fighter=cls._clean_str(row.get("fighter")),
            kd=cls._clean_int(row.get("kd")),
            sig_str=cls._clean_str(row.get("sig_str")),
            sig_str_pct=cls._clean_str(row.get("sig_str_pct")),
            total_str=cls._clean_str(row.get("total_str")),
            td=cls._clean_str(row.get("td")),
            td_pct=cls._clean_str(row.get("td_pct")),
            sub_att=cls._clean_int(row.get("sub_att")),
            rev=cls._clean_int(row.get("rev")),
            ctrl=cls._clean_str(row.get("ctrl")),
            head=cls._clean_str(row.get("head")),
            body=cls._clean_str(row.get("body")),
            leg=cls._clean_str(row.get("leg")),
            distance=cls._clean_str(row.get("distance")),
            clinch=cls._clean_str(row.get("clinch")),
            ground=cls._clean_str(row.get("ground")),
        )

    @staticmethod
    def _line_to_row(line: FightStatLine) -> Dict[str, object]:
        return {
            "fight_id": line.fight_id,
            "fighter_id": line.fighter_id,
            "fighter": line.fighter,
            "kd": "" if line.kd is None else line.kd,
            "sig_str": line.sig_str,
            "sig_str_pct": line.sig_str_pct,
            "total_str": line.total_str,
            "td": line.td,
            "td_pct": line.td_pct,
            "sub_att": "" if line.sub_att is None else line.sub_att,
            "rev": "" if line.rev is None else line.rev,
            "ctrl": line.ctrl,
            "head": line.head,
            "body": line.body,
            "leg": line.leg,
            "distance": line.distance,
            "clinch": line.clinch,
            "ground": line.ground,
        }
