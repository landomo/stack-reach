AUTHOR_PROFILE = {
    "name": "Leandro Oliva",
    "bio": (
        "Former Wall Street Journal Editor | AI & Cultural Data Researcher | "
        "Political Economy of Platforms. Amsterdam - NYC based. Columbia J School 2015."
    ),
    "publication_url": "https://www.leandrooliva.com",
    "substack_handle": "lolivas",
    "core_topics": [
        "AI policy and regulation",
        "Political economy of platforms",
        "AI impact on journalism and media",
        "Labor market effects of AI hiring and screening",
        "AI infrastructure pricing and commoditization",
        "US-Europe AI dynamics and sovereignty",
        "Coding agents and developer tooling",
        "Publisher strategies in the age of AI",
    ],
    "recent_posts": [
        "The AI Frontier Europe Can Actually Win",
        "Coding Agents Have a Memory Problem. Three Companies Are Selling the Fix.",
        "The Same People Get Rejected Everywhere (AI hiring bias study)",
        "Publishers Make Big Moves in the Struggle With AI",
        "What DeepSeek's 75% Price Cut Says About the Real Cost of AI",
        "After Google I/O, Publishers Are Out of Time. But There Is a Roadmap.",
        "Why Your AI Bill Is About to Look Very Different",
    ],
    "voice": (
        "Data-driven, policy-oriented, journalist background. "
        "Engages critically with AI hype. Focuses on structural and economic consequences."
    ),
}

# Stable topic vocabulary used for the dashboard's topic chips.
# The scorer tags every note with 1-3 of these EXACT labels, so chips and tags
# always match. Keep labels short — they double as the chip text.
TOPIC_TAGS = [
    "AI policy & regulation",
    "Platform economics",
    "AI & journalism",
    "AI & the labor market",
    "AI infrastructure & pricing",
    "US–Europe AI sovereignty",
    "Coding agents & tooling",
    "Publisher strategy",
]

RELEVANCE_SYSTEM_PROMPT = f"""You are helping {AUTHOR_PROFILE['name']}, a Substack writer,
find valuable engagement opportunities on Substack Notes.

Their profile:
- Bio: {AUTHOR_PROFILE['bio']}
- Core topics: {', '.join(AUTHOR_PROFILE['core_topics'])}
- Writing voice: {AUTHOR_PROFILE['voice']}
- Recent posts: {'; '.join(AUTHOR_PROFILE['recent_posts'])}

Your job is to evaluate Substack Notes for engagement potential and draft reply angles."""
