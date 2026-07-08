# Quality Review Prompt

Review this YouTube Short package before manual upload.

Topic:
{{topic_title}}

Script:
{{script_text}}

Metadata:
{{metadata}}

Check for:
- Factual claims that need verification.
- Misleading title or description.
- Copyright or reused-content risk.
- Unsafe, sensitive, hateful, sexual, violent, medical, financial, or dangerous advice.
- Weak hook or unclear payoff.
- Language that sounds unnatural for {{language}}.

Return:
- pass/fail for each area.
- specific notes.
- suggested fixes.
