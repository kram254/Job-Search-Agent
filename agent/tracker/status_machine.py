from typing import Optional, List, Dict, Tuple


CANONICAL_STATES = {
    "discovered": "Job found via scan, not yet applied",
    "queued": "Added to pipeline queue",
    "applied": "Application submitted",
    "screening": "Initial screening / phone screen scheduled",
    "interview": "Technical or behavioral interview in progress",
    "offer": "Offer received",
    "accepted": "Offer accepted",
    "rejected": "Application rejected",
    "withdrawn": "Candidate withdrew application",
    "ghosted": "No response after follow-up cadence exhausted",
    "on_hold": "Process paused by company"
}

STATE_ALIASES: Dict[str, str] = {
    "new": "discovered",
    "found": "discovered",
    "pending": "queued",
    "in_queue": "queued",
    "submitted": "applied",
    "sent": "applied",
    "phone screen": "screening",
    "phone_screen": "screening",
    "hr screen": "screening",
    "hr_screen": "screening",
    "technical": "interview",
    "tech_interview": "interview",
    "onsite": "interview",
    "final": "interview",
    "offer_received": "offer",
    "offer received": "offer",
    "hired": "accepted",
    "passed": "rejected",
    "declined": "rejected",
    "not selected": "rejected",
    "not_selected": "rejected",
    "no response": "ghosted",
    "no_response": "ghosted",
    "paused": "on_hold",
    "hold": "on_hold"
}

VALID_TRANSITIONS: Dict[str, List[str]] = {
    "discovered": ["queued", "rejected", "withdrawn"],
    "queued": ["applied", "rejected", "withdrawn"],
    "applied": ["screening", "interview", "rejected", "ghosted", "withdrawn"],
    "screening": ["interview", "rejected", "ghosted", "withdrawn"],
    "interview": ["offer", "rejected", "ghosted", "withdrawn", "on_hold"],
    "offer": ["accepted", "rejected", "withdrawn"],
    "accepted": [],
    "rejected": [],
    "withdrawn": [],
    "ghosted": ["applied", "withdrawn"],
    "on_hold": ["interview", "offer", "rejected", "withdrawn", "ghosted"]
}


class StatusMachine:
    """ATS status state machine with canonical states and valid transitions."""

    def normalize(self, raw_status: str) -> str:
        if not raw_status:
            return "discovered"
        normalized = raw_status.strip().lower()
        if normalized in CANONICAL_STATES:
            return normalized
        if normalized in STATE_ALIASES:
            return STATE_ALIASES[normalized]
        for canonical in CANONICAL_STATES:
            if canonical in normalized or normalized in canonical:
                return canonical
        return "discovered"

    def can_transition(self, current: str, target: str) -> bool:
        current_canon = self.normalize(current)
        target_canon = self.normalize(target)
        allowed = VALID_TRANSITIONS.get(current_canon, [])
        return target_canon in allowed

    def transition(self, current: str, target: str) -> Tuple[bool, str, str]:
        current_canon = self.normalize(current)
        target_canon = self.normalize(target)

        if current_canon == target_canon:
            return True, target_canon, "no_change"

        if self.can_transition(current_canon, target_canon):
            return True, target_canon, "ok"

        return False, current_canon, f"invalid_transition:{current_canon}->{target_canon}"

    def get_next_states(self, current: str) -> List[str]:
        return VALID_TRANSITIONS.get(self.normalize(current), [])

    def describe(self, state: str) -> str:
        return CANONICAL_STATES.get(self.normalize(state), "unknown state")

    def all_states(self) -> Dict[str, str]:
        return CANONICAL_STATES.copy()

    def is_terminal(self, state: str) -> bool:
        canon = self.normalize(state)
        return not VALID_TRANSITIONS.get(canon)
