import os
import discord
from pathlib import Path
from datetime import datetime, timedelta
import json
from typing import Optional, List, Tuple

DATA_DIR = Path(os.getenv("DATA_DIR", os.getenv("RAILWAY_VOLUME_MOUNT_PATH", str(Path(__file__).parent.parent / "data"))))
DATA_DIR.mkdir(parents=True, exist_ok=True)

BANS_FILE = DATA_DIR / "bans.json"
KICK_COOLDOWNS_FILE = DATA_DIR / "kick_cooldowns.json"
LEAVE_COOLDOWNS_FILE = DATA_DIR / "leave_cooldowns.json"
MEMBERS_FILE = DATA_DIR / "members.json"
RANK_COOLDOWNS_FILE = DATA_DIR / "rank_cooldowns.json"

DIVISIONS = {
    "Division 1": {"role_id": 1520173789957062787},
    "Division 6": {"role_id": 1520180291061415957},
    "Division 10": {"role_id": 1520199862216425534},
    "Division 11": {"role_id": 1520199922752819381},
}

LIEUTENANT_ROLE_ID = 1520240253628055572
VICE_CAPTAIN_ROLE_ID = 1520235446712406078
DIVISION_CAPTAIN_ROLE_ID = 1520199922752819381

def load_json(file: Path) -> dict:
    if file.exists():
        with open(file, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_json(file: Path, data: dict) -> None:
    file.parent.mkdir(parents=True, exist_ok=True)
    with open(file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_division_by_member(member: discord.Member) -> Optional[Tuple[str, dict]]:
    for div_name, div_data in DIVISIONS.items():
        role = member.guild.get_role(div_data["role_id"])
        if role and role in member.roles:
            return (div_name, div_data)
    return None

def count_division_members(guild: discord.Guild, division_name: str) -> int:
    div_data = DIVISIONS.get(division_name)
    if not div_data:
        return 0
    role = guild.get_role(div_data["role_id"])
    return len(role.members) if role else 0

def is_member_banned(member_id: int) -> bool:
    bans = load_json(BANS_FILE)
    return str(member_id) in bans

def ban_member(member_id: int) -> None:
    bans = load_json(BANS_FILE)
    bans[str(member_id)] = datetime.now().isoformat()
    save_json(BANS_FILE, bans)

def unban_member(member_id: int) -> None:
    bans = load_json(BANS_FILE)
    if str(member_id) in bans:
        del bans[str(member_id)]
        save_json(BANS_FILE, bans)

def can_rejoin_after_kick(member_id: int, division_name: str) -> bool:
    cooldowns = load_json(KICK_COOLDOWNS_FILE)
    key = f"{member_id}_{division_name}"
    if key not in cooldowns:
        return True
    last_kick = datetime.fromisoformat(cooldowns[key])
    return datetime.now() >= last_kick + timedelta(days=3)

def set_kick_cooldown(member_id: int, division_name: str) -> None:
    cooldowns = load_json(KICK_COOLDOWNS_FILE)
    key = f"{member_id}_{division_name}"
    cooldowns[key] = datetime.now().isoformat()
    save_json(KICK_COOLDOWNS_FILE, cooldowns)

def can_rejoin_after_leave(member_id: int) -> bool:
    cooldowns = load_json(LEAVE_COOLDOWNS_FILE)
    if str(member_id) not in cooldowns:
        return True
    last_leave = datetime.fromisoformat(cooldowns[str(member_id)])
    return datetime.now() >= last_leave + timedelta(days=3)

def set_leave_cooldown(member_id: int) -> None:
    cooldowns = load_json(LEAVE_COOLDOWNS_FILE)
    cooldowns[str(member_id)] = datetime.now().isoformat()
    save_json(LEAVE_COOLDOWNS_FILE, cooldowns)

def add_member_to_division(member_id: int, division_name: str, join_date: str = None) -> None:
    members = load_json(MEMBERS_FILE)
    key = f"{member_id}_{division_name}"
    members[key] = {
        "join_date": join_date or datetime.now().isoformat(),
        "division": division_name,
        "rank": None,
    }
    save_json(MEMBERS_FILE, members)

def get_member_divisions(member_id: int) -> List[str]:
    members = load_json(MEMBERS_FILE)
    divisions = []
    for key, data in members.items():
        if key.startswith(f"{member_id}_"):
            divisions.append(data["division"])
    return divisions

def get_member_rank(member_id: int, division_name: str) -> Optional[str]:
    members = load_json(MEMBERS_FILE)
    key = f"{member_id}_{division_name}"
    if key in members:
        return members[key].get("rank")
    return None

def set_member_rank(member_id: int, division_name: str, rank: Optional[str]) -> None:
    members = load_json(MEMBERS_FILE)
    key = f"{member_id}_{division_name}"
    if key in members:
        members[key]["rank"] = rank
        save_json(MEMBERS_FILE, members)

def get_member_join_date(member_id: int, division_name: str) -> Optional[str]:
    members = load_json(MEMBERS_FILE)
    key = f"{member_id}_{division_name}"
    if key in members:
        return members[key].get("join_date")
    return None

def can_rank(captain_id: int, division_name: str, rank_type: int) -> bool:
    cooldowns = load_json(RANK_COOLDOWNS_FILE)
    key = f"{captain_id}_{division_name}_rank{rank_type}"
    if key not in cooldowns:
        return True
    last_rank = datetime.fromisoformat(cooldowns[key])
    return datetime.now() >= last_rank + timedelta(days=10)

def set_rank_cooldown(captain_id: int, division_name: str, rank_type: int) -> None:
    cooldowns = load_json(RANK_COOLDOWNS_FILE)
    key = f"{captain_id}_{division_name}_rank{rank_type}"
    cooldowns[key] = datetime.now().isoformat()
    save_json(RANK_COOLDOWNS_FILE, cooldowns)

def get_rank_holder(guild: discord.Guild, division_name: str, rank_type: int) -> Optional[discord.Member]:
    if rank_type == 1:
        role_id = LIEUTENANT_ROLE_ID
    elif rank_type == 2:
        role_id = VICE_CAPTAIN_ROLE_ID
    else:
        return None
    
    role = guild.get_role(role_id)
    if not role:
        return None
    
    members = load_json(MEMBERS_FILE)
    for member in role.members:
        key = f"{member.id}_{division_name}"
        if key in members:
            return member
    
    return None
