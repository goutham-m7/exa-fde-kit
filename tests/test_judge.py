import httpx
import pytest

from exa_fde_kit.judge import Claim, LexicalJudge, StringJudge, agreement, llm_judge


def test_claim_checks_each_sentence_in_its_own_evidence():
    lexical = LexicalJudge()
    evidence = ("The depot accepts 12 crates. It does not store ice.",)
    assert lexical.supports(Claim("The depot accepts 12 crates.", evidence, ("depot",)))
    for false in (
        "The depot accepts 13 crates.",
        "The depot accepts 12 crates. It stores ice.",
        "",
    ):
        claim = Claim(false, evidence, ("depot",))
        assert not lexical.supports(claim)
    assert StringJudge().supports(Claim("The depot accepts 13 crates.", evidence, ("depot",)))
    assert not lexical.supports(Claim("The depot accepts 12 crates.", (), ("depot",)))


def test_judge_agreement_and_optional_model(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert llm_judge() is None
    rows = agreement()
    assert rows["string"].total == rows["lexical"].total == 30
    assert rows["lexical"].correct > rows["string"].correct

    def respond(req):
        assert req.url.host == "api.openai.com"
        assert req.headers["authorization"] == "Bearer test-only"
        return httpx.Response(
            200, json={"choices": [{"message": {"content": '{"supported":false}'}}]}
        )

    monkeypatch.setenv("OPENAI_API_KEY", "test-only")
    with httpx.Client(transport=httpx.MockTransport(respond)) as http:
        assert not llm_judge(http).supports(Claim("An unsupported claim.", ("Other.",), ("claim",)))


def test_model_rejects_malformed_verdict(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-only")
    response = {"choices": [{"message": {"content": '{"supported": "yes"}'}}]}
    with httpx.Client(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=response))
    ) as http:
        with pytest.raises(ValueError, match="invalid model judge verdict"):
            llm_judge(http).supports(Claim("A claim", ("A passage",)))
