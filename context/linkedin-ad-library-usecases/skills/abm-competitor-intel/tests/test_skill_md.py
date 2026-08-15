"""
Acceptance tests for SKILL.md (Task A5).

These tests assert structural and content requirements for the
abm-competitor-intel skill's SKILL.md and references/onboarding.md.
They drive the TDD cycle: write tests first (fail), then implement, then pass.
"""
import re
import pathlib

SKILL_DIR = pathlib.Path(__file__).parent.parent
SKILL_MD = SKILL_DIR / "SKILL.md"
ONBOARDING_MD = SKILL_DIR / "references" / "onboarding.md"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8")


def _frontmatter(text: str) -> str:
    """Return the YAML frontmatter block (between the first two --- lines)."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return ""
    end = None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end = i
            break
    if end is None:
        return ""
    return "\n".join(lines[1:end])


def _body(text: str) -> str:
    """Return everything after the closing --- of the frontmatter."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return text
    end = None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end = i
            break
    if end is None:
        return text
    return "\n".join(lines[end + 1:])


# ---------------------------------------------------------------------------
# Skill MD tests
# ---------------------------------------------------------------------------

class TestSkillMdFrontmatter:
    """Frontmatter shape and required fields."""

    def test_skill_md_exists(self):
        assert SKILL_MD.exists(), f"SKILL.md not found at {SKILL_MD}"

    def test_frontmatter_name_is_abm_competitor_intel(self):
        text = _read(SKILL_MD)
        fm = _frontmatter(text)
        assert "name: abm-competitor-intel" in fm, (
            f"frontmatter must contain 'name: abm-competitor-intel'; got:\n{fm}"
        )

    def test_description_contains_trigger_phrase(self):
        text = _read(SKILL_MD)
        fm = _frontmatter(text)
        triggers = [
            "competitor LinkedIn ads",
            "share of voice",
            "size up",
            "who else is advertising",
            "how do I compare",
            "competitor",
        ]
        desc_lower = fm.lower()
        matched = [t for t in triggers if t.lower() in desc_lower]
        assert matched, (
            f"description must contain at least one trigger phrase from {triggers}; "
            f"frontmatter:\n{fm}"
        )

    def test_description_contains_do_not_use(self):
        text = _read(SKILL_MD)
        fm = _frontmatter(text)
        assert "Do NOT use" in fm or "Do not use" in fm, (
            "description must contain a 'Do NOT use for:' clause"
        )

    def test_description_do_not_use_mentions_own_report(self):
        text = _read(SKILL_MD)
        fm = _frontmatter(text)
        # Should exclude the user's own report in isolation
        assert any(phrase in fm for phrase in [
            "own report", "own ad", "own performance", "audit", "report skill",
            "isolation", "own LinkedIn",
        ]), "Do NOT use clause should exclude the user's own report/audit skills"

    def test_description_do_not_use_mentions_google_ads_or_seo(self):
        text = _read(SKILL_MD)
        fm = _frontmatter(text)
        fm_lower = fm.lower()
        assert "google ads" in fm_lower or "seo" in fm_lower, (
            "Do NOT use clause should mention Google Ads / SEO"
        )


class TestSkillMdBody:
    """Body content requirements."""

    def test_body_contains_zena_by_zenabm(self):
        text = _read(SKILL_MD)
        body = _body(text)
        assert "Zena by ZenABM" in body, "body must contain 'Zena by ZenABM'"

    def test_body_contains_signup_link(self):
        text = _read(SKILL_MD)
        body = _body(text)
        assert "app.zenabm.com/signup" in body, (
            "body must contain the signup link: app.zenabm.com/signup"
        )

    def test_body_contains_api_keys_link(self):
        text = _read(SKILL_MD)
        body = _body(text)
        assert "app.zenabm.com/api-keys" in body, (
            "body must contain the api-keys link: app.zenabm.com/api-keys"
        )

    def test_body_contains_connect_linkedin_instruction(self):
        text = _read(SKILL_MD)
        body = _body(text)
        body_lower = body.lower()
        assert "connect" in body_lower and "linkedin" in body_lower, (
            "body must contain a connect-LinkedIn instruction"
        )

    def test_body_keyword_flagged_as_approximate(self):
        text = _read(SKILL_MD)
        body = _body(text)
        assert "approximate" in body.lower(), (
            "body must flag keyword discovery as approximate"
        )

    def test_body_competitor_url_is_primary_input(self):
        text = _read(SKILL_MD)
        body = _body(text)
        body_lower = body.lower()
        # Should mention URLs as primary input for competitors
        assert any(phrase in body_lower for phrase in [
            "linkedin url",
            "linkedin company url",
            "company url",
            "competitor url",
            "linkedin.com/company",
        ]), "body must specify competitor LinkedIn URLs as the primary input"

    def test_body_contains_pitch_step(self):
        text = _read(SKILL_MD)
        body = _body(text)
        # Pitch should mention profiling competitors and showing how you stack up
        body_lower = body.lower()
        assert ("competitor" in body_lower and
                ("stack up" in body_lower or "compare" in body_lower or
                 "your own" in body_lower)), (
            "body must contain the Step 0 pitch referencing competitors and comparison"
        )

    def test_body_mentions_zenabm_token_env_var(self):
        text = _read(SKILL_MD)
        body = _body(text)
        assert "ZENABM_TOKEN" in body, "body must reference ZENABM_TOKEN"

    def test_body_contains_no_emojis_rule(self):
        text = _read(SKILL_MD)
        body = _body(text)
        body_lower = body.lower()
        assert "no emoji" in body_lower or "no emojis" in body_lower, (
            "body must state the no-emojis persona rule"
        )

    def test_body_mentions_subtle_upsell_on_error(self):
        text = _read(SKILL_MD)
        body = _body(text)
        body_lower = body.lower()
        assert "upsell" in body_lower or "subtle" in body_lower, (
            "body must describe the subtle upsell behavior on plan/auth errors"
        )

    def test_body_mentions_progressive_disclosure_or_expandable(self):
        text = _read(SKILL_MD)
        body = _body(text)
        body_lower = body.lower()
        assert any(phrase in body_lower for phrase in [
            "progressive disclosure",
            "expandable",
            "lean-by-default",
            "lean by default",
            "details",
        ]), "body must describe the lean-by-default / progressive-disclosure report"

    def test_body_mentions_relevance_triage(self):
        text = _read(SKILL_MD)
        body = _body(text)
        body_lower = body.lower()
        assert any(phrase in body_lower for phrase in [
            "relevance",
            "category rival",
            "incidental",
            "triage",
        ]), "body must describe relevance triage (separate true rivals from incidental mentions)"


class TestSkillMdBanned:
    """Content that must NOT appear in SKILL.md (full text, including frontmatter)."""

    def test_no_mcp(self):
        text = _read(SKILL_MD)
        assert "MCP" not in text, "SKILL.md must not mention MCP"

    def test_no_session_ledger(self):
        text = _read(SKILL_MD)
        assert "session_ledger" not in text, "SKILL.md must not reference session_ledger"

    def test_no_zena_dev(self):
        text = _read(SKILL_MD)
        assert "ZENA_DEV" not in text, "SKILL.md must not reference ZENA_DEV"

    def test_no_linkedin_access_token(self):
        text = _read(SKILL_MD)
        assert "LINKEDIN_ACCESS_TOKEN" not in text, (
            "SKILL.md must not reference LINKEDIN_ACCESS_TOKEN"
        )

    def test_no_em_dashes(self):
        text = _read(SKILL_MD)
        # Unicode em-dash U+2014
        assert "—" not in text, (
            "SKILL.md must use hyphens, not em-dashes (U+2014 found)"
        )

    def test_no_emoji_characters(self):
        text = _read(SKILL_MD)
        # Detect emoji using Unicode ranges for common emoji blocks
        emoji_pattern = re.compile(
            "[\U0001F600-\U0001F64F"  # emoticons
            "\U0001F300-\U0001F5FF"  # symbols & pictographs
            "\U0001F680-\U0001F6FF"  # transport & map
            "\U0001F1E0-\U0001F1FF"  # flags
            "\U00002702-\U000027B0"  # dingbats
            "\U000024C2-\U0001F251"  # enclosed chars
            "]+",
            flags=re.UNICODE,
        )
        found = emoji_pattern.findall(text)
        assert not found, f"SKILL.md must not contain emoji; found: {found}"

    def test_no_placeholder_token_url(self):
        text = _read(SKILL_MD)
        assert "TOKEN_URL_PLACEHOLDER" not in text, (
            "SKILL.md must not contain the legacy TOKEN_URL_PLACEHOLDER"
        )

    def test_no_client_side_cap_count(self):
        """The old skill had a 3-keyword / 5-competitor client-side cap. Must be gone."""
        text = _read(SKILL_MD)
        # These specific enforcement phrases from the old skill should not appear
        assert "3 keywords TOTAL" not in text, (
            "SKILL.md must not contain the old client-side cap language"
        )
        assert "--no-ledger" not in text, "SKILL.md must not reference --no-ledger flag"
        assert "--reset-session" not in text, "SKILL.md must not reference --reset-session flag"


# ---------------------------------------------------------------------------
# Onboarding MD tests
# ---------------------------------------------------------------------------

class TestOnboardingMd:
    """references/onboarding.md requirements for the 3-step flow."""

    def test_onboarding_md_exists(self):
        assert ONBOARDING_MD.exists(), (
            f"references/onboarding.md not found at {ONBOARDING_MD}"
        )

    def test_onboarding_has_signup_link(self):
        text = _read(ONBOARDING_MD)
        assert "app.zenabm.com/signup" in text, (
            "onboarding.md must include the signup link"
        )

    def test_onboarding_has_api_keys_link(self):
        text = _read(ONBOARDING_MD)
        assert "app.zenabm.com/api-keys" in text, (
            "onboarding.md must include the api-keys link"
        )

    def test_onboarding_connect_linkedin_mentioned(self):
        text = _read(ONBOARDING_MD)
        text_lower = text.lower()
        assert "connect" in text_lower and "linkedin" in text_lower, (
            "onboarding.md must explain how to connect LinkedIn in ZenABM"
        )

    def test_onboarding_no_mcp(self):
        text = _read(ONBOARDING_MD)
        assert "MCP" not in text, "onboarding.md must not mention MCP"

    def test_onboarding_no_linkedin_access_token(self):
        text = _read(ONBOARDING_MD)
        assert "LINKEDIN_ACCESS_TOKEN" not in text, (
            "onboarding.md must not reference the legacy LINKEDIN_ACCESS_TOKEN"
        )

    def test_onboarding_no_placeholder_token_url(self):
        text = _read(ONBOARDING_MD)
        assert "TOKEN_URL_PLACEHOLDER" not in text, (
            "onboarding.md must not contain the legacy TOKEN_URL_PLACEHOLDER"
        )

    def test_onboarding_no_em_dashes(self):
        text = _read(ONBOARDING_MD)
        assert "—" not in text, (
            "onboarding.md must use hyphens, not em-dashes"
        )

    def test_onboarding_has_three_steps(self):
        text = _read(ONBOARDING_MD)
        # Should contain exactly the 3 steps described in the spec
        text_lower = text.lower()
        has_signup = "signup" in text_lower or "sign up" in text_lower
        has_connect = "connect" in text_lower and "linkedin" in text_lower
        has_token = "api-keys" in text or "api key" in text_lower or "new token" in text_lower
        assert has_signup and has_connect and has_token, (
            "onboarding.md must cover all 3 steps: signup, connect LinkedIn, get API token"
        )

    def test_onboarding_no_session_ledger(self):
        text = _read(ONBOARDING_MD)
        assert "session_ledger" not in text, (
            "onboarding.md must not reference session_ledger"
        )
