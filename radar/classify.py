"""Conservative, inspectable labels for public job titles."""

import re


EXCLUDED = re.compile(
    r"recruit|talent acquisition|sales|account|channel manager|developer relation|"
    r"marketing|communicat|support|customer success|operations|business development|"
    r"deployment manager|product manager|program manager|demand planning|legal|"
    r"finance|human resources|people partner|solutions architect|counsel|"
    r"economist|policy research|user experience research|developer productivity|"
    r"\bgtm\b|executive assistant|workplace|procurement|people research|real estate|"
    r"\bux\b|user research|design research|market research",
    re.I,
)

ROLE_PATTERNS = (
    ("research_engineering", re.compile(r"research (?:software )?engineer|robotics research engineer", re.I)),
    ("research", re.compile(r"research (?:scientist|intern|fellow|manager|lead|director)|\bresearcher\b|"
                                     r"applied scientist|machine learning scientist|\bai scientist\b|robotics scientist", re.I)),
    ("ai_infrastructure", re.compile(r"inference|training infrastructure|ai infrastructure|ml infrastructure|"
                                              r"\bml infra\b|distributed training|gpu systems|\bcompiler\b|"
                                              r"model serving|ai accelerator", re.I)),
    ("ai_engineering", re.compile(r"machine learning engineer|\bml engineer\b|\bai engineer\b|"
                                           r"robotics engineer|computer vision engineer|deep learning engineer|"
                                           r"applied ai engineer|forward deployed engineer|"
                                           r"software engineer.*(?:robot|\bai\b|\bml\b|machine learning|deep learning)|"
                                           r"(?:robot|robotics|\bai\b|\bml\b).*software engineer", re.I)),
)

TOPIC_PATTERNS = {
    "Robotics": re.compile(r"robot|embodied|manipulation|humanoid|motion planning|actuation", re.I),
    "Language models": re.compile(r"language model|\bllm\b|\bgpt\b|transformer|pretrain|pre-train|post-train|reasoning", re.I),
    "Multimodal": re.compile(r"multimodal|vision.language|video generation|\baudio\b|\bspeech\b", re.I),
    "AI infrastructure": re.compile(r"inference|\bgpu\b|distributed|(?:training|ai|ml) infrastructure|\bml infra\b|\bcompute\b|compiler|serving|accelerator", re.I),
    "Safety": re.compile(r"alignment|safety|red team|interpretability|\bevals?\b|evaluation", re.I),
    "Agents": re.compile(r"\bagents?\b|tool use|computer use|planning", re.I),
}


def classify_job(title):
    """Only a title match is counted; generic employer boilerplate is not evidence."""
    if EXCLUDED.search(title):
        return {"role_family": "other", "topics": [], "topic_evidence": {}}
    role_family = next((name for name, pattern in ROLE_PATTERNS if pattern.search(title)), "other")
    if role_family == "other":
        return {"role_family": role_family, "topics": [], "topic_evidence": {}}
    evidence = {name: match.group(0) for name, pattern in TOPIC_PATTERNS.items()
                if (match := pattern.search(title))}
    return {"role_family": role_family, "topics": list(evidence), "topic_evidence": evidence}
